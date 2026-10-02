"""Tests for the valence_domains compatibility layer.

Three stand-in modules model the three lookup routes (group API, manifest
object, Domain-only API). Each is injected as ``sys.modules['valence_domains']``
and the registry adapter must report the same names and metadata for the same
logical content. One subprocess test runs against a real Valence source
checkout when ``ADMESH_VALENCE_SRC`` points at one.
"""

from __future__ import annotations

import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

from admesh import _valence_compat
from admesh.registry import (
    list_available_domains,
    load_domain_from_registry,
    load_domain_with_metadata,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

_FORT14 = """stand-in mesh
1 3
1 0.0 0.0 0.0
2 1.0 0.0 0.0
3 0.0 1.0 0.0
1 3 1 2 3
0
0
0
0
"""


class _Mesh:
    def __init__(self, path: Path, **extra):
        self.id = "default@v1"
        self.filename = path.name
        self.path = path
        self.license = "MIT"
        for key, value in extra.items():
            setattr(self, key, value)

    def exists(self) -> bool:
        return True

    def load(self) -> None:  # pragma: no cover - never called
        raise AssertionError("load() must not run for an existing mesh")


class _Group:
    def __init__(self, name, full_name, meshes, alias_of=None, **extra):
        self.name = name
        self.full_name = full_name
        self.meshes = meshes
        self.alias_of = alias_of
        for key, value in extra.items():
            setattr(self, key, value)

    def get_mesh(self, mesh_id):
        for m in self.meshes:
            if m.id == mesh_id:
                return m
        raise KeyError(mesh_id)


def _content(tmp_path: Path, *, new_schema: bool):
    """Build the logical content: primary Domain, alias, Collection."""
    mesh_file = tmp_path / "m.14"
    mesh_file.write_text(_FORT14)
    if new_schema:
        mesh_kw = {"format": "ADCIRC"}
        dom_kw = {"continent": "Europe"}
    else:
        mesh_kw = {"type": "ADCIRC"}
        dom_kw = {"region": "Europe"}
    domain = _Group(
        "Dom", "Dom Full", [_Mesh(mesh_file, **mesh_kw)], category="real-world", **dom_kw
    )
    alias = _Group("DomAlias", "Dom Alias", [], alias_of="Dom")
    coll = _Group("Coll", "Coll Full", [_Mesh(mesh_file, **mesh_kw)])
    return domain, alias, coll


def _fake_group_api(tmp_path):
    domain, alias, coll = _content(tmp_path, new_schema=True)
    by_name = {g.name.lower(): g for g in (domain, alias, coll)}
    mod = types.ModuleType("valence_domains")

    def get_group(name, manifest=None):
        g = by_name.get(name.lower())
        if g is None:
            raise KeyError(name)
        return domain if g.alias_of else g

    mod.get_group = get_group
    mod.list_domains = lambda manifest=None: [domain]
    mod.list_collections = lambda manifest=None: [coll]
    mod.get_collection = lambda name, manifest=None: coll
    return mod


def _fake_manifest_api(tmp_path):
    domain, alias, coll = _content(tmp_path, new_schema=True)
    by_name = {g.name.lower(): g for g in (domain, alias, coll)}

    class Manifest:
        collections = [coll]
        primary_domains = [domain]

        def get_group(self, name):
            return by_name.get(name.lower())

        def resolve_alias(self, g):
            return by_name[g.alias_of.lower()] if g.alias_of else g

    mod = types.ModuleType("valence_domains")
    mod.load_manifest = lambda path=None: Manifest()
    return mod


def _fake_domain_api(tmp_path):
    domain, _alias, _coll = _content(tmp_path, new_schema=False)
    mod = types.ModuleType("valence_domains")

    def get_domain(name):
        if name.lower() == "dom":
            return domain
        raise KeyError(name)

    mod.get_domain = get_domain
    mod.list_domains = lambda: [domain]
    return mod


ROUTES = {
    "group_api": _fake_group_api,
    "manifest_api": _fake_manifest_api,
    "domain_api": _fake_domain_api,
}


@pytest.fixture(params=sorted(ROUTES))
def route(request, tmp_path, monkeypatch):
    mod = ROUTES[request.param](tmp_path)
    monkeypatch.setitem(sys.modules, "valence_domains", mod)
    return request.param


def test_list_available_domains_names(route):
    names = list(list_available_domains())
    if route == "domain_api":
        assert names == ["Dom"]
    else:
        assert names == ["Coll", "Dom"]
        assert "DomAlias" not in names


def test_list_available_domains_descriptions(route):
    listed = list_available_domains()
    assert listed["Dom"] == "Dom Full"


def test_metadata_identical_across_routes(route):
    _domain, meta = load_domain_with_metadata("Dom")
    assert meta["name"] == "Dom"
    assert meta["full_name"] == "Dom Full"
    assert meta["category"] == "real-world"
    assert meta["continent"] == "Europe"
    assert meta["region"] == "Europe"
    assert meta["format"] == "ADCIRC"
    assert meta["type"] == "ADCIRC"
    assert meta["license"] == "MIT"
    assert meta["id"] == "default@v1"


def test_alias_resolves_to_primary(route):
    if route == "domain_api":
        pytest.skip("route c has no aliases")
    assert _valence_compat.get_domain_or_group("DomAlias").name == "Dom"
    _domain, meta = load_domain_with_metadata("DomAlias")
    assert meta["name"] == "Dom"


def test_collection_loads(route):
    if route == "domain_api":
        pytest.skip("route c has no collections")
    domain = load_domain_from_registry("Coll")
    assert callable(domain.sdf)
    _domain, meta = load_domain_with_metadata("Coll")
    assert meta["name"] == "Coll"


def test_unknown_name_raises_value_error(route):
    with pytest.raises(ValueError, match="not found"):
        load_domain_from_registry("Nope")


def test_entry_metadata_twins():
    class New:
        continent = "Asia"
        format = "ADCIRC"

    class Old:
        region = "Asia"
        type = "ADCIRC"

    for obj in (New(), Old()):
        meta = _valence_compat.entry_metadata(obj, ("continent", "region", "format", "type"))
        assert meta == {
            "continent": "Asia",
            "region": "Asia",
            "format": "ADCIRC",
            "type": "ADCIRC",
        }


def test_entry_metadata_skips_missing():
    assert _valence_compat.entry_metadata(object()) == {}


def test_route_precedence_prefers_group_api(tmp_path, monkeypatch):
    """A module offering every route is served by the group API."""
    mod = _fake_group_api(tmp_path)
    calls = []
    mod.load_manifest = lambda path=None: calls.append(path)
    mod.get_domain = lambda name: calls.append(name)
    monkeypatch.setitem(sys.modules, "valence_domains", mod)
    assert _valence_compat.get_domain_or_group("Dom").name == "Dom"
    assert calls == []


def test_manifest_object_without_group_api_falls_to_domain_api(tmp_path, monkeypatch):
    """A load_manifest result lacking get_group does not select route b."""
    mod = _fake_domain_api(tmp_path)

    class OldManifest:
        domains = []

        def get_domain(self, name):
            return None

    mod.load_manifest = lambda path=None: OldManifest()
    monkeypatch.setitem(sys.modules, "valence_domains", mod)
    assert _valence_compat.get_domain_or_group("Dom").name == "Dom"
    assert [e.name for e in _valence_compat.list_entries()] == ["Dom"]


_SUBPROCESS_SCRIPT = """
import sys
from admesh import _valence_compat as c
m = sys.argv[1]
d = c.get_domain_or_group("FixtureDomain", manifest=m)
a = c.get_domain_or_group("FixtureAlias", manifest=m)
k = c.get_domain_or_group("FixtureCollection", manifest=m)
assert d.name == "FixtureDomain", d
assert a.name == "FixtureDomain", a
assert k.name == "FixtureCollection", k
names = sorted(e.name for e in c.list_entries(manifest=m))
assert names == ["FixtureCollection", "FixtureDomain"], names
meta = c.entry_metadata(d.meshes[0], c.MESH_FIELDS)
assert meta["format"] == meta["type"] == "ADCIRC", meta
print("OK")
"""


def test_valence_source_checkout_fixture():
    """Resolve a Domain, an alias and a Collection from a real Valence checkout."""
    src = os.environ.get("ADMESH_VALENCE_SRC")
    if not src:
        pytest.skip("ADMESH_VALENCE_SRC not set")
    root = Path(src)
    fixture = root / "tests" / "fixtures" / "manifest_v04_minimal.toml"
    if not (root / "packages").is_dir() or not fixture.is_file():
        pytest.skip("ADMESH_VALENCE_SRC has no packages/ or manifest_v04_minimal.toml")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(root / "packages"), str(REPO_ROOT / "src")])
    result = subprocess.run(
        [sys.executable, "-c", _SUBPROCESS_SCRIPT, str(fixture)],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout
