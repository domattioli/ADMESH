"""Gmsh .msh (ASCII v2.2) reader/writer tests (issue #5)."""

from __future__ import annotations

import io

import numpy as np
import pytest

import admesh
from admesh import BoundarySegment, BoundaryType, Mesh
from admesh.gmsh import GmshParseError, read_msh, write_msh


def _square_mesh(*, bathymetry=None, boundaries=()) -> Mesh:
    """Unit square split into two triangles (4 nodes, 0-based)."""
    nodes = np.array(
        [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], dtype=np.float64
    )
    elements = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
    return Mesh(
        nodes=nodes,
        elements=elements,
        boundaries=tuple(boundaries),
        bathymetry=bathymetry,
    )


def _seg(node_ids, bc_type, is_open) -> BoundarySegment:
    return BoundarySegment(
        node_ids=np.array(node_ids, dtype=np.int64),
        bc_type=bc_type,
        is_open=is_open,
    )


def _assert_boundaries_equal(a_segs, b_segs) -> None:
    assert len(a_segs) == len(b_segs)
    for a, b in zip(a_segs, b_segs):
        assert int(a.bc_type) == int(b.bc_type)
        assert a.is_open == b.is_open
        assert np.array_equal(a.node_ids, b.node_ids)


def test_roundtrip_nodes_and_triangles() -> None:
    mesh = _square_mesh()
    buf = io.StringIO()
    write_msh(mesh, buf)
    buf.seek(0)
    rt = read_msh(buf)

    assert np.allclose(mesh.nodes, rt.nodes)
    assert np.array_equal(mesh.elements, rt.elements)
    assert rt.boundaries == ()
    assert rt.bathymetry is None


def test_roundtrip_with_boundaries() -> None:
    boundaries = [
        _seg([0, 1], BoundaryType.OPEN, True),
        _seg([1, 2, 3, 0], BoundaryType.MAINLAND, False),
    ]
    mesh = _square_mesh(boundaries=boundaries)

    buf = io.StringIO()
    write_msh(mesh, buf)
    buf.seek(0)
    rt = read_msh(buf)

    assert np.array_equal(mesh.elements, rt.elements)
    _assert_boundaries_equal(mesh.boundaries, rt.boundaries)


def test_physical_group_label_mapping() -> None:
    boundaries = [
        _seg([0, 1], BoundaryType.OPEN, True),
        _seg([1, 2], BoundaryType.MAINLAND, False),
        _seg([2, 3], BoundaryType.ISLAND, False),
        _seg([3, 0], BoundaryType.MAINLAND_FLUX, False),
    ]
    mesh = _square_mesh(boundaries=boundaries)
    buf = io.StringIO()
    write_msh(mesh, buf)

    # Each label's canonical name appears in the $PhysicalNames block.
    text = buf.getvalue()
    for label in ("open_0", "mainland_0", "island_0", "mainland_flux_0"):
        assert f'"{label}"' in text

    buf.seek(0)
    rt = read_msh(buf)
    _assert_boundaries_equal(mesh.boundaries, rt.boundaries)
    # Mapped codes come back as BoundaryType members, not raw ints.
    assert all(isinstance(s.bc_type, BoundaryType) for s in rt.boundaries)


def test_unmapped_bc_code_roundtrips_as_int() -> None:
    mesh = _square_mesh(boundaries=[_seg([0, 1, 2], 99, False)])
    buf = io.StringIO()
    write_msh(mesh, buf)
    assert '"bc99_0"' in buf.getvalue()

    buf.seek(0)
    rt = read_msh(buf)
    assert len(rt.boundaries) == 1
    assert int(rt.boundaries[0].bc_type) == 99
    assert np.array_equal(rt.boundaries[0].node_ids, np.array([0, 1, 2]))


def test_repeated_label_segments_stay_distinct() -> None:
    boundaries = [
        _seg([0, 1], BoundaryType.MAINLAND, False),
        _seg([2, 3], BoundaryType.MAINLAND, False),
    ]
    mesh = _square_mesh(boundaries=boundaries)
    buf = io.StringIO()
    write_msh(mesh, buf)
    text = buf.getvalue()
    assert '"mainland_0"' in text and '"mainland_1"' in text

    buf.seek(0)
    rt = read_msh(buf)
    _assert_boundaries_equal(mesh.boundaries, rt.boundaries)


def test_bathymetry_roundtrips_via_node_z() -> None:
    bathy = np.array([1.5, -2.0, 0.25, 3.0], dtype=np.float64)
    mesh = _square_mesh(bathymetry=bathy)
    buf = io.StringIO()
    write_msh(mesh, buf)
    buf.seek(0)
    rt = read_msh(buf)
    assert rt.bathymetry is not None
    assert np.allclose(rt.bathymetry, bathy)


def test_to_msh_method_and_path_roundtrip(tmp_path) -> None:
    mesh = _square_mesh(boundaries=[_seg([0, 1, 2, 3, 0], BoundaryType.MAINLAND, False)])
    out = tmp_path / "mesh.msh"
    mesh.to_msh(out)
    rt = read_msh(out)
    assert np.array_equal(mesh.elements, rt.elements)
    _assert_boundaries_equal(mesh.boundaries, rt.boundaries)


def test_cross_format_gmsh_fort14_gmsh_preserves_labels() -> None:
    """Gmsh -> admesh -> fort.14 -> admesh -> Gmsh: BC labels survive."""
    boundaries = [
        _seg([0, 1], BoundaryType.OPEN, True),
        _seg([1, 2, 3, 0], BoundaryType.MAINLAND, False),
    ]
    mesh = _square_mesh(boundaries=boundaries)

    g1 = io.StringIO()
    write_msh(mesh, g1)
    g1.seek(0)
    m1 = read_msh(g1)

    f = io.StringIO()
    m1.to_fort14(f)
    f.seek(0)
    m2 = admesh.read_fort14(f)

    g2 = io.StringIO()
    write_msh(m2, g2)
    g2.seek(0)
    m3 = read_msh(g2)

    _assert_boundaries_equal(mesh.boundaries, m3.boundaries)


def test_public_api_exports() -> None:
    assert admesh.read_msh is read_msh
    assert admesh.write_msh is write_msh
    assert admesh.GmshParseError is GmshParseError


def test_parse_error_on_binary_header() -> None:
    binary = "$MeshFormat\n2.2 1 8\n$EndMeshFormat\n"
    with pytest.raises(GmshParseError):
        read_msh(io.StringIO(binary))


def test_parse_error_on_missing_nodes() -> None:
    only_fmt = "$MeshFormat\n2.2 0 8\n$EndMeshFormat\n"
    with pytest.raises(GmshParseError):
        read_msh(io.StringIO(only_fmt))


def test_reads_file_without_physical_names() -> None:
    """A minimal foreign-style file (no $PhysicalNames) still parses."""
    text = (
        "$MeshFormat\n2.2 0 8\n$EndMeshFormat\n"
        "$Nodes\n3\n1 0 0 0\n2 1 0 0\n3 0 1 0\n$EndNodes\n"
        "$Elements\n1\n1 2 2 1 1 1 2 3\n$EndElements\n"
    )
    mesh = read_msh(io.StringIO(text))
    assert mesh.n_nodes == 3
    assert np.array_equal(mesh.elements, np.array([[0, 1, 2]]))
    assert mesh.boundaries == ()
