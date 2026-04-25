"""Smoke test for the v1 public re-export surface (T009).

Asserts that the names promised in
``specs/001-pythonize-and-fort14-integration/contracts/python-api.md`` are
importable from the top-level ``admesh`` namespace at this stage of the
port.
"""

from __future__ import annotations


def test_top_level_imports():
    from admesh import BoundarySegment, BoundaryType, Domain, Mesh

    assert BoundarySegment.__module__ == "admesh.api"
    assert Domain.__module__ == "admesh.api"
    assert Mesh.__module__ == "admesh.api"
    assert BoundaryType.__module__ == "admesh.boundary_types"


def test_all_includes_v1_types():
    import admesh

    expected = {"BoundarySegment", "BoundaryType", "Domain", "Mesh"}
    assert expected.issubset(set(admesh.__all__))


def test_faithful_port_modules_still_exposed():
    """Constitution Principle I — the 13 stage modules stay accessible."""
    import admesh

    faithful = {
        "background_grid",
        "bathymetry",
        "boundary",
        "curvature",
        "distance",
        "distmesh",
        "domains",
        "dominate_tide",
        "in_polygon",
        "inpaint",
        "medial_axis",
        "mesh_size",
        "quality",
        "routine",
    }
    assert faithful.issubset(set(admesh.__all__))
