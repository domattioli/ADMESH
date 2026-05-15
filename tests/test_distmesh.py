"""Tests for admesh.distmesh + admesh.routine."""

import numpy as np

from admesh import domains
from admesh.distmesh import distmesh2d, fixmesh
from admesh.quality import mesh_quality
from admesh.routine import triangulate

from conftest import assert_valid_mesh as _assert_valid_mesh


def test_fixmesh_removes_duplicate() -> None:
    p = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 0.0]])
    t = np.array([[0, 1, 2], [3, 1, 2]])
    p2, t2, _ = fixmesh(p, t)
    # The duplicate should collapse; 3 unique points remain.
    assert len(p2) == 3
    # Both triangles map to the same canonical connectivity (same 3 verts).
    assert t2.shape == (2, 3)
    assert set(map(tuple, np.sort(t2, axis=1).tolist())) == {(0, 1, 2)}


def test_fixmesh_flips_negative_triangle() -> None:
    p = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    t = np.array([[0, 2, 1]])  # negatively oriented
    _, t2, _ = fixmesh(p, t)
    # After flipping, signed area is positive.
    d12 = p[t2[0, 1]] - p[t2[0, 0]]
    d13 = p[t2[0, 2]] - p[t2[0, 0]]
    area = 0.5 * (d12[0] * d13[1] - d12[1] * d13[0])
    assert area > 0


def test_distmesh2d_unit_square_coarse() -> None:
    fd = domains.UNIT_SQUARE.fd
    p, t = distmesh2d(
        fd=fd, fh=None, h0=0.2, bbox=domains.UNIT_SQUARE.bbox,
        pfix=domains.UNIT_SQUARE.fixed_points, niter=80, seed=0,
    )
    _assert_valid_mesh(p, t, fd, geps=1e-3)
    min_q, mean_q, _ = mesh_quality(p, t)
    assert mean_q > 0.6
    assert min_q > 0.1


def test_distmesh2d_unit_disk_coarse() -> None:
    fd = domains.UNIT_DISK.fd
    p, t = distmesh2d(
        fd=fd, fh=None, h0=0.25, bbox=domains.UNIT_DISK.bbox,
        pfix=None, niter=80, seed=0,
    )
    _assert_valid_mesh(p, t, fd, geps=1e-2)
    min_q, mean_q, _ = mesh_quality(p, t)
    assert mean_q > 0.6


def test_triangulate_dispatches_to_distmesh() -> None:
    p, t = triangulate(domains.UNIT_SQUARE, h0=0.2, niter=60, seed=0)
    _assert_valid_mesh(p, t, domains.UNIT_SQUARE.fd, geps=1e-3)


# ---------------------------------------------------------------------------
# Issue #45: initial_points warm-start
# ---------------------------------------------------------------------------


def test_distmesh2d_initial_points_skips_lattice() -> None:
    """Warm-start: providing initial_points bypasses lattice+rejection."""
    fd = domains.UNIT_SQUARE.fd
    # Cold-start reference.
    p_cold, t_cold = distmesh2d(
        fd=fd, fh=None, h0=0.2, bbox=domains.UNIT_SQUARE.bbox,
        pfix=domains.UNIT_SQUARE.fixed_points, niter=100, seed=0,
    )
    # Warm-start from the cold solution — should converge quickly and
    # produce a valid mesh with similar node count.
    p_warm, t_warm = distmesh2d(
        fd=fd, fh=None, h0=0.2, bbox=domains.UNIT_SQUARE.bbox,
        pfix=domains.UNIT_SQUARE.fixed_points,
        initial_points=p_cold,
        niter=30, seed=0,
    )
    _assert_valid_mesh(p_warm, t_warm, fd, geps=1e-3)
    min_q, mean_q, _ = mesh_quality(p_warm, t_warm)
    assert mean_q > 0.6
    # Node count roughly similar (within 30%).
    assert abs(len(p_warm) - len(p_cold)) / max(len(p_cold), 1) < 0.30


def test_distmesh2d_initial_points_filters_outside() -> None:
    """Points far outside the domain are filtered before the truss loop."""
    fd = domains.UNIT_SQUARE.fd
    # Cold-start to get a good interior distribution.
    p_ref, _ = distmesh2d(
        fd=fd, fh=None, h0=0.2, bbox=domains.UNIT_SQUARE.bbox,
        pfix=domains.UNIT_SQUARE.fixed_points, niter=80, seed=0,
    )
    # Append two clearly-outside points and warm-start from the result.
    outside = np.array([[5.0, 5.0], [-5.0, -5.0]])
    pts = np.vstack([p_ref, outside])
    p, t = distmesh2d(
        fd=fd, fh=None, h0=0.2, bbox=domains.UNIT_SQUARE.bbox,
        pfix=domains.UNIT_SQUARE.fixed_points,
        initial_points=pts, niter=30, seed=0,
    )
    # Far-outside points (fd >> h0) must not appear in the result.
    geps = 1e-3 * 0.2
    assert (fd(p) <= geps + 0.05).all(), "outside points leaked into result"
    assert len(p) <= len(p_ref) + 4, "extra outside points not dropped"


def test_triangulate_api_initial_points() -> None:
    """api.triangulate passes initial_points through to distmesh2d."""
    import admesh
    from admesh import domains as _d

    dom_api = admesh.Domain(
        sdf=_d.UNIT_SQUARE.fd,
        bbox=_d.UNIT_SQUARE.bbox,
    )
    # Cold mesh.
    m0 = admesh.triangulate(dom_api, h_max=0.2, seed=0, max_iter=100, quality_gate=(0.0, 0.0))
    # Warm-start from cold mesh nodes.
    m1 = admesh.triangulate(
        dom_api, h_max=0.2, seed=0, max_iter=30,
        initial_points=m0.nodes, quality_gate=(0.0, 0.0),
    )
    assert m1.n_nodes > 0
    assert m1.n_elements > 0


# ---------------------------------------------------------------------------
# Issue #47: convergence diagnostics
# ---------------------------------------------------------------------------


def test_distmesh2d_return_diagnostics_basic() -> None:
    """return_diagnostics=True returns 3-tuple with per-iter history."""
    fd = domains.UNIT_SQUARE.fd
    result = distmesh2d(
        fd=fd, fh=None, h0=0.25, bbox=domains.UNIT_SQUARE.bbox,
        niter=20, seed=0, return_diagnostics=True,
    )
    assert len(result) == 3
    p, t, diags = result
    assert isinstance(diags, list)
    assert len(diags) > 0
    first = diags[0]
    assert set(first.keys()) >= {"iter", "n_pts", "n_elements", "max_disp", "n_outside"}
    # iter values are monotonically increasing.
    iters = [d["iter"] for d in diags]
    assert iters == list(range(len(diags)))


def test_distmesh2d_return_diagnostics_false_gives_tuple2() -> None:
    """Default (return_diagnostics=False) returns 2-tuple — no regression."""
    fd = domains.UNIT_SQUARE.fd
    result = distmesh2d(
        fd=fd, fh=None, h0=0.25, bbox=domains.UNIT_SQUARE.bbox,
        niter=10, seed=0, return_diagnostics=False,
    )
    assert len(result) == 2
    p, t = result
    assert p.ndim == 2 and p.shape[1] == 2


def test_distmesh2d_diagnostics_all_fields_numeric() -> None:
    """All diagnostic fields are finite non-negative numbers."""
    fd = domains.UNIT_SQUARE.fd
    _, _, diags = distmesh2d(
        fd=fd, fh=None, h0=0.2, bbox=domains.UNIT_SQUARE.bbox,
        niter=200, seed=0, return_diagnostics=True,
    )
    assert len(diags) > 0
    for d in diags:
        assert d["n_pts"] >= 0
        assert d["n_elements"] >= 0
        assert np.isfinite(d["max_disp"])
        assert d["n_outside"] >= 0
