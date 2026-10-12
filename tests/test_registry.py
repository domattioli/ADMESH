"""Tests for the token-gated Valence registry adapter (client mocked)."""

import io

import pytest

import admesh
from admesh import _registry_client as rc
from admesh.api import Domain
from admesh.registry import (
    list_available_domains,
    load_domain_from_registry,
    load_domain_with_metadata,
)

HASHES = {"sha256": "b" * 64}


@pytest.fixture
def fort14_bytes():
    from admesh.fort14 import write_fort14

    from admesh.domains import ALL

    d = ALL["unit_square"]
    domain = Domain(sdf=d.fd, bbox=d.bbox)
    mesh = admesh.triangulate(domain, h_max=0.4, max_iter=50, seed=0)
    buf = io.StringIO()
    write_fort14(mesh, buf)
    return buf.getvalue().encode("utf-8")


@pytest.fixture
def fake_client(monkeypatch, fort14_bytes):
    monkeypatch.setattr(rc, "fetch_mesh", lambda name: (fort14_bytes, dict(HASHES)))
    monkeypatch.setattr(rc, "list_names", lambda: ["Zed", "Alpha"])


def test_load_domain_from_registry(fake_client):
    assert isinstance(load_domain_from_registry("X"), Domain)


def test_metadata_keys(fake_client):
    domain, meta = load_domain_with_metadata("X")
    assert isinstance(domain, Domain)
    assert meta == {"name": "X", **HASHES}


def test_mesh_id_deprecation(fake_client):
    with pytest.warns(DeprecationWarning):
        load_domain_from_registry("X", mesh_id="other@v2")


def test_list_available_domains(fake_client):
    assert list(list_available_domains().items()) == [("Alpha", ""), ("Zed", "")]


def test_no_token_raises(monkeypatch):
    monkeypatch.delenv("VALENCE_TOKEN", raising=False)
    for fn in (load_domain_from_registry, load_domain_with_metadata):
        with pytest.raises(rc.RegistryAuthError, match="needs a token"):
            fn("test-mesh")
    with pytest.raises(rc.RegistryAuthError, match="needs a token"):
        list_available_domains()


def test_triangulate_slug_without_token_names_slug(monkeypatch):
    monkeypatch.delenv("VALENCE_TOKEN", raising=False)
    with pytest.raises(rc.RegistryAuthError, match="some-slug"):
        admesh.triangulate("some-slug", h_max=0.5)
