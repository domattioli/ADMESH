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
