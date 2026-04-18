"""Package-level smoke test — verifies the import graph is intact."""

import importlib

import admesh


def test_version() -> None:
    assert admesh.__version__


def test_all_submodules_importable() -> None:
    for name in admesh.__all__:
        importlib.import_module(f"admesh.{name}")
