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


def test_faithful_port_modules_still_importable():
    """Constitution Article II.1 — the 13 stage modules remain accessible.

    Spec 009 R3 (Constitution Amendment, proposed Article VIII) removes the
    stage module names from ``admesh.__all__`` to clarify the public /
    internal split. The numerical-port invariant is preserved by keeping
    every stage module importable at its existing path, not by listing
    them in ``__all__``.
    """
    import importlib

    faithful = (
        "admesh.background_grid",
        "admesh.bathymetry",
        "admesh.boundary",
        "admesh.curvature",
        "admesh.distance",
        "admesh.distmesh",
        "admesh.domains",
        "admesh.dominate_tide",
        "admesh.in_polygon",
        "admesh.inpaint",
        "admesh.medial_axis",
        "admesh.mesh_size",
        "admesh.quality",
        "admesh.routine",
    )
    for modname in faithful:
        mod = importlib.import_module(modname)
        assert mod.__name__ == modname
