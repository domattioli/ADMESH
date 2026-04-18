"""Top-level ADMESH driver.

MVP subset of ``01_ADMESH_Library/01_ADMESH_Routine/ADmeshRoutine.m``
+ ``ADmeshSubMeshRoutine.m`` @ 19b2eb9.

The MVP exposes :func:`triangulate` — a thin orchestrator that maps
an :class:`~admesh.domains.Domain` to the DistMesh2D inputs
(``fd``, ``fh``, ``bbox``, ``pfix``). The full ADMESH orchestration
(PTS construction, bathymetry / tide / medial-axis size-field
composition, quad conversion, boundary post-processing) lands in
post-MVP phases P1–P4.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
from numpy.typing import NDArray

from admesh.distmesh import SizeFn, distmesh2d
from admesh.domains import Domain


def triangulate(
    domain: Domain,
    h0: float = 0.1,
    fh: SizeFn | None = None,
    **opts,
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Produce a triangular mesh for a :class:`Domain`.

    Parameters
    ----------
    domain : Domain
    h0 : float
        Target edge length.
    fh : callable or None
        Mesh-size function (uniform if None).
    **opts :
        Forwarded to :func:`admesh.distmesh.distmesh2d`.
    """
    pfix = domain.fixed_points if domain.fixed_points.size else None
    return distmesh2d(
        fd=domain.fd,
        fh=fh,
        h0=h0,
        bbox=domain.bbox,
        pfix=pfix,
        **opts,
    )
