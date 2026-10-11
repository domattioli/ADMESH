"""Thin client for the token-gated Valence mesh API (spec 031).

Uses only the standard library. The token comes from ``VALENCE_TOKEN`` and
the base URL defaults to the public Valence API and can be overridden with
``VALENCE_API_URL``. The token never appears in messages.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request

__all__ = [
    "RegistryError",
    "RegistryAuthError",
    "RegistryNotFoundError",
    "RegistryUnavailableError",
    "RegistryIntegrityError",
    "list_names",
    "fetch_hash",
    "fetch_mesh",
]

# Default public Valence API. VALENCE_API_URL is an optional override.
_DEFAULT_BASE_URL = "https://valence-api.iqh766c2.workers.dev"
_TIMEOUT_S = 30.0
_TOKEN_VAR = "VALENCE_TOKEN"
_URL_VAR = "VALENCE_API_URL"
_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_SHA_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class RegistryError(RuntimeError):
    """Base class for registry failures."""


class RegistryAuthError(RegistryError):
    """Token missing, invalid or expired."""


class RegistryNotFoundError(RegistryError, ValueError):
    """The mesh name is not in the registry."""


class RegistryUnavailableError(RegistryError):
    """Registry API unreachable, rate limited or failing."""


class RegistryIntegrityError(RegistryError):
    """The payload failed its hash check."""


def _config() -> tuple[str, str]:
    token = os.environ.get(_TOKEN_VAR, "").strip()
    if not token:
        raise RegistryAuthError(
            f"Valence registry needs a token. Set the {_TOKEN_VAR} "
            "environment variable."
        )
    base = os.environ.get(_URL_VAR, "").strip() or _DEFAULT_BASE_URL
    return base.rstrip("/"), token


def _get(path: str) -> bytes:
    base, token = _config()
    req = urllib.request.Request(
        base + path, headers={"Authorization": f"Bearer {token}", "User-Agent": "admesh-registry/1"}
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        code = e.code
        if code == 401:
            raise RegistryAuthError(
                f"Valence registry token is invalid or expired. Check {_TOKEN_VAR}."
            ) from None
        if code == 404:
            raise RegistryNotFoundError(
                "Mesh not found in the Valence registry."
            ) from None
        if code == 429:
            retry = None
            try:
                retry = e.headers.get("Retry-After")
            except Exception:
                pass
            after = f" Retry after {retry} s." if retry else " Retry later."
            raise RegistryUnavailableError(
                "Valence registry API unavailable: rate limit reached." + after
            ) from None
        if code == 405:
            raise RegistryUnavailableError(
                "Valence registry API unavailable: method not allowed (HTTP 405)."
            ) from None
        raise RegistryUnavailableError(
            f"Valence registry API unavailable (HTTP {code})."
        ) from None
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError):
        raise RegistryUnavailableError(
            "Valence registry API unavailable: connection failed or timed out."
        ) from None


def _check_name(name: str) -> str:
    if not isinstance(name, str) or name in (".", "..") or not _NAME_RE.match(name):
        raise RegistryNotFoundError("Mesh not found in the Valence registry.")
    return urllib.parse.quote(name, safe="")


def _json(raw: bytes, what: str):
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise RegistryIntegrityError(
            f"Registry {what} response is malformed."
        ) from None


def list_names() -> list[str]:
    """Return mesh names from ``GET /meshes`` (a JSON array of strings)."""
    data = _json(_get("/meshes"), "list")
    if not isinstance(data, list) or not all(isinstance(n, str) for n in data):
        raise RegistryIntegrityError("Registry list response is malformed.")
    return data


def fetch_hash(name: str) -> dict[str, str]:
    """Return ``{"sha256"}`` from ``GET /meshes/{name}/hash``."""
    q = _check_name(name)
    data = _json(_get(f"/meshes/{q}/hash"), "hash")
    sha = data.get("sha256") if isinstance(data, dict) else None
    if not isinstance(data, dict) or set(data) != {"sha256"} or not isinstance(sha, str) or not _SHA_RE.match(sha):
        raise RegistryIntegrityError("Registry hash response is malformed.")
    return {"sha256": sha.lower()}


def fetch_mesh(name: str) -> tuple[bytes, dict[str, str]]:
    """Return verified fort.14 bytes and their hashes."""
    q = _check_name(name)
    hashes = fetch_hash(name)
    payload = _get(f"/meshes/{q}")
    sha256 = hashlib.sha256(payload).hexdigest()
    if sha256 != hashes["sha256"]:
        raise RegistryIntegrityError(
            "Registry payload failed hash check; mesh rejected."
        )
    return payload, hashes
