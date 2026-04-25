"""Package-level smoke test — verifies the import graph is intact."""

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
