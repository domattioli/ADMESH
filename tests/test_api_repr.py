"""Tests for ``Mesh.__repr__`` / ``Mesh.__str__`` (T011)."""

from __future__ import annotations

import numpy as np

import admesh
from admesh import BoundarySegment, BoundaryType, Mesh


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
