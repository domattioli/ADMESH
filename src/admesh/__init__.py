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
from admesh.gmsh import GmshParseError, read_msh, write_msh
from admesh.loaders import (
    load_domain_from_fort14,
    load_domain_from_json,
    load_domain_from_toml,
)
from admesh.quad_prep import smooth_for_quadrangulation
from admesh._stages.quality import mesh_quality, right_iso_quality
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

__version__ = "0.6.0"

# Public, semver-guarded API surface for ADMESH 0.1.0.
#
# Faithful-port stage modules (curvature, medial_axis, distance, distmesh,
# routine, etc.) are NOT listed here -- they are internal-by-convention per
# Constitution Article II.1 (and the proposed Article VIII in
# specs/009-release-readiness-for-0.1.0/CONSTITUTION-AMENDMENT.md). Direct
# imports such as `from admesh._stages.curvature import apply_curvature` continue to
# work but carry no semver guarantee on the inner signature.
__all__ = [
    # --- Mesh + domain primitives ---
    "BoundarySegment",
    "BoundaryType",
    "Domain",
    "Mesh",
    # --- Top-level triangulation entry point ---
    "triangulate",
    # --- I/O ---
    "Fort14ParseError",
    "read_fort14",
    "write_fort14",
    "GmshParseError",
    "read_msh",
    "write_msh",
    # --- Size-field composition ---
    "SizeFieldFn",
    "compose_size_field",
    # --- Quality metrics ---
    "mesh_quality",
    "right_iso_quality",
    # --- Quad-prep smoother (spec 004) ---
    "smooth_for_quadrangulation",
    # --- Domain loaders (file + registry) ---
    "load_domain_from_fort14",
    "load_domain_from_json",
    "load_domain_from_toml",
    "load_domain_from_registry",
    "load_domain_with_metadata",
    "list_available_domains",
    # --- Valence balancing (issue #27) ---
    "BalanceConfig",
    "BalanceResult",
    "ValenceStats",
    "balance_valence_triangles",
    "compute_valence",
    "get_valence_report",
]
