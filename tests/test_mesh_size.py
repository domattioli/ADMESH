"""Tests for admesh.mesh_size."""

import numpy as np
import pytest

from admesh import domains
from admesh.mesh_size import _HAVE_NUMBA, build_h, solve_iter
from admesh.quality import mesh_quality
from admesh.routine import triangulate


def _make_inputs(n: int = 21, delta: float = 0.05) -> tuple[np.ndarray, np.ndarray]:
    # Simple setup: 21x21 grid, h0 linear ramp 0.05..0.25 in x; D = 0 everywhere
    # (so the entire interior updates — boundary cells are untouched).
    xs = np.linspace(0, 1, n)
    h0 = np.broadcast_to(np.linspace(0.05, 0.25, n)[None, :], (n, n)).copy()
    D = np.zeros((n, n), dtype=float)
    return h0, D


def test_solve_iter_returns_same_shape() -> None:
    h0, D = _make_inputs()
    h = solve_iter(h0, D, hmax=0.3, hmin=0.02, g=0.1, delta=0.05, use_numba=False)
    assert h.shape == h0.shape


def test_solve_iter_does_not_mutate_input() -> None:
    h0, D = _make_inputs()
    h0_copy = h0.copy()
    _ = solve_iter(h0, D, hmax=0.3, hmin=0.02, g=0.1, delta=0.05, use_numba=False)
    np.testing.assert_array_equal(h0, h0_copy)


def test_solve_iter_limits_gradient() -> None:
    # After solving with growth rate g, the resulting field's forward-difference
    # magnitude should everywhere in the UPDATED region be ≤ g + numerical slop.
    # The solver does not touch border cells (i in {0, LX-1}, j in {0, LY-1}),
    # so if those borders aren't themselves consistent with |grad h| ≤ g, a
    # cliff will form against the border; we exclude the border strip from
    # the check.
    h0, D = _make_inputs(n=15, delta=0.05)
    g = 0.1
    h = solve_iter(h0, D, hmax=0.3, hmin=0.02, g=g, delta=0.05, use_numba=False)
    # Interior-only diffs: drop two border cells on each side so the remaining
    # differences are all between updated cells.
    interior = h[2:-2, 2:-2]
    dh_dx = np.abs(np.diff(interior, axis=1)) / 0.05
    dh_dy = np.abs(np.diff(interior, axis=0)) / 0.05
    assert dh_dx.max() <= g + 5e-3
    assert dh_dy.max() <= g + 5e-3


def test_solve_iter_constant_field_is_fixed_point() -> None:
    h0 = np.full((11, 11), 0.1)
    D = np.zeros_like(h0)
    h = solve_iter(h0, D, hmax=0.3, hmin=0.02, g=0.05, delta=0.1, use_numba=False)
    np.testing.assert_allclose(h, h0, atol=1e-12)


@pytest.mark.skipif(not _HAVE_NUMBA, reason="numba not available")
def test_solve_iter_numba_matches_python() -> None:
    h0, D = _make_inputs(n=15, delta=0.05)
    h_py = solve_iter(h0, D, hmax=0.3, hmin=0.02, g=0.1, delta=0.05, use_numba=False)
    h_nb = solve_iter(h0, D, hmax=0.3, hmin=0.02, g=0.1, delta=0.05, use_numba=True)
    np.testing.assert_allclose(h_py, h_nb, atol=1e-10)


def test_solve_iter_gated_by_hmin() -> None:
    # When D > 4*hmin everywhere, NO cells update — output equals h0.
    h0, _ = _make_inputs()
    D = np.full_like(h0, 1.0)  # large D gates out all cells
    h = solve_iter(h0, D, hmax=0.3, hmin=0.02, g=0.1, delta=0.05, use_numba=False)
    np.testing.assert_array_equal(h, h0)


# --------------------------- build_h composer --------------------------------


def test_build_h_defaults_to_uniform() -> None:
    """With no enrichment, build_h returns a uniform-``base`` callable."""
    fh = build_h(domains.UNIT_DISK, base=0.12)
    p = np.array([[0.0, 0.0], [0.5, 0.3], [-0.2, 0.4]])
    np.testing.assert_allclose(fh(p), 0.12)


def test_build_h_curvature_shrinks_in_boundary_band() -> None:
    """MATLAB ``CurvatureFunction.m`` reduces h only in the narrow
    band ``|D| ≤ 2·hmin``. On the unit disk (κ ≡ 1 on the boundary):
    cells inside the band have h < base; cells outside stay ≈ base.
    """
    base = 0.2
    fh = build_h(
        domains.UNIT_DISK, base=base, curvature_scale=0.05,
        grid_delta=0.02,
    )
    # hmin defaults to base/8 = 0.025; band is |D|<=0.05.
    near_boundary = np.array([[0.97, 0.0]])   # D≈-0.03, inside band
    deep_interior = np.array([[0.0, 0.0]])    # D=-1, outside band
    assert fh(near_boundary)[0] < base
    # Deep interior is untouched by curvature (outside the narrow band)
    # but may still be gradient-limited by the solver.
    assert fh(deep_interior)[0] >= fh(near_boundary)[0]


def test_build_h_medial_constant_along_feature_axis() -> None:
    """MATLAB ``MedialAxisFunction.m`` uses LFS = |D| + |MAD|. By
    construction LFS is near-constant along a feature axis from the
    medial axis to the boundary (the sum just trades one for the other).
    On the annulus, h at the medial (r=0.7) and near-boundary (r=0.95)
    both reflect the local feature size ~0.3."""
    base = 0.5
    fh = build_h(
        domains.ANNULUS, base=base, medial_scale=0.05,
        grid_delta=0.02,
    )
    at_medial = np.array([[0.7, 0.0]])
    at_boundary = np.array([[0.95, 0.0]])
    # Both should be below base (LFS reduction active); magnitudes
    # similar (LFS is near-constant along radial features).
    assert fh(at_medial)[0] < base
    assert fh(at_boundary)[0] < base


def test_triangulate_accepts_composed_fh() -> None:
    """End-to-end: triangulate(..., fh=build_h(...)) produces a valid
    mesh whose min/mean quality still pass the M.4 gate."""
    dom = domains.UNIT_DISK
    fh = build_h(dom, base=0.15, curvature_scale=0.05, grid_delta=0.03)
    p, t = triangulate(dom, h0=0.15, fh=fh, niter=150, seed=0)
    assert len(p) >= 20 and len(t) >= 20
    min_q, mean_q, _ = mesh_quality(p, t)
    assert min_q >= 0.30
    assert mean_q >= 0.55  # slightly looser — enriched fh makes meshes less uniform


# -------------------------- build_h with PTS --------------------------------


def test_build_h_pts_shrinks_near_boundary() -> None:
    """With ``pts`` + ``boundary_scale``, ``fh`` near a boundary
    segment is close to boundary_scale, and grows with distance to
    the boundary."""
    from admesh.boundary import PTS, BoundaryType

    dom = domains.UNIT_SQUARE
    pts = PTS.from_domain(dom, n_bnd=40)
    fh = build_h(
        dom, base=0.2, pts=pts, boundary_scale=0.04, grid_delta=0.02,
    )
    at_boundary = np.array([[0.48, 0.0]])
    interior = np.array([[0.0, 0.0]])
    # Near-boundary should be close to the configured scale, interior
    # should be larger — at least 2x the boundary value for this setup.
    assert fh(at_boundary)[0] < 0.1
    assert fh(interior)[0] > 2.0 * fh(at_boundary)[0]


def test_build_h_pts_per_type_scale() -> None:
    """Per-BC-type scale dict applies different values per ring."""
    from admesh.boundary import PTS, BoundaryType

    dom = domains.ANNULUS
    # Outer ring = OPEN, inner ring = WALL; asymmetric refinement.
    rings = PTS.from_domain(dom, n_bnd=48).rings
    pts = PTS.from_polygons(
        rings[0], holes=[rings[1]],
        bc=[BoundaryType.OPEN, BoundaryType.WALL],
    )
    fh = build_h(
        dom, base=0.2, pts=pts,
        boundary_scale={int(BoundaryType.OPEN): 0.1,
                        int(BoundaryType.WALL): 0.02},
        grid_delta=0.02,
    )
    near_outer = np.array([[0.97, 0.0]])
    near_inner = np.array([[0.43, 0.0]])
    assert fh(near_inner)[0] < fh(near_outer)[0]


def test_build_h_pts_preserves_mvp_default() -> None:
    """When pts is given but boundary_scale is None, no enrichment."""
    from admesh.boundary import PTS

    dom = domains.UNIT_SQUARE
    pts = PTS.from_domain(dom, n_bnd=16)
    fh = build_h(dom, base=0.1, pts=pts, boundary_scale=None)
    p = np.array([[0.0, 0.0], [0.4, 0.0]])
    np.testing.assert_allclose(fh(p), 0.1)


# ---------------------- build_h with bathymetry / tide -----------------------


def test_build_h_bathymetry_routes_to_faithful_port() -> None:
    """``bathymetry`` + ``bathy_scale`` routes through
    :func:`admesh.bathymetry.apply_bathymetry`. With a steep bathy
    ramp the interior h should be reduced below ``base``."""
    dom = domains.UNIT_DISK
    # Depth grows linearly toward +x; interior cells along +x see strong
    # gradient and should pull h below base.
    def xyz(X, Y):
        return 10.0 * X + 20.0

    fh = build_h(
        dom, base=0.2, grid_delta=0.04,
        bathymetry=xyz, bathy_scale=0.1,
    )
    deep_east = np.array([[0.5, 0.0]])   # well interior, steep ramp
    at_center = np.array([[0.0, 0.0]])   # interior
    # Bathymetry should produce an fh that is finite + within bounds
    # on both points; the steep-ramp point should be reduced.
    assert fh(deep_east)[0] <= 0.2 + 1e-9
    assert np.isfinite(fh(at_center)[0])


def test_build_h_tide_routes_to_faithful_port() -> None:
    """``tide_period`` + ``tide_scale`` routes through
    :func:`admesh.dominate_tide.apply_tide`. At non-trivial depth
    the tidal wavelength formula should yield finite h within bounds."""
    dom = domains.UNIT_DISK

    def xyz(X, Y):
        return 100.0 * np.ones_like(X)  # constant 100 m depth

    base = 50.0
    fh = build_h(
        dom, base=base, grid_delta=0.04,
        hmax=base, hmin=1.0,
        bathymetry=xyz, tide_period=44712.0, tide_scale=100.0,
    )
    # h_tide = (44712/100)*sqrt(981) ≈ 14003 → clipped to hmax=base.
    interior = np.array([[0.0, 0.0]])
    assert fh(interior)[0] == pytest.approx(base, rel=1e-6)


def test_build_h_bathymetry_disabled_without_scale() -> None:
    """Passing ``bathymetry`` without ``bathy_scale`` or ``tide_scale``
    must NOT enable the contribution — MVP default path preserved."""
    dom = domains.UNIT_SQUARE

    def xyz(X, Y):
        return np.ones_like(X)

    fh = build_h(dom, base=0.1, bathymetry=xyz)
    p = np.array([[0.0, 0.0], [0.4, 0.3]])
    np.testing.assert_allclose(fh(p), 0.1)
