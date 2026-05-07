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


def _seed_boundary_1d(
    polygon: NDArray[np.float64],
    fh: SizeFn | None,
    h0: float,
) -> NDArray[np.float64]:
    """Place interior seed points along each edge of *polygon* at ~fh spacing.

    Mirrors the boundary-seeding step of ``createInitialPointList.m`` @ 19b2eb9
    (the PTS path uses pre-sampled ring vertices; this applies the same logic to
    the Domain path's explicit ``boundary_polygon``).

    Parameters
    ----------
    polygon : (M, 2) array
        Ordered boundary vertices (need not repeat first vertex).
    fh : callable or None
        Mesh-size function evaluated at each edge midpoint to set local
        spacing.  ``None`` -> uniform ``h0`` spacing.
    h0 : float
        Minimum / fallback seed spacing.

    Returns
    -------
    (K, 2) array
        Interior seed points (endpoints excluded — those live in
        ``Domain.fixed_points``).  Empty array when all edges are shorter
        than one seed interval.
    """
    poly = np.asarray(polygon, dtype=float)
    n = len(poly)
    seeds: list[NDArray[np.float64]] = []

    for i in range(n):
        v0 = poly[i]
        v1 = poly[(i + 1) % n]
        edge = v1 - v0
        edge_len = float(np.linalg.norm(edge))
        if edge_len < 1e-14:
            continue

        if fh is not None:
            mid = ((v0 + v1) / 2.0).reshape(1, 2)
            local_h = float(fh(mid)[0])
            if not np.isfinite(local_h) or local_h <= 0.0:
                local_h = h0
            local_h = max(local_h, h0)
        else:
            local_h = h0

        n_segs = int(edge_len / local_h)
        if n_segs < 2:
            continue

        ts = np.arange(1, n_segs) / n_segs        # interior parameter values
        pts = v0[None, :] + ts[:, None] * edge[None, :]
        seeds.append(pts)

    if not seeds:
        return np.empty((0, 2), dtype=float)
    return np.vstack(seeds)


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

    pfix_parts: list[NDArray[np.float64]] = []

    if target.boundary_polygon is not None:
        seeds = _seed_boundary_1d(target.boundary_polygon, fh, h0)
        if seeds.size:
            pfix_parts.append(seeds)

    if target.fixed_points.size:
        pfix_parts.append(target.fixed_points)

    pfix: NDArray[np.float64] | None = (
        np.vstack(pfix_parts) if pfix_parts else None
    )

    return distmesh2d(
        fd=target.fd,
        fh=fh,
        h0=h0,
        bbox=target.bbox,
        pfix=pfix,
        **opts,
    )
