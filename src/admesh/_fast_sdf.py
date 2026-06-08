"""Vectorized signed-distance function for polygon domains.

Replaces the per-point shapely ``distance``/``contains`` SDF in
``admesh.loaders`` with a Numba-parallel kernel: distance = minimum
point-to-segment distance over all boundary edges (outer + holes); sign =
even-odd ray cast over the same edges (negative inside the domain, positive
outside or inside a hole).

Falls back to a pure-NumPy implementation if Numba is unavailable.
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
    distance term is pruned with a cKDTree over segment midpoints: only the
    ``knn`` nearest segments per query point are tested exactly. The sign uses
    a full even-odd ray cast. Falls back to the brute kernel otherwise.
    """
    edges = _pack_edges(rings)
    ax = np.ascontiguousarray(edges[:, 0])
    ay = np.ascontiguousarray(edges[:, 1])
    bx = np.ascontiguousarray(edges[:, 2])
    by = np.ascontiguousarray(edges[:, 3])
    nseg = ax.shape[0]

    grid = None
    if _HAVE_NUMBA and nseg > 4 * knn:
        # uniform grid sized to ~1 segment per cell; prunes BOTH the distance
        # term (2D cell ring search) and the sign term (row-bucketed ray cast),
        # entirely inside one numba-parallel kernel (no scipy per-call overhead).
        ncell = max(8, int(np.sqrt(nseg) * grid_density))
        grid = _build_grid(ax, ay, bx, by, ncell, ncell)

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
        return _sdf_numpy(px, py, ax, ay, bx, by)

    return sdf
