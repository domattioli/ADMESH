"""Vectorized signed-distance function for polygon domains.

Replaces the per-point shapely ``distance``/``contains`` SDF in
``admesh.loaders`` with a Numba-parallel kernel: distance = minimum
point-to-segment distance over all boundary edges (outer + holes); sign =
even-odd ray cast over the same edges (negative inside the domain, positive
outside or inside a hole).

Falls back to a pruned-tree NumPy implementation (or brute-force NumPy) if Numba is unavailable.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

try:
    from numba import njit, prange

    _HAVE_NUMBA = True
except ImportError:  # pragma: no cover
    _HAVE_NUMBA = False


def _pack_edges(rings: list[np.ndarray]) -> np.ndarray:
    """Stack all ring edges into a contiguous (Nseg, 4) array [ax, ay, bx, by]."""
    segs = []
    for r in rings:
        r = np.asarray(r, dtype=np.float64)
        if len(r) < 2:
            continue
        a = r
        b = np.roll(r, -1, axis=0)
        segs.append(np.hstack([a, b]))
    if not segs:
        raise ValueError("rings produced no edges")
    return np.ascontiguousarray(np.vstack(segs))


def _sdf_numpy(px, py, ax, ay, bx, by):
    # distance: min over segments, chunked to bound memory
    n = px.shape[0]
    out = np.empty(n, dtype=np.float64)
    dx = bx - ax
    dy = by - ay
    seg_len2 = dx * dx + dy * dy
    seg_len2[seg_len2 == 0.0] = 1.0
    chunk = max(1, 4_000_000 // max(1, ax.shape[0]))
    for s in range(0, n, chunk):
        e = min(s + chunk, n)
        qx = px[s:e, None]
        qy = py[s:e, None]
        t = ((qx - ax) * dx + (qy - ay) * dy) / seg_len2
        np.clip(t, 0.0, 1.0, out=t)
        cx = ax + t * dx
        cy = ay + t * dy
        d = np.hypot(qx - cx, qy - cy)
        dmin = d.min(axis=1)
        # even-odd ray cast
        cond = (ay > qy) != (by > qy)
        xint = (bx - ax) * (qy - ay) / (by - ay + 1e-300) + ax
        crossings = (cond & (qx < xint)).sum(axis=1)
        inside = (crossings & 1).astype(bool)
        out[s:e] = np.where(inside, -dmin, dmin)
    return out


if _HAVE_NUMBA:

    @njit(parallel=True, fastmath=True, cache=True)
    def _sdf_numba(px, py, ax, ay, bx, by):  # pragma: no cover - compiled
        n = px.shape[0]
        m = ax.shape[0]
        out = np.empty(n, dtype=np.float64)
        for i in prange(n):
            qx = px[i]
            qy = py[i]
            dmin = 1e300
            crossings = 0
            for j in range(m):
                axj = ax[j]
                ayj = ay[j]
                bxj = bx[j]
                byj = by[j]
                ex = bxj - axj
                ey = byj - ayj
                seg2 = ex * ex + ey * ey
                if seg2 == 0.0:
                    t = 0.0
                else:
                    t = ((qx - axj) * ex + (qy - ayj) * ey) / seg2
                    if t < 0.0:
                        t = 0.0
                    elif t > 1.0:
                        t = 1.0
                cx = axj + t * ex
                cy = ayj + t * ey
                ddx = qx - cx
                ddy = qy - cy
                d = (ddx * ddx + ddy * ddy) ** 0.5
                if d < dmin:
                    dmin = d
                if (ayj > qy) != (byj > qy):
                    xint = (bxj - axj) * (qy - ayj) / (byj - ayj) + axj
                    if qx < xint:
                        crossings += 1
            out[i] = -dmin if (crossings & 1) else dmin
        return out


if _HAVE_NUMBA:

    @njit(parallel=True, fastmath=True, cache=True)
    def _dist_knn_numba(px, py, ax, ay, bx, by, cand):  # pragma: no cover
        # exact min point-segment distance over k candidate segments per point;
        # full even-odd ray cast over all segments for the sign.
        n = px.shape[0]
        m = ax.shape[0]
        k = cand.shape[1]
        out = np.empty(n, dtype=np.float64)
        for i in prange(n):
            qx = px[i]
            qy = py[i]
            dmin = 1e300
            for c in range(k):
                j = cand[i, c]
                axj = ax[j]
                ayj = ay[j]
                ex = bx[j] - axj
                ey = by[j] - ayj
                seg2 = ex * ex + ey * ey
                if seg2 == 0.0:
                    t = 0.0
                else:
                    t = ((qx - axj) * ex + (qy - ayj) * ey) / seg2
                    if t < 0.0:
                        t = 0.0
                    elif t > 1.0:
                        t = 1.0
                ddx = qx - (axj + t * ex)
                ddy = qy - (ayj + t * ey)
                d = (ddx * ddx + ddy * ddy) ** 0.5
                if d < dmin:
                    dmin = d
            crossings = 0
            for j in range(m):
                ayj = ay[j]
                byj = by[j]
                if (ayj > qy) != (byj > qy):
                    xint = (bx[j] - ax[j]) * (qy - ayj) / (byj - ayj) + ax[j]
                    if qx < xint:
                        crossings += 1
            out[i] = -dmin if (crossings & 1) else dmin
        return out


def _build_grid(ax, ay, bx, by, nx, ny):
    """Bucket segments into a uniform grid (2D cells for distance, rows for sign).

    Returns grid metadata plus CSR arrays:
      cell_indptr/cell_segs : segments overlapping each of nx*ny cells
      row_indptr/row_segs   : segments overlapping each of ny rows (each seg
                              listed once per row -> safe parity count)
    """
    xmin = min(ax.min(), bx.min())
    xmax = max(ax.max(), bx.max())
    ymin = min(ay.min(), by.min())
    ymax = max(ay.max(), by.max())
    xspan = xmax - xmin or 1.0
    yspan = ymax - ymin or 1.0
    # pad so points on the max edge land in the last cell
    xmax += xspan * 1e-9
    ymax += yspan * 1e-9
    inv_cx = nx / (xmax - xmin)
    inv_cy = ny / (ymax - ymin)
    m = ax.shape[0]

    sx0 = np.clip(((np.minimum(ax, bx) - xmin) * inv_cx).astype(np.int64), 0, nx - 1)
    sx1 = np.clip(((np.maximum(ax, bx) - xmin) * inv_cx).astype(np.int64), 0, nx - 1)
    sy0 = np.clip(((np.minimum(ay, by) - ymin) * inv_cy).astype(np.int64), 0, ny - 1)
    sy1 = np.clip(((np.maximum(ay, by) - ymin) * inv_cy).astype(np.int64), 0, ny - 1)

    cell_lists: list[list[int]] = [[] for _ in range(nx * ny)]
    row_lists: list[list[int]] = [[] for _ in range(ny)]
    for j in range(m):
        for ry in range(sy0[j], sy1[j] + 1):
            row_lists[ry].append(j)
            base = ry * nx
            for rx in range(sx0[j], sx1[j] + 1):
                cell_lists[base + rx].append(j)

    def _csr(lists):
        counts = np.array([len(c) for c in lists], dtype=np.int64)
        indptr = np.zeros(len(lists) + 1, dtype=np.int64)
        np.cumsum(counts, out=indptr[1:])
        segs = np.empty(int(indptr[-1]), dtype=np.int64)
        for i, c in enumerate(lists):
            if c:
                segs[indptr[i] : indptr[i + 1]] = c
        return np.ascontiguousarray(indptr), np.ascontiguousarray(segs)

    cell_indptr, cell_segs = _csr(cell_lists)
    row_indptr, row_segs = _csr(row_lists)
    meta = np.array([xmin, ymin, inv_cx, inv_cy, float(nx), float(ny)], dtype=np.float64)
    return meta, cell_indptr, cell_segs, row_indptr, row_segs


def _build_prune(ax, ay, bx, by):
    """Build a pruning structure: uniform grid with per-cell candidate tables and sign row table.

    Distance part uses width-class grouping; sign part uses row table with sentinel segments."""
    m = ax.shape[0]

    # Calculate ncell: 4 * sqrt(m), clipped to [8, 128]
    ncell = int(np.clip(4 * np.sqrt(m), 8, 128))

    # Precompute segment vectors and squared lengths
    dx = bx - ax
    dy = by - ay
    L2 = dx * dx + dy * dy
    L2[L2 == 0.0] = 1.0

    # Grid bounds
    xmin = min(ax.min(), bx.min())
    xmax = max(ax.max(), bx.max())
    ymin = min(ay.min(), by.min())
    ymax = max(ay.max(), by.max())
    # pad 1% so boundary points on the max edges and slightly outside the
    # segments' bbox (gradient probes, lattice) stay on the table path
    pad = 0.01 * max(xmax - xmin, ymax - ymin, 1e-12)
    xmin -= pad
    ymin -= pad
    xmax += pad
    ymax += pad

    # Cell dimensions
    cw = (xmax - xmin) / ncell or 1.0
    ch = (ymax - ymin) / ncell or 1.0
    hd = 0.5 * np.hypot(cw, ch)

    # Cell centers
    cx = xmin + (np.arange(ncell) + 0.5) * cw
    cy = ymin + (np.arange(ncell) + 0.5) * ch

    # Meshgrid: row = y index
    CX, CY = np.meshgrid(cx, cy)
    CX = CX.ravel()[:, None]
    CY = CY.ravel()[:, None]

    # Compute candidates for each cell, chunked to limit memory (~2M floats per chunk)
    ncells_total = ncell * ncell
    chunk_size = max(1, 2_000_000 // max(1, m))

    # First pass: compute counts
    counts = np.zeros(ncells_total, dtype=np.int64)
    for s_cell in range(0, ncells_total, chunk_size):
        e_cell = min(s_cell + chunk_size, ncells_total)
        CX_chunk = CX[s_cell:e_cell]
        CY_chunk = CY[s_cell:e_cell]

        # Distance from cell centers to all segments
        t = ((CX_chunk - ax) * dx + (CY_chunk - ay) * dy) / L2
        np.clip(t, 0.0, 1.0, out=t)
        d = np.hypot(CX_chunk - (ax + t * dx), CY_chunk - (ay + t * dy))

        # Keep candidates: distance <= min_j D[c, j] + 2 * hd * (1 + 1e-9)
        keep = d <= d.min(axis=1, keepdims=True) + 2.0 * hd * (1 + 1e-9)
        counts[s_cell:e_cell] = keep.sum(axis=1)

    maxc = counts.max()

    # Second pass: build candidate table, padded with first candidate
    table = np.zeros((ncells_total, maxc), dtype=np.int64)
    for s_cell in range(0, ncells_total, chunk_size):
        e_cell = min(s_cell + chunk_size, ncells_total)
        CX_chunk = CX[s_cell:e_cell]
        CY_chunk = CY[s_cell:e_cell]

        t = ((CX_chunk - ax) * dx + (CY_chunk - ay) * dy) / L2
        np.clip(t, 0.0, 1.0, out=t)
        d = np.hypot(CX_chunk - (ax + t * dx), CY_chunk - (ay + t * dy))

        keep = d <= d.min(axis=1, keepdims=True) + 2.0 * hd * (1 + 1e-9)

        # Order by not-keep (True values at end), then take first maxc
        order = np.argsort(~keep, axis=1, kind="stable")[:, :maxc]
        first = order[:, :1]
        col = np.arange(maxc)[None, :]
        cell_counts = counts[s_cell:e_cell]
        table[s_cell:e_cell] = np.where(col < cell_counts[:, None], order, first)

    # Build row buckets for sign calculation
    grid_meta, _, _, row_indptr, row_segs = _build_grid(ax, ay, bx, by, 1, ncell)
    ymin_row, inv_cy, ny = grid_meta[1], grid_meta[3], int(grid_meta[5])

    # Build row table with sentinel index m at padding
    row_lens = np.diff(row_indptr)
    max_row_len = int(row_lens.max())
    row_table = np.full((ny, max_row_len), m, dtype=np.int64)
    for r in range(ny):
        row_table[r, :row_lens[r]] = row_segs[row_indptr[r]:row_indptr[r + 1]]

    # Sentinel-extended endpoint arrays
    ax_s = np.r_[ax, 0.0]
    ay_s = np.r_[ay, np.inf]
    bx_s = np.r_[bx, 0.0]
    by_s = np.r_[by, np.inf]

    return {
        "xmin": xmin,
        "ymin": ymin,
        "cw": cw,
        "ch": ch,
        "ncell": ncell,
        "table": table,
        "counts": counts,
        "dx": dx,
        "dy": dy,
        "L2": L2,
        "row_table": row_table,
        "row_lens": row_lens,
        "ax_s": ax_s,
        "ay_s": ay_s,
        "bx_s": bx_s,
        "by_s": by_s,
        "ymin_row": ymin_row,
        "inv_cy": inv_cy,
        "ny": ny,
    }


def _sdf_numpy_pruned(px, py, ax, ay, bx, by, prune):
    """Pruned NumPy SDF: width-class grouping for distance and sign computation."""
    n = px.shape[0]
    out = np.empty(n, dtype=np.float64)

    # Unpack pruning structure
    xmin = prune["xmin"]
    ymin = prune["ymin"]
    cw = prune["cw"]
    ch = prune["ch"]
    ncell = prune["ncell"]
    table = prune["table"]
    counts = prune["counts"]
    dx = prune["dx"]
    dy = prune["dy"]
    L2 = prune["L2"]
    row_table = prune["row_table"]
    row_lens = prune["row_lens"]
    ax_s = prune["ax_s"]
    ay_s = prune["ay_s"]
    bx_s = prune["bx_s"]
    by_s = prune["by_s"]
    ymin_row = prune["ymin_row"]
    inv_cy = prune["inv_cy"]
    ny = prune["ny"]

    # Compute cell indices for all points
    fx = (px - xmin) / cw
    fy = (py - ymin) / ch
    ix = np.floor(fx).astype(np.int64)
    iy = np.floor(fy).astype(np.int64)
    inside = (ix >= 0) & (ix < ncell) & (iy >= 0) & (iy < ncell)

    # Points inside grid: gather candidates and compute distances
    sel_inside = np.nonzero(inside)[0]
    sel_outside = np.nonzero(~inside)[0]

    # Width classes for grouping
    WID = np.array([8, 16, 32, 64, 128, 256, 512, 1 << 30], dtype=np.int64)

    # Chunk over inside points to limit memory (~2M entries per chunk)
    if len(sel_inside) > 0:
        n_inside = len(sel_inside)
        max_candidates = counts.max()
        chunk_size = max(1, 2_000_000 // max(1, max_candidates))

        for s_chunk in range(0, n_inside, chunk_size):
            e_chunk = min(s_chunk + chunk_size, n_inside)
            chunk_indices = sel_inside[s_chunk:e_chunk]
            qx_chunk = px[chunk_indices]
            qy_chunk = py[chunk_indices]
            chunk_n = e_chunk - s_chunk

            # Get cell indices for this chunk
            ix_chunk = ix[chunk_indices]
            iy_chunk = iy[chunk_indices]
            cell_idx = iy_chunk * ncell + ix_chunk

            # Distance: group by width class of candidate counts
            cell_counts = counts[cell_idx]
            width_cls = np.searchsorted(WID, cell_counts)
            dmin_chunk = np.full(chunk_n, 1e300, dtype=np.float64)

            for cls in np.unique(width_cls):
                sel_cls = np.nonzero(width_cls == cls)[0]
                w = min(int(WID[cls]), table.shape[1])
                c = table[cell_idx[sel_cls], :w]
                qx_c = qx_chunk[sel_cls, None]
                qy_c = qy_chunk[sel_cls, None]
                t = ((qx_c - ax[c]) * dx[c] + (qy_c - ay[c]) * dy[c]) / L2[c]
                np.clip(t, 0.0, 1.0, out=t)
                dists = np.hypot(qx_c - (ax[c] + t * dx[c]), qy_c - (ay[c] + t * dy[c]))
                dmin_chunk[sel_cls] = dists.min(axis=1)

            # Sign: row table with width-class grouping over row lengths
            rows = np.clip((qy_chunk - ymin_row) * inv_cy, 0, ny - 1).astype(np.int64)
            row_width_cls = np.searchsorted(WID, row_lens[rows])
            crossings = np.zeros(chunk_n, dtype=np.int64)

            for cls in np.unique(row_width_cls):
                sel_cls = np.nonzero(row_width_cls == cls)[0]
                w = min(int(WID[cls]), row_table.shape[1])
                sg = row_table[rows[sel_cls], :w]
                qx_r = qx_chunk[sel_cls, None]
                qy_r = qy_chunk[sel_cls, None]
                a_x, a_y, b_x, b_y = ax_s[sg], ay_s[sg], bx_s[sg], by_s[sg]
                cond = (a_y > qy_r) != (b_y > qy_r)
                with np.errstate(invalid="ignore", divide="ignore"):
                    xint = (b_x - a_x) * (qy_r - a_y) / (b_y - a_y + 1e-300) + a_x
                crossings[sel_cls] = (cond & (qx_r < xint)).sum(axis=1)

            inside_chunk = (crossings & 1).astype(bool)
            out[chunk_indices] = np.where(inside_chunk, -dmin_chunk, dmin_chunk)

    # Points outside grid: compute with brute force
    if len(sel_outside) > 0:
        out[sel_outside] = _sdf_numpy(px[sel_outside], py[sel_outside], ax, ay, bx, by)

    return out


if _HAVE_NUMBA:

    @njit(parallel=True, fastmath=True, cache=True)
    def _grid_sdf_numba(px, py, ax, ay, bx, by, meta,
                        cell_indptr, cell_segs, row_indptr, row_segs):  # pragma: no cover
        xmin = meta[0]
        ymin = meta[1]
        inv_cx = meta[2]
        inv_cy = meta[3]
        nx = int(meta[4])
        ny = int(meta[5])
        cw = 1.0 / inv_cx
        ch = 1.0 / inv_cy
        cell_min = cw if cw < ch else ch
        n = px.shape[0]
        out = np.empty(n, dtype=np.float64)
        for i in prange(n):
            qx = px[i]
            qy = py[i]
            cx = int((qx - xmin) * inv_cx)
            cy = int((qy - ymin) * inv_cy)
            if cx < 0:
                cx = 0
            elif cx >= nx:
                cx = nx - 1
            if cy < 0:
                cy = 0
            elif cy >= ny:
                cy = ny - 1
            # distance: expanding Chebyshev ring over 2D cells
            dmin = 1e300
            rmax = nx if nx > ny else ny
            for r in range(rmax + 1):
                if r > 0 and (r - 1) * cell_min > dmin:
                    break
                x0 = cx - r
                x1 = cx + r
                y0 = cy - r
                y1 = cy + r
                for gy in range(y0, y1 + 1):
                    if gy < 0 or gy >= ny:
                        continue
                    for gx in range(x0, x1 + 1):
                        if gx < 0 or gx >= nx:
                            continue
                        # ring shell only
                        if r > 0 and gx != x0 and gx != x1 and gy != y0 and gy != y1:
                            continue
                        cidx = gy * nx + gx
                        for p in range(cell_indptr[cidx], cell_indptr[cidx + 1]):
                            j = cell_segs[p]
                            axj = ax[j]
                            ayj = ay[j]
                            ex = bx[j] - axj
                            ey = by[j] - ayj
                            seg2 = ex * ex + ey * ey
                            if seg2 == 0.0:
                                t = 0.0
                            else:
                                t = ((qx - axj) * ex + (qy - ayj) * ey) / seg2
                                if t < 0.0:
                                    t = 0.0
                                elif t > 1.0:
                                    t = 1.0
                            ddx = qx - (axj + t * ex)
                            ddy = qy - (ayj + t * ey)
                            d = (ddx * ddx + ddy * ddy) ** 0.5
                            if d < dmin:
                                dmin = d
            # sign: even-odd ray cast over segments bucketed into this row
            crossings = 0
            for p in range(row_indptr[cy], row_indptr[cy + 1]):
                j = row_segs[p]
                ayj = ay[j]
                byj = by[j]
                if (ayj > qy) != (byj > qy):
                    xint = (bx[j] - ax[j]) * (qy - ayj) / (byj - ayj) + ax[j]
                    if qx < xint:
                        crossings += 1
            out[i] = -dmin if (crossings & 1) else dmin
        return out


def fast_sdf(rings: list[np.ndarray], knn: int = 32, grid_density: float = 1.0) -> Callable[[np.ndarray], np.ndarray]:
    """Build a vectorized SDF closure over polygon rings (outer first, holes after).

    When SciPy + Numba are available and the boundary has many segments, the
    distance term is pruned with a uniform grid of candidate tables. The sign uses
    a full even-odd ray cast. Falls back to pruned NumPy (or brute NumPy) otherwise.
    """
    edges = _pack_edges(rings)
    ax = np.ascontiguousarray(edges[:, 0])
    ay = np.ascontiguousarray(edges[:, 1])
    bx = np.ascontiguousarray(edges[:, 2])
    by = np.ascontiguousarray(edges[:, 3])
    nseg = ax.shape[0]

    grid = None
    prune = None

    if _HAVE_NUMBA and nseg > 4 * knn:
        # uniform grid sized to ~1 segment per cell; prunes BOTH the distance
        # term (2D cell ring search) and the sign term (row-bucketed ray cast),
        # entirely inside one numba-parallel kernel (no scipy per-call overhead).
        ncell = max(8, int(np.sqrt(nseg) * grid_density))
        grid = _build_grid(ax, ay, bx, by, ncell, ncell)
    elif not _HAVE_NUMBA and nseg > 4 * knn:
        # Pruned NumPy fallback when Numba is unavailable
        prune = _build_prune(ax, ay, bx, by)

    def sdf(p: np.ndarray) -> np.ndarray:
        pts = np.asarray(p, dtype=np.float64)
        if pts.ndim == 1:
            pts = pts[None, :]
        px = np.ascontiguousarray(pts[:, 0])
        py = np.ascontiguousarray(pts[:, 1])
        if grid is not None:
            meta, cell_indptr, cell_segs, row_indptr, row_segs = grid
            return _grid_sdf_numba(
                px, py, ax, ay, bx, by, meta,
                cell_indptr, cell_segs, row_indptr, row_segs,
            )
        if _HAVE_NUMBA:
            return _sdf_numba(px, py, ax, ay, bx, by)
        if prune is not None:
            return _sdf_numpy_pruned(px, py, ax, ay, bx, by, prune)
        return _sdf_numpy(px, py, ax, ay, bx, by)

    return sdf
