"""DistMesh 2D triangulation.

MVP subset of ``01_ADMESH_Library/10_Distmesh_2d/`` @ 19b2eb9.

The ADMESH repo's ``distmesh2d.m`` is a GUI-wrapped variant of
Persson & Strang's canonical DistMesh2D (2004) with ADMESH-specific
helpers (``createInitialPointList``, ``rejectionMethod``,
``GetMeshConstraints``, ``projectBackToBoundary``,
``BoundaryCleanUp``, ``createMeshStruct``). For the triangulation-only
MVP we port the **canonical Persson algorithm** — callable with an
SDF ``fd`` and a mesh-size function ``fh`` — omitting the PTS /
constraint machinery, which lands in post-MVP phase P1.

Also ported: :func:`fixmesh` (dedupe nodes, drop unused, reorient
negative-area triangles) from ``fixmesh.m``.

Reference: Persson & Strang, "A Simple Mesh Generator in MATLAB",
SIAM Review 46(2), 2004. <http://persson.berkeley.edu/distmesh/>
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.spatial import Delaunay

Points = NDArray[np.float64]
SDF = Callable[[Points], NDArray[np.float64]]
SizeFn = Callable[[Points], NDArray[np.float64]]


def _unique_bars(t: NDArray[np.int64], n: int) -> NDArray[np.int64]:
    """Unique sorted bars (a<b) from row-sorted triangles.

    Equivalent to ``np.unique(vstack(edges), axis=0)`` but dedups on a packed
    1D integer key (``a*n + b``) so it is an int64 sort instead of a 2D lexsort.
    With a<b guaranteed (``t`` is row-sorted) the key order matches lexicographic
    row order, so the output is bit-identical to the axis=0 unique.
    """
    e = np.vstack([t[:, [0, 1]], t[:, [0, 2]], t[:, [1, 2]]])
    key = e[:, 0].astype(np.int64) * n + e[:, 1]
    uk = np.unique(key)
    return np.column_stack([uk // n, uk % n]).astype(e.dtype)


def _initial_distribution(bbox: tuple[float, float, float, float], h0: float) -> Points:
    """Equilateral-triangle lattice covering the bounding box."""
    xmin, ymin, xmax, ymax = bbox
    xs = np.arange(xmin, xmax + 0.5 * h0, h0)
    ys = np.arange(ymin, ymax + 0.5 * h0, h0 * np.sqrt(3) / 2)
    X, Y = np.meshgrid(xs, ys, indexing="xy")
    # Shift odd rows by h0/2 to form equilateral triangles.
    X[1::2, :] = X[1::2, :] + h0 / 2.0
    return np.column_stack([X.ravel(), Y.ravel()])


def _rejection_method(
    p: Points, fh: SizeFn, rng: np.random.Generator
) -> Points:
    """Keep each point with probability ``(r0/r(p))**2`` where ``r(p)=fh(p)``."""
    r = fh(p)
    r0 = r.min()
    probs = (r0 / r) ** 2
    keep = rng.random(len(p)) < probs
    return p[keep]


def distmesh2d(
    fd: SDF,
    fh: SizeFn | None,
    h0: float,
    bbox: tuple[float, float, float, float],
    pfix: ArrayLike | None = None,
    *,
    initial_points: ArrayLike | None = None,
    dptol: float = 2e-3,
    ttol: float = 0.27,
    Fscale: float = 1.2,
    deltat: float = 0.2,
    geps_factor: float = 1e-3,
    niter: int = 500,
    seed: int = 0,
    return_diagnostics: bool = False,
) -> "tuple[Points, NDArray[np.int64]] | tuple[Points, NDArray[np.int64], list[dict]]":
    """Triangulate a 2-D domain defined by a signed distance function.

    Parameters
    ----------
    fd : callable ``(N, 2) -> (N,)``
        Signed distance function (negative inside).
    fh : callable ``(N, 2) -> (N,)`` or None
        Desired mesh-size function; ``None`` means uniform (constant 1).
    h0 : float
        Target edge length (sets the initial lattice spacing).
    bbox : (xmin, ymin, xmax, ymax)
    pfix : (M, 2) array or None
        Fixed points (always present in the mesh, never moved).
    initial_points : (K, 2) array or None
        Warm-start point distribution.  When supplied the lattice seeding and
        rejection-sampling steps are skipped; the provided points are used
        directly (after filtering out any that lie outside the domain).  Useful
        for iterative refinement or for callers that supply their own
        distribution (e.g. CHILmesh warm-start).  ``seed`` is ignored when
        ``initial_points`` is set.
    dptol : float
        Stopping criterion — relative interior-node movement tolerance.
    ttol : float
        Re-triangulation trigger (relative node movement).
    Fscale : float
        Truss internal-pressure factor (> 1).
    deltat : float
        Euler time step for the force-displacement update.
    geps_factor : float
        Boundary tolerance: ``geps = geps_factor * h0``.
    niter : int
        Maximum iterations.
    seed : int
        RNG seed for the rejection step (ignored when ``initial_points`` set).
    return_diagnostics : bool
        When True return a third element — a list of per-iteration dicts with
        keys ``iter``, ``n_pts``, ``n_elements``, ``max_disp``, ``n_outside``.

    Returns
    -------
    p : (N, 2) ndarray of node coordinates
    t : (M, 3) ndarray of triangle indices (0-based)
    diagnostics : list[dict]  (only when ``return_diagnostics=True``)
    """
    if fh is None:
        fh = lambda q: np.ones(len(q), dtype=float)  # noqa: E731
    rng = np.random.default_rng(seed)
    geps = geps_factor * h0
    deps = np.sqrt(np.finfo(float).eps) * h0

    if initial_points is not None:
        # Warm-start: use caller-supplied distribution, just filter outside.
        p = np.asarray(initial_points, dtype=float).reshape(-1, 2)
        p = p[fd(p) < geps]
    else:
        # 1. Initial lattice + drop points outside the domain.
        p = _initial_distribution(bbox, h0)
        p = p[fd(p) < geps]
        # 2. Probability-based rejection by fh.
        p = _rejection_method(p, fh, rng)

    diagnostics: list[dict] = []

    # 3. Fixed points first (they get indices 0..nfix-1 and are never moved).
    if pfix is not None:
        pfix_arr = np.asarray(pfix, dtype=float).reshape(-1, 2)
        if pfix_arr.size:
            # Drop any free points that coincide with fixed points.
            if len(p):
                dist_to_fix = np.min(
                    np.linalg.norm(p[:, None, :] - pfix_arr[None, :, :], axis=2), axis=1
                )
                p = p[dist_to_fix > geps]
            p = np.vstack([pfix_arr, p])
            nfix = len(pfix_arr)
        else:
            nfix = 0
    else:
        nfix = 0

    N = len(p)
    pold = np.full_like(p, np.inf)

    t = np.empty((0, 3), dtype=np.int64)
    bars = np.empty((0, 2), dtype=np.int64)

    for _k in range(niter):
        # (Re)triangulate if any node moved more than ttol*h0.
        moved = np.sqrt(((p - pold) ** 2).sum(axis=1)) / h0
        if moved.max() > ttol:
            pold = p.copy()
            tri = Delaunay(p)
            t_all = tri.simplices
            centroids = (p[t_all[:, 0]] + p[t_all[:, 1]] + p[t_all[:, 2]]) / 3.0
            keep = fd(centroids) < -geps
            t = np.sort(t_all[keep], axis=1)
            bars = _unique_bars(t, len(p))

        if bars.size == 0:
            break

        # Truss forces: F = max(L0 - L, 0) along each bar.
        barvec = p[bars[:, 0]] - p[bars[:, 1]]
        L = np.sqrt((barvec ** 2).sum(axis=1))
        hbars = fh((p[bars[:, 0]] + p[bars[:, 1]]) / 2.0)
        L0 = hbars * Fscale * np.sqrt((L ** 2).sum() / (hbars ** 2).sum())
        F = np.maximum(L0 - L, 0.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            Fvec = np.where(L[:, None] > 0, (F / L)[:, None] * barvec, 0.0)

        Ftot = np.zeros_like(p)
        np.add.at(Ftot, bars[:, 0], Fvec)
        np.add.at(Ftot, bars[:, 1], -Fvec)

        # Zero force at fixed points (they don't move).
        if nfix > 0:
            Ftot[:nfix] = 0.0

        p_new = p + deltat * Ftot

        # Project points that drifted outside back to the boundary along -grad fd.
        d = fd(p_new)
        outside = d > 0
        if outside.any():
            po = p_new[outside]
            d_o = d[outside]
            dx = (fd(po + np.array([deps, 0.0])) - d_o) / deps
            dy = (fd(po + np.array([0.0, deps])) - d_o) / deps
            denom = dx * dx + dy * dy
            safe = denom > 0
            shift = np.zeros_like(po)
            shift[safe, 0] = d_o[safe] * dx[safe] / denom[safe]
            shift[safe, 1] = d_o[safe] * dy[safe] / denom[safe]
            p_new[outside] = po - shift

        # Stopping criterion on interior-node movement.
        if nfix < len(p_new):
            dp_interior = np.linalg.norm(p_new[nfix:] - p[nfix:], axis=1)
            max_d = dp_interior.max() if dp_interior.size else 0.0
        else:
            max_d = 0.0

        if return_diagnostics:
            n_out = int(outside.sum()) if outside.any() else 0
            diagnostics.append({
                "iter": _k,
                "n_pts": len(p_new),
                "n_elements": len(t),
                "max_disp": float(max_d / h0),
                "n_outside": n_out,
            })

        if nfix < len(p_new) and max_d / h0 < dptol:
            p = p_new
            break

        p = p_new

    # Final retriangulation on the converged node set. Without this,
    # `t` is the Delaunay result from the *previous* retri trigger,
    # so any post-trigger node motion (including final-iteration
    # boundary projection) can leave stale triangles — including
    # near-colinear slivers on straight boundaries. Re-Delaunay +
    # re-filter by centroid SDF before handing off to fixmesh.
    if len(p) >= 3:
        tri = Delaunay(p)
        t_all = tri.simplices
        centroids = (p[t_all[:, 0]] + p[t_all[:, 1]] + p[t_all[:, 2]]) / 3.0
        keep = fd(centroids) < -geps
        t = np.sort(t_all[keep], axis=1)

    # Boundary cleanup — port of MATLAB BoundaryCleanUp.m. Drops
    # free-boundary-attached triangles with q < 0.15. MATLAB's
    # canonical Persson distmesh2d doesn't include this, but
    # MATLAB ADMESH's distmesh2d does (see 10_Distmesh_2d/distmesh2d.m
    # line 226). Enabling here for boundary quality on non-uniform
    # fh; no regression on MVP domains (all already min_q > 0.69).
    t = _boundary_cleanup(p, t, None)

    p_out, t_out = fixmesh(p, t)[:2]
    if return_diagnostics:
        return p_out, t_out, diagnostics
    return p_out, t_out
def fixmesh(
    p: Points, t: NDArray[np.integer], ptol: float = 1024 * np.finfo(float).eps
) -> tuple[Points, NDArray[np.int64], NDArray[np.int64]]:
    """Dedupe points, drop unused, reorient negative-area triangles.

    Port of ``fixmesh.m``.
    """
    p = np.asarray(p, dtype=float)
    t = np.asarray(t, dtype=np.int64)
    if p.size == 0 or t.size == 0:
        return p, t, np.arange(len(p), dtype=np.int64)

    snap = np.max(p.max(axis=0) - p.min(axis=0)) * ptol
    if snap == 0:
        snap = ptol
    rounded = np.round(p / snap) * snap
    # stable unique (first-occurrence order).
    _, ix, jx = np.unique(rounded, axis=0, return_index=True, return_inverse=True)
    order = np.argsort(ix)
    ix_stable = ix[order]
    # Map each original point to its position in the stable-unique list.
    pos_of_unique_in_stable = np.empty_like(order)
    pos_of_unique_in_stable[order] = np.arange(len(order))
    jx_stable = pos_of_unique_in_stable[jx]

    p = p[ix_stable]
    t = jx_stable[t]

    pix, _, jx1 = np.unique(t, return_index=True, return_inverse=True)
    t = jx1.reshape(t.shape)
    p = p[pix]

    # Reorient triangles with negative signed area.
    d12 = p[t[:, 1]] - p[t[:, 0]]
    d13 = p[t[:, 2]] - p[t[:, 0]]
    area = (d12[:, 0] * d13[:, 1] - d12[:, 1] * d13[:, 0]) / 2.0
    flip = area < 0
    if flip.any():
        t[flip, 0], t[flip, 1] = t[flip, 1].copy(), t[flip, 0].copy()

    return p, t, ix_stable[pix]


# ---------------------------------------------------------------------------
# ADMESH-variant distmesh pathway — faithful port of MATLAB
# ``01_ADMESH_Library/10_Distmesh_2d/distmesh2d.m`` @ 19b2eb9.
# ---------------------------------------------------------------------------


from dataclasses import dataclass


@dataclass(frozen=True)
class MeshOutput:
    """Triangulation result with per-node boundary labels.

    Attributes
    ----------
    p : (N, 2) ndarray
    t : (M, 3) ndarray
    node_bc : (N,) int64
        :class:`~admesh.boundary.BoundaryType` for nodes on a PTS
        boundary segment, or ``-1`` for interior nodes.
    ring_id : (N,) int64
        Ring index (``0`` outer, ``1+`` holes) for boundary nodes,
        or ``-1`` for interior.
    """

    p: Points
    t: NDArray[np.int64]
    node_bc: NDArray[np.int64]
    ring_id: NDArray[np.int64]


def _boundary_cleanup(
    p: Points, t: NDArray[np.int64], C: NDArray[np.int64] | None = None
) -> NDArray[np.int64]:
    """Port of ``BoundaryCleanUp.m``, applied iteratively to fixed-point.

    Drops triangles attached to the free boundary whose element
    quality ``q = (b+c-a)(c+a-b)(a+b-c)/(abc)`` is below ``0.15``.
    Preserves triangles containing any constrained edge. Iterates
    until no further triangles are dropped — a single pass only
    catches slivers attached to the *current* free boundary, so when
    pfix-free runs leave near-boundary slivers in chains, the second
    layer surfaces only after the first is removed.

    Parameters
    ----------
    p : (N, 2) ndarray
    t : (M, 3) ndarray
    C : (K, 2) ndarray or None
        Constrained edges (vertex-index pairs). Triangles attached to
        any constrained edge are kept regardless of quality.
    """
    prev = -1
    while t.size and len(t) != prev:
        prev = len(t)
        t = _boundary_cleanup_one_pass(p, t, C)
    return t


def _boundary_cleanup_one_pass(
    p: Points, t: NDArray[np.int64], C: NDArray[np.int64] | None = None
) -> NDArray[np.int64]:
    """Single pass of ``BoundaryCleanUp.m``."""
    if t.size == 0:
        return t

    # Free boundary = edges that appear in exactly one triangle.
    edges = np.vstack([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]])
    edges_sorted = np.sort(edges, axis=1)
    _, inv, counts = np.unique(edges_sorted, axis=0, return_inverse=True, return_counts=True)
    is_free = counts[inv] == 1  # (3M,) — one entry per triangle-edge slot
    # A triangle is "attached to the free boundary" if any of its
    # 3 edges is a free-boundary edge. Reshape into (3, M) for clarity.
    free_per_tri = is_free.reshape(3, -1).any(axis=0)
    boundary_tri = np.where(free_per_tri)[0]
    if boundary_tri.size == 0:
        return t

    # Element quality on the boundary triangles
    #   q = (b+c-a)(c+a-b)(a+b-c) / (a*b*c),   a,b,c = edge lengths.
    bt = t[boundary_tri]
    x = p[:, 0]
    y = p[:, 1]
    a = np.hypot(x[bt[:, 1]] - x[bt[:, 0]], y[bt[:, 1]] - y[bt[:, 0]])
    b = np.hypot(x[bt[:, 2]] - x[bt[:, 1]], y[bt[:, 2]] - y[bt[:, 1]])
    c = np.hypot(x[bt[:, 0]] - x[bt[:, 2]], y[bt[:, 0]] - y[bt[:, 2]])
    denom = a * b * c
    with np.errstate(divide="ignore", invalid="ignore"):
        q = np.where(denom > 0, (b + c - a) * (c + a - b) * (a + b - c) / denom, 0.0)
    bad_mask = q < 0.15
    bad = boundary_tri[bad_mask]

    if C is not None and len(C):
        # Triangles incident to a constrained edge — preserve them.
        C_sorted = np.sort(np.asarray(C, dtype=np.int64), axis=1)
        edges_by_tri = edges_sorted.reshape(3, -1, 2)  # (3, M, 2)
        keep_tri = np.zeros(len(t), dtype=bool)
        # Match constrained edges across all triangle-edges via set membership.
        C_set = {tuple(row) for row in C_sorted}
        for s in range(3):
            for ti in range(len(t)):
                if tuple(edges_by_tri[s, ti]) in C_set:
                    keep_tri[ti] = True
        bad = bad[~keep_tri[bad]]

    keep = np.ones(len(t), dtype=bool)
    keep[bad] = False
    return t[keep]


def _boundary_density_control(
    p: Points,
    t: NDArray[np.int64],
    C: NDArray[np.int64] | None = None,
    nC: int = 0,
) -> Points:
    """Port of ``BoundaryDensityControl.m``.

    For each triangle attached to a free-boundary edge, compute the
    element quality ``q = (b+c-a)(c+a-b)(a+b-c)/(abc)`` (edge lengths
    ``a,b,c``). If ``q < 0.2``, mark the triangle's **interior vertex**
    — the one not on the free edge — for removal. Fixed points
    (indices ``< nC``) and constrained-segment endpoints (``C``) are
    never removed.

    Called from the main loop on the ``k > niter/2`` density-control
    branch; returns an updated ``p`` with the flagged interior vertices
    dropped.
    """
    if t.size == 0 or p.size == 0:
        return p

    # Free-boundary edges = edges appearing exactly once. Keep the slot
    # layout (s ∈ {0,1,2}) so for each free slot we can recover the
    # interior vertex of that triangle as ``t[:, (s+2) % 3]``.
    edges = np.vstack([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]])
    edges_sorted = np.sort(edges, axis=1)
    _, inv, counts = np.unique(
        edges_sorted, axis=0, return_inverse=True, return_counts=True
    )
    is_free_per_slot = (counts[inv] == 1).reshape(3, -1)  # (3, M)

    # Triangle quality for every triangle (used only if at least one
    # slot of that triangle is free, but easier to compute uniformly).
    x = p[:, 0]
    y = p[:, 1]
    a = np.hypot(x[t[:, 1]] - x[t[:, 0]], y[t[:, 1]] - y[t[:, 0]])
    b = np.hypot(x[t[:, 2]] - x[t[:, 1]], y[t[:, 2]] - y[t[:, 1]])
    c = np.hypot(x[t[:, 0]] - x[t[:, 2]], y[t[:, 0]] - y[t[:, 2]])
    denom = a * b * c
    with np.errstate(divide="ignore", invalid="ignore"):
        q = np.where(denom > 0, (b + c - a) * (c + a - b) * (a + b - c) / denom, 0.0)
    bad_tri = q < 0.2

    # For each slot, collect interior-vertex indices of triangles that
    # are both free at that slot AND have q < 0.2.
    bad_ids_parts: list[NDArray[np.int64]] = []
    for s in range(3):
        bad_slot = is_free_per_slot[s] & bad_tri
        if bad_slot.any():
            bad_ids_parts.append(t[bad_slot, (s + 2) % 3])

    if not bad_ids_parts:
        return p
    bad_ids = np.unique(np.concatenate(bad_ids_parts))

    # Preserve fixed points (MATLAB: ``setdiff(badQ, 1:nC)``).
    bad_ids = bad_ids[bad_ids >= nC]
    if C is not None and len(C):
        C_set = set(np.asarray(C, dtype=np.int64).ravel().tolist())
        bad_ids = np.array(
            [int(i) for i in bad_ids if int(i) not in C_set], dtype=np.int64
        )
    if bad_ids.size == 0:
        return p

    keep = np.ones(len(p), dtype=bool)
    keep[bad_ids] = False
    return p[keep]


def _constraint_density_control(
    p: Points,
    nC: int,
    C: NDArray[np.int64] | None,
    fh: SizeFn,
) -> Points:
    """Port of ``ConstraintDensityControl.m``.

    For each constraint segment ``C[i] = (v1, v2)``, build a thin
    rectangle of half-width ``fh(midpoint) * sqrt(3)/8`` straddling the
    segment and drop every non-fixed point falling inside. Returns ``p``
    unchanged when ``C`` is empty.
    """
    if C is None or len(C) == 0:
        return p

    from admesh._stages.in_polygon import in_polygon

    C_arr = np.asarray(C, dtype=np.int64).reshape(-1, 2)
    x1 = p[C_arr[:, 0], 0]
    y1 = p[C_arr[:, 0], 1]
    x2 = p[C_arr[:, 1], 0]
    y2 = p[C_arr[:, 1], 1]
    dx = x1 - x2
    dy = y1 - y2
    eL = np.hypot(dx, dy)
    eL = np.where(eL > 0, eL, 1.0)
    nx = dy / eL
    ny = -dx / eL
    xm = 0.5 * (x1 + x2)
    ym = 0.5 * (y1 + y2)
    L_mid = fh(np.column_stack([xm, ym])) * np.sqrt(3.0) / 8.0

    if nC >= len(p):
        return p
    q = p[nC:]
    remove_mask = np.zeros(len(q), dtype=bool)
    for i in range(len(C_arr)):
        Lx = nx[i] * L_mid[i]
        Ly = ny[i] * L_mid[i]
        poly_x = np.array([x1[i] + Lx, x1[i] - Lx, x2[i] - Lx, x2[i] + Lx])
        poly_y = np.array([y1[i] + Ly, y1[i] - Ly, y2[i] - Ly, y2[i] + Ly])
        inside, _ = in_polygon(q[:, 0], q[:, 1], poly_x, poly_y)
        remove_mask |= inside

    if not remove_mask.any():
        return p
    keep = np.ones(len(p), dtype=bool)
    keep[nC + np.where(remove_mask)[0]] = False
    return p[keep]


def _project_back_to_boundary(
    p: Points, fd: SDF, geps: float, *, deps: float
) -> Points:
    """Port of ``projectBackToBoundary.m``.

    Projects all points with ``d(p) > -geps*100`` onto the boundary
    along the gradient of ``fd``. This is broader than the canonical
    Persson projection (which only pulls points with ``d > 0``) — it
    actively pulls boundary-adjacent interior points onto the
    boundary too, which materially changes the equilibrium.
    """
    pdist = fd(p)
    ix = pdist > -geps * 100.0
    if not ix.any():
        return p
    po = p[ix]
    dx = (fd(po + np.array([deps, 0.0])) - fd(po)) / deps
    dy = (fd(po + np.array([0.0, deps])) - fd(po)) / deps
    d_o = pdist[ix]
    p_out = p.copy()
    p_out[ix, 0] = po[:, 0] - d_o * dx
    p_out[ix, 1] = po[:, 1] - d_o * dy
    return p_out


def _initial_point_list_from_pts(
    fd: SDF, pts, hmin: float, geps: float
) -> Points:
    """Port of ``createInitialPointList.m``.

    Bbox taken from the concatenated PTS ring points; equilateral
    lattice with spacing ``(hmin, hmin*sqrt(3)/2)``; even rows (MATLAB
    ``2:2:end`` = Python ``1::2``) shifted by ``hmin/2``; rejects
    ``fd(p) >= geps``.
    """
    all_p = np.vstack(pts.rings)
    xmin, ymin = all_p.min(axis=0)
    xmax, ymax = all_p.max(axis=0)
    xs = np.arange(xmin, xmax + 0.5 * hmin, hmin)
    ys = np.arange(ymin, ymax + 0.5 * hmin, hmin * np.sqrt(3) / 2.0)
    X, Y = np.meshgrid(xs, ys, indexing="xy")
    X[1::2, :] = X[1::2, :] + hmin / 2.0
    p = np.column_stack([X.ravel(), Y.ravel()])
    return p[fd(p) < geps]


def _element_quality_mean(p: Points, t: NDArray[np.int64]) -> float:
    """Mean element quality used by the MATLAB best-quality tracker.

    MATLAB calls ``MeshQuality(p,t,0,'Triangle')`` whose return is the
    mean per-element quality on the current mesh.
    """
    if t.size == 0:
        return 0.0
    x = p[:, 0]
    y = p[:, 1]
    a = np.hypot(x[t[:, 1]] - x[t[:, 0]], y[t[:, 1]] - y[t[:, 0]])
    b = np.hypot(x[t[:, 2]] - x[t[:, 1]], y[t[:, 2]] - y[t[:, 1]])
    c = np.hypot(x[t[:, 0]] - x[t[:, 2]], y[t[:, 0]] - y[t[:, 2]])
    denom = a * b * c
    with np.errstate(divide="ignore", invalid="ignore"):
        q = np.where(denom > 0, (b + c - a) * (c + a - b) * (a + b - c) / denom, 0.0)
    return float(np.mean(np.clip(q, 0.0, 1.0)))


def distmesh2d_admesh(
    pts,
    fh: SizeFn | None,
    h0: float,
    *,
    pfix: ArrayLike | None = None,
    cleanup: bool = True,
    **opts,
) -> MeshOutput:
    """Faithful port of MATLAB ``distmesh2d.m`` @ 19b2eb9.

    Parameter values match the MATLAB source:
    ``ttol=0.5``, ``Fscale=1.15``, ``deltat=0.3``, ``geps=0.001*hmin``,
    ``niter=1000``, density-control frequency 75 iterations, best-
    quality tracking in the last 50 iterations. Projection uses
    ``projectBackToBoundary``'s ``-geps*100`` threshold (pulls
    boundary-adjacent inside points to the boundary).

    Parameters
    ----------
    pts : admesh.boundary.PTS
    fh : callable ``(N, 2) -> (N,)`` or None
        Mesh-size function; uniform if ``None``.
    h0 : float
        Target minimum edge length (``hmin`` in the MATLAB source).
    pfix : (M, 2) array or None
        Fixed points (always present in the mesh, never moved). Mirrors
        MATLAB ``GetMeshConstraints`` semantics: only points from
        ``PTS.BC`` constraints are pinned, **not** the densified ring
        vertices. Pass ``None`` (default) for no pinning — the boundary
        emerges from truss equilibrium + ``projectBackToBoundary`` at
        ``fh``-driven spacing. Pass a small set of corner / constraint
        points to anchor sharp features that must land exactly.
    cleanup : bool
        Run :func:`_boundary_cleanup` on the final best-quality mesh.
    **opts :
        ``fd``, ``seed``, ``niter`` overrides.

    Returns
    -------
    MeshOutput
    """
    from admesh._stages.boundary import classify_nodes_against_pts

    # Parameter values from ``distmesh2d.m`` lines 38-43.
    ttol = 0.5
    Fscale = 1.15
    deltat = 0.3
    geps = 1e-3 * h0
    densityctrlfreq = 75
    niter = int(opts.pop("niter", 1000))
    seed = int(opts.pop("seed", 0))
    rng = np.random.default_rng(seed)
    deps = np.sqrt(np.finfo(float).eps) * h0

    fd = opts.pop("fd", None)
    if fd is None:
        fd = _polygon_sdf_from_pts(pts)
    if fh is None:
        fh = lambda q: np.ones(len(q), dtype=float)  # noqa: E731

    # createInitialPointList → rejectionMethod → GetMeshConstraints(pfix)
    p = _initial_point_list_from_pts(fd, pts, h0, geps)
    p = _rejection_method(p, fh, rng)

    # Constraints (pfix). Faithful to MATLAB ``GetMeshConstraints.m``
    # @ 19b2eb9: pfix is **only** the points from ``PTS.BC`` (open-ocean
    # BC, line constraints, barriers) — *not* the densified polygon
    # ring. When the PTS has no constraints, ``nC = 0`` and the boundary
    # emerges from truss equilibrium + ``projectBackToBoundary``, with
    # spacing driven by ``fh``. Pre-Apr-26 code stuffed the entire ring
    # into pfix, which forced uniform boundary spacing regardless of
    # curvature.
    if pfix is not None:
        pfix_arr = np.asarray(pfix, dtype=float).reshape(-1, 2)
    else:
        pfix_arr = np.empty((0, 2))
    nC = len(pfix_arr)
    if nC:
        # Drop free points that coincide with a fixed point.
        if len(p):
            d2fix = np.min(
                np.linalg.norm(p[:, None, :] - pfix_arr[None, :, :], axis=2), axis=1
            )
            p = p[d2fix > geps]
        p = np.vstack([pfix_arr, p])
    C: NDArray[np.int64] | None = None  # no interior constraints

    N = len(p)
    pold = np.full_like(p, np.inf)
    qold = 0.0
    P = p.copy()
    T = np.empty((0, 3), dtype=np.int64)
    t = np.empty((0, 3), dtype=np.int64)
    bars = np.empty((0, 2), dtype=np.int64)

    k = 0
    while k < niter:
        # Retriangulate if any node moved > ttol*h0.
        moved = np.sqrt(((p - pold) ** 2).sum(axis=1)) / h0
        if moved.max() > ttol:
            pold = p.copy()
            tri = Delaunay(p)
            t_all = tri.simplices
            centroids = (p[t_all[:, 0]] + p[t_all[:, 1]] + p[t_all[:, 2]]) / 3.0
            t = np.sort(t_all[fd(centroids) < -geps], axis=1)
            bars = np.unique(
                np.vstack([t[:, [0, 1]], t[:, [0, 2]], t[:, [1, 2]]]), axis=0
            )

        if bars.size == 0:
            k += 1
            continue

        # Truss forces.
        barvec = p[bars[:, 0]] - p[bars[:, 1]]
        L = np.sqrt((barvec ** 2).sum(axis=1))
        hbars = fh((p[bars[:, 0]] + p[bars[:, 1]]) / 2.0)
        L0 = hbars * Fscale * np.sqrt((L ** 2).sum() / (hbars ** 2).sum())

        # Density control — ``distmesh2d.m`` lines 167-197.
        if (k % densityctrlfreq == 0) and (k < niter - 5) and k > 0:
            too_close = L0 > 2.0 * L
            if too_close.any():
                drop_ids = np.unique(bars[too_close].ravel())
                # Never drop fixed points (MATLAB: setdiff(..., 1:nC)).
                drop_ids = drop_ids[drop_ids >= nC]
                keep_mask = np.ones(N, dtype=bool)
                keep_mask[drop_ids] = False
                p = p[keep_mask]
                N = len(p)
                pold = np.full_like(p, np.inf)
                k += 1
                continue
            # MATLAB lines 183-195: ``k > niter/2`` late-run thinning.
            # BoundaryDensityControl drops the interior vertex of any
            # free-boundary triangle with q < 0.2; ConstraintDensityControl
            # drops non-fixed points lying in a ``sqrt(3)/8·fh`` strip
            # around each constraint segment. Mirrors the MATLAB
            # ``continue`` — force a retriangulation next iter via
            # ``pold=inf`` whether or not any points were actually removed.
            if k > niter // 2 and t.size:
                p = _boundary_density_control(p, t, C, nC)
                p = _constraint_density_control(p, nC, C, fh)
                N = len(p)
                pold = np.full_like(p, np.inf)
                k += 1
                continue

        F = np.maximum(L0 - L, 0.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            Fvec = np.where(L[:, None] > 0, (F / L)[:, None] * barvec, 0.0)

        Ftot = np.zeros_like(p)
        np.add.at(Ftot, bars[:, 0], Fvec)
        np.add.at(Ftot, bars[:, 1], -Fvec)
        if nC > 0:
            Ftot[:nC] = 0.0
        p = p + deltat * Ftot

        # Pull boundary-adjacent interior points onto the boundary
        # (MATLAB ``in`` = indices nC..N-1, i.e. non-fixed nodes).
        if nC < N:
            p[nC:] = _project_back_to_boundary(p[nC:], fd, geps, deps=deps)

        # Best-quality tracking in the last 50 iterations.
        if k > (niter - 50) and t.size:
            q = _element_quality_mean(p, t)
            if q > qold:
                qold = q
                P = p.copy()
                T = t.copy()
        k += 1

    # On early termination / never-entered best-q window, fall back to
    # the current positions + triangulation.
    if qold == 0.0:
        P, T = p, t

    # Final cleanup: BoundaryCleanUp(P,T,C); fixmesh(P,T).
    if cleanup:
        T = _boundary_cleanup(P, T, C)
    P, T, _ = fixmesh(P, T)

    ring_id, bc = classify_nodes_against_pts(pts, P, tol=0.2 * h0)
    return MeshOutput(p=P, t=T, node_bc=bc, ring_id=ring_id)


def _polygon_sdf_from_pts(pts) -> SDF:
    """SDF for the multiply-connected region described by ``pts``.

    ``d(p) < 0`` iff ``p`` is inside the outer ring AND outside every
    hole. Computed via a ray-cast inside test (from
    :mod:`admesh.in_polygon`) plus per-segment Euclidean distance.
    """
    from admesh._stages.in_polygon import in_polygon
    from admesh._stages.mesh_size import _point_segment_distance  # reuse

    outer = pts.rings[0]
    holes = pts.rings[1:]

    def fd(p: Points) -> NDArray[np.float64]:
        p = np.asarray(p, dtype=float).reshape(-1, 2)
        in_outer, _ = in_polygon(p[:, 0], p[:, 1], outer[:, 0], outer[:, 1])
        inside_any_hole = np.zeros(len(p), dtype=bool)
        for h in holes:
            in_h, _ = in_polygon(p[:, 0], p[:, 1], h[:, 0], h[:, 1])
            inside_any_hole |= in_h
        inside = in_outer & ~inside_any_hole

        d_min = np.full(len(p), np.inf)
        for ring in pts.rings:
            M = len(ring)
            for i in range(M):
                a = ring[i]
                b = ring[(i + 1) % M]
                d, _ = _point_segment_distance(p, a, b)
                d_min = np.minimum(d_min, d)

        return np.where(inside, -d_min, d_min)

    return fd
