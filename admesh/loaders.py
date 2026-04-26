"""Domain loading utilities for TOML, fort.14, and JSON formats.

Provides loaders to construct Domain objects from file-based domain definitions
compatible with ADMESH-Domains registry format.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable

import numpy as np

from admesh.api import Domain

__all__ = [
    "load_domain_from_toml",
    "load_domain_from_fort14",
    "load_domain_from_json",
]

def _shapely_sdf(rings: list[np.ndarray]) -> Callable[[np.ndarray], np.ndarray]:
    from shapely.geometry import Polygon
    from shapely.prepared import prep
    from shapely import distance as shp_distance, points as shp_points

    if not rings:
        raise ValueError("rings must contain at least one outer ring")
    outer = np.asarray(rings[0], dtype=np.float64)
    holes = [np.asarray(r, dtype=np.float64) for r in rings[1:]]
    polygon = Polygon(outer, holes=holes if holes else None)
    boundary = polygon.boundary
    prepared = prep(polygon)

    def sdf(p: np.ndarray) -> np.ndarray:
        pts = np.asarray(p, dtype=np.float64)
        if pts.ndim == 1:
            pts = pts[None, :]
        sp = shp_points(pts[:, 0], pts[:, 1])
        d = shp_distance(sp, boundary)
        inside = np.array([prepared.contains(g) for g in sp])
        return np.where(inside, -d, d).astype(np.float64)

    return sdf


def _domain_from_polygon(
    rings: list[np.ndarray],
    *,
    pfix: np.ndarray | None = None,
) -> Domain:
    """Internal helper: build a Domain from polygon rings via Shapely SDF."""
    if not rings:
        raise ValueError("rings must be non-empty")
    outer = np.asarray(rings[0], dtype=np.float64)
    if outer.ndim != 2 or outer.shape[1] != 2:
        raise ValueError(f"outer ring must have shape (M, 2), got {outer.shape}")
    bbox = (
        float(outer[:, 0].min()),
        float(outer[:, 1].min()),
        float(outer[:, 0].max()),
        float(outer[:, 1].max()),
    )
    return Domain(sdf=_shapely_sdf(rings), bbox=bbox, pfix=pfix)


# Use tomllib (Python 3.11+) or fall back to toml package
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore[import-not-found]
    except ImportError:
        import toml as tomllib  # type: ignore[import-not-found]


def load_domain_from_toml(path: str | Path) -> Domain:
    """Load a domain definition from a TOML file.

    Expected TOML structure::

        [domain]
        name = "example"
        bbox = [-1.0, -1.0, 1.0, 1.0]

        [[domain.rings]]
        coords = [[-1, -1], [1, -1], [1, 1], [-1, 1]]

        [[domain.rings]]  # Optional: interior islands
        coords = [[-0.25, -0.25], [0.25, -0.25], [0.25, 0.25], [-0.25, 0.25]]

        [[domain.fixed_points]]  # Optional: pinned vertices
        coords = [[-1, -1], [1, 1]]

    Parameters
    ----------
    path : str or Path
        Path to TOML domain file.

    Returns
    -------
    Domain
        Ready for admesh.triangulate().
    """
    path = Path(path)
    with open(path, "rb" if hasattr(tomllib, "load") else "r") as f:  # type: ignore[arg-type]
        if hasattr(tomllib, "load"):
            data = tomllib.load(f)  # type: ignore[attr-defined]
        else:
            data = tomllib.load(f)  # type: ignore[attr-defined]

    domain_spec = data.get("domain", {})
    bbox_raw = domain_spec.get("bbox")
    if not bbox_raw or len(bbox_raw) != 4:
        raise ValueError(f"TOML domain.bbox must be a 4-tuple; got {bbox_raw}")
    bbox = tuple(float(x) for x in bbox_raw)  # type: ignore[arg-type]

    rings_raw = domain_spec.get("rings", [])
    if not rings_raw:
        raise ValueError("TOML domain.rings must contain at least one ring (outer boundary)")

    rings = [np.array(r.get("coords", []), dtype=np.float64) for r in rings_raw]

    fixed_points = None
    fixed_raw = domain_spec.get("fixed_points")
    if fixed_raw:
        coords_list = [fp.get("coords") for fp in fixed_raw]
        if coords_list and coords_list[0]:
            fixed_points = np.array(coords_list[0], dtype=np.float64)

    return _domain_from_polygon(rings, pfix=fixed_points)


def load_domain_from_fort14(path: str | Path) -> Domain:
    """Load a domain boundary from a fort.14 mesh file.

    Extracts the outer boundary polygon from a fort.14 mesh. Uses mesh
    node coordinates to compute bbox and boundary vertices as fixed points.

    Parameters
    ----------
    path : str or Path
        Path to fort.14 mesh file.

    Returns
    -------
    Domain
        Domain with polygon rings extracted from fort.14 boundaries.
    """
    from admesh.fort14 import read_fort14

    mesh = read_fort14(path)

    # Extract outer boundary from first land boundary segment
    rings = []
    if mesh.boundaries:
        # Use first land boundary as outer ring
        for seg in mesh.boundaries:
            if not seg.is_open:
                ring_indices = seg.node_ids
                ring_coords = mesh.nodes[ring_indices]
                rings.append(ring_coords)
                break

    if not rings:
        raise ValueError(f"No land boundary found in {path}")

    # Use mesh nodes to compute bbox
    xmin, ymin = mesh.nodes.min(axis=0)
    xmax, ymax = mesh.nodes.max(axis=0)
    bbox = (float(xmin), float(ymin), float(xmax), float(ymax))

    # Mark boundary vertices as fixed points
    fixed_points = None
    if rings and len(rings[0]) > 0:
        fixed_points = np.array(rings[0][[0, len(rings[0]) // 2, -1]], dtype=np.float64)

    return _domain_from_polygon(rings, pfix=fixed_points)


def load_domain_from_json(path: str | Path) -> Domain:
    """Load a domain definition from a JSON file.

    Expected JSON structure::

        {
          "name": "example",
          "bbox": [-1.0, -1.0, 1.0, 1.0],
          "rings": [
            [[-1, -1], [1, -1], [1, 1], [-1, 1]],
            [[-0.25, -0.25], [0.25, -0.25], [0.25, 0.25], [-0.25, 0.25]]
          ],
          "fixed_points": [[-1, -1], [1, 1]]
        }

    Parameters
    ----------
    path : str or Path
        Path to JSON domain file.

    Returns
    -------
    Domain
        Ready for admesh.triangulate().
    """
    path = Path(path)
    with open(path) as f:
        data = json.load(f)

    bbox_raw = data.get("bbox")
    if not bbox_raw or len(bbox_raw) != 4:
        raise ValueError(f"JSON bbox must be a 4-tuple; got {bbox_raw}")
    bbox = tuple(float(x) for x in bbox_raw)  # type: ignore[arg-type]

    rings_raw = data.get("rings", [])
    if not rings_raw:
        raise ValueError("JSON rings must contain at least one ring (outer boundary)")

    rings = [np.array(r, dtype=np.float64) for r in rings_raw]

    fixed_points = None
    fixed_raw = data.get("fixed_points")
    if fixed_raw:
        fixed_points = np.array(fixed_raw, dtype=np.float64)

    return _domain_from_polygon(rings, pfix=fixed_points)
