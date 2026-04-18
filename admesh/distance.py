"""Distance-function utilities.

MVP subset of ``01_ADMESH_Library/03_Distance_Function/`` @ 19b2eb9.

The full MATLAB ``SignedDistanceFunction.m`` operates on the
``PTS`` edge/polygon/boundary-condition structure with kd-tree nearest-
neighbor search, ``bwdist`` initialization, and per-segment exact
distance. That full port is deferred to post-MVP phase P4 — the MVP
triangulates domains defined analytically in ``admesh.domains`` via
signed distance *functions*, so only two utilities are needed here:

- :func:`eval_sdf_grid` — sample an SDF ``fd(p)`` onto a rectangular
  grid covering the domain bounding box.
- :func:`grad_sdf` — compute the gradient of a sampled SDF with a
  4th-order central-difference stencil in the interior (matching
  MATLAB ``SignedDistanceFunction.m`` lines 202–208) and 2nd-order
  forward/backward differences at the borders.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
from numpy.typing import NDArray

Points = NDArray[np.float64]
SDF = Callable[[Points], NDArray[np.float64]]


def eval_sdf_grid(
    fd: SDF,
    bbox: tuple[float, float, float, float],
    delta: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Sample ``fd`` on a rectangular grid of spacing ``delta`` over ``bbox``.

    Returns ``(X, Y, D)`` with shape ``(LY, LX)``, matching MATLAB's
    ``meshgrid`` convention (``X`` varies along columns, ``Y`` along rows).
    """
    xmin, ymin, xmax, ymax = bbox
    xs = np.arange(xmin, xmax + 0.5 * delta, delta)
    ys = np.arange(ymin, ymax + 0.5 * delta, delta)
    X, Y = np.meshgrid(xs, ys, indexing="xy")
    pts = np.column_stack([X.ravel(), Y.ravel()])
    D = fd(pts).reshape(X.shape)
    return X, Y, D


def grad_sdf(
    D: NDArray[np.float64], delta: float
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Gradient of a sampled distance field.

    4th-order central differences in the interior (stencil
    ``[1, -8, 0, 8, -1] / (12·delta)``) and 2nd-order one-sided
    differences within two cells of each border. Matches the MATLAB
    4th-order interior stencil; the border treatment is a numerical
    convenience (MATLAB leaves the border cells at 0).
    """
    D = np.asarray(D, dtype=float)
    if D.ndim != 2:
        raise ValueError("D must be 2-D")
    LY, LX = D.shape
    gx = np.zeros_like(D)
    gy = np.zeros_like(D)

    if LX >= 5:
        gx[:, 2 : LX - 2] = (
            D[:, 0 : LX - 4] - 8 * D[:, 1 : LX - 3]
            + 8 * D[:, 3 : LX - 1] - D[:, 4:LX]
        ) / (12.0 * delta)
    if LY >= 5:
        gy[2 : LY - 2, :] = (
            D[0 : LY - 4, :] - 8 * D[1 : LY - 3, :]
            + 8 * D[3 : LY - 1, :] - D[4:LY, :]
        ) / (12.0 * delta)

    if LX >= 3:
        gx[:, 0] = (D[:, 1] - D[:, 0]) / delta
        gx[:, 1] = (D[:, 2] - D[:, 0]) / (2.0 * delta)
        gx[:, LX - 2] = (D[:, LX - 1] - D[:, LX - 3]) / (2.0 * delta)
        gx[:, LX - 1] = (D[:, LX - 1] - D[:, LX - 2]) / delta
    if LY >= 3:
        gy[0, :] = (D[1, :] - D[0, :]) / delta
        gy[1, :] = (D[2, :] - D[0, :]) / (2.0 * delta)
        gy[LY - 2, :] = (D[LY - 1, :] - D[LY - 3, :]) / (2.0 * delta)
        gy[LY - 1, :] = (D[LY - 1, :] - D[LY - 2, :]) / delta

    return gx, gy
