"""PTS + boundary-condition enforcement — clean-room P3.

Covers: explicit-polygon construction, SDF-contour construction via
marching squares, BC classification of mesh nodes.
"""

from __future__ import annotations

import numpy as np
import pytest

from admesh import domains
from admesh.boundary import (
    PTS,
    BoundaryType,
    _signed_area,
    enforce_boundary_conditions,
)


# ---------------------------- from_polygons ---------------------------------


def test_from_polygons_single_ring_wall() -> None:
    outer = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    pts = PTS.from_polygons(outer)
    assert pts.n_rings == 1
    assert pts.n_vertices == 4
    assert (pts.bc_type[0] == int(BoundaryType.WALL)).all()


def test_from_polygons_with_holes_per_ring_bc() -> None:
    outer = np.array([[-2.0, -2], [2, -2], [2, 2], [-2, 2]])
    hole = np.array([[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]])
    pts = PTS.from_polygons(
        outer, holes=[hole], bc=[BoundaryType.OPEN, BoundaryType.WALL],
    )
    assert pts.n_rings == 2
    assert (pts.bc_type[0] == int(BoundaryType.OPEN)).all()
    assert (pts.bc_type[1] == int(BoundaryType.WALL)).all()


def test_from_polygons_rejects_bc_length_mismatch() -> None:
    outer = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    with pytest.raises(ValueError):
        PTS.from_polygons(outer, bc=[BoundaryType.WALL, BoundaryType.OPEN])


# ---------------------------- from_domain -----------------------------------


def test_from_domain_unit_square_single_ring() -> None:
    pts = PTS.from_domain(domains.UNIT_SQUARE, n_bnd=32)
    assert pts.n_rings == 1
    assert len(pts.rings[0]) == 32
    # Outer CCW orientation (signed area > 0).
    assert _signed_area(pts.rings[0]) > 0
    # All points land near the boundary |x|=0.5 or |y|=0.5.
    r = pts.rings[0]
    on_bnd = np.isclose(np.abs(r[:, 0]), 0.5, atol=1e-2) | np.isclose(
        np.abs(r[:, 1]), 0.5, atol=1e-2
    )
    assert on_bnd.all()


def test_from_domain_annulus_two_rings() -> None:
    pts = PTS.from_domain(domains.ANNULUS, n_bnd=64)
    assert pts.n_rings == 2
    # Outer ring has larger perimeter.
    r_outer = np.hypot(pts.rings[0][:, 0], pts.rings[0][:, 1])
    r_inner = np.hypot(pts.rings[1][:, 0], pts.rings[1][:, 1])
    assert np.allclose(r_outer.mean(), 1.0, atol=5e-2)
    assert np.allclose(r_inner.mean(), 0.4, atol=5e-2)
    # Outer CCW (>0), inner CW (<0).
    assert _signed_area(pts.rings[0]) > 0
    assert _signed_area(pts.rings[1]) < 0


def test_from_domain_unit_disk_is_circle() -> None:
    pts = PTS.from_domain(domains.UNIT_DISK, n_bnd=48)
    assert pts.n_rings == 1
    r = np.hypot(pts.rings[0][:, 0], pts.rings[0][:, 1])
    # Marching squares inherits grid-resolution error; 2% is the bar.
    np.testing.assert_allclose(r, 1.0, atol=2e-2)


# ---------------------------- enforce_boundary_conditions -------------------


def test_enforce_bc_classifies_nodes() -> None:
    outer = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    pts = PTS.from_polygons(outer, bc=BoundaryType.WALL)
    p = np.array([
        [0.5, 0.5],   # interior
        [0.5, 0.0],   # bottom edge
        [1.0, 0.5],   # right edge
        [0.001, 0.5], # near-left edge (within tol=1e-2)
        [0.1, 0.1],   # interior (far from edges given tol)
    ])
    ring_id, bc = enforce_boundary_conditions(pts, p, tol=1e-2)
    assert ring_id[0] == -1 and bc[0] == -1
    assert ring_id[1] == 0 and bc[1] == int(BoundaryType.WALL)
    assert ring_id[2] == 0 and bc[2] == int(BoundaryType.WALL)
    assert ring_id[3] == 0 and bc[3] == int(BoundaryType.WALL)
    assert ring_id[4] == -1 and bc[4] == -1


def test_enforce_bc_annulus_picks_correct_ring() -> None:
    pts = PTS.from_domain(domains.ANNULUS, n_bnd=64)
    # One point near the outer boundary (r=1), one near the inner (r=0.4).
    p = np.array([[1.0, 0.0], [0.4, 0.0], [0.7, 0.0]])
    ring_id, bc = enforce_boundary_conditions(pts, p, tol=5e-2)
    assert ring_id[0] == 0  # outer
    assert ring_id[1] == 1  # inner
    assert ring_id[2] == -1  # middle of annulus, far from either ring
