"""ADMESH — Python port of QuADMesh-MATLAB/01_ADMESH_Library.

Source commit pin: 19b2eb9f078a648daec3fd40d5d4c6e072f467ac
"""

from admesh.api import (
    BoundarySegment,
    Domain,
    Mesh,
    domain_from_polygon,
    domain_from_sdf,
    triangulate,
)
from admesh.boundary_types import BoundaryType
from admesh.fort14 import Fort14ParseError, read_fort14, write_fort14
from admesh.quad_prep import smooth_for_quadrangulation
from admesh.quality import mesh_quality, right_iso_quality
from admesh.size_field import SizeFieldFn, compose_size_field

__version__ = "0.1.0"

__all__ = [
    # v1 public API surface (additive layer over the faithful port).
    "BoundarySegment",
    "BoundaryType",
    "Domain",
    "Fort14ParseError",
    "Mesh",
    "SizeFieldFn",
    "compose_size_field",
    "domain_from_polygon",
    "domain_from_sdf",
    "mesh_quality",
    "read_fort14",
    "right_iso_quality",
    "smooth_for_quadrangulation",
    "triangulate",
    "write_fort14",
    # Faithful-port stage modules (Constitution Principle I — untouched).
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
