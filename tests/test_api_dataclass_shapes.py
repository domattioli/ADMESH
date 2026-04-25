"""Tests for ``admesh.api`` dataclass shapes (T007).

Frozen-ness, ``BoundarySegment.__post_init__`` validation, and the
``n_*`` count properties on :class:`admesh.api.Mesh`.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from admesh.api import BoundarySegment, Domain, Mesh
from admesh.boundary_types import BoundaryType


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
