"""background_grid — port of 02_Create_Background_Grid/CreateBackgroundGrid.m.

MATLAB source: github.com/domattioli/QuADMesh-MATLAB @ 19b2eb9,
path 01_ADMESH_Library/02_Create_Background_Grid/CreateBackgroundGrid.m.
An unmaintained copy of the MATLAB original is archived in-repo at
``archive/matlab/admesh_library/02_Create_Background_Grid/``.

Stage 02 of the routine: synthesize the regular Cartesian background grid
that every downstream size-field stage (curvature, medial axis, bathymetry,
dominate-tide, inpaint, gradient-limit) samples and accumulates on.

The MATLAB original returns ``[X, Y, delta]`` for a grid spanning the
domain bounding box padded by ``hmax`` on every side, with spacing
``delta = hmin / res``. This port keeps that construction and packages it
in a frozen :class:`BackgroundGrid`. The ``(X, Y)`` arrays match
:func:`admesh._stages.distance.eval_sdf_grid` for the same ``bbox`` and
``delta`` (``meshgrid(..., indexing="xy")``, ``X`` along columns).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

__all__ = ["BackgroundGrid", "create_background_grid"]


@dataclass(frozen=True)
class BackgroundGrid:
    """Structured Cartesian background grid for the size-field stages.

    Attributes
    ----------
    X, Y:
        ``(LY, LX)`` coordinate arrays in MATLAB ``meshgrid`` convention
        (``X`` varies along columns, ``Y`` along rows).
    delta:
        Uniform grid spacing; ``Δx == Δy == delta``.
    bbox:
        ``(xmin, ymin, xmax, ymax)`` of the (padded) grid extent.
    """

    X: NDArray[np.float64]
    Y: NDArray[np.float64]
    delta: float
    bbox: tuple[float, float, float, float]


def create_background_grid(
    domain,
    h0: float,
    padding: float | None = None,
    res: int = 1,
) -> BackgroundGrid:
    """Build the structured background grid over ``domain``.

    Port of ``CreateBackgroundGrid.m``. The MATLAB signature is
    ``[X, Y, delta] = CreateBackgroundGrid(PTS, hmax, hmin, res)``: the
    bounding box is padded by ``hmax`` on every side and the spacing is
    ``delta = hmin / res``. Here ``h0`` plays the role of ``hmin`` (the
    grid spacing), ``padding`` plays the role of the ``hmax`` pad, and
    ``res`` is the same integer spacing factor.

    Parameters
    ----------
    domain:
        Object exposing a ``bbox`` of ``(xmin, ymin, xmax, ymax)``.
    h0:
        Target grid spacing before the ``res`` factor.
    padding:
        Absolute pad added to every side of ``domain.bbox``. Defaults to
        ``h0`` when ``None`` (MATLAB pads by ``hmax``; with no separate
        coarse size in this signature, one cell of pad is the faithful
        minimum).
    res:
        Integer spacing factor; ``delta = h0 / res``.

    Returns
    -------
    BackgroundGrid
        Frozen grid with ``X``, ``Y``, ``delta``, and the padded ``bbox``.
    """
    if res < 1:
        raise ValueError("res must be a positive integer")
    pad = h0 if padding is None else padding
    delta = h0 / res

    xmin, ymin, xmax, ymax = domain.bbox
    xmin, ymin, xmax, ymax = xmin - pad, ymin - pad, xmax + pad, ymax + pad

    xs = np.arange(xmin, xmax + 0.5 * delta, delta)
    ys = np.arange(ymin, ymax + 0.5 * delta, delta)
    X, Y = np.meshgrid(xs, ys, indexing="xy")
    return BackgroundGrid(X=X, Y=Y, delta=delta, bbox=(xmin, ymin, xmax, ymax))
