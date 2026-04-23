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

from admesh.distmesh import (
    _boundary_cleanup,
    _initial_point_list_from_pts,
    _project_back_to_boundary,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "distmesh"


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
