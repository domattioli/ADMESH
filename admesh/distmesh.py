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

from typing import Callable

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.spatial import Delaunay

Points = NDArray[np.float64]
SDF = Callable[[Points], NDArray[np.float64]]
SizeFn = Callable[[Points], NDArray[np.float64]]


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
    dptol: float = 1e-3,
    ttol: float = 0.1,
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
            bars = np.unique(
                np.vstack([t[:, [0, 1]], t[:, [0, 2]], t[:, [1, 2]]]), axis=0
            )

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
            dx = (fd(po + np.array([deps, 0.0])) - fd(po)) / deps
            dy = (fd(po + np.array([0.0, deps])) - fd(po)) / deps
            denom = dx * dx + dy * dy
            safe = denom > 0
            d_o = d[outside]
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
