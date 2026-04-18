"""Point-in-polygon tests.

Port of ``01_ADMESH_Library/12_In_Polygon/`` — which in the MATLAB repo
contains ONLY a compiled mex binary (``InPolygon.mexmaci64``), no source.
The port therefore targets MATLAB's canonical ``inpolygon(xq, yq, xv, yv)``
semantics: returns ``(in, on)`` where ``in`` is True for points inside OR
on the polygon boundary, and ``on`` is True only for points on the
boundary (within ``on_tol``). See ``docs/PORTING_NOTES.md``.

Call sites in the MATLAB source (e.g. ``SignedDistanceFunction.m:43``)
use the three-output form ``[IN, ~, ~] = InPolygon(...)``; we expose the
same two-valued return plus an optional tolerance parameter.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


def in_polygon(
    xq: ArrayLike,
    yq: ArrayLike,
    xv: ArrayLike,
    yv: ArrayLike,
    on_tol: float = 1e-12,
) -> tuple[NDArray[np.bool_], NDArray[np.bool_]]:
    """Vectorized point-in-polygon test.

    Parameters
    ----------
    xq, yq : array_like
        Query point coordinates. Same shape; output matches this shape.
    xv, yv : array_like
        Polygon vertex coordinates, in order. The polygon is closed
        implicitly (the last vertex is joined to the first). A trailing
        repeat of the first vertex is tolerated.
    on_tol : float
        Tolerance on the perpendicular distance from a query point to a
        polygon edge for classification as "on the boundary".

    Returns
    -------
    inside : ndarray of bool
        True for points strictly inside OR on the boundary.
    on_boundary : ndarray of bool
        True only for points on the boundary (within ``on_tol``).
    """
    xq = np.asarray(xq, dtype=float)
    yq = np.asarray(yq, dtype=float)
    xv = np.asarray(xv, dtype=float).ravel()
    yv = np.asarray(yv, dtype=float).ravel()

    if xq.shape != yq.shape:
        raise ValueError("xq and yq must have the same shape")
    if xv.shape != yv.shape:
        raise ValueError("xv and yv must have the same shape")
    if xv.size < 3:
        raise ValueError("polygon needs at least 3 vertices")

    if xv[0] == xv[-1] and yv[0] == yv[-1]:
        xv = xv[:-1]
        yv = yv[:-1]

    orig_shape = xq.shape
    qx = xq.ravel()
    qy = yq.ravel()

    x1 = xv
    y1 = yv
    x2 = np.roll(xv, -1)
    y2 = np.roll(yv, -1)

    QX = qx[:, None]
    QY = qy[:, None]

    # On-boundary test: perpendicular distance to each segment, clamped to [0, 1].
    ex = x2 - x1
    ey = y2 - y1
    seg_len_sq = ex * ex + ey * ey
    safe = np.where(seg_len_sq > 0, seg_len_sq, 1.0)
    t = np.where(
        seg_len_sq > 0,
        ((QX - x1) * ex + (QY - y1) * ey) / safe,
        0.0,
    )
    t = np.clip(t, 0.0, 1.0)
    px = x1 + t * ex
    py = y1 + t * ey
    dist_sq = (QX - px) ** 2 + (QY - py) ** 2
    on_boundary = np.any(dist_sq <= on_tol * on_tol, axis=1)

    # Ray-cast test (horizontal ray to +x). Strict-vs-nonstrict on y avoids
    # double-counting at shared vertices.
    y1b = y1[None, :]
    y2b = y2[None, :]
    x1b = x1[None, :]
    x2b = x2[None, :]

    cond = (y1b > QY) != (y2b > QY)
    with np.errstate(divide="ignore", invalid="ignore"):
        xcross = (x2b - x1b) * (QY - y1b) / (y2b - y1b) + x1b
    crossings = np.where(cond & (QX < xcross), 1, 0).sum(axis=1)
    strictly_inside = (crossings % 2) == 1

    inside = strictly_inside | on_boundary
    return inside.reshape(orig_shape), on_boundary.reshape(orig_shape)
