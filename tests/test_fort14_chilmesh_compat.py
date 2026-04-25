"""chilmesh-compatibility round-trip tests (T030, T031, T032).

These exercise the fort.14 round-trip with a hand-crafted boundary
list that mixes every named :class:`BoundaryType`, plus a numeric
unmapped code. The hypothesis: if admesh2D's own reader reproduces
the segment list bit-for-bit, then any well-behaved third-party
reader (chilmesh, OceanMesh, etc.) reading the same file will see
the same structure.
"""

from __future__ import annotations

import io

import numpy as np

import admesh
from admesh import BoundarySegment, BoundaryType, Mesh


def _square_with_mixed_bcs() -> Mesh:
    """Square mesh whose boundary segments cover OPEN/MAINLAND/ISLAND/MAINLAND_FLUX
    plus one unmapped numeric code (22, external-barrier).

    Connectivity is irrelevant for this test — we care about the
    boundary block round-trip. Geometry is a simple 4-node square so
    every segment can reference real node ids.
    """
    nodes = np.array(
        [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], dtype=np.float64
    )
    elements = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)

    seg_open = BoundarySegment(
        node_ids=np.array([0, 1], dtype=np.int64),
        bc_type=BoundaryType.OPEN,
        is_open=True,
    )
    seg_mainland = BoundarySegment(
        node_ids=np.array([1, 2], dtype=np.int64),
        bc_type=BoundaryType.MAINLAND,
        is_open=False,
    )
    seg_island = BoundarySegment(
        node_ids=np.array([2, 3], dtype=np.int64),
        bc_type=BoundaryType.ISLAND,
        is_open=False,
    )
    seg_flux = BoundarySegment(
        node_ids=np.array([3, 0], dtype=np.int64),
        bc_type=BoundaryType.MAINLAND_FLUX,
        is_open=False,
    )
    seg_unmapped = BoundarySegment(
        node_ids=np.array([0, 1, 2], dtype=np.int64),
        bc_type=22,  # external-barrier; intentionally outside our enum
        is_open=False,
    )
    return Mesh(
        nodes=nodes,
        elements=elements,
        boundaries=(seg_open, seg_mainland, seg_island, seg_flux, seg_unmapped),
        title="mixed-bcs-test",
    )


# ---------------------------------------------------------------------------
# T030: per-segment BC + node-id round-trip
# ---------------------------------------------------------------------------


def test_round_trip_preserves_segment_count():
    mesh = _square_with_mixed_bcs()
    buf = io.StringIO()
    mesh.to_fort14(buf)
    buf.seek(0)
    rt = admesh.read_fort14(buf)
    assert len(rt.boundaries) == len(mesh.boundaries)


def test_round_trip_preserves_named_bc_identity():
    mesh = _square_with_mixed_bcs()
    buf = io.StringIO()
    mesh.to_fort14(buf)
    buf.seek(0)
    rt = admesh.read_fort14(buf)

    for src, dst in zip(mesh.boundaries, rt.boundaries):
        if isinstance(src.bc_type, BoundaryType):
            assert isinstance(dst.bc_type, BoundaryType)
            assert dst.bc_type is src.bc_type
        else:
            assert not isinstance(dst.bc_type, BoundaryType)
            assert int(dst.bc_type) == int(src.bc_type)


def test_round_trip_preserves_unmapped_numeric_bc():
    mesh = _square_with_mixed_bcs()
    buf = io.StringIO()
    mesh.to_fort14(buf)
    buf.seek(0)
    rt = admesh.read_fort14(buf)

    unmapped_src = mesh.boundaries[-1]
    unmapped_dst = rt.boundaries[-1]
    assert int(unmapped_dst.bc_type) == 22
    assert not isinstance(unmapped_dst.bc_type, BoundaryType)
    assert np.array_equal(unmapped_dst.node_ids, unmapped_src.node_ids)


def test_round_trip_preserves_node_id_ordering_per_segment():
    mesh = _square_with_mixed_bcs()
    buf = io.StringIO()
    mesh.to_fort14(buf)
    buf.seek(0)
    rt = admesh.read_fort14(buf)

    for src, dst in zip(mesh.boundaries, rt.boundaries):
        assert np.array_equal(dst.node_ids, src.node_ids)


# ---------------------------------------------------------------------------
# T031: open/land block placement
# ---------------------------------------------------------------------------


def test_open_segments_land_in_open_block():
    """Every segment with `bc_type == OPEN` must round-trip with `is_open=True`."""
    mesh = _square_with_mixed_bcs()
    buf = io.StringIO()
    mesh.to_fort14(buf)
    buf.seek(0)
    rt = admesh.read_fort14(buf)

    open_segs = [s for s in rt.boundaries if s.bc_type == BoundaryType.OPEN]
    assert all(s.is_open for s in open_segs)


def test_non_open_named_segments_land_in_land_block():
    mesh = _square_with_mixed_bcs()
    buf = io.StringIO()
    mesh.to_fort14(buf)
    buf.seek(0)
    rt = admesh.read_fort14(buf)

    for seg in rt.boundaries:
        if isinstance(seg.bc_type, BoundaryType) and seg.bc_type != BoundaryType.OPEN:
            assert not seg.is_open, (
                f"named non-OPEN segment {seg.bc_type.name} ended up in open block"
            )


def test_unmapped_numeric_follows_is_open_flag():
    """Numeric BC code lands in whatever block its `is_open` flag chose."""
    mesh = _square_with_mixed_bcs()
    buf = io.StringIO()
    mesh.to_fort14(buf)
    buf.seek(0)
    rt = admesh.read_fort14(buf)

    unmapped = [s for s in rt.boundaries if not isinstance(s.bc_type, BoundaryType)]
    assert len(unmapped) == 1
    # Source had is_open=False → should still be in the land block.
    assert not unmapped[0].is_open


# ---------------------------------------------------------------------------
# T032: multiply-connected (annulus) — outer OPEN, inner MAINLAND
# ---------------------------------------------------------------------------


def test_annulus_two_rings_round_trip_separately():
    """Hand-build a doubly-connected mesh and verify both rings survive."""
    # Two concentric squares: outer 4 corners are nodes 0..3, inner 4
    # corners are nodes 4..7. Triangulate the strip so both rings
    # become real boundary edges.
    outer = np.array(
        [[-2.0, -2.0], [2.0, -2.0], [2.0, 2.0], [-2.0, 2.0]], dtype=np.float64
    )
    inner = np.array(
        [[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]], dtype=np.float64
    )
    nodes = np.vstack([outer, inner])
    # 8 triangles forming the annular strip (each side splits into 2).
    elements = np.array(
        [
            [0, 1, 5], [0, 5, 4],   # bottom
            [1, 2, 6], [1, 6, 5],   # right
            [2, 3, 7], [2, 7, 6],   # top
            [3, 0, 4], [3, 4, 7],   # left
        ],
        dtype=np.int64,
    )
    seg_outer = BoundarySegment(
        node_ids=np.array([0, 1, 2, 3], dtype=np.int64),
        bc_type=BoundaryType.OPEN,
        is_open=True,
    )
    seg_inner = BoundarySegment(
        node_ids=np.array([4, 5, 6, 7], dtype=np.int64),
        bc_type=BoundaryType.MAINLAND,
        is_open=False,
    )
    mesh = Mesh(
        nodes=nodes, elements=elements,
        boundaries=(seg_outer, seg_inner), title="annulus",
    )

    buf = io.StringIO()
    mesh.to_fort14(buf)
    buf.seek(0)
    rt = admesh.read_fort14(buf)

    assert len(rt.boundaries) == 2
    rt_outer = next(s for s in rt.boundaries if s.bc_type == BoundaryType.OPEN)
    rt_inner = next(
        s for s in rt.boundaries if s.bc_type == BoundaryType.MAINLAND
    )
    assert np.array_equal(rt_outer.node_ids, seg_outer.node_ids)
    assert np.array_equal(rt_inner.node_ids, seg_inner.node_ids)
    assert rt_outer.is_open
    assert not rt_inner.is_open
