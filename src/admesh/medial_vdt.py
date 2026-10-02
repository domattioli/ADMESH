"""Vector-distance-transform (VDT) medial axis and channel-width size field.

This module implements the medial-axis and width-function procedure of

    Kang, Y. and Kubatko, E. J. (2024), "An automatic mesh generator for
    coupled 1D-2D hydrodynamic models", Geosci. Model Dev., 17, 1603-1625,
    https://doi.org/10.5194/gmd-17-1603-2024 (CC BY 4.0).

It is written from Section 2 of that article (Eqs. 7-14 and Appendix A) and
adds nothing beyond it except the numerical choices listed under "Paper gap"
in the code comments. It is an additive, opt-in size-field contribution; the
faithful-port stages are not touched.

Procedure (paper section and equation numbers in brackets)
----------------------------------------------------------
1. *Vector distance transform* ``V(x, P) = Phi(x, dP) - x`` with
   ``Phi = arginf_{y in dP} ||x - y||`` [Eqs. 7 and 8], evaluated on a
   background grid. Where the infimum has several arguments (on the medial
   axis) one of them is chosen arbitrarily, as the paper prescribes.
2. *Medial-axis points* ``MA(P) = {x in P : div V(x, P) > 0}`` [Eq. 9,
   Appendix A], with the divergence taken by central differences on the grid.
3. *Branches and order* [Appendix A and Section 3.2.1, step 2]: the cluster of
   medial-axis points is thinned, end points and branch points are
   identified, and traversable points between them form branches. Branches
   with a free end are order 1, branches that become free-ended after the
   order-1 branches are removed are order 2, and so on.
4. *Pruning near corners* [Eqs. 10-12]: for each medial-axis point ``p`` on an
   order-1 branch, with the four grid neighbours ``p_i`` and VDT values
   ``v = V(p)``, ``v_i = V(p_i)``::

       ell   = max_i ||(p + v) - (p_i + v_i)||                  (Eq. 10)
       theta = max_i arccos( v . v_i / (||v|| ||v_i||) )        (Eq. 11)

   and the point is pruned when ``theta < 0.9 pi`` and ``ell < 2 delta_w``
   (Eq. 12 with the paper's values ``delta_theta = 0.9 pi`` and
   ``delta_ell = 2 delta_w``).
5. *Width function* [Eqs. 13 and 14]::

       d(x, dP) = ||V(x, P)||
       f_w(x)   = 2 ( d(x, dP) + d(x, MA(P)) )

The public entry point for mesh generation is :func:`vdt_size_field`, which
returns a callable ``pts (N, 2) -> h (N,)`` with
``h = clip(f_w / (2 R), hmin, hmax)``; ``R`` is the number of elements per
local feature size ``f_w / 2``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage
from scipy.interpolate import RegularGridInterpolator
from scipy.spatial import cKDTree

__all__ = [
    "VDTMedialAxis",
    "compute_vdt_medial_axis",
    "grid_interpolator",
    "vdt_size_field",
]

#: Pruning thresholds suggested in the paper (Eq. 12 discussion).
THETA_MAX = 0.9 * np.pi
ELL_FACTOR = 2.0  # delta_ell = ELL_FACTOR * delta_w

_PAD_CELLS = 2

_STRUCT8 = np.ones((3, 3), dtype=bool)

# Neighbour offsets (drow, dcol) in clockwise order starting north; used by the
# thinning and branch-classification helpers.
_RING = ((-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1))


@dataclass(frozen=True)
class VDTMedialAxis:
    """Result of :func:`compute_vdt_medial_axis` on a regular grid.

    Arrays are indexed ``[row, col]`` with ``row`` along y and ``col`` along x.
    """

    xs: NDArray[np.float64]
    ys: NDArray[np.float64]
    delta: float
    sdf: NDArray[np.float64]
    vdt: NDArray[np.float64]  # (LY, LX, 2): V = Phi(x) - x           (Eq. 7)
    medial_raw: NDArray[np.bool_]  # thinned medial axis before pruning
    medial: NDArray[np.bool_]  # medial axis after corner pruning
    branch_order: NDArray[np.int32]  # per raw-medial pixel; 0 = no order (loop)
    pruned: NDArray[np.bool_]  # pixels removed by the pruning step
    width: NDArray[np.float64]  # f_w                                 (Eq. 14)
    endpoints: NDArray[np.float64]  # (K, 2) free ends of the pruned axis


def _build_simple_table() -> NDArray[np.bool_]:
    """Lookup table over the 256 neighbourhood codes: is the centre pixel simple?

    A foreground pixel is simple (its removal changes neither the number of
    8-connected foreground components nor the 4-connected background) when its
    foreground neighbours form one 8-connected group and the background
    neighbours that include an edge neighbour form one 4-connected group. Bit
    ``k`` of a code is the pixel at ``_RING[k]``.
    """
    table = np.zeros(256, dtype=bool)
    edge = (0, 2, 4, 6)
    for code in range(256):
        fg = [k for k in range(8) if code >> k & 1]
        bg = [k for k in range(8) if not code >> k & 1]

        def comps(items, adjacent):
            items = set(items)
            groups = []
            while items:
                seed = items.pop()
                stack, grp = [seed], {seed}
                while stack:
                    cur = stack.pop()
                    for other in list(items):
                        if adjacent(cur, other):
                            items.discard(other)
                            grp.add(other)
                            stack.append(other)
                groups.append(grp)
            return groups

        def adj8(i, j):
            return max(abs(_RING[i][0] - _RING[j][0]), abs(_RING[i][1] - _RING[j][1])) == 1

        def adj4(i, j):
            return abs(_RING[i][0] - _RING[j][0]) + abs(_RING[i][1] - _RING[j][1]) == 1

        fg_groups = comps(fg, adj8)
        bg_groups = [g for g in comps(bg, adj4) if g & set(edge)]
        table[code] = len(fg_groups) == 1 and len(bg_groups) == 1
    return table


_SIMPLE = _build_simple_table()


def _thin(mask: NDArray[np.bool_]) -> NDArray[np.bool_]:
    """Thin a binary image to one-pixel-wide 8-connected lines.

    Paper gap: the paper thins the cluster of medial-axis points with a
    morphological thinning operator without naming the algorithm. This
    removes simple boundary pixels one at a time, from the four edge
    directions in turn, and keeps line end points. Connectivity is preserved
    exactly because every removal is checked against the live image.
    """
    if not mask.any():
        return mask.copy()
    rows, cols = np.nonzero(mask)
    r0, r1 = max(rows.min() - 1, 0), min(rows.max() + 2, mask.shape[0])
    c0, c1 = max(cols.min() - 1, 0), min(cols.max() + 2, mask.shape[1])
    img = np.pad(mask[r0:r1, c0:c1], 2).astype(np.uint8)
    weights = [1 << k for k in range(8)]

    def code_at(r: int, c: int) -> int:
        code = 0
        for k, (dr, dc) in enumerate(_RING):
            if img[r + dr, c + dc]:
                code |= weights[k]
        return code

    changed = True
    while changed:
        changed = False
        for edge_k in (0, 2, 4, 6):
            dr, dc = _RING[edge_k]
            h, w = img.shape
            inner = img[1:-1, 1:-1].astype(bool)
            ring = _ring_stack(inner)
            nb = sum(x.astype(np.int16) for x in ring)
            exposed = np.pad(~ring[edge_k], 1, constant_values=True)
            cand = np.nonzero((img == 1) & exposed & np.pad(nb >= 2, 1))
            for r, c in zip(*cand):
                if _SIMPLE[code_at(int(r), int(c))] and bin(code_at(int(r), int(c))).count("1") >= 2:
                    img[r, c] = 0
                    changed = True
    out = np.zeros_like(mask)
    out[r0:r1, c0:c1] = img[2:-2, 2:-2].astype(bool)
    return out


def _ring_stack(mask: NDArray[np.bool_]) -> list[NDArray[np.bool_]]:
    p = np.pad(mask, 1)
    h, w = mask.shape
    return [p[1 + dr:1 + dr + h, 1 + dc:1 + dc + w] for dr, dc in _RING]


def _neighbour_stats(mask: NDArray[np.bool_]):
    """Return (neighbour count, crossing number) for every pixel of ``mask``."""
    ring = _ring_stack(mask)
    count = sum(r.astype(np.int16) for r in ring)
    cross = np.zeros(mask.shape, dtype=np.int16)
    for k in range(8):
        cross += (~ring[k] & ring[(k + 1) % 8]).astype(np.int16)
    return count, cross


def _vdt_on_grid(
    sdf: Callable[[NDArray[np.float64]], NDArray[np.float64]],
    xs: NDArray[np.float64],
    ys: NDArray[np.float64],
    delta: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return the sampled signed distance ``D`` and the VDT ``V`` (Eqs. 7, 8).

    Paper gap: the paper takes the nearest boundary point ``Phi(x)`` from an
    exact boundary description. Only a signed-distance callable is available
    here, so the boundary is represented by the zero crossings of ``D`` along
    grid edges (linearly interpolated), each carrying the unit normal of ``D``
    at the crossing. ``Phi(x)`` is the orthogonal projection of ``x`` onto the
    tangent line through the nearest crossing. The nearest crossing is chosen
    by a k-d tree, which realises the paper's "arbitrarily choose one of the
    arguments of the infimum".
    """
    X, Y = np.meshgrid(xs, ys, indexing="xy")
    pts = np.column_stack([X.ravel(), Y.ravel()])
    D = np.asarray(sdf(pts), dtype=np.float64).reshape(X.shape)
    gy, gx = np.gradient(D, delta)

    inside = D < 0.0
    q_list: list[NDArray[np.float64]] = []
    n_list: list[NDArray[np.float64]] = []
    for axis in (1, 0):  # edges along x (columns), then along y (rows)
        if axis == 1:
            sl_a = (slice(None), slice(0, -1))
            sl_b = (slice(None), slice(1, None))
        else:
            sl_a = (slice(0, -1), slice(None))
            sl_b = (slice(1, None), slice(None))
        cut = inside[sl_a] != inside[sl_b]
        if not cut.any():
            continue
        da, db = D[sl_a][cut], D[sl_b][cut]
        t = da / (da - db)
        pa = np.column_stack([X[sl_a][cut], Y[sl_a][cut]])
        pb = np.column_stack([X[sl_b][cut], Y[sl_b][cut]])
        q_list.append(pa + t[:, None] * (pb - pa))
        ga = np.column_stack([gx[sl_a][cut], gy[sl_a][cut]])
        gb = np.column_stack([gx[sl_b][cut], gy[sl_b][cut]])
        g = ga + t[:, None] * (gb - ga)
        norm = np.linalg.norm(g, axis=1)
        fallback = np.zeros_like(g)
        fallback[:, 0 if axis == 1 else 1] = np.sign(db - da)
        good = norm > 1e-9
        g = np.where(good[:, None], g / np.where(good, norm, 1.0)[:, None], fallback)
        n_list.append(g)
    if not q_list:
        return D, np.zeros(D.shape + (2,))
    q = np.vstack(q_list)
    nrm = np.vstack(n_list)
    tree = cKDTree(q)
    _, idx = tree.query(pts, workers=-1)
    rel = pts - q[idx]
    # V = Phi - x = -((x - q) . n) n
    proj = np.einsum("ij,ij->i", rel, nrm[idx])
    V = -proj[:, None] * nrm[idx]
    return D, V.reshape(D.shape + (2,))


def _prune_flags(
    V: NDArray[np.float64],
    rr: NDArray[np.intp],
    cc: NDArray[np.intp],
    xs: NDArray[np.float64],
    ys: NDArray[np.float64],
    delta_w: float,
    theta_max: float,
    ell_factor: float,
) -> NDArray[np.bool_]:
    """Evaluate Eqs. 10-12 for the pixels ``(rr, cc)``."""
    LY, LX = V.shape[:2]
    p = np.column_stack([xs[cc], ys[rr]])
    v = V[rr, cc]
    foot = p + v
    ell = np.zeros(len(rr))
    theta = np.zeros(len(rr))
    nv = np.linalg.norm(v, axis=1)
    for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        r2 = np.clip(rr + dr, 0, LY - 1)
        c2 = np.clip(cc + dc, 0, LX - 1)
        p2 = np.column_stack([xs[c2], ys[r2]])
        v2 = V[r2, c2]
        ell = np.maximum(ell, np.linalg.norm(foot - (p2 + v2), axis=1))
        n2 = np.linalg.norm(v2, axis=1)
        denom = nv * n2
        ok = denom > 1e-12
        cosang = np.ones(len(rr))
        cosang[ok] = np.einsum("ij,ij->i", v[ok], v2[ok]) / denom[ok]
        theta = np.maximum(theta, np.arccos(np.clip(cosang, -1.0, 1.0)))
    return (theta < theta_max) & (ell < ell_factor * delta_w)


def _branch_orders(ma: NDArray[np.bool_]):
    """Label branches of a thinned medial axis and assign their order.

    Returns ``(branch_labels, order_per_label, count, cross)`` where
    ``order_per_label[b]`` is the order of branch ``b`` (0 for branches that
    never become free-ended, such as loops).
    """
    count, cross = _neighbour_stats(ma)
    junction = ma & (cross >= 3)
    branch_mask = ma & ~junction
    bl, nb = ndimage.label(branch_mask, structure=_STRUCT8)
    jl, nj = ndimage.label(junction, structure=_STRUCT8)
    free_end = np.zeros(nb + 1, dtype=np.int64)
    end_pix = branch_mask & (count <= 1)
    if end_pix.any():
        free_end += np.bincount(bl[end_pix], minlength=nb + 1)

    # junction <-> branch adjacency
    adj_b: dict[int, set[int]] = {b: set() for b in range(1, nb + 1)}
    adj_j: dict[int, set[int]] = {j: set() for j in range(1, nj + 1)}
    if nj:
        H, W = ma.shape
        pj = np.pad(jl, 1)
        for dr, dc in _RING:
            jj = pj[1 + dr:1 + dr + H, 1 + dc:1 + dc + W]
            sel = (bl > 0) & (jj > 0)
            if sel.any():
                pairs = np.unique(np.column_stack([bl[sel], jj[sel]]), axis=0)
                for b, j in pairs:
                    adj_b[int(b)].add(int(j))
                    adj_j[int(j)].add(int(b))
    order = np.zeros(nb + 1, dtype=np.int32)
    live = set(range(1, nb + 1))
    k = 1
    while live:
        leaf = []
        for b in live:
            if free_end[b] > 0 or any(
                len(adj_j[j] & live) <= 1 for j in adj_b[b]
            ):
                leaf.append(b)
        if not leaf:
            break
        for b in leaf:
            order[b] = k
        live -= set(leaf)
        k += 1
    return bl, order, nb, count, cross


def _tip_walk(
    pix: set[tuple[int, int]], tip: tuple[int, int]
) -> list[tuple[int, int]]:
    """Order the pixels of one branch by 8-connected distance from ``tip``."""
    seen = {tip}
    queue = [tip]
    out = []
    while queue:
        nxt = []
        for r, c in queue:
            out.append((r, c))
            for dr, dc in _RING:
                q = (r + dr, c + dc)
                if q in pix and q not in seen:
                    seen.add(q)
                    nxt.append(q)
        queue = nxt
    return out


def compute_vdt_medial_axis(
    sdf: Callable[[NDArray[np.float64]], NDArray[np.float64]],
    bbox: tuple[float, float, float, float],
    delta: float,
    *,
    delta_w: float,
    theta_max: float = THETA_MAX,
    ell_factor: float = ELL_FACTOR,
) -> VDTMedialAxis:
    """Compute the pruned VDT medial axis and width function on a grid.

    Parameters
    ----------
    sdf
        Signed-distance callable ``(N, 2) -> (N,)``, negative inside.
    bbox
        ``(xmin, ymin, xmax, ymax)``; the grid is padded by two cells on every
        side so that boundary crossings on the bbox edge are captured.
    delta
        Background-grid spacing.
    delta_w
        User-defined minimum width ``delta_w`` of the paper; features narrower
        than this are "narrow". It sets the corner-pruning length
        ``2 * delta_w`` (Eq. 12).
    theta_max, ell_factor
        Pruning thresholds ``delta_theta`` (default ``0.9 pi``) and
        ``delta_ell / delta_w`` (default 2) of Eq. 12.

    Returns
    -------
    VDTMedialAxis
    """
    if delta <= 0 or delta_w <= 0:
        raise ValueError("delta and delta_w must be positive")
    xmin, ymin, xmax, ymax = (float(b) for b in bbox)
    pad = _PAD_CELLS * delta
    nx = int(np.ceil((xmax - xmin + 2 * pad) / delta)) + 1
    ny = int(np.ceil((ymax - ymin + 2 * pad) / delta)) + 1
    xs = xmin - pad + delta * np.arange(nx)
    ys = ymin - pad + delta * np.arange(ny)

    D, V = _vdt_on_grid(sdf, xs, ys, delta)

    # Eq. 9: medial axis = {x in P : div V > 0}, central differences.
    div = np.gradient(V[..., 0], delta, axis=1) + np.gradient(V[..., 1], delta, axis=0)
    inside = D < 0.0
    cluster = inside & (div > 0.0)
    ma_raw = _thin(cluster)

    bl, order_lab, nb, count, cross = _branch_orders(ma_raw)
    order_px = np.zeros(ma_raw.shape, dtype=np.int32)
    has_lab = bl > 0
    order_px[has_lab] = order_lab[bl[has_lab]]

    pruned = np.zeros_like(ma_raw)
    o1 = ma_raw & (order_px == 1)
    if o1.any():
        rr, cc = np.nonzero(o1)
        flag_arr = np.zeros(ma_raw.shape, dtype=bool)
        flag_arr[rr, cc] = _prune_flags(
            V, rr, cc, xs, ys, delta_w, theta_max, ell_factor
        )
        # Paper gap: the paper prunes "points" of order-1 branches that meet
        # Eq. 12. Pruning is applied here from each free tip inward and stops at
        # the first point that fails Eq. 12, so a branch is shortened rather
        # than split into disconnected pieces.
        objs = ndimage.find_objects(bl)
        for b in np.unique(bl[o1]):
            sl = objs[b - 1]
            sub = bl[sl] == b
            r_off, c_off = sl[0].start, sl[1].start
            pix = {(int(r) + r_off, int(c) + c_off) for r, c in zip(*np.nonzero(sub))}
            tips = [p for p in pix if count[p] <= 1]
            for tip in tips:
                for p in _tip_walk(pix, tip):
                    if flag_arr[p]:
                        pruned[p] = True
                    else:
                        break
    ma = ma_raw & ~pruned

    # Eqs. 13-14.
    d_bnd = np.linalg.norm(V, axis=2)
    if ma.any():
        d_ma = ndimage.distance_transform_edt(~ma) * delta
    else:
        # Paper gap: no medial axis (or all of it pruned) leaves d(x, MA)
        # undefined; use the bbox diagonal so f_w is large and the size field
        # saturates at hmax.
        d_ma = np.full(D.shape, float(np.hypot(xmax - xmin, ymax - ymin)))
    width = 2.0 * (d_bnd + d_ma)

    c2, _ = _neighbour_stats(ma)
    ends = ma & (c2 <= 1)
    er, ec = np.nonzero(ends)
    endpoints = np.column_stack([xs[ec], ys[er]]) if len(er) else np.empty((0, 2))
    return VDTMedialAxis(
        xs=xs, ys=ys, delta=float(delta), sdf=D, vdt=V, medial_raw=ma_raw,
        medial=ma, branch_order=order_px, pruned=pruned, width=width,
        endpoints=endpoints,
    )


def grid_interpolator(
    xs: NDArray[np.float64], ys: NDArray[np.float64], values: NDArray[np.float64]
) -> Callable[[NDArray[np.float64]], NDArray[np.float64]]:
    """Return ``pts (N, 2) -> values (N,)`` by bilinear interpolation.

    ``values`` has shape ``(len(ys), len(xs))``. Query points outside the grid
    are clamped to its extent.
    """
    interp = RegularGridInterpolator((ys, xs), values, method="linear")
    x0, x1, y0, y1 = xs[0], xs[-1], ys[0], ys[-1]
    lo, hi = float(np.min(values)), float(np.max(values))

    def field(pts: NDArray[np.float64]) -> NDArray[np.float64]:
        p = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
        q = np.column_stack([np.clip(p[:, 1], y0, y1), np.clip(p[:, 0], x0, x1)])
        # Bilinear weights can overshoot the grid range by one rounding step.
        return np.clip(interp(q), lo, hi)

    return field


def vdt_size_field(
    domain,
    delta: float,
    *,
    hmin: float,
    hmax: float,
    R: float = 2.0,
    delta_w: float | None = None,
) -> Callable[[NDArray[np.float64]], NDArray[np.float64]]:
    """Channel-width size contribution from the VDT medial axis.

    Parameters
    ----------
    domain
        Object with ``bbox`` and a signed-distance callable named ``sdf`` or
        ``fd`` (negative inside).
    delta
        Background-grid spacing.
    hmin, hmax
        Size bounds; the returned field lies in ``[hmin, hmax]``.
    R
        Elements per local feature size ``f_w / 2`` (Eq. 14).
    delta_w
        Minimum width of the paper's decomposition. Paper gap: the paper
        leaves ``delta_w`` to the user. The default ``2 * R * hmax`` is the
        width ``f_w`` at which ``f_w / (2 R)`` reaches ``hmax``, so wider
        features receive no refinement from this contribution.

    Returns
    -------
    Callable
        ``h(pts)`` with ``pts`` of shape ``(N, 2)`` and ``h`` of shape
        ``(N,)``: ``h = clip(f_w / (2 R), hmin, hmax)`` with ``f_w`` from
        Eq. 14, bilinearly interpolated from the grid. The callable carries
        an ``h_floor`` attribute: the smallest grid value inside the domain.
    """
    sdf = getattr(domain, "sdf", None) or getattr(domain, "fd")
    if delta_w is None:
        delta_w = 2.0 * R * float(hmax)
    res = compute_vdt_medial_axis(sdf, domain.bbox, delta, delta_w=delta_w)
    h_grid = np.clip(res.width / (2.0 * R), hmin, hmax)
    field = grid_interpolator(res.xs, res.ys, h_grid)
    inside = res.sdf < 0.0
    # Smallest size the field takes inside the domain, for callers that need
    # the initial lattice spacing of a mesh generator.
    field.h_floor = float(h_grid[inside].min()) if inside.any() else float(hmax)  # type: ignore[attr-defined]
    return field
