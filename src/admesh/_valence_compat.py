"""Compatibility layer over the ``valence_domains`` lookup API.

The registry adapter in :mod:`admesh.registry` talks to ``valence_domains``
only through this module. Three lookup routes exist, tried in this order.
Each route is chosen by feature detection (``getattr`` / ``hasattr``) on the
installed package, never by comparing version numbers.

Route a: top-level group API
    ``valence_domains.get_group(name, manifest=None)`` resolves a Domain,
    a Domain alias (to its primary Domain) or a Collection, and raises
    ``KeyError`` for an unknown name. ``list_domains(manifest=None)`` lists
    primary Domains and ``list_collections(manifest=None)`` lists Collections.

Route b: manifest object
    ``valence_domains.load_manifest(path=None)`` returns a manifest. When that
    manifest has ``get_group``, ``collections`` and ``primary_domains``,
    lookups run on it and ``resolve_alias`` maps an alias to its primary
    Domain.

Route c: Domain-only API
    ``valence_domains.get_domain(name)`` and ``valence_domains.list_domains()``.
    There are no Collections on this route, and the ``manifest`` argument is
    ignored because these functions take none.

Field names differ between schema generations: ``continent`` replaced
``region`` and ``format`` replaced ``type``. :func:`entry_metadata` reports
both names of each pair with the same value.

Hosting: newer ``valence_domains`` releases raise ``MeshNotHostedError``
from ``Mesh.load()`` for a registered mesh whose license does not allow a
hosted copy. That is an expected registry state, not a network failure.
:func:`raise_if_not_hosted` raises it before any download is attempted, and
does nothing on releases without the class.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "get_domain_or_group",
    "list_entries",
    "entry_metadata",
    "raise_if_not_hosted",
    "DOMAIN_FIELDS",
    "MESH_FIELDS",
]

DOMAIN_FIELDS: tuple[str, ...] = (
    "name",
    "full_name",
    "description",
    "category",
    "continent",
    "region",
    "bounding_box",
)

MESH_FIELDS: tuple[str, ...] = (
    "id",
    "filename",
    "bounding_box",
    "license",
    "contributor",
    "contributed_by",
    "version",
    "format",
    "type",
)

# Pairs of field names that carry the same value in different schemas.
_FIELD_TWINS: dict[str, str] = {
    "continent": "region",
    "region": "continent",
    "format": "type",
    "type": "format",
}


def _import_valence_domains() -> Any:
    import valence_domains

    return valence_domains


def raise_if_not_hosted(mesh: Any) -> None:
    """Raise ``valence_domains.MeshNotHostedError`` for a mesh with no hosted copy.

    Feature-detected: when the installed ``valence_domains`` has no
    ``MeshNotHostedError`` class, or the mesh has no ``license_eligible``
    attribute, this does nothing and ``Mesh.load()`` behaves as before.
    Otherwise a mesh with ``license_eligible`` false raises the registry's
    own error, whose message names the mesh and says it is not hosted.
    """
    not_hosted = getattr(_import_valence_domains(), "MeshNotHostedError", None)
    if not_hosted is None:
        return
    if getattr(mesh, "license_eligible", True) is False:
        raise not_hosted(getattr(mesh, "full_id", None) or getattr(mesh, "id", repr(mesh)))


def _has_group_api(vd: Any) -> bool:
    return callable(getattr(vd, "get_group", None)) and callable(
        getattr(vd, "list_collections", None)
    )


def _group_manifest(vd: Any, manifest: Any) -> Any | None:
    """Return a manifest object that offers the group API, or ``None``."""
    load = getattr(vd, "load_manifest", None)
    if not callable(load):
        return None
    m = load() if manifest is None else load(manifest)
    needed = ("get_group", "collections", "primary_domains")
    if all(hasattr(m, attr) for attr in needed):
        return m
    return None


def get_domain_or_group(name: str, manifest: Any = None) -> Any:
    """Return the Domain or Collection called ``name``.

    An alias resolves to its primary Domain. Raises ``KeyError`` when no
    entry matches. ``manifest`` is passed to routes a and b (a path or a
    manifest object for route a, a path for route b) and ignored by route c.
    """
    vd = _import_valence_domains()
    if _has_group_api(vd):
        return vd.get_group(name, manifest=manifest)
    m = _group_manifest(vd, manifest)
    if m is not None:
        found = m.get_group(name)
        if found is None:
            raise KeyError(f"No domain or collection named {name!r} in manifest")
        if getattr(found, "alias_of", None) is not None:
            return m.resolve_alias(found)
        return found
    return vd.get_domain(name)


def list_entries(manifest: Any = None) -> list[Any]:
    """Return every primary Domain plus every Collection.

    Aliases are not listed. Route c returns Domains only.
    """
    vd = _import_valence_domains()
    if _has_group_api(vd):
        return [*vd.list_domains(manifest=manifest), *vd.list_collections(manifest=manifest)]
    m = _group_manifest(vd, manifest)
    if m is not None:
        return [*m.primary_domains, *m.collections]
    return list(vd.list_domains())


def entry_metadata(obj: Any, fields: tuple[str, ...] = DOMAIN_FIELDS) -> dict[str, Any]:
    """Collect the non-``None`` ``fields`` of ``obj`` into a dict.

    When one name of a twin pair (``continent``/``region``,
    ``format``/``type``) is missing on ``obj``, its value is taken from the
    other name. Both names then appear in the result with the same value.
    """
    out: dict[str, Any] = {}
    for field in fields:
        value = getattr(obj, field, None)
        if value is None:
            twin = _FIELD_TWINS.get(field)
            if twin is not None:
                value = getattr(obj, twin, None)
        if value is not None:
            out[field] = value
    return out
