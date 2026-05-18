"""Mesh-size field: iterative gradient-limited PDE solver.

Port of ``01_ADMESH_Library/09_Mesh_Size/MeshSizeIterativeSolver.c``
@ 19b2eb9 from C (MATLAB mex) to Python.

The C routine solves (to steady state) the upwind iteration

    h_{t+1}(i,j) = h_t(i,j) + (delta/2) * (min(|grad h|, g) - |grad h|)

over cells where ``D[i,j] <= 4 * hmin`` (boundary-ish region), with
``|grad h|`` computed from one-sided upwind differences of the current
``h_t``. The iteration terminates when the L1 residual falls below
``tol = 1e-5`` (MATLAB ``10e-6`` == 1e-5).

Parameter mapping (mex signature vs. Python):

    mex: MeshSizeIter(h0, D, hmax, hmin, g, delta) -> h
    py:  solve_iter(h0, D, hmax, hmin, g, delta) -> h

``hmax`` is accepted for API parity but unused in the C kernel (only
``hmin`` gates the update region).

Two implementations ship in-module:

- :func:`_solve_iter_py` — pure-NumPy reference. Vectorized row by row
  would break the serial cell-order update pattern of the mex, so we
  keep it a scalar loop.
- :func:`_solve_iter_nb` — Numba ``@njit`` acceleration of the same
  loop; enabled automatically when ``numba`` is importable.

``solve_iter`` dispatches to the Numba path by default; pass
``use_numba=False`` to force the pure-Python path (used for debugging
and for the parity test).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

try:
    import numba as _nb

    _HAVE_NUMBA = True
except ImportError:  # pragma: no cover
    _HAVE_NUMBA = False


_TOL = 1e-5


def _solve_iter_py(
    h0: NDArray[np.float64],
    D: NDArray[np.float64],
    hmin: float,
    g: float,
    delta: float,
) -> NDArray[np.float64]:
    h = h0.astype(np.float64, copy=True)
    LY, LX = h.shape
    deltat = delta / 2.0
    four_hmin = 4.0 * hmin

    while True:
        R = 0.0
        for i in range(1, LX - 1):
            for j in range(1, LY - 1):
                if D[j, i] > four_hmin:
                    continue

                xfor = min((h[j, i + 1] - h[j, i]) / delta, 0.0)
                xfor *= xfor
                xback = max((h[j, i] - h[j, i - 1]) / delta, 0.0)
                xback *= xback
                yfor = min((h[j + 1, i] - h[j, i]) / delta, 0.0)
                yfor *= yfor
                yback = max((h[j, i] - h[j - 1, i]) / delta, 0.0)
                yback *= yback

                Delta = (xfor + xback + yfor + yback) ** 0.5
                hn = h[j, i] + deltat * (min(Delta, g) - Delta)
                R += abs(hn - h[j, i])
                h[j, i] = hn

        if R <= _TOL:
            break

    return h


if _HAVE_NUMBA:

    @_nb.njit(cache=True)
    def _solve_iter_nb(
        h0: NDArray[np.float64],
        D: NDArray[np.float64],
        hmin: float,
        g: float,
        delta: float,
    ) -> NDArray[np.float64]:
        h = h0.copy()
        LY, LX = h.shape
        deltat = delta / 2.0
        four_hmin = 4.0 * hmin
        tol = 1e-5

        while True:
            R = 0.0
            for i in range(1, LX - 1):
                for j in range(1, LY - 1):
                    if D[j, i] > four_hmin:
                        continue
                    xfor = (h[j, i + 1] - h[j, i]) / delta
                    if xfor > 0.0:
                        xfor = 0.0
                    xfor *= xfor

                    xback = (h[j, i] - h[j, i - 1]) / delta
                    if xback < 0.0:
                        xback = 0.0
                    xback *= xback

                    yfor = (h[j + 1, i] - h[j, i]) / delta
                    if yfor > 0.0:
                        yfor = 0.0
                    yfor *= yfor

                    yback = (h[j, i] - h[j - 1, i]) / delta
                    if yback < 0.0:
                        yback = 0.0
                    yback *= yback

                    Delta = (xfor + xback + yfor + yback) ** 0.5
                    if Delta < g:
                        hn = h[j, i]
                    else:
                        hn = h[j, i] + deltat * (g - Delta)
                    R += abs(hn - h[j, i])
                    h[j, i] = hn

            if R <= tol:
                break

        return h


def solve_iter(
    h0: NDArray[np.float64],
    D: NDArray[np.float64],
    hmax: float,  # noqa: ARG001 — accepted for mex-signature parity
    hmin: float,
    g: float,
    delta: float,
    *,
    use_numba: bool = True,
) -> NDArray[np.float64]:
    """Solve the gradient-limited mesh-size field.

    See module docstring for the algorithm and parameter meaning.
    Returns a new array; ``h0`` is not mutated.
    """
    h0 = np.asarray(h0, dtype=np.float64)
    D = np.asarray(D, dtype=np.float64)
    if h0.shape != D.shape:
        raise ValueError("h0 and D must have the same shape")

    if use_numba and _HAVE_NUMBA:
        return _solve_iter_nb(h0, D, float(hmin), float(g), float(delta))
    return _solve_iter_py(h0, D, float(hmin), float(g), float(delta))


# ---------------------------------------------------------------------------
# Size-field composer (Phase P1) — wires curvature + medial into a single
# ``fh(p)`` callable suitable for ``distmesh2d`` and ``triangulate``.
# ---------------------------------------------------------------------------


def build_h(
    domain,
    *,
    base: float = 0.1,
    grid_delta: float | None = None,
    curvature_scale: float | None = None,
    medial_scale: float | None = None,
    pts=None,
    boundary_scale=None,
    bathymetry=None,
    bathy_scale: float | None = None,
    tide_period: float | None = None,
    tide_scale: float | None = None,
    hmin: float | None = None,
    hmax: float | None = None,
    g: float = 0.2,
):
    """Compose a mesh-size function for a :class:`~admesh.domains.Domain`.

    Parameters
    ----------
    domain : Domain
    base : float
        Target edge length where no size-reducing term is active.
    grid_delta : float or None
        Sampling resolution for the intermediate grid. Defaults to
        ``base / 4`` — fine enough that the interpolant is smooth at
        target mesh scale.
    curvature_scale : float or None
        If set, reduces ``h`` near boundaries of high curvature:
        ``h_curv = 1 / (|κ| + 1/hmax)``, scaled so the max reduction
        factor is ``curvature_scale``. ``None`` disables the term.
    medial_scale : float or None
        If set, reduces ``h`` near the medial axis (useful for
        narrow channels / pinch points):
        ``h_med = max(medial_scale, d_medial)``. ``None`` disables.
    pts : PTS or None
        If set, use the PTS's boundary segments to drive a
        boundary-distance-based size reduction; composes with the
        other terms.
    boundary_scale : dict[int, float] or float or None
        With ``pts`` set: target ``h`` at the nearest boundary of
        each BC type. If a dict, keys are :class:`~admesh.boundary.
        BoundaryType` int values; a ``float`` applies uniformly
        across all BC types. Cells grow toward ``base`` with
        distance to the nearest BC-typed segment. ``None`` disables.
    bathymetry : callable ``(X, Y) -> Z`` or None
        Bathymetric elevation sampler. Routed through
        :func:`admesh.bathymetry.create_elevation_grid` (which
        NaN-inpaints missing depth values) to produce the ``Z``
        grid used by the bathymetry + tide terms.
    bathy_scale : float or None
        If set (with ``bathymetry``), routes to
        :func:`admesh.bathymetry.apply_bathymetry`. This is MATLAB's
        ``s`` parameter — elements per e-folding depth change.
    tide_period : float or None
        Dominant tidal period in seconds (MATLAB ``Tide_Period``).
        Required with ``tide_scale``.
    tide_scale : float or None
        Elements per tidal wavelength (MATLAB ``tide_value`` =
        ``sz``). Routes to :func:`admesh.dominate_tide.apply_tide`;
        requires ``bathymetry`` + ``tide_period``.
    hmin : float or None
        Lower bound for the composed field. Defaults to ``base / 8``.
    hmax : float or None
        Upper bound. Defaults to ``base``.
    g : float
        Gradient-limit for the Eikonal smoother (``solve_iter``).

    Returns
    -------
    fh : callable ``(N, 2) -> (N,)``
        Interpolant-backed size function usable as ``distmesh2d``'s
        ``fh`` argument. If no reduction term is active, returns a
        uniform-``base`` callable (no grid work).
    """
    want_pts = pts is not None and boundary_scale is not None
    want_bathy = bathymetry is not None and bathy_scale is not None
    want_tide = (
        bathymetry is not None and tide_scale is not None and tide_period is not None
    )
    if (
        curvature_scale is None
        and medial_scale is None
        and not want_pts
        and not want_bathy
        and not want_tide
    ):
        # No enrichment requested — identical to the MVP default.
        return lambda p: np.full(len(np.asarray(p, dtype=float).reshape(-1, 2)), base)

    from admesh._stages.distance import eval_sdf_grid

    delta = float(grid_delta) if grid_delta is not None else base / 4.0
    hmin = float(hmin) if hmin is not None else base / 8.0
    hmax = float(hmax) if hmax is not None else base

    X, Y, D = eval_sdf_grid(domain.fd, domain.bbox, delta)
    h = np.full_like(D, base)

    if curvature_scale is not None:
        # Route to the MATLAB-faithful port (CurvatureFunction.m).
        # Mapping: `K = π / curvature_scale` — K is MATLAB's "elements
        # per radian"; at unit curvature, the MATLAB formula yields
        # h = π/K = curvature_scale near the boundary.
        from admesh._stages.curvature import apply_curvature

        K = float(np.pi / float(curvature_scale))
        h = apply_curvature(h, D, delta, K=K, g=g, hmax=hmax, hmin=hmin)

    if medial_scale is not None:
        # Route to the MATLAB-faithful port (MedialAxisFunction.m).
        # Mapping: `R = 0.4 / medial_scale` — calibrated so that on a
        # typical feature (LFS ≈ 0.4), ``h = LFS/R ≈ medial_scale``.
        # MATLAB's R is "elements per LFS unit"; users more naturally
        # think in target-h units.
        from admesh._stages.medial_axis import apply_medial_axis

        R = float(0.4 / float(medial_scale))
        h = apply_medial_axis(h, D, delta, R=R, hmax=hmax, hmin=hmin)

    if want_pts:
        h_bnd = _pts_boundary_field(pts, X, Y, boundary_scale, hmax, g)
        h = np.minimum(h, h_bnd)

    if want_bathy or want_tide:
        from admesh._stages.bathymetry import create_elevation_grid
        Z = create_elevation_grid(X, Y, bathymetry)

        if want_bathy:
            from admesh._stages.bathymetry import apply_bathymetry
            # With no curvature stage active, let bathymetry drive the
            # boundary band too (MATLAB ``Settings.K = 'Off'``).
            mask_band = curvature_scale is not None
            h = apply_bathymetry(
                h, D, Z, delta,
                s=float(bathy_scale), hmin=hmin, hmax=hmax,
                mask_boundary_band=mask_band,
            )

        if want_tide:
            from admesh._stages.dominate_tide import apply_tide
            h = apply_tide(
                h, Z,
                tide_period=float(tide_period),
                tide_value=float(tide_scale),
                hmin=hmin, hmax=hmax,
            )

    h = np.clip(h, hmin, hmax)

    # Gradient-limit: solves the Eikonal smoother so the size field's
    # spatial rate-of-change is bounded by g.
    D_abs = np.abs(D)
    h_smooth = solve_iter(h, D_abs, hmax, hmin, g, delta)

    # Build an interpolant. Use scipy's RegularGridInterpolator for
    # bilinear lookup on the generated grid.
    from scipy.interpolate import RegularGridInterpolator

    xs = X[0, :]
    ys = Y[:, 0]
    interp = RegularGridInterpolator(
        (ys, xs), h_smooth, method="linear", bounds_error=False, fill_value=hmax,
    )

    def fh(p):
        p = np.asarray(p, dtype=float).reshape(-1, 2)
        # RegularGridInterpolator expects (y, x) order.
        return interp(np.column_stack([p[:, 1], p[:, 0]]))

    return fh


def _pts_boundary_field(pts, X, Y, boundary_scale, hmax, g):
    """PTS-driven boundary-distance size field on a ``(LY, LX)`` grid.

    For each grid cell, compute the distance to the nearest PTS
    segment of each BC type, and return a size field with
    pre-embedded grading slope ``g``:

        h(type) = min(scale[type] + g * d_to_nearest_segment, hmax)

    This matches the MATLAB convention — see ``CurvatureFunction.m``
    line 64, ``h_curve(I) = ... - g*D(I)`` — where the grading slope
    is embedded in the h-field initial condition rather than relying
    entirely on the post-hoc Eikonal solver. The solver
    (``MeshSizeIterativeSolver.c``) only touches cells with
    ``D <= 4*hmin``, so composition terms extending beyond that band
    must already satisfy ``|grad h| <= g`` on their own.

    The returned grid takes the elementwise minimum across BC types.
    ``boundary_scale`` is either a float (applied to every BC type
    in ``pts``) or a dict keyed by :class:`BoundaryType` int values.
    """
    grid_pts = np.column_stack([X.ravel(), Y.ravel()])
    LY, LX = X.shape

    # Collect segments per BC-type.
    segments_by_type: dict[int, list[tuple[np.ndarray, np.ndarray]]] = {}
    for ring, tags in zip(pts.rings, pts.bc_type):
        M = len(ring)
        for si in range(M):
            a = ring[si]
            b = ring[(si + 1) % M]
            segments_by_type.setdefault(int(tags[si]), []).append((a, b))

    if isinstance(boundary_scale, dict):
        scale_lookup = {int(k): float(v) for k, v in boundary_scale.items()}
    else:
        scale_val = float(boundary_scale)
        scale_lookup = {t: scale_val for t in segments_by_type}

    result = np.full((LY, LX), hmax)
    for bc_int, segs in segments_by_type.items():
        if bc_int not in scale_lookup:
            continue
        d_min = np.full(len(grid_pts), np.inf)
        for a, b in segs:
            d, _ = _point_segment_distance(grid_pts, a, b)
            d_min = np.minimum(d_min, d)
        # Grading slope g embedded directly — see MATLAB CurvatureFunction.m:64.
        h_type = np.minimum(scale_lookup[bc_int] + g * d_min, hmax).reshape(LY, LX)
        result = np.minimum(result, h_type)
    return result


def _point_segment_distance(p, a, b):
    """Vectorized perpendicular distance (reproduces admesh.boundary helper).

    Kept local to avoid a circular import; small enough not to matter.
    """
    ab = b - a
    denom = float(ab @ ab)
    if denom < 1e-30:
        return np.linalg.norm(p - a, axis=1), np.zeros(len(p))
    t = np.clip(((p - a) @ ab) / denom, 0.0, 1.0)
    proj = a + t[:, None] * ab
    return np.linalg.norm(p - proj, axis=1), t
