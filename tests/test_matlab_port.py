"""Port-correctness tests for the faithful MATLAB port of
``01_ADMESH_Library/10_Distmesh_2d/``.

These tests exercise the Python implementations against reference
values derived by hand-executing the MATLAB algorithm on small
inputs. They are complementary to the full MATLAB-fixture parity
suite (``tests/fixtures/distmesh/*.npz`` via
``scripts/export_matlab_fixtures.m`` + ``scripts/mat_to_npz.py``) —
the hand-derived cases run in any environment; the full fixtures
run only when a MATLAB-exported ``.npz`` is present.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from admesh.curvature import apply_curvature
from admesh.distmesh import (
    _boundary_cleanup,
    _initial_point_list_from_pts,
    _project_back_to_boundary,
)
from admesh.medial_axis import (
    _average_outward_flux,
    apply_medial_axis,
    medial_axis_mask,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "distmesh"
FIXTURE_ROOT_CURV = Path(__file__).parent / "fixtures" / "curvature"
FIXTURE_ROOT_MED = Path(__file__).parent / "fixtures" / "medial_axis"


# ---------------------------------------------------------------------------
# BoundaryCleanUp — hand-derived cases
# ---------------------------------------------------------------------------


def test_boundary_cleanup_matches_matlab_q_formula():
    """Quality formula: q = (b+c-a)(c+a-b)(a+b-c) / (abc).

    Unit right triangle with legs 1 and hypotenuse sqrt(2) should
    have q ≈ 0.828. It's > 0.15, so cleanup should keep it.
    """
    p = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [2.0, 2.0]])
    # Second triangle far away is needed so the first isn't isolated.
    t = np.array([[0, 1, 2], [0, 1, 3]])
    cleaned = _boundary_cleanup(p, t, None)
    # Both tris are boundary-attached but both have q > 0.15.
    # Verify hand-computed q for [0,1,2]:
    a, b, c = 1.0, np.sqrt(2.0), 1.0
    q_expected = (b + c - a) * (c + a - b) * (a + b - c) / (a * b * c)
    assert q_expected == pytest.approx(0.828, abs=5e-3)
    assert len(cleaned) == 2


def test_boundary_cleanup_keeps_interior_triangle():
    """A triangle whose edges are all internal (no free-boundary edge)
    is never a cleanup candidate regardless of its quality."""
    # Central triangle [3,4,5] is interior; surrounded by 3 triangles.
    p = np.array([
        [0.0, 0.0],   # 0
        [1.0, 0.0],   # 1
        [0.5, 1.0],   # 2
        [0.5, 0.3],   # 3 interior
        [0.6, 0.4],   # 4 interior
        [0.4, 0.4],   # 5 interior
    ])
    t = np.array([
        [3, 4, 5],    # interior sliver-ish (small but interior)
        [0, 1, 3],
        [1, 2, 4],
        [2, 0, 5],
        [0, 3, 5],
        [1, 4, 3],
        [2, 5, 4],
    ])
    cleaned = _boundary_cleanup(p, t, None)
    # The interior triangle [3,4,5] has no free-boundary edge, so
    # it survives even if its q is low.
    assert np.any(np.all(np.sort(cleaned, axis=1) == [3, 4, 5], axis=1))


def test_boundary_cleanup_constraint_preserves_sliver():
    p = np.array([[-0.4, -0.5], [-0.2, -0.5], [0.0, -0.5 + 1e-4], [0.0, 0.0]])
    t = np.array([[0, 1, 2], [0, 1, 3]])
    # Without constraint: sliver dropped.
    assert len(_boundary_cleanup(p, t, None)) == 1
    # With constraint on (0,2): sliver kept.
    C = np.array([[0, 2]])
    assert len(_boundary_cleanup(p, t, C)) == 2


# ---------------------------------------------------------------------------
# projectBackToBoundary — hand-derived cases
# ---------------------------------------------------------------------------


def test_project_back_outside_point_lands_on_boundary():
    """Outside point at (1.1, 0) on unit disk → projects to (1, 0)."""
    fd = lambda p: np.hypot(p[:, 0], p[:, 1]) - 1.0  # noqa: E731
    p = np.array([[1.1, 0.0]])
    geps = 1e-5
    deps = 1e-8
    out = _project_back_to_boundary(p, fd, geps, deps=deps)
    assert out[0, 0] == pytest.approx(1.0, abs=1e-4)
    assert out[0, 1] == pytest.approx(0.0, abs=1e-4)


def test_project_back_pulls_adjacent_inside_to_boundary():
    """Signature difference from canonical Persson — points with
    ``d > -geps*100`` are ALSO projected. A point at (0.999, 0) on
    the unit disk has d=-0.001; if geps=1e-5 then -geps*100=-0.001,
    so -0.001 > -0.001 is False, but try geps=1e-4: -geps*100=-0.01,
    and -0.001 > -0.01 is True → projected onto the boundary."""
    fd = lambda p: np.hypot(p[:, 0], p[:, 1]) - 1.0  # noqa: E731
    p = np.array([[0.999, 0.0]])
    geps = 1e-4
    deps = 1e-8
    out = _project_back_to_boundary(p, fd, geps, deps=deps)
    # Point pulled OUTWARD to r ≈ 1.
    r_out = np.hypot(out[0, 0], out[0, 1])
    assert r_out == pytest.approx(1.0, abs=1e-3)


def test_project_back_leaves_deep_interior_points_alone():
    """A point at (0, 0) on the unit disk has d=-1; with any sane
    geps, -1 < -geps*100, so the point is not in the projection mask
    and stays put."""
    fd = lambda p: np.hypot(p[:, 0], p[:, 1]) - 1.0  # noqa: E731
    p = np.array([[0.0, 0.0], [-0.5, 0.6]])
    geps = 1e-3
    deps = 1e-8
    out = _project_back_to_boundary(p, fd, geps, deps=deps)
    np.testing.assert_allclose(out, p, atol=1e-12)


# ---------------------------------------------------------------------------
# createInitialPointList — hand-derived cases
# ---------------------------------------------------------------------------


def test_initial_point_list_unit_square():
    """Unit square [-0.5, 0.5]^2 with hmin=0.5 should produce 9
    lattice candidates (3×3 grid) — all 9 are inside (d ≤ 0) at the
    corners, so all 9 survive with geps=1e-4."""
    fd = lambda p: np.maximum(np.abs(p[:, 0]), np.abs(p[:, 1])) - 0.5  # noqa: E731
    # Mock PTS-like object with a rings attribute.
    class _FakePTS:
        rings = [np.array([[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]])]
    pts = _FakePTS()
    p = _initial_point_list_from_pts(fd, pts, hmin=0.5, geps=1e-4)
    # xs = [-0.5, 0.0, 0.5]; ys (spacing 0.5*sqrt(3)/2 ≈ 0.433): [-0.5, -0.067, 0.366]
    # After even-row shift (MATLAB 2:2:end = py 1::2), row 1 (y ≈ -0.067)
    # has xs + 0.25 = [-0.25, 0.25, 0.75]. The 0.75 is outside the square
    # (d = 0.25 > geps), so dropped.
    # Counts: row 0 (3 kept), row 1 (2 kept, 0.75 dropped), row 2 (3 kept).
    assert len(p) == 8


# ---------------------------------------------------------------------------
# MATLAB-exported fixture parity (skips if no .npz present)
# ---------------------------------------------------------------------------


def _load_npz_if_exists(relpath: str) -> dict | None:
    path = FIXTURE_ROOT / relpath
    if not path.exists():
        return None
    return dict(np.load(path))


@pytest.mark.parametrize("name", ["collinear_sliver", "collinear_sliver_constrained"])
def test_boundary_cleanup_matlab_fixture(name: str):
    fx = _load_npz_if_exists(f"boundary_cleanup/{name}.npz")
    if fx is None:
        pytest.skip(f"MATLAB fixture not available: {name}.npz")
    p = fx["p"]
    t = fx["t"]
    C = fx.get("C")
    out_key = "t_constrained" if "constrained" in name else "t_cleaned"
    expected = fx[out_key]
    got = _boundary_cleanup(p, t, C)
    np.testing.assert_array_equal(np.sort(got, axis=1), np.sort(expected, axis=1))


def test_project_back_matlab_fixture():
    fx = _load_npz_if_exists("project_back/unit_disk.npz")
    if fx is None:
        pytest.skip("MATLAB fixture not available: project_back/unit_disk.npz")
    fd = lambda q: np.hypot(q[:, 0], q[:, 1]) - 1.0  # noqa: E731
    got = _project_back_to_boundary(
        fx["p_in"].reshape(-1, 2), fd, float(fx["geps"]), deps=1e-10
    )
    np.testing.assert_allclose(got, fx["p_proj"].reshape(-1, 2), atol=1e-6)


def test_initial_points_matlab_fixture():
    fx = _load_npz_if_exists("initial_points/unit_square_coarse.npz")
    if fx is None:
        pytest.skip("MATLAB fixture not available: initial_points/unit_square_coarse.npz")
    fd = lambda q: np.maximum(np.abs(q[:, 0]), np.abs(q[:, 1])) - 0.5  # noqa: E731
    class _FakePTS:
        rings = [np.array([[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]])]
    got = _initial_point_list_from_pts(
        fd, _FakePTS(), float(fx["hmin"]), float(fx["geps"])
    )
    # Order may differ; compare as sets of tuples (rounded).
    got_set = {tuple(np.round(r, 10)) for r in got}
    exp_set = {tuple(np.round(r, 10)) for r in fx["p_init"].reshape(-1, 2)}
    assert got_set == exp_set


# ---------------------------------------------------------------------------
# CurvatureFunction — hand-derived cases
# ---------------------------------------------------------------------------


def test_apply_curvature_leaves_interior_at_hmax():
    """Only the narrow band |D| <= 2*hmin is modified; deep interior
    cells stay at their input h0 value (= hmax in this setup)."""
    from admesh.distance import eval_sdf_grid
    from admesh import domains
    X, Y, D = eval_sdf_grid(domains.UNIT_DISK.fd, domains.UNIT_DISK.bbox, 0.02)
    hmax, hmin = 0.2, 0.025
    h0 = np.full_like(D, hmax)
    h = apply_curvature(h0, D, 0.02, K=30.0, g=0.2, hmax=hmax, hmin=hmin)
    # Cell at origin is deep interior (|D|=1 >> 2*hmin=0.05).
    jc, ic = D.shape[0] // 2, D.shape[1] // 2
    assert h[jc, ic] == pytest.approx(hmax, abs=1e-10)


def test_apply_curvature_reduces_in_band_on_unit_disk():
    """Inside the narrow band, MATLAB formula gives h ≈ π/K at D=0
    (since κ=1 on the unit disk, formula becomes (1+0)/(K/π*1) - 0 = π/K)."""
    from admesh.distance import eval_sdf_grid
    from admesh import domains
    delta = 0.01
    X, Y, D = eval_sdf_grid(domains.UNIT_DISK.fd, domains.UNIT_DISK.bbox, delta)
    hmax, hmin = 0.5, 0.05
    h0 = np.full_like(D, hmax)
    K = 30.0
    h = apply_curvature(h0, D, delta, K=K, g=0.2, hmax=hmax, hmin=hmin)
    # Expected at D=0 boundary: h ≈ π/K = 0.1047.
    band_cells = np.abs(D) <= 2 * hmin
    boundary_cells = np.abs(D) <= delta  # very close to boundary
    expected = np.pi / K
    # Assertion: the minimum h on boundary cells is near π/K.
    assert h[boundary_cells].min() == pytest.approx(expected, abs=0.03)
    # All band cells are ≤ hmax (the formula reduces h where κ > 0).
    assert (h[band_cells] <= hmax + 1e-12).all()


# ---------------------------------------------------------------------------
# MedialAxisFunction — hand-derived cases
# ---------------------------------------------------------------------------


def test_aof_positive_on_medial_axis():
    """MATLAB AOF is high (> threshold 0.15) where the local gradient
    field 'looks outward' — i.e., on the medial axis. On a thin strip,
    that's the midline."""
    from admesh.distance import grad_sdf
    # A horizontal strip |y| <= 0.5: SDF = |y| - 0.5 (interior where y < 0.5).
    xs = np.linspace(-1.0, 1.0, 41)
    ys = np.linspace(-0.6, 0.6, 25)
    X, Y = np.meshgrid(xs, ys, indexing="xy")
    D = np.abs(Y) - 0.5
    delta = xs[1] - xs[0]
    gx, gy = grad_sdf(D, delta)
    aof = _average_outward_flux(gx, gy, delta)
    # Midline at y=0: index ≈ 12.
    mid_j = np.argmin(np.abs(ys))
    # AOF should be strongly positive at midline, weakly positive or
    # negative near the top/bottom boundary.
    mid_vals = aof[mid_j, 5:-5]
    assert mid_vals.mean() > 0.05


def test_medial_axis_mask_finds_annulus_midline():
    """Annulus medial axis is the circle r = (inner+outer)/2 = 0.7."""
    from admesh.distance import eval_sdf_grid
    from admesh import domains
    delta = 0.02
    X, Y, D = eval_sdf_grid(domains.ANNULUS.fd, domains.ANNULUS.bbox, delta)
    ma = medial_axis_mask(D, delta)
    # Medial cells should lie near r ≈ 0.7.
    ma_points_x = X[ma]
    ma_points_y = Y[ma]
    radii = np.hypot(ma_points_x, ma_points_y)
    # At least some medial cells detected; their mean r should be ≈ 0.7.
    assert ma.any()
    assert radii.mean() == pytest.approx(0.7, abs=0.05)


def test_apply_medial_axis_lfs_is_near_constant_on_annulus():
    """LFS = |D| + |MAD| is near-constant = (outer-inner)/2 along any
    radial line on the annulus (the sum trades distance-to-boundary
    for distance-to-medial). On annulus(0.4, 1.0): LFS ≈ 0.3."""
    from admesh.distance import eval_sdf_grid
    from admesh import domains
    delta = 0.02
    X, Y, D = eval_sdf_grid(domains.ANNULUS.fd, domains.ANNULUS.bbox, delta)
    hmax, hmin = 0.5, 0.01
    R = 1.0  # so h_lfs = LFS directly
    h0 = np.full_like(D, hmax)
    h = apply_medial_axis(h0, D, delta, R=R, hmax=hmax, hmin=hmin)
    # Sample along positive x-axis inside the ring; h should cluster
    # around 0.3 (the feature size of the ring).
    xs = X[0, :]
    jc = D.shape[0] // 2
    inside_ring = (xs >= 0.5) & (xs <= 0.9)
    if inside_ring.any():
        ring_h = h[jc, inside_ring]
        assert ring_h.mean() == pytest.approx(0.3, abs=0.1)
