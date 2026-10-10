"""Thin client for the token-gated Valence mesh API (spec 031).

Uses only the standard library. The token comes from ``VALENCE_TOKEN`` and
the base URL from ``VALENCE_API_URL``. The token never appears in messages.
"""

from __future__ import annotations

import hashlib
import json
import os
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

# TODO: placeholder until the production URL is fixed. While empty,
# VALENCE_API_URL is required.
_DEFAULT_BASE_URL = ""
_TIMEOUT_S = 10.0
_TOKEN_VAR = "VALENCE_TOKEN"
_URL_VAR = "VALENCE_API_URL"


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
    if not base:
        raise RegistryUnavailableError(
            f"Valence registry API unavailable: no API URL configured. "
            f"Set the {_URL_VAR} environment variable."
        )
    return base.rstrip("/"), token


def _get(path: str) -> bytes:
    base, token = _config()
    req = urllib.request.Request(
        base + path, headers={"Authorization": f"Bearer {token}"}
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
            raise RegistryUnavailableError(
                "Valence registry API unavailable: rate limit reached. "
                "Retry later."
            ) from None
        raise RegistryUnavailableError(
            f"Valence registry API unavailable (HTTP {code})."
        ) from None
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError):
        raise RegistryUnavailableError(
            "Valence registry API unavailable: connection failed or timed out."
        ) from None


def _quote(name: str) -> str:
    return urllib.parse.quote(name, safe="")


def list_names() -> list[str]:
    """Return mesh names from ``GET /meshes``."""
    data = json.loads(_get("/meshes").decode("utf-8"))
    if isinstance(data, dict):
        data = data.get("meshes", data.get("names", []))
    return [str(n["name"] if isinstance(n, dict) else n) for n in data]


def fetch_hash(name: str) -> dict[str, str]:
    """Return ``{"sha256"}`` from ``GET /meshes/{name}/hash``."""
    data = json.loads(_get(f"/meshes/{_quote(name)}/hash").decode("utf-8"))
    return {"sha256": str(data["sha256"])}


def fetch_mesh(name: str) -> tuple[bytes, dict[str, str]]:
    """Return verified fort.14 bytes and their hashes."""
    hashes = fetch_hash(name)
    payload = _get(f"/meshes/{_quote(name)}")
    sha256 = hashlib.sha256(payload).hexdigest()
    if sha256 != hashes["sha256"].lower():
        raise RegistryIntegrityError(
            "Registry payload failed hash check; mesh rejected."
        )
    return payload, hashes
