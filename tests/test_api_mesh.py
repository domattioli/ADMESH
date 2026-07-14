"""Tests for ``admesh.api`` Mesh dataclass (T007, T011, T012).

Frozen-ness, ``BoundarySegment.__post_init__`` validation,
``n_*`` count properties, ``__repr__`` / ``__str__``, and ``Mesh.equals``.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

import admesh
from admesh import BoundarySegment, BoundaryType, Domain, Mesh


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


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


def _toy_mesh_with_quality() -> Mesh:
    nodes = np.array(
        [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]], dtype=np.float64
    )
    elements = np.array([[0, 1, 2], [1, 3, 2]], dtype=np.int64)
    quality = np.array([0.41, 0.93], dtype=np.float64)
    seg_open = BoundarySegment(
        node_ids=np.array([0, 1], dtype=np.int64),
        bc_type=BoundaryType.OPEN,
        is_open=True,
    )
    seg_main = BoundarySegment(
        node_ids=np.array([1, 3, 2, 0], dtype=np.int64),
        bc_type=BoundaryType.MAINLAND,
        is_open=False,
    )
    return Mesh(
        nodes=nodes, elements=elements, boundaries=(seg_open, seg_main),
        quality=quality,
    )


# ---------------------------------------------------------------------------
# Frozen-ness
# ---------------------------------------------------------------------------


def test_mesh_is_frozen():
    mesh = Mesh(
        nodes=np.zeros((3, 2), dtype=np.float64),
        elements=np.array([[0, 1, 2]], dtype=np.int64),
    )
    with pytest.raises(FrozenInstanceError):
        mesh.title = "mutated"  # type: ignore[misc]


def test_domain_is_frozen():
    domain = Domain(sdf=lambda p: np.zeros(p.shape[0]), bbox=(0.0, 0.0, 1.0, 1.0))
    with pytest.raises(FrozenInstanceError):
        domain.bbox = (0.0, 0.0, 2.0, 2.0)  # type: ignore[misc]


def test_boundary_segment_is_frozen():
    seg = BoundarySegment(
        node_ids=np.array([0, 1, 2], dtype=np.int64),
        bc_type=BoundaryType.OPEN,
        is_open=True,
    )
    with pytest.raises(FrozenInstanceError):
        seg.is_open = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# BoundarySegment.__post_init__ validation
# ---------------------------------------------------------------------------


def test_boundary_segment_rejects_non_ndarray():
    with pytest.raises(TypeError):
        BoundarySegment(node_ids=[0, 1, 2], bc_type=BoundaryType.OPEN, is_open=True)  # type: ignore[arg-type]


def test_boundary_segment_rejects_2d_array():
    with pytest.raises(ValueError):
        BoundarySegment(
            node_ids=np.zeros((2, 2), dtype=np.int64),
            bc_type=BoundaryType.OPEN,
            is_open=True,
        )


def test_boundary_segment_rejects_wrong_dtype():
    with pytest.raises(ValueError):
        BoundarySegment(
            node_ids=np.array([0, 1, 2], dtype=np.int32),
            bc_type=BoundaryType.OPEN,
            is_open=True,
        )


def test_boundary_segment_rejects_negative_index():
    with pytest.raises(ValueError):
        BoundarySegment(
            node_ids=np.array([0, -1, 2], dtype=np.int64),
            bc_type=BoundaryType.OPEN,
            is_open=True,
        )


def test_boundary_segment_accepts_empty():
    seg = BoundarySegment(
        node_ids=np.array([], dtype=np.int64),
        bc_type=BoundaryType.OPEN,
        is_open=True,
    )
    assert seg.node_ids.size == 0


def test_boundary_segment_accepts_unmapped_int_bc():
    seg = BoundarySegment(
        node_ids=np.array([0, 1], dtype=np.int64),
        bc_type=22,
        is_open=False,
    )
    assert seg.bc_type == 22
    assert not isinstance(seg.bc_type, BoundaryType)


# ---------------------------------------------------------------------------
# Mesh count properties
# ---------------------------------------------------------------------------


def test_mesh_count_properties():
    nodes = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]], dtype=np.float64)
    elements = np.array([[0, 1, 2], [1, 3, 2]], dtype=np.int64)
    seg_a = BoundarySegment(
        node_ids=np.array([0, 1], dtype=np.int64),
        bc_type=BoundaryType.OPEN,
        is_open=True,
    )
    seg_b = BoundarySegment(
        node_ids=np.array([1, 3, 2, 0], dtype=np.int64),
        bc_type=BoundaryType.MAINLAND,
        is_open=False,
    )
    mesh = Mesh(nodes=nodes, elements=elements, boundaries=(seg_a, seg_b))
    assert mesh.n_nodes == 4
    assert mesh.n_elements == 2
    assert mesh.n_boundaries == 2


def test_mesh_defaults():
    nodes = np.zeros((3, 2), dtype=np.float64)
    elements = np.array([[0, 1, 2]], dtype=np.int64)
    mesh = Mesh(nodes=nodes, elements=elements)
    assert mesh.boundaries == ()
    assert mesh.bathymetry is None
    assert mesh.quality is None
    assert mesh.title == ""
    assert mesh.n_boundaries == 0


# ---------------------------------------------------------------------------
# Mesh.__repr__ / Mesh.__str__
# ---------------------------------------------------------------------------


def test_repr_summary_includes_counts_and_quality():
    mesh = _toy_mesh_with_quality()
    text = repr(mesh)
    assert "n_nodes=4" in text
    assert "n_elements=2" in text
    assert "min_q=" in text
    assert "mean_q=" in text
    assert "n_boundaries=2" in text


def test_repr_omits_quality_when_none():
    mesh = _toy_mesh_with_quality()
    bare = Mesh(nodes=mesh.nodes, elements=mesh.elements)
    text = repr(bare)
    assert "min_q" not in text
    assert "mean_q" not in text
    assert "n_nodes=4" in text


def test_str_lists_per_segment_breakdown():
    mesh = _toy_mesh_with_quality()
    text = str(mesh)
    assert "OPEN" in text
    assert "MAINLAND" in text
    # Per-segment node counts shown.
    assert "(2 nodes)" in text
    assert "(4 nodes)" in text


def test_str_renders_unmapped_numeric_bc():
    nodes = np.zeros((3, 2), dtype=np.float64)
    elements = np.array([[0, 1, 2]], dtype=np.int64)
    seg = BoundarySegment(
        node_ids=np.array([0, 1, 2], dtype=np.int64),
        bc_type=22,
        is_open=False,
    )
    mesh = Mesh(nodes=nodes, elements=elements, boundaries=(seg,))
    text = str(mesh)
    assert "code=22" in text


# ---------------------------------------------------------------------------
# Mesh.equals
# ---------------------------------------------------------------------------


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
