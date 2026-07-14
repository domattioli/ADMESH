"""Smoke tests for package-level import graph and public re-export surface.

Verifies the import graph is intact and the v1 public API surface is
importable from the top-level ``admesh`` namespace (T009).
"""

from __future__ import annotations

import importlib
import types

import admesh


def test_version() -> None:
    assert admesh.__version__


def test_all_submodules_importable() -> None:
    """Every name in ``admesh.__all__`` must resolve.

    Submodule names must import as ``admesh.<name>``; the v1 additive
    layer also re-exports public classes and functions (``Mesh``,
    ``Domain``, ``triangulate``, …) at the top level, and those are
    skipped here since they are not submodules.
    """
    for name in admesh.__all__:
        attr = getattr(admesh, name, None)
        # Only treat as a submodule if it isn't already a non-module
        # attribute on the package. Class / function re-exports skip.
        if attr is not None and not isinstance(attr, types.ModuleType):
            continue
        importlib.import_module(f"admesh.{name}")


def test_top_level_imports():
    from admesh import BoundarySegment, BoundaryType, Domain, Mesh

    assert BoundarySegment.__module__ == "admesh.api"
    assert Domain.__module__ == "admesh.api"
    assert Mesh.__module__ == "admesh.api"
    assert BoundaryType.__module__ == "admesh.boundary_types"


def test_all_includes_v1_types():
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
