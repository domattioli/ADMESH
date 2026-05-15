"""ADMESH — Python port of QuADMesh-MATLAB/01_ADMESH_Library.

Source commit pin: 19b2eb9f078a648daec3fd40d5d4c6e072f467ac
"""

from admesh import domains
from admesh.api import (
    BoundarySegment,
    Domain,
    Mesh,
    triangulate,
)
from admesh.boundary_types import BoundaryType
from admesh.fort14 import Fort14ParseError, read_fort14, write_fort14
from admesh.loaders import (
    load_domain_from_fort14,
    load_domain_from_json,
    load_domain_from_toml,
)
from admesh.quad_prep import smooth_for_quadrangulation
from admesh.quality import mesh_quality, right_iso_quality
from admesh.registry import (
    list_available_domains,
    load_domain_from_registry,
    load_domain_with_metadata,
)
from admesh.size_field import SizeFieldFn, compose_size_field
from admesh.valence import (
    BalanceConfig,
    BalanceResult,
    ValenceStats,
    balance_valence_triangles,
    compute_valence,
    get_valence_report,
)

__version__ = "0.2.0"

__all__ = [
    # v1 public API surface (additive layer over the faithful port).
    "BoundarySegment",
    "BoundaryType",
    "Domain",
    "Fort14ParseError",
    "Mesh",
    "SizeFieldFn",
    "compose_size_field",
    "list_available_domains",
    "load_domain_from_fort14",
    "load_domain_from_json",
    "load_domain_from_registry",
    "load_domain_from_toml",
    "load_domain_with_metadata",
    "mesh_quality",
    "read_fort14",
    "right_iso_quality",
    "smooth_for_quadrangulation",
    "triangulate",
    "write_fort14",
    # Valence balancing (issue #27)
    "BalanceConfig",
    "BalanceResult",
    "ValenceStats",
    "balance_valence_triangles",
    "compute_valence",
    "get_valence_report",
    # Faithful-port stage modules (Constitution Principle I -- untouched).
    "background_grid",
    "bathymetry",
    "boundary",
    "curvature",
    "distance",
    "distmesh",
    "domains",
    "dominate_tide",
    "in_polygon",
    "inpaint",
    "medial_axis",
    "mesh_size",
    "quality",
    "routine",
]
