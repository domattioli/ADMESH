"""Registry client tests over a mocked urllib (no network, no token)."""

import hashlib
import io
import json
import urllib.error

import pytest

from admesh import _registry_client as rc

TOKEN = "s3cret-token-value"


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(code, headers=None):
    return urllib.error.HTTPError("http://x", code, "err", headers or {}, io.BytesIO(b""))


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("VALENCE_TOKEN", TOKEN)
    monkeypatch.setenv("VALENCE_API_URL", "http://api.test")


def _fake(monkeypatch, handler):
    calls = []

    def urlopen(req, timeout=None):
        calls.append((req, timeout))
        return handler(req)

    monkeypatch.setattr(rc.urllib.request, "urlopen", urlopen)
    return calls


def test_missing_token_no_network(monkeypatch):
    monkeypatch.delenv("VALENCE_TOKEN", raising=False)
    monkeypatch.setenv("VALENCE_API_URL", "http://api.test")
    calls = _fake(monkeypatch, lambda r: _Resp(b"[]"))
    with pytest.raises(rc.RegistryAuthError, match="Valence registry needs a token"):
        rc.list_names()
    assert calls == []


def test_default_url_used_when_unset(monkeypatch):
    monkeypatch.setenv("VALENCE_TOKEN", TOKEN)
    monkeypatch.delenv("VALENCE_API_URL", raising=False)
    calls = _fake(monkeypatch, lambda r: _Resp(b"[]"))
    rc.list_names()
    assert calls[0][0].full_url.startswith("https://valence-api.iqh766c2.workers.dev/")


def test_url_override_wins(env, monkeypatch):
    calls = _fake(monkeypatch, lambda r: _Resp(b"[]"))
    rc.list_names()
    assert calls[0][0].full_url.startswith("http://api.test/")


def test_user_agent_not_urllib_default(env, monkeypatch):
    calls = _fake(monkeypatch, lambda r: _Resp(b"[]"))
    rc.list_names()
    ua = calls[0][0].get_header("User-agent")
    assert ua == "admesh-registry/1"
    assert not ua.startswith("Python-urllib")


def test_401(env, monkeypatch):
    def h(r):
        raise _http_error(401)

    _fake(monkeypatch, h)
    with pytest.raises(rc.RegistryAuthError, match="invalid or expired") as ei:
        rc.list_names()
    assert TOKEN not in str(ei.value)


def test_404_is_value_error(env, monkeypatch):
    def h(r):
        raise _http_error(404)

    _fake(monkeypatch, h)
    with pytest.raises(ValueError, match="not found"):
        rc.fetch_hash("nope")


@pytest.mark.parametrize("code", [429, 500, 503])
def test_unavailable_codes(env, monkeypatch, code):
    def h(r):
        raise _http_error(code)

    _fake(monkeypatch, h)
    with pytest.raises(rc.RegistryUnavailableError, match="Valence registry API unavailable"):
        rc.list_names()


@pytest.mark.parametrize("exc", [urllib.error.URLError("down"), TimeoutError()])
def test_network_failure(env, monkeypatch, exc):
    def h(r):
        raise exc

    _fake(monkeypatch, h)
    with pytest.raises(rc.RegistryUnavailableError, match="Valence registry API unavailable"):
        rc.list_names()


def test_405_is_hard_error(env, monkeypatch):
    # Contract: 401/404/405 are hard errors; 405 must not look transient.
    def h(r):
        raise _http_error(405)

    _fake(monkeypatch, h)
    with pytest.raises(rc.RegistryError) as ei:
        rc.list_names()
    assert type(ei.value) is rc.RegistryError


def _mesh_handler(payload, hashes):
    def h(req):
        if req.full_url.endswith("/hash"):
            return _Resp(json.dumps(hashes).encode())
        return _Resp(payload)

    return h


def _hashes(p):
    return {"sha256": hashlib.sha256(p).hexdigest()}


def test_fetch_mesh_ok_and_headers(env, monkeypatch):
    p = b"mesh bytes"
    calls = _fake(monkeypatch, _mesh_handler(p, _hashes(p)))
    data, h = rc.fetch_mesh("A")
    assert data == p and h == _hashes(p)
    assert all(t == rc._TIMEOUT_S for _, t in calls)
    assert calls[0][0].get_header("Authorization") == f"Bearer {TOKEN}"


def test_hash_mismatch(env, monkeypatch):
    p = b"mesh bytes"
    h = _hashes(p)
    h["sha256"] = "0" * 64
    _fake(monkeypatch, _mesh_handler(p, h))
    with pytest.raises(rc.RegistryIntegrityError, match="hash check") as ei:
        rc.fetch_mesh("A")
    assert TOKEN not in str(ei.value)


def test_list_names(env, monkeypatch):
    _fake(monkeypatch, lambda r: _Resp(b'["B", "A"]'))
    assert rc.list_names() == ["B", "A"]


def test_429_includes_retry_after(env, monkeypatch):
    def h(r):
        raise _http_error(429, {"Retry-After": "17"})

    _fake(monkeypatch, h)
    with pytest.raises(rc.RegistryUnavailableError, match="Retry after 17 s"):
        rc.list_names()


@pytest.mark.parametrize("body", [b'{"meshes": ["A"]}', b'{"names": ["A"]}',
                                  b'[{"name": "A"}]', b'[1]', b'not json'])
def test_list_rejects_non_array_of_strings(env, monkeypatch, body):
    _fake(monkeypatch, lambda r: _Resp(body))
    with pytest.raises(rc.RegistryIntegrityError):
        rc.list_names()


@pytest.mark.parametrize("body", [b'["x"]', b'{}', b'{"sha256": "abc"}',
                                  b'{"sha256": 5}', b'nope',
                                  json.dumps({"sha256": "a" * 64 + "\n"}).encode(),
                                  json.dumps({"sha256": "A" * 64}).encode()])
def test_hash_rejects_malformed(env, monkeypatch, body):
    _fake(monkeypatch, lambda r: _Resp(body))
    with pytest.raises(rc.RegistryIntegrityError):
        rc.fetch_hash("A")


@pytest.mark.parametrize("name", ["", ".", "..", "a/b", "a b", "a%2Fb", "a?x=1"])
def test_bad_name_rejected_before_request(env, monkeypatch, name):
    calls = _fake(monkeypatch, lambda r: _Resp(b"{}"))
    with pytest.raises(rc.RegistryNotFoundError):
        rc.fetch_hash(name)
    with pytest.raises(ValueError):
        rc.fetch_mesh(name)
    assert calls == []


def test_triangulate_source_bare_14_name_goes_to_registry(monkeypatch, tmp_path):
    """A bare ``Name.14`` that is not a local file is fetched from the registry."""
    import admesh.api as api
    import admesh.registry as reg

    monkeypatch.chdir(tmp_path)
    seen = []
    monkeypatch.setattr(reg, "load_domain_from_registry",
                        lambda n: seen.append(n) or "DOM")
    assert api._load_domain_from_source("Block_O.14") == "DOM"
    assert seen == ["Block_O.14"]


def test_registry_filename_requested_verbatim(env, monkeypatch):
    calls = _fake(monkeypatch, lambda r: _Resp(b'{"sha256": "' + b"0" * 64 + b'"}'))
    rc.fetch_hash("annulus_200pts.fort.14")
    assert calls[0][0].full_url.endswith("/meshes/annulus_200pts.fort.14/hash")
