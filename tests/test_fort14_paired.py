"""Spec-002 fort.14 paired-edge / single-node-barrier BC unit tests.

Per ``specs/002-size-field-defaults/contracts/fort14-paired-edge.md``
§ "Fixture coverage". Five tests:

  - Tier 1 fixture round-trip (`example10n` = wetting_and_drying_test.14)
  - synthetic IBTYPE 3 (single-node external weir + crest data)
  - synthetic IBTYPE 24 (paired-node internal barrier)
  - unknown IBTYPE 99 — falls back to single-node, plain int bc_type
  - malformed paired-record — raises Fort14ParseError
"""

from __future__ import annotations

import io
import pathlib

import numpy as np
import pytest

import admesh
from admesh.boundary_types import BoundaryType
from admesh.fort14 import Fort14ParseError


_FIXTURE_DIR = (
    pathlib.Path(__file__).parent / "fixtures" / "fort14" / "adcirc_examples"
)


# ---------------------------------------------------------------------------
# Synthetic-mesh helpers
# ---------------------------------------------------------------------------


def _two_triangle_mesh() -> admesh.Mesh:
    """Minimum mesh: 4 nodes, 2 triangles, 1 land-boundary segment.

    Square [0,0]–[1,1] split along the diagonal into two triangles.
    Used as the substrate for synthetic IBTYPE 3 / 24 round-trip tests.
    """
    nodes = np.array(
        [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
        dtype=np.float64,
    )
    elements = np.array(
        [[0, 1, 2], [0, 2, 3]],
        dtype=np.int64,
    )
    return admesh.Mesh(nodes=nodes, elements=elements, boundaries=())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_fort14_paired_round_trip_example10n() -> None:
    """Full round-trip on the canonical paired-edge fixture."""
    fixture = _FIXTURE_DIR / "wetting_and_drying_test.14"
    if not fixture.exists():
        pytest.skip(f"fixture not present: {fixture}")
    src = admesh.read_fort14(fixture)
    buf = io.StringIO()
    src.to_fort14(buf)
    buf.seek(0)
    rt = admesh.read_fort14(buf)

    # Connectivity exact; coords + bathy + barrier data within
    # writer-precision tolerance (%.3f for crest/coefs → atol=1e-3).
    assert src.equals(rt, atol=1e-3)
    assert src.n_nodes == rt.n_nodes
    assert src.n_elements == rt.n_elements
    assert len(src.boundaries) == len(rt.boundaries)

    for a, b in zip(src.boundaries, rt.boundaries):
        assert int(a.bc_type) == int(b.bc_type)
        assert a.is_open == b.is_open
        assert np.array_equal(a.node_ids, b.node_ids)
        if a.paired_node_ids is None:
            assert b.paired_node_ids is None
        else:
            assert np.array_equal(a.paired_node_ids, b.paired_node_ids)
        if a.barrier_data is None:
            assert b.barrier_data is None
        else:
            assert a.barrier_data.shape == b.barrier_data.shape
            assert np.allclose(a.barrier_data, b.barrier_data, atol=1e-3)


def test_fort14_ibtype_3_external_weir(tmp_path) -> None:
    """Synthetic IBTYPE 3 mesh: round-trip preserves the crest column.

    Single-segment land boundary with 3 nodes, IBTYPE 3 (external weir),
    barrier_data = (3, 2) — two trailing floats per record. Confirms
    the column-agnostic reader/writer handles non-canonical shapes
    (the contract docs 3 floats; `wetting_and_drying_test.14` uses 2).
    """
    mesh = _two_triangle_mesh()
    seg = admesh.BoundarySegment(
        node_ids=np.array([0, 1, 2], dtype=np.int64),
        bc_type=BoundaryType.EXTERNAL_BARRIER,
        is_open=False,
        paired_node_ids=None,
        barrier_data=np.array(
            [[3.5, 1.0], [3.5, 1.0], [3.5, 1.0]], dtype=np.float64
        ),
    )
    mesh = admesh.Mesh(
        nodes=mesh.nodes,
        elements=mesh.elements,
        boundaries=(seg,),
    )

    out = tmp_path / "ibtype3.14"
    mesh.to_fort14(out)
    rt = admesh.read_fort14(out)
    assert rt.n_nodes == mesh.n_nodes
    assert rt.n_elements == mesh.n_elements
    assert len(rt.boundaries) == 1
    rt_seg = rt.boundaries[0]
    assert int(rt_seg.bc_type) == 3
    assert isinstance(rt_seg.bc_type, BoundaryType)
    assert rt_seg.bc_type is BoundaryType.EXTERNAL_BARRIER
    assert rt_seg.paired_node_ids is None
    assert rt_seg.barrier_data is not None
    assert rt_seg.barrier_data.shape == (3, 2)
    assert np.allclose(rt_seg.barrier_data, seg.barrier_data, atol=1e-3)
    assert np.array_equal(rt_seg.node_ids, seg.node_ids)


def test_fort14_ibtype_24_internal_barrier(tmp_path) -> None:
    """Synthetic IBTYPE 24 mesh: paired ids + crest preserved exactly."""
    mesh = _two_triangle_mesh()
    # Use 4 nodes — enough for a 2-pair segment.
    nodes = np.array(
        [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
        dtype=np.float64,
    )
    elements = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
    seg = admesh.BoundarySegment(
        node_ids=np.array([0, 1], dtype=np.int64),
        bc_type=BoundaryType.INTERNAL_BARRIER,
        is_open=False,
        paired_node_ids=np.array([2, 3], dtype=np.int64),
        barrier_data=np.array(
            [[2.0, 1.0, 1.0], [2.0, 1.0, 1.0]], dtype=np.float64
        ),
    )
    mesh = admesh.Mesh(nodes=nodes, elements=elements, boundaries=(seg,))

    out = tmp_path / "ibtype24.14"
    mesh.to_fort14(out)
    rt = admesh.read_fort14(out)

    assert len(rt.boundaries) == 1
    rt_seg = rt.boundaries[0]
    assert rt_seg.bc_type is BoundaryType.INTERNAL_BARRIER
    assert int(rt_seg.bc_type) == 24
    assert np.array_equal(rt_seg.node_ids, seg.node_ids)
    assert rt_seg.paired_node_ids is not None
    assert np.array_equal(rt_seg.paired_node_ids, seg.paired_node_ids)
    assert rt_seg.barrier_data is not None
    assert rt_seg.barrier_data.shape == (2, 3)
    assert np.allclose(rt_seg.barrier_data, seg.barrier_data, atol=1e-3)


def test_fort14_unknown_ibtype_falls_back(tmp_path) -> None:
    """An unknown IBTYPE round-trips as plain int with no barrier_data."""
    nodes = np.array(
        [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
        dtype=np.float64,
    )
    elements = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
    # IBTYPE 99 — not in any of the recognized frozensets.
    seg = admesh.BoundarySegment(
        node_ids=np.array([0, 1, 2], dtype=np.int64),
        bc_type=99,
        is_open=False,
    )
    mesh = admesh.Mesh(nodes=nodes, elements=elements, boundaries=(seg,))

    out = tmp_path / "ibtype99.14"
    mesh.to_fort14(out)
    rt = admesh.read_fort14(out)
    assert len(rt.boundaries) == 1
    rt_seg = rt.boundaries[0]
    # Plain int round-trip — bc_type is NOT a BoundaryType member.
    assert not isinstance(rt_seg.bc_type, BoundaryType)
    assert int(rt_seg.bc_type) == 99
    assert rt_seg.paired_node_ids is None
    assert rt_seg.barrier_data is None


def test_fort14_malformed_paired_record(tmp_path) -> None:
    """An IBTYPE 24 record with too few tokens raises Fort14ParseError."""
    # Construct a minimal fort.14 with one IBTYPE-24 segment that has
    # only 2 tokens per record (should be 5).
    text = (
        "title\n"
        "1 4\n"
        "1 0.0 0.0 0.0\n"
        "2 1.0 0.0 0.0\n"
        "3 1.0 1.0 0.0\n"
        "4 0.0 1.0 0.0\n"
        "1 3 1 2 3\n"
        "0\n"  # NOPE
        "0\n"  # NETA
        "1\n"  # NBOU
        "2\n"  # NVEL
        "2 24\n"  # one segment with 2 paired records, IBTYPE 24
        "1 2\n"  # malformed: only 2 tokens
        "3 4\n"
    )
    path = tmp_path / "malformed.14"
    path.write_text(text)
    with pytest.raises(Fort14ParseError) as exc:
        admesh.read_fort14(path)
    # Error should mention the paired-edge expectation.
    assert "paired-edge" in str(exc.value)
