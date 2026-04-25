"""fort.14 index and sign-convention tests (T017).

The reader/writer apply 1-based↔0-based index conversion and
elevation↔depth sign flip strictly at the I/O boundary.
"""

from __future__ import annotations

import io

import numpy as np

import admesh
from admesh import BoundarySegment, BoundaryType, Mesh


def _square_mesh_with_bath() -> Mesh:
    nodes = np.array(
        [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], dtype=np.float64
    )
    elements = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
    bath = np.array([10.0, 20.0, 30.0, 40.0], dtype=np.float64)  # elevation
    seg_open = BoundarySegment(
        node_ids=np.array([0, 1], dtype=np.int64),
        bc_type=BoundaryType.OPEN,
        is_open=True,
    )
    seg_main = BoundarySegment(
        node_ids=np.array([1, 2, 3, 0], dtype=np.int64),
        bc_type=BoundaryType.MAINLAND,
        is_open=False,
    )
    return Mesh(
        nodes=nodes, elements=elements, boundaries=(seg_open, seg_main),
        bathymetry=bath, title="conventions",
    )


def test_writer_emits_one_based_node_ids():
    buf = io.StringIO()
    _square_mesh_with_bath().to_fort14(buf)
    text = buf.getvalue()
    lines = text.splitlines()
    # Element block starts after title + counts + 4 nodes = 6 lines.
    elem_line = lines[6].split()
    # First triangle's vertices were 0,1,2 internally → 1,2,3 on disk.
    assert elem_line[0] == "1"  # element id
    assert elem_line[1] == "3"  # nodes-per-element
    assert {elem_line[2], elem_line[3], elem_line[4]} == {"1", "2", "3"}


def test_writer_flips_elevation_to_depth():
    buf = io.StringIO()
    _square_mesh_with_bath().to_fort14(buf)
    lines = buf.getvalue().splitlines()
    # Node line 0: "1 x y depth" — elevation 10 → depth -10.
    node0 = lines[2].split()
    assert float(node0[3]) == -10.0


def test_reader_inverts_both_conventions():
    buf = io.StringIO()
    mesh = _square_mesh_with_bath()
    mesh.to_fort14(buf)
    buf.seek(0)
    rt = admesh.read_fort14(buf)
    # Elements are 0-based again.
    assert rt.elements.min() == 0
    assert rt.elements.max() == mesh.n_nodes - 1
    # Bathymetry sign flipped back to elevation.
    assert np.allclose(rt.bathymetry, mesh.bathymetry)


def test_one_based_open_segment_node_ids_round_trip():
    buf = io.StringIO()
    mesh = _square_mesh_with_bath()
    mesh.to_fort14(buf)
    buf.seek(0)
    rt = admesh.read_fort14(buf)
    open_seg = rt.boundaries[0]
    # Was [0, 1] internally → emitted as [1, 2] → read back as [0, 1].
    assert np.array_equal(open_seg.node_ids, np.array([0, 1]))
    assert open_seg.is_open
    assert open_seg.bc_type == BoundaryType.OPEN
