"""Integration with ADMESH-Domains registry.

Provides functions to discover and load mesh domains from the ADMESH-Domains
package, enabling seamless pipeline: load_domain_from_registry() → triangulate().
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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


def load_domain_from_registry(mesh_id: str) -> Domain:
    """Fetch a domain from ADMESH-Domains registry by mesh_id.

    Requires the admesh-domains package to be installed.

    Parameters
    ----------
    mesh_id : str
        Mesh identifier from ADMESH-Domains registry
        (e.g., 'noaa-hsofs-v20').

    Returns
    -------
    Domain
        Domain ready for admesh.triangulate().

    Raises
    ------
    ImportError
        If admesh-domains package is not installed.
    ValueError
        If mesh_id is not found in the registry.

    Examples
    --------
    >>> from admesh import load_domain_from_registry, triangulate
    >>> domain = load_domain_from_registry('noaa-hsofs-v20')
    >>> mesh = triangulate(domain, h0=0.1)
    """
    try:
        import admesh_domains
    except ImportError as e:
        raise ImportError(
            "admesh-domains package required for registry access. Install with:\n"
            "  pip install admesh-domains"
        ) from e

    # Load default registry
    registry = admesh_domains.load_default_registry()

    # Fetch domain definition
    try:
        domain_def = registry.get_domain(mesh_id)
    except (KeyError, AttributeError) as e:
        raise ValueError(
            f"Mesh '{mesh_id}' not found in ADMESH-Domains registry"
        ) from e

    # Convert ADMESH-Domains domain object → admesh.Domain
    return _convert_to_admesh_domain(domain_def)


def list_available_domains() -> dict[str, str]:
    """List all available mesh IDs in ADMESH-Domains registry.

    Requires the admesh-domains package to be installed.

    Returns
    -------
    dict[str, str]
        Mapping of mesh_id to short description.

    Raises
    ------
    ImportError
        If admesh-domains package is not installed.

    Examples
    --------
    >>> domains = list_available_domains()
    >>> for mesh_id, desc in sorted(domains.items()):
    ...     print(f"{mesh_id}: {desc}")
    """
    try:
        import admesh_domains
    except ImportError as e:
        raise ImportError(
            "admesh-domains package required for registry access. Install with:\n"
            "  pip install admesh-domains"
        ) from e

    registry = admesh_domains.load_default_registry()
    return registry.list_domains()  # type: ignore[union-attr]


def load_domain_with_metadata(
    mesh_id: str,
) -> tuple[Domain, dict]:
    """Load domain + provenance metadata from ADMESH-Domains registry.

    Requires the admesh-domains package to be installed.

    Parameters
    ----------
    mesh_id : str
        Mesh identifier from ADMESH-Domains registry.

    Returns
    -------
    domain : Domain
        Domain ready for admesh.triangulate().
    metadata : dict
        Provenance metadata (version, license, contributor, etc.)

    Raises
    ------
    ImportError
        If admesh-domains package is not installed.
    ValueError
        If mesh_id is not found in the registry.

    Examples
    --------
    >>> domain, meta = load_domain_with_metadata('noaa-hsofs-v20')
    >>> print(f"Version: {meta.get('version')}")
    >>> print(f"Contributor: {meta.get('contributed_by')}")
    >>> mesh = triangulate(domain, h0=0.1)
    """
    try:
        import admesh_domains
    except ImportError as e:
        raise ImportError(
            "admesh-domains package required for registry access. Install with:\n"
            "  pip install admesh-domains"
        ) from e

    registry = admesh_domains.load_default_registry()

    try:
        domain_def = registry.get_domain_with_metadata(mesh_id)
    except (KeyError, AttributeError):
        # Fall back to basic get_domain if metadata API not available
        domain_def = registry.get_domain(mesh_id)
        metadata = {}

    domain = _convert_to_admesh_domain(domain_def)

    # Extract metadata from ADMESH-Domains domain object
    metadata = getattr(domain_def, "metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    return domain, metadata


def _convert_to_admesh_domain(admesh_domains_obj: object) -> Domain:
    """Convert ADMESH-Domains domain object to admesh.Domain.

    Parameters
    ----------
    admesh_domains_obj : object
        Domain object from ADMESH-Domains package.

    Returns
    -------
    Domain
        ADMESH Domain ready for triangulation.
    """
    # Extract rings (outer boundary + holes)
    rings_attr = getattr(admesh_domains_obj, "rings", None)
    if rings_attr is None:
        # Try alternative name
        rings_attr = getattr(admesh_domains_obj, "boundaries", None)

    if not rings_attr:
        raise ValueError(
            "ADMESH-Domains domain object must have 'rings' or 'boundaries' attribute"
        )

    rings = [
        np.array(r, dtype=np.float64) if not isinstance(r, np.ndarray) else r
        for r in (rings_attr if isinstance(rings_attr, (list, tuple)) else [rings_attr])
    ]

    # Extract bbox
    bbox_attr = getattr(admesh_domains_obj, "bbox", None)
    if bbox_attr is None:
        # Compute bbox from rings
        all_coords = np.vstack(rings)
        bbox = (
            float(all_coords[:, 0].min()),
            float(all_coords[:, 1].min()),
            float(all_coords[:, 0].max()),
            float(all_coords[:, 1].max()),
        )
    else:
        bbox = tuple(float(x) for x in bbox_attr)  # type: ignore[arg-type]

    # Extract fixed points if available
    pfix = getattr(admesh_domains_obj, "fixed_points", None)
    if pfix is not None and not isinstance(pfix, np.ndarray):
        pfix = np.array(pfix, dtype=np.float64) if pfix else None

    return _domain_from_polygon(rings, pfix=pfix)
