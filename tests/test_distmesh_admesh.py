"""ADMESH-variant distmesh path — clean-room P3."""

from __future__ import annotations

import numpy as np

from admesh import domains
from admesh.boundary import PTS, BoundaryType
from admesh.distmesh import MeshOutput, _boundary_cleanup, distmesh2d_admesh
from admesh.quality import mesh_quality
from admesh.routine import triangulate


def _analytic_pts_unit_square(n_side: int = 16) -> PTS:
    """Hand-constructed unit-square PTS (avoids marching-squares delta sensitivity)."""
    t = np.linspace(0, 1, n_side, endpoint=False)
    # CCW outer: bottom → right → top → left
    bottom = np.column_stack([-0.5 + t, np.full_like(t, -0.5)])
    right = np.column_stack([np.full_like(t, 0.5), -0.5 + t])
    top = np.column_stack([0.5 - t, np.full_like(t, 0.5)])
    left = np.column_stack([np.full_like(t, -0.5), 0.5 - t])
    outer = np.vstack([bottom, right, top, left])
    return PTS.from_polygons(outer, bc=BoundaryType.WALL)


def test_distmesh2d_admesh_returns_meshoutput() -> None:
    pts = _analytic_pts_unit_square(n_side=12)
    out = distmesh2d_admesh(pts, fh=None, h0=0.2, niter=80, seed=0)
    assert isinstance(out, MeshOutput)
    assert out.p.ndim == 2 and out.p.shape[1] == 2
    assert out.t.ndim == 2 and out.t.shape[1] == 3
    assert out.node_bc.shape == (len(out.p),)
    assert out.ring_id.shape == (len(out.p),)


def test_distmesh2d_admesh_labels_boundary_nodes() -> None:
    pts = _analytic_pts_unit_square(n_side=12)
    out = distmesh2d_admesh(pts, fh=None, h0=0.2, niter=80, seed=0)
    # All PTS ring vertices should land on ring 0 with BC=WALL.
    wall_nodes = out.node_bc == int(BoundaryType.WALL)
    assert wall_nodes.any(), "no nodes tagged WALL"
    # Those tagged WALL all on the square boundary:
    wall_pts = out.p[wall_nodes]
    on_bnd = (np.isclose(np.abs(wall_pts[:, 0]), 0.5, atol=0.05) |
              np.isclose(np.abs(wall_pts[:, 1]), 0.5, atol=0.05))
    assert on_bnd.all()


def test_distmesh2d_admesh_annulus_has_two_rings() -> None:
    pts = PTS.from_domain(domains.ANNULUS, n_bnd=48)
    out = distmesh2d_admesh(pts, fh=None, h0=0.15, niter=100, seed=0)
    uniq_rings = set(out.ring_id.tolist()) - {-1}
    assert uniq_rings == {0, 1}, f"expected rings {{0,1}}, got {uniq_rings}"
    min_q, mean_q, _ = mesh_quality(out.p, out.t)
    assert min_q >= 0.25
    assert mean_q >= 0.55


def test_triangulate_dispatches_to_pts_path() -> None:
    """triangulate() with a PTS returns MeshOutput (not a (p,t) tuple)."""
    pts = _analytic_pts_unit_square(n_side=8)
    result = triangulate(pts, h0=0.2, niter=60, seed=0)
    assert isinstance(result, MeshOutput)


def test_triangulate_domain_path_unchanged() -> None:
    """MVP regression: triangulate(Domain) still returns (p, t) tuple."""
    result = triangulate(domains.UNIT_SQUARE, h0=0.2, niter=60, seed=0)
    assert isinstance(result, tuple) and len(result) == 2
    p, t = result
    assert p.ndim == 2 and t.ndim == 2


def test_boundary_cleanup_removes_slivers() -> None:
    """Construct a mesh where one triangle has 3 boundary nodes on the
    same ring, near-collinear. Cleanup should drop it."""
    pts = _analytic_pts_unit_square(n_side=8)
    # 3 near-collinear points on the bottom edge.
    p = np.array([
        [-0.4, -0.5],
        [-0.2, -0.5],
        [0.0,  -0.5 + 1e-4],
        [0.0, 0.0],  # interior node
    ])
    # 2 triangles: one is a sliver on the boundary; one is a regular
    # interior triangle.
    t = np.array([[0, 1, 2], [0, 1, 3]])
    cleaned = _boundary_cleanup(p, t, pts)
    # Should drop the sliver (nodes 0,1,2 all on bottom edge ring 0).
    assert len(cleaned) == 1
    assert (cleaned[0] == [0, 1, 3]).all()
