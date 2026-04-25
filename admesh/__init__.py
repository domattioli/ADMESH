"""ADMESH — Python port of QuADMesh-MATLAB/01_ADMESH_Library.

Source commit pin: 19b2eb9f078a648daec3fd40d5d4c6e072f467ac
"""

from admesh.api import BoundarySegment, Domain, Mesh
from admesh.boundary_types import BoundaryType

__version__ = "0.1.0"

__all__ = [
    # v1 public API surface (additive layer over the faithful port).
    "BoundarySegment",
    "BoundaryType",
    "Domain",
    "Mesh",
    # TODO: re-export once implemented.
    # "triangulate",         # T021
    # "domain_from_polygon", # T020
    # "domain_from_sdf",     # T020
    # "read_fort14",         # T024
    # "write_fort14",        # T024
    # "compose_size_field",  # T038
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
