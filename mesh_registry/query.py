"""Registry query interface for discovering meshes by spatial, feature, and license criteria.

Provides find() API for filtering the mesh registry.
"""

import logging
from typing import List, Optional, Union, Dict, Tuple
from datetime import datetime

from shapely.geometry import box

from mesh_registry.schema import Mesh, Manifest, License, MeshFeature
from mesh_registry.manifest import load_manifest

logger = logging.getLogger(__name__)


def find(
    bbox: Optional[Tuple[float, float, float, float]] = None,
    features: Optional[List[Union[str, MeshFeature]]] = None,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
    license: Optional[Union[str, License]] = None,
    namespace: Optional[str] = None,
    contributor: Optional[str] = None,
    include_deprecated: bool = False,
    manifest: Optional[Union[str, Manifest]] = None,
    sort_by: str = "size",
) -> List[Mesh]:
    """Query the mesh registry by geographic, feature, and metadata criteria.

    Args:
        bbox: Bounding box filter as (min_lon, min_lat, max_lon, max_lat).
              Queries for meshes with bbox overlapping this region.
              Supports antimeridian crossing (min_lon > max_lon).
        features: List of features to filter by. Results include meshes
                  with ANY of the specified features (union, not intersection).
        min_size: Minimum triangle count (inclusive).
        max_size: Maximum triangle count (inclusive).
        license: License identifier or License enum to filter by.
        namespace: Namespace filter (e.g., "noaa", "usace").
        contributor: Contributor name/email substring filter.
        include_deprecated: Include deprecated/tombstoned meshes in results.
        manifest: Manifest object or path to load. If None, auto-loads from HF.
        sort_by: Sort results by "size" (default), "name", or "created_date".

    Returns:
        List of Mesh objects matching all filters, sorted as specified.

    Raises:
        FileNotFoundError: If manifest path doesn't exist.
        ValueError: If filters are invalid.
    """
    start_time = datetime.now()

    # Load manifest if not provided
    if manifest is None:
        manifest = load_manifest("registry_data/manifest.toml")
    elif isinstance(manifest, str):
        manifest = load_manifest(manifest)
    elif not isinstance(manifest, Manifest):
        raise ValueError(f"manifest must be Manifest object or str path, got {type(manifest)}")

    results = manifest.meshes[:]  # Copy list

    # Filter by review_state (exclude deprecated unless requested)
    if not include_deprecated:
        results = [m for m in results if m.review_state != "deprecated"]

    # Filter by bbox (spatial overlap)
    if bbox is not None:
        results = _filter_by_bbox(results, bbox)

    # Filter by features (union: any of the specified features)
    if features is not None:
        results = _filter_by_features(results, features)

    # Filter by size range
    if min_size is not None:
        results = [m for m in results if m.num_triangles >= min_size]
    if max_size is not None:
        results = [m for m in results if m.num_triangles <= max_size]

    # Filter by license
    if license is not None:
        results = _filter_by_license(results, license)

    # Filter by namespace (from composite ID)
    if namespace is not None:
        results = [m for m in results if m.id.split("/")[0] == namespace]

    # Filter by contributor substring
    if contributor is not None:
        results = [m for m in results if contributor.lower() in m.created_by.lower()]

    # Sort results
    results = _sort_results(results, sort_by)

    # Log query execution
    latency_ms = (datetime.now() - start_time).total_seconds() * 1000
    logger.debug(
        f"Query executed: filters={{bbox={bbox is not None}, features={len(features) if features else 0}, "
        f"size={min_size is not None or max_size is not None}, license={license is not None}, "
        f"namespace={namespace is not None}, contributor={contributor is not None}}} "
        f"results={len(results)} latency_ms={latency_ms:.1f}"
    )

    return results


# Private filter functions


def _filter_by_bbox(meshes: List[Mesh], bbox: Tuple[float, float, float, float]) -> List[Mesh]:
    """Filter meshes by bounding box spatial overlap.

    Uses shapely.box().intersects() for robust antimeridian handling.

    Args:
        meshes: List of meshes to filter.
        bbox: Query bbox as (min_lon, min_lat, max_lon, max_lat).

    Returns:
        Meshes with bounding boxes overlapping the query bbox.
    """
    min_lon, min_lat, max_lon, max_lat = bbox

    # Validate bbox
    if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180):
        raise ValueError(f"Invalid longitude in bbox: {bbox}")
    if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        raise ValueError(f"Invalid latitude in bbox: {bbox}")

    # Create query box (handles antimeridian automatically via shapely)
    try:
        query_box = box(min_lon, min_lat, max_lon, max_lat)
    except Exception as e:
        raise ValueError(f"Invalid bbox: {bbox}") from e

    results = []
    for mesh in meshes:
        bbox_obj = mesh.bounding_box
        try:
            mesh_box = box(bbox_obj.min_lon, bbox_obj.min_lat, bbox_obj.max_lon, bbox_obj.max_lat)
            if query_box.intersects(mesh_box):
                results.append(mesh)
        except Exception:
            # Skip meshes with invalid bboxes
            logger.warning(f"Invalid bbox for mesh {mesh.id}: {bbox_obj}")
            continue

    return results


def _filter_by_features(meshes: List[Mesh], features: List[Union[str, MeshFeature]]) -> List[Mesh]:
    """Filter meshes by features (union: any of the specified features).

    Args:
        meshes: List of meshes to filter.
        features: List of feature strings or MeshFeature enums.

    Returns:
        Meshes with at least one of the specified features.
    """
    # Normalize features to set of strings
    feature_set = set()
    for f in features:
        if isinstance(f, MeshFeature):
            feature_set.add(f.value)
        elif isinstance(f, str):
            feature_set.add(f)
        else:
            raise ValueError(f"Invalid feature type: {type(f)}")

    results = []
    for mesh in meshes:
        mesh_features = {f.value if isinstance(f, MeshFeature) else f for f in mesh.features}
        if mesh_features & feature_set:  # Intersection: has any feature
            results.append(mesh)

    return results


def _filter_by_license(meshes: List[Mesh], license_filter: Union[str, License]) -> List[Mesh]:
    """Filter meshes by license.

    Args:
        meshes: List of meshes to filter.
        license_filter: License identifier string or License enum.

    Returns:
        Meshes with matching license.

    Raises:
        ValueError: If license_filter is invalid.
    """
    # Normalize to License enum
    if isinstance(license_filter, License):
        target_license = license_filter
    elif isinstance(license_filter, str):
        try:
            target_license = License(license_filter)
        except ValueError as e:
            raise ValueError(f"Invalid license: {license_filter}") from e
    else:
        raise ValueError(f"Invalid license type: {type(license_filter)}")

    return [m for m in meshes if m.license == target_license]


def _sort_results(meshes: List[Mesh], sort_by: str = "size") -> List[Mesh]:
    """Sort results by specified field.

    Args:
        meshes: List of meshes to sort.
        sort_by: Sort key: "size" (num_triangles), "name", or "created_date".

    Returns:
        Sorted list of meshes.

    Raises:
        ValueError: If sort_by is invalid.
    """
    if sort_by == "size":
        return sorted(meshes, key=lambda m: m.num_triangles)
    elif sort_by == "name":
        return sorted(meshes, key=lambda m: m.name)
    elif sort_by == "created_date":
        return sorted(meshes, key=lambda m: m.created_date)
    else:
        raise ValueError(f"Invalid sort_by: {sort_by}")
