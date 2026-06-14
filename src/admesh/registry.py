"""Integration with Valence-Domains 0.4.x registry.

Provides functions to discover and load mesh domains from the Valence-Domains
package, enabling the seamless pipeline:
``load_domain_from_registry(name) -> triangulate(domain)``.

This adapter targets the ``valence-domains>=0.4`` API surface
documented in ``docs/VALENCE_DOMAINS_CONTRACT.md``. Network fetches use
``huggingface_hub`` and require the optional ``[registry]`` extra
(``pip install admesh2D[registry]``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from admesh.api import Domain
from admesh.loaders import _domain_from_polygon

if TYPE_CHECKING:
    pass

__all__ = [
    "load_domain_from_registry",
    "list_available_domains",
    "load_domain_with_metadata",
]


_REGISTRY_IMPORT_HINT = (
    "valence-domains package required for registry access. Install with:\n"
    "  pip install valence-domains"
)
_HF_HUB_IMPORT_HINT = (
    "huggingface_hub required to download registry meshes. Install with:\n"
    "  pip install admesh2D[registry]"
)


def _import_valence_domains() -> Any:
    """Lazy import ``valence_domains`` with a friendly install hint."""
    try:
        import valence_domains
    except ImportError as e:
        raise ImportError(_REGISTRY_IMPORT_HINT) from e
    return valence_domains


def _resolve_mesh(name: str, mesh_id: str) -> Any:
    """Resolve ``(name, mesh_id)`` to a downloaded ``Mesh`` reference.

    Looks up the domain, picks the requested mesh (or the first mesh
    when ``mesh_id`` is not present), and triggers a download via
    ``Mesh.load()`` if the file is not on disk. Surfaces a friendly
    ``ImportError`` if the ``huggingface_hub`` extra is missing.

    Parameters
    ----------
    name : str
        Domain name (e.g. ``"BaranjaHill"``).
    mesh_id : str
        Mesh id (e.g. ``"default@v1"``).

    Returns
    -------
    Any
        ``valence_domains.Mesh`` reference with a populated local ``.path``.
    """
    valence_domains = _import_valence_domains()

    try:
        ad_domain = valence_domains.get_domain(name)
    except (KeyError, AttributeError) as e:
        raise ValueError(
            f"Domain '{name}' not found in Valence-Domains registry"
        ) from e

    mesh_ref = None
    get_mesh = getattr(ad_domain, "get_mesh", None)
    if callable(get_mesh):
        try:
            mesh_ref = get_mesh(mesh_id)
        except (KeyError, AttributeError, ValueError):
            mesh_ref = None

    if mesh_ref is None:
        meshes = getattr(ad_domain, "meshes", None) or []
        if not meshes:
            raise ValueError(
                f"Domain '{name}' exposes no meshes in the registry"
            )
        mesh_ref = meshes[0]

    if not mesh_ref.exists():
        try:
            import huggingface_hub  # noqa: F401
        except ImportError as e:
            raise ImportError(_HF_HUB_IMPORT_HINT) from e
        mesh_ref.load()

    return mesh_ref


def load_domain_from_registry(name: str, mesh_id: str = "default@v1") -> Domain:
    """Fetch a domain from the ADMESH-Domains registry by ``name``.

    Requires the ``valence-domains`` package. Network downloads through
    ``Mesh.load()`` additionally require the optional ``[registry]`` extra
    (``pip install admesh2D[registry]``).

    Parameters
    ----------
    name : str
        Domain name in the registry (e.g. ``'BaranjaHill'``).
    mesh_id : str, optional
        Mesh id within the domain. Defaults to ``"default@v1"``; falls
        back to the first available mesh if the id is unknown.

    Returns
    -------
    Domain
        Domain ready for :func:`admesh.triangulate`.

    Raises
    ------
    ImportError
        If ``valence-domains`` is not installed, or if ``huggingface_hub``
        is needed for a network fetch and is not installed.
    ValueError
        If the domain name is not in the registry.

    Examples
    --------
    >>> from admesh import load_domain_from_registry, triangulate
    >>> domain = load_domain_from_registry('BaranjaHill')
    >>> mesh = triangulate(domain, h0=0.1)
    """
    from admesh.fort14 import read_fort14

    mesh_ref = _resolve_mesh(name, mesh_id)
    src = read_fort14(mesh_ref.path)
    return Domain.from_mesh(src)


def list_available_domains() -> dict[str, str]:
    """List domains available in the Valence-Domains registry.

    Requires the ``valence-domains`` package.

    Returns
    -------
    dict[str, str]
        Mapping of domain name to a short description (``full_name`` if
        populated, otherwise ``description``, otherwise an empty string),
        sorted by domain name.

    Raises
    ------
    ImportError
        If ``valence-domains`` is not installed.
    """
    valence_domains = _import_valence_domains()
    items = valence_domains.list_domains()
    return {
        d.name: (getattr(d, "full_name", None) or getattr(d, "description", None) or "")
        for d in sorted(items, key=lambda d: d.name)
    }


def load_domain_with_metadata(
    name: str, mesh_id: str = "default@v1"
) -> tuple[Domain, dict]:
    """Load a domain plus provenance metadata from the registry.

    Returns the same :class:`Domain` as :func:`load_domain_from_registry`
    plus a metadata dict drawn from the upstream ``Domain``/``Mesh``
    objects (license, contributor, bounding box, etc.; missing fields
    are skipped).

    Parameters
    ----------
    name : str
        Domain name in the registry.
    mesh_id : str, optional
        Mesh id within the domain.

    Returns
    -------
    domain : Domain
        Domain ready for :func:`admesh.triangulate`.
    metadata : dict
        Provenance fields extracted from the registry objects.

    Raises
    ------
    ImportError
        If ``valence-domains`` (or ``huggingface_hub`` for the download)
        is not installed.
    ValueError
        If the domain name is not in the registry.
    """
    from admesh.fort14 import read_fort14

    valence_domains = _import_valence_domains()

    try:
        ad_domain = valence_domains.get_domain(name)
    except (KeyError, AttributeError) as e:
        raise ValueError(
            f"Domain '{name}' not found in Valence-Domains registry"
        ) from e

    mesh_ref = _resolve_mesh(name, mesh_id)
    src = read_fort14(mesh_ref.path)
    domain = Domain.from_mesh(src)

    metadata: dict[str, Any] = {}
    for src_obj, fields in (
        (
            ad_domain,
            (
                "name",
                "full_name",
                "description",
                "category",
                "region",
                "bounding_box",
            ),
        ),
        (
            mesh_ref,
            (
                "id",
                "filename",
                "bounding_box",
                "license",
                "contributor",
                "contributed_by",
                "version",
            ),
        ),
    ):
        for field in fields:
            value = getattr(src_obj, field, None)
            if value is not None and field not in metadata:
                metadata[field] = value

    if "bounding_box" not in metadata:
        metadata["bounding_box"] = getattr(ad_domain, "bounding_box", None)

    return domain, metadata


def _convert_to_valence_domain(valence_domains_obj: object) -> Domain:
    """Convert a legacy Valence-Domains domain object to ``admesh.Domain``.

    Retained for tests that exercise the 0.3.x legacy shape
    (``.rings``/``.bbox``/``.fixed_points``). New callers should use
    :func:`load_domain_from_registry`, which routes through the 0.4.x
    ``Mesh.load()`` / ``read_fort14`` chain.
    """
    rings_attr = getattr(valence_domains_obj, "rings", None)
    if rings_attr is None:
        rings_attr = getattr(valence_domains_obj, "boundaries", None)

    if not rings_attr:
        raise ValueError(
            "Valence-Domains domain object must have 'rings' or 'boundaries' attribute"
        )

    rings = [
        np.array(r, dtype=np.float64) if not isinstance(r, np.ndarray) else r
        for r in (rings_attr if isinstance(rings_attr, (list, tuple)) else [rings_attr])
    ]

    bbox_attr = getattr(valence_domains_obj, "bbox", None)
    if bbox_attr is None:
        all_coords = np.vstack(rings)
        bbox = (
            float(all_coords[:, 0].min()),
            float(all_coords[:, 1].min()),
            float(all_coords[:, 0].max()),
            float(all_coords[:, 1].max()),
        )
    else:
        bbox = tuple(float(x) for x in bbox_attr)  # type: ignore[arg-type]

    pfix = getattr(valence_domains_obj, "fixed_points", None)
    if pfix is not None and not isinstance(pfix, np.ndarray):
        pfix = np.array(pfix, dtype=np.float64) if pfix else None

    _ = bbox  # bbox is computed for parity with the legacy adapter
    return _domain_from_polygon(rings, pfix=pfix)
