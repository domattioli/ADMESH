"""Top-level ADMESH driver.

MVP subset of ``01_ADMESH_Library/01_ADMESH_Routine/ADmeshRoutine.m``
+ ``ADmeshSubMeshRoutine.m`` @ 19b2eb9.

The MVP exposes :func:`triangulate` — a thin orchestrator that maps
an :class:`~admesh.domains.Domain` or :class:`~admesh.boundary.PTS`
to the DistMesh2D inputs. Dispatches to
:func:`admesh.distmesh.distmesh2d` for Domain inputs (MVP path) or
:func:`admesh.distmesh.distmesh2d_admesh` for PTS inputs (P3 path).
"""

from __future__ import annotations

from typing import Union

import numpy as np
from numpy.typing import NDArray

from admesh.boundary import PTS
from admesh.distmesh import MeshOutput, SizeFn, distmesh2d, distmesh2d_admesh
from admesh.domains import Domain

DomainOrPTS = Union[Domain, PTS]


def triangulate(
    target: DomainOrPTS,
    h0: float = 0.1,
    fh: SizeFn | None = None,
    **opts,
) -> tuple[NDArray[np.float64], NDArray[np.int64]] | MeshOutput:
    """Produce a triangular mesh for a :class:`Domain` or :class:`PTS`.

    Parameters
    ----------
    target : Domain or PTS
        If a :class:`Domain`, runs the MVP canonical-distmesh path
        and returns ``(p, t)``.
        If a :class:`PTS`, runs the ADMESH-variant path with
        boundary-cleanup and BC labels; returns a
        :class:`~admesh.distmesh.MeshOutput`.
    h0 : float
        Target edge length.
    fh : callable or None
        Mesh-size function (uniform if None).
    **opts :
        Forwarded to the underlying distmesh call.
    """
    if isinstance(target, PTS):
        return distmesh2d_admesh(target, fh=fh, h0=h0, **opts)

    pfix = target.fixed_points if target.fixed_points.size else None
    return distmesh2d(
        fd=target.fd,
        fh=fh,
        h0=h0,
        bbox=target.bbox,
        pfix=pfix,
        **opts,
    )
