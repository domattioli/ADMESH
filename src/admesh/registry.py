"""Access to the token-gated Valence mesh registry.

Provides ``load_domain_from_registry(name) -> triangulate(domain)``. Calls go
to the Valence HTTP API through :mod:`admesh._registry_client`. Set
``VALENCE_TOKEN`` (and ``VALENCE_API_URL`` when the default is not usable).
"""

from __future__ import annotations

import io
import warnings

import numpy as np

from admesh import _registry_client as _client
from admesh.api import Domain
from admesh._registry_client import (  # noqa: F401
    RegistryAuthError,
    RegistryError,
    RegistryIntegrityError,
    RegistryNotFoundError,
    RegistryUnavailableError,
)

__all__ = [
    "load_domain_from_registry",
    "list_available_domains",
    "load_domain_with_metadata",
]

_DEFAULT_MESH_ID = "default@v1"


def _load(name: str, mesh_id: str) -> tuple[Domain, dict]:
    from admesh.fort14 import read_fort14

    if mesh_id != _DEFAULT_MESH_ID:
        warnings.warn(
            "mesh_id is ignored; the registry API has no mesh-id concept.",
            DeprecationWarning,
            stacklevel=3,
        )
    payload, hashes = _client.fetch_mesh(name)
    src = read_fort14(io.StringIO(payload.decode("utf-8")))
    meta = {"name": name, "sha256": hashes["sha256"]}
    import dataclasses

    from admesh.loaders import _fort14_rings, _open_ring

    dom = Domain.from_mesh(src)
    rings = _fort14_rings(src)
    if rings:
        # Carry the boundary rings so boundary="fixed" has posts to pin.
        dom = dataclasses.replace(
            dom,
            pts=_open_ring(np.asarray(rings[0], dtype=np.float64)),
            holes=tuple(_open_ring(np.asarray(r, dtype=np.float64)) for r in rings[1:]),
        )
    return dom, meta


def load_domain_from_registry(name: str, mesh_id: str = _DEFAULT_MESH_ID) -> Domain:
    """Fetch a domain from the Valence registry by ``name``.

    Requires ``VALENCE_TOKEN``. ``mesh_id`` is accepted for compatibility and
    ignored (a ``DeprecationWarning`` is issued when it is not the default).

    Raises
    ------
    RegistryAuthError
        Token missing, invalid or expired.
    RegistryNotFoundError
        Unknown name (also a ``ValueError``).
    RegistryUnavailableError
        API unreachable, rate limited or failing.
    RegistryIntegrityError
        Payload failed its hash check.
    """
    return _load(name, mesh_id)[0]


def list_available_domains() -> dict[str, str]:
    """List mesh names in the registry.

    The API returns names only, so every value is an empty string.
    """
    return {n: "" for n in sorted(_client.list_names())}


def load_domain_with_metadata(
    name: str, mesh_id: str = _DEFAULT_MESH_ID
) -> tuple[Domain, dict]:
    """Load a domain plus ``{"name", "sha256"}`` metadata.

    Parameters
    ----------
    name : str
        Mesh name in the registry.
    mesh_id : str, optional
        Ignored; kept for compatibility.

    Returns
    -------
    domain : Domain
        Domain ready for :func:`admesh.triangulate`.
    metadata : dict
        ``name`` and ``sha256``.

    Raises
    ------
    RegistryError
        On any registry failure (see :func:`load_domain_from_registry`).
    """
    return _load(name, mesh_id)
