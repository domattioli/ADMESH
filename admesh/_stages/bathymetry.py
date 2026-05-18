"""Bathymetry-driven mesh-size contribution.

Faithful port of ``01_ADMESH_Library/06_Bathymetry_Function/`` @
``19b2eb9``:

- :func:`create_elevation_grid` — port of ``CreateElevationGrid.m``.
  Samples a user-supplied ``xyzFun(X, Y) -> Z`` onto a background
  grid and fills any NaN gaps via :func:`admesh.inpaint.inpaint_nans`.
- :func:`apply_bathymetry` — port of ``BathymetryFunction.m``.
  Computes ``h_bathy = s · |Z| / |∇Z|``, clips to ``[hmin, hmax]``,
  optionally masks the boundary band to ``hmax`` (when the curvature
  stage is active), and composes via ``h0 = min(h_bathy, h0)``.

The ``h_bathy`` formula (MATLAB line 112) comes from the ADCIRC
mesh-generation literature (Bilgili et al., 2006): resolve the
bathymetric gradient at ``s`` elements per e-folding depth change,
so that cells with rapidly varying depth get smaller edge lengths.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
from numpy.typing import NDArray

from admesh._stages.inpaint import inpaint_nans

Points = NDArray[np.float64]
XYZFun = Callable[[NDArray[np.float64], NDArray[np.float64]], NDArray[np.float64]]


def create_elevation_grid(
    X: NDArray[np.float64],
    Y: NDArray[np.float64],
    xyz_fun: XYZFun | None,
) -> NDArray[np.float64] | None:
    """Sample a bathymetry function onto the background grid.

    Port of ``01_ADMESH_Library/06_Bathymetry_Function/
    CreateElevationGrid.m`` @ ``19b2eb9``.

    Parameters
    ----------
    X, Y : (LY, LX) ndarrays
        Background grid coordinates.
    xyz_fun : callable ``(X, Y) -> Z`` or None
        Bathymetry interpolant. If ``None`` (analogous to MATLAB
        ``isempty(xyzFun)``), returns ``None`` (MATLAB line 25:
        ``Z = []``).

    Returns
    -------
    Z : (LY, LX) ndarray or None
        Bathymetric elevation sampled on the grid. If ``xyz_fun``
        returned any NaNs, they are filled via ``inpaint_nans``
        (MATLAB line 19-21).
    """
    if xyz_fun is None:
        return None
    Z = np.asarray(xyz_fun(X, Y), dtype=np.float64)
    if Z.shape != X.shape:
        raise ValueError(
            f"xyz_fun returned shape {Z.shape}; expected {X.shape}"
        )
    if np.isnan(Z).any():
        Z = inpaint_nans(Z)
    return Z


def apply_bathymetry(
    h0: NDArray[np.float64],
    D: NDArray[np.float64],
    Z: NDArray[np.float64],
    delta: float,
    *,
    s: float,
    hmin: float,
    hmax: float,
    mask_boundary_band: bool = True,
) -> NDArray[np.float64]:
    """Apply bathymetric mesh-size contribution.

    Port of ``01_ADMESH_Library/06_Bathymetry_Function/
    BathymetryFunction.m`` @ ``19b2eb9``.

    Parameters
    ----------
    h0 : (LY, LX) ndarray
        Current mesh-size field; ``h_bathy`` is composed in via
        elementwise ``min`` (MATLAB line 129).
    D : (LY, LX) ndarray
        Signed distance function (interior ``D < 0``).
    Z : (LY, LX) ndarray
        Bathymetric elevation on the grid (typically from
        :func:`create_elevation_grid`).
    delta : float
        Grid spacing.
    s : float
        Bathymetry mesh-size factor (MATLAB arg ``s``). Larger ``s``
        requests finer resolution of depth gradients.
    hmin, hmax : float
        Clipping bounds (MATLAB lines 115-116).
    mask_boundary_band : bool, default True
        When True, cells in the near-boundary band + exterior
        (``D >= -4·hmin``) are pinned to ``hmax`` — MATLAB line 121,
        active when ``Settings.K.Status == 'On'`` (curvature stage
        active). The curvature stage owns that band; bathymetry only
        drives sizing deep in the interior. Set False to let
        bathymetry drive sizing everywhere (MATLAB ``Settings.K =
        'Off'``).

    Returns
    -------
    h_out : (LY, LX) ndarray
        Composed mesh-size field (new array).
    """
    h0 = np.asarray(h0, dtype=np.float64)
    D = np.asarray(D, dtype=np.float64)
    Z = np.asarray(Z, dtype=np.float64)
    if h0.shape != D.shape or h0.shape != Z.shape:
        raise ValueError("h0, D, Z must share shape")

    LY, LX = Z.shape
    gradBx = np.zeros_like(Z)
    gradBy = np.zeros_like(Z)

    # MATLAB lines 51-55: 4th-order central difference on interior
    # [3:LY-2, 3:LX-2] (1-based). Python 0-based: [2:LY-2, 2:LX-2].
    # Stencil: ( 1·f[i-2] - 8·f[i-1] + 8·f[i+1] - 1·f[i+2] ) / (12·h).
    if LX >= 5 and LY >= 5:
        gradBx[2:LY - 2, 2:LX - 2] = (
            Z[2:LY - 2, 0:LX - 4]
            - 8.0 * Z[2:LY - 2, 1:LX - 3]
            + 8.0 * Z[2:LY - 2, 3:LX - 1]
            - Z[2:LY - 2, 4:LX]
        ) / (12.0 * delta)
        gradBy[2:LY - 2, 2:LX - 2] = (
            Z[0:LY - 4, 2:LX - 2]
            - 8.0 * Z[1:LY - 3, 2:LX - 2]
            + 8.0 * Z[3:LY - 1, 2:LX - 2]
            - Z[4:LY, 2:LX - 2]
        ) / (12.0 * delta)

    # MATLAB line 112: h_bathy = s * |Z| / |∇Z|. Guard against divide-by-zero
    # where the gradient is exactly zero (typically the boundary strip MATLAB
    # leaves at 0 via its narrower stencil support).
    grad_mag = np.hypot(gradBx, gradBy)
    with np.errstate(divide="ignore", invalid="ignore"):
        h_bathy = s * np.abs(Z) / grad_mag
    # Where gradient is ~0 (or Z is 0 giving 0/0), h_bathy is "unconstrained" —
    # set to hmax so min(h_bathy, h0) leaves h0 untouched there.
    h_bathy = np.where(np.isfinite(h_bathy), h_bathy, hmax)

    # MATLAB lines 115-116.
    np.clip(h_bathy, hmin, hmax, out=h_bathy)

    # MATLAB line 121: mask boundary band + exterior to hmax (curvature
    # stage owns sizing there).
    if mask_boundary_band:
        h_bathy[D >= -4.0 * hmin] = hmax

    # MATLAB line 129: compose.
    return np.minimum(h_bathy, h0)
