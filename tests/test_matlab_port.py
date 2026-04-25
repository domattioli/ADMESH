"""Port-correctness tests for the faithful MATLAB ports of
``01_ADMESH_Library/{04_Curvature_Function, 05_Medial_Axis,
08_Enforce_Boundary_Conditions, 10_Distmesh_2d}``.

These tests exercise the Python implementations against reference
values derived by hand-executing the MATLAB algorithm on small
inputs. They are complementary to the full MATLAB-fixture parity
suite (``tests/fixtures/<stage>/*.npz`` via
``scripts/export_matlab_fixtures.m`` + ``scripts/mat_to_npz.py``) —
the hand-derived cases run in any environment; the full fixtures
run only when a MATLAB-exported ``.npz`` is present.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from admesh.boundary import (
    BCSegment,
    PTS,
    create_polygon_structure,
    enforce_boundary_conditions,
)
from admesh.curvature import apply_curvature
from admesh.distmesh import (
    _boundary_cleanup,
    _boundary_density_control,
    _constraint_density_control,
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
FIXTURE_ROOT_BND = Path(__file__).parent / "fixtures" / "boundary"


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
# BoundaryDensityControl / ConstraintDensityControl — hand-derived cases
# ---------------------------------------------------------------------------


def test_boundary_density_control_drops_apex_of_attached_sliver():
    """A sliver whose free edge lies on the mesh perimeter, with its
    two other edges shared with good interior triangles, should lose
    only its apex vertex.

    Mesh: small 3-tri patch around a near-boundary interior apex (3):
      - tri_body_1 = (0, 3, 2), tri_body_2 = (1, 3, 2): interior
      - tri_sliver = (0, 1, 3): base (0,1) on the perimeter, apex at 3
    With 3 placed very close to (0,1), tri_sliver has q ≪ 0.2 while
    the bodies have q > 0.2. MATLAB's ``iNode`` for the sliver's free
    edge (0,1) = 3. The interior-body free edges (0,2) and (1,2) also
    point to 3, but those triangles are good-quality and don't mark.
    """
    p = np.array([
        [0.0, 0.0],   # 0
        [1.0, 0.0],   # 1
        [0.5, 1.0],   # 2
        [0.5, 0.05],  # 3 — apex close to edge (0,1) → sliver
    ])
    t = np.array(
        [
            [0, 3, 2],  # body 1 (good)
            [1, 3, 2],  # body 2 (good)
            [0, 1, 3],  # sliver (q ≈ 0.016)
        ],
        dtype=np.int64,
    )
    out = _boundary_density_control(p, t, C=None, nC=0)
    assert len(out) == 3
    # Vertices 0, 1, 2 preserved (in order); 3 removed.
    np.testing.assert_allclose(out, p[:3])


def test_boundary_density_control_keeps_fixed_apex():
    """When the bad sliver's apex is a fixed point (index < nC), the
    removal must be skipped even though MATLAB would otherwise target
    it. Mirrors ``setdiff(badQ, 1:nC)`` at MATLAB line 60.
    """
    # Same geometry as above but with the apex as the FIRST (fixed) point.
    p = np.array([
        [0.5, 0.05],  # 0 — fixed apex
        [0.0, 0.0],   # 1
        [1.0, 0.0],   # 2
        [0.5, 1.0],   # 3
    ])
    t = np.array(
        [
            [1, 0, 3],  # body 1
            [2, 0, 3],  # body 2
            [1, 2, 0],  # sliver (apex = 0 is fixed)
        ],
        dtype=np.int64,
    )
    out = _boundary_density_control(p, t, C=None, nC=1)
    assert len(out) == 4


def test_boundary_density_control_keeps_good_quality_triangles():
    """When no boundary triangle has q < 0.2, nothing is removed."""
    # Equilateral-ish pair sharing one edge; all qs are near 1.
    p = np.array([
        [0.0, 0.0],
        [1.0, 0.0],
        [0.5, np.sqrt(3) / 2.0],
        [0.5, -np.sqrt(3) / 2.0],
    ])
    t = np.array([[0, 1, 2], [0, 1, 3]], dtype=np.int64)
    out = _boundary_density_control(p, t, C=None, nC=0)
    assert len(out) == 4


def test_constraint_density_control_noop_when_C_empty():
    p = np.array([[0.0, 0.0], [1.0, 1.0], [0.5, 0.5]])
    fh = lambda q: np.full(len(q), 0.1)  # noqa: E731
    out = _constraint_density_control(p, nC=0, C=None, fh=fh)
    np.testing.assert_allclose(out, p)
    out2 = _constraint_density_control(p, nC=0, C=np.empty((0, 2), dtype=np.int64), fh=fh)
    np.testing.assert_allclose(out2, p)


def test_constraint_density_control_removes_points_in_strip():
    """Constraint segment from (0,0)→(1,0); fh=0.8 ⇒ half-width ≈ 0.173.
    A point at (0.5, 0.1) lies inside the strip; (0.5, 0.5) does not.
    Segment endpoints are fixed (nC=2) so they survive regardless.
    """
    p = np.array([
        [0.0, 0.0],  # 0 — fixed endpoint of C
        [1.0, 0.0],  # 1 — fixed endpoint of C
        [0.5, 0.1],  # 2 — inside strip (expected to be removed)
        [0.5, 0.5],  # 3 — outside strip (keep)
    ])
    C = np.array([[0, 1]], dtype=np.int64)
    fh = lambda q: np.full(len(q), 0.8)  # noqa: E731
    # Half-width = 0.8 * sqrt(3)/8 ≈ 0.173, so 0.1 is inside, 0.5 is outside.
    out = _constraint_density_control(p, nC=2, C=C, fh=fh)
    assert len(out) == 3
    # Rows 0,1,3 should remain.
    np.testing.assert_allclose(out, p[[0, 1, 3]])


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


# ---------------------------------------------------------------------------
# EnforceBoundaryConditions + create_polygon_structure — hand-derived cases
# ---------------------------------------------------------------------------


def test_create_polygon_structure_L_matches_edge_lengths():
    """MATLAB line 60: POLY.L = sqrt(dx^2 + dy^2) per edge."""
    # 3-edge polyline: lengths sqrt(2), 2, 1.
    pts = np.array([[0.0, 0.0], [1.0, 1.0], [3.0, 1.0], [3.0, 0.0]])
    poly = create_polygon_structure(pts)
    np.testing.assert_allclose(poly.L, [np.sqrt(2.0), 2.0, 1.0], atol=1e-12)


def test_create_polygon_structure_normal_convention_matches_matlab():
    """MATLAB lines 61-62: nx = dy/L, ny = -dx/L with dx=x1-x2, dy=y1-y2.

    For edge [(0,0) -> (1,0)]: dx=-1, dy=0. L=1. nx=0, ny=-(-1)/1=1.
    So corner 0 of the rectangle is (x1 + nx*d, y1 + ny*d) = (0, d).
    """
    pts = np.array([[0.0, 0.0], [1.0, 0.0]])
    poly = create_polygon_structure(pts, delta=0.2)
    d = np.sqrt(3.0) / 2.0 * 0.2
    assert poly.x[0, 0] == pytest.approx(0.0, abs=1e-12)
    assert poly.y[0, 0] == pytest.approx(d, abs=1e-12)
    assert poly.x[0, 1] == pytest.approx(0.0, abs=1e-12)
    assert poly.y[0, 1] == pytest.approx(-d, abs=1e-12)


def test_enforce_bc_matches_matlab_line_37_far_exterior():
    """MATLAB line 37: h_ic(D > hmin) = hmax."""
    h0 = np.full((2, 3), 0.25)
    X = np.zeros_like(h0); Y = np.zeros_like(h0)
    D = np.array([[-0.3, 0.05, 0.5], [-1.0, 0.0, 0.2]])
    pts = PTS.from_polygons(np.array([[0.0, 0], [1, 0], [1, 1], [0, 1]]))
    h = enforce_boundary_conditions(h0, X, Y, D, None, pts, hmax=1.0, hmin=0.1)
    # D > 0.1 → hmax=1; D <= 0.1 → clip of 0.25 is unchanged (still 0.25).
    np.testing.assert_allclose(h, [[0.25, 0.25, 1.0], [0.25, 0.25, 1.0]])


def test_enforce_bc_early_return_when_no_BC():
    """MATLAB line 42: isempty(PTS.BC) → return. IB is NOT applied."""
    h0 = np.full((2, 2), 0.3)
    X = np.zeros_like(h0); Y = np.zeros_like(h0)
    D = np.full_like(h0, -0.5)
    pts = PTS.from_polygons(np.array([[0.0, 0], [1, 0], [1, 1], [0, 1]]))
    IB = np.ones_like(h0, dtype=bool)  # would set everything to hmax
    h = enforce_boundary_conditions(h0, X, Y, D, IB, pts, hmax=1.0, hmin=0.01)
    # IB NOT applied because pts.BC is empty.
    np.testing.assert_allclose(h, 0.3)


def test_enforce_bc_open_ocean_applies_when_BC_nonempty():
    """MATLAB line 47: h_ic(IB) = hmax; only fires when BC is non-empty."""
    h0 = np.full((2, 2), 0.3)
    X = np.zeros_like(h0); Y = np.zeros_like(h0)
    D = np.full_like(h0, -0.5)
    bc_seg = BCSegment(num=-1, points=np.array([[0.0, 0], [1, 0]]))
    pts = PTS.from_polygons(
        np.array([[0.0, 0], [1, 0], [1, 1], [0, 1]]), BC=[bc_seg]
    )
    IB = np.array([[True, False], [False, True]])
    h = enforce_boundary_conditions(h0, X, Y, D, IB, pts, hmax=1.0, hmin=0.01)
    assert h[0, 0] == 1.0 and h[1, 1] == 1.0
    assert h[0, 1] == 0.3 and h[1, 0] == 0.3


def test_enforce_bc_external_barrier_sets_h_to_L_in_band():
    """MATLAB lines 94-136: external-barrier num=3 sets h=L on band cells
    inside per-edge polygon. Horizontal barrier of length 2 at y=0.
    L=2; d=sqrt(3)/2 * 2 ≈ 1.732; band |D|<=2 covers most cells.
    """
    xs = np.linspace(-3.0, 3.0, 13)
    ys = np.linspace(-3.0, 3.0, 13)
    X, Y = np.meshgrid(xs, ys, indexing="xy")
    D = Y.copy()
    h0 = np.full_like(D, 0.5)
    bc_seg = BCSegment(num=3, points=np.array([[-1.0, 0.0], [1.0, 0.0]]))
    pts = PTS.from_polygons(
        np.array([[-3.0, -3], [3, -3], [3, 3], [-3, 3]]), BC=[bc_seg]
    )
    h = enforce_boundary_conditions(h0, X, Y, D, None, pts, hmax=5.0, hmin=0.01)
    # On-barrier cell: abs(D)=0 <= L=2; x=0 is inside rect [x1-d,x2+d]×[-d,d].
    jc = np.argmin(np.abs(ys))
    ic = np.argmin(np.abs(xs))
    assert h[jc, ic] == pytest.approx(2.0, abs=1e-10)


def test_enforce_bc_internal_barrier_triaged_same_as_external():
    """MATLAB lines 142-183 mirror lines 94-136; only the BC.num triage
    differs. A num=4 internal barrier should behave just like num=3.
    """
    xs = np.linspace(-3.0, 3.0, 13)
    ys = np.linspace(-3.0, 3.0, 13)
    X, Y = np.meshgrid(xs, ys, indexing="xy")
    D = Y.copy()
    h0 = np.full_like(D, 0.5)
    bc_seg_int = BCSegment(num=4, points=np.array([[-1.0, 0.0], [1.0, 0.0]]))
    bc_seg_ext = BCSegment(num=3, points=np.array([[-1.0, 0.0], [1.0, 0.0]]))
    pts_int = PTS.from_polygons(
        np.array([[-3.0, -3], [3, -3], [3, 3], [-3, 3]]), BC=[bc_seg_int]
    )
    pts_ext = PTS.from_polygons(
        np.array([[-3.0, -3], [3, -3], [3, 3], [-3, 3]]), BC=[bc_seg_ext]
    )
    h_int = enforce_boundary_conditions(h0, X, Y, D, None, pts_int, hmax=5.0, hmin=0.01)
    h_ext = enforce_boundary_conditions(h0, X, Y, D, None, pts_ext, hmax=5.0, hmin=0.01)
    np.testing.assert_allclose(h_int, h_ext)


# --------------------- MATLAB-exported fixture parity ---------------------


def test_enforce_bc_matlab_fixture():
    path = FIXTURE_ROOT_BND / "enforce_bc_simple.npz"
    if not path.exists():
        pytest.skip("MATLAB fixture not available: boundary/enforce_bc_simple.npz")
    fx = dict(np.load(path, allow_pickle=True))
    pts_obj = fx.get("pts")
    # Fixture format: arrays for h0, X, Y, D, hmax, hmin; PTS reconstructed
    # from stored ring + BC points.
    h0 = fx["h0"]; X = fx["X"]; Y = fx["Y"]; D = fx["D"]
    hmax = float(fx["hmax"]); hmin = float(fx["hmin"])
    ring = fx["ring"]
    pts = PTS.from_polygons(ring)
    got = enforce_boundary_conditions(h0, X, Y, D, None, pts, hmax=hmax, hmin=hmin)
    np.testing.assert_allclose(got, fx["h_expected"], atol=1e-8)
