"""Tests for ``Mesh.equals`` (T012)."""

from __future__ import annotations

import numpy as np
import pytest

from admesh import BoundarySegment, BoundaryType, Mesh


def _two_triangle_mesh(*, with_bath: bool = False) -> Mesh:
    nodes = np.array(
        [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]], dtype=np.float64
    )
    elements = np.array([[0, 1, 2], [1, 3, 2]], dtype=np.int64)
    seg = BoundarySegment(
        node_ids=np.array([0, 1, 3, 2], dtype=np.int64),
        bc_type=BoundaryType.MAINLAND,
        is_open=False,
    )
    bath = np.array([1.0, 2.0, 3.0, 4.0]) if with_bath else None
    return Mesh(nodes=nodes, elements=elements, boundaries=(seg,), bathymetry=bath)


def test_equals_self():
    mesh = _two_triangle_mesh()
    assert mesh.equals(mesh)


def test_equals_atol_perturbation():
    a = _two_triangle_mesh()
    b_nodes = a.nodes.copy()
    b_nodes[0, 0] += 5e-7
    b = Mesh(nodes=b_nodes, elements=a.elements, boundaries=a.boundaries)
    assert a.equals(b, atol=1e-5)
    assert not a.equals(b, atol=1e-9)


def test_equals_connectivity_difference_trips_at_high_tol():
    a = _two_triangle_mesh()
    swapped = a.elements[::-1].copy()
    b = Mesh(nodes=a.nodes, elements=swapped, boundaries=a.boundaries)
    assert not a.equals(b, atol=1e-2)


def test_equals_bathymetry_presence_must_match():
    a = _two_triangle_mesh(with_bath=True)
    b = _two_triangle_mesh(with_bath=False)
    assert not a.equals(b)


def test_equals_bathymetry_tolerance():
    a = _two_triangle_mesh(with_bath=True)
    perturbed = a.bathymetry + 5e-7
    b = Mesh(
        nodes=a.nodes, elements=a.elements, boundaries=a.boundaries,
        bathymetry=perturbed,
    )
    assert a.equals(b, atol=1e-5)
    assert not a.equals(b, atol=1e-9)


def test_equals_bc_type_difference_trips():
    a = _two_triangle_mesh()
    other_seg = BoundarySegment(
        node_ids=a.boundaries[0].node_ids,
        bc_type=BoundaryType.OPEN,
        is_open=True,
    )
    b = Mesh(nodes=a.nodes, elements=a.elements, boundaries=(other_seg,))
    assert not a.equals(b)


def test_equals_node_id_difference_trips():
    a = _two_triangle_mesh()
    other_seg = BoundarySegment(
        node_ids=np.array([0, 1, 2, 3], dtype=np.int64),
        bc_type=BoundaryType.MAINLAND,
        is_open=False,
    )
    b = Mesh(nodes=a.nodes, elements=a.elements, boundaries=(other_seg,))
    assert not a.equals(b)


def test_equals_returns_notimplemented_for_non_mesh():
    a = _two_triangle_mesh()
    # `==` against an unrelated object should return False (Python falls
    # back to identity when NotImplemented bubbles).
    assert (a.equals("not a mesh") in (False, NotImplemented))
