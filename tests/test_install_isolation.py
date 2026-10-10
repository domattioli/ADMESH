"""admesh2D must not depend on or import valence_domains (spec 031)."""

import importlib.metadata
import pathlib

import admesh


def test_no_valence_domains_import_in_sources():
    root = pathlib.Path(admesh.__file__).parent
    for py in root.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert "import valence_domains" not in text, py
        assert "from valence_domains" not in text, py


def test_metadata_has_no_valence_domains():
    try:
        reqs = importlib.metadata.requires("admesh2D") or []
    except importlib.metadata.PackageNotFoundError:
        return
    assert not any("valence-domains" in r.lower().replace("_", "-") for r in reqs)
