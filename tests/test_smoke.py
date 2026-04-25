"""Package-level smoke test — verifies the import graph is intact."""

import importlib
import inspect

import admesh


def test_version() -> None:
    assert admesh.__version__


def test_all_submodules_importable() -> None:
    """Every name in ``admesh.__all__`` must resolve.

    Submodule names must import as ``admesh.<name>``; the v1 additive
    layer also re-exports public classes (``Mesh``, ``Domain``, …) at
    the top level, and those are skipped here since they are not
    submodules.
    """
    for name in admesh.__all__:
        attr = getattr(admesh, name, None)
        if attr is not None and inspect.isclass(attr):
            continue
        importlib.import_module(f"admesh.{name}")
