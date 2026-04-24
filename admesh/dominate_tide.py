"""Tidal-wavelength mesh-size contribution.

Faithful port of ``01_ADMESH_Library/07_Dominate_Tide/
Dominate_tide.m`` @ ``19b2eb9``.

Shallow-water wave theory gives the wavelength of a long wave
propagating at depth ``|Z|`` as ``λ = √(g·|Z|) · T`` where ``T`` is
the tidal period. Resolving the wave with ``sz`` elements per
wavelength yields

    h_tide = (T / sz) · √(g · |Z|)

which is MATLAB line 35 exactly. The result is clipped to
``[hmin, hmax]`` and composed via elementwise ``min`` into the
running ``h0`` field.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

# MATLAB line 33: ``g = 9.81; % gravity (m/s^2)``.
_G = 9.81


def apply_tide(
    h0: NDArray[np.float64],
    Z: NDArray[np.float64],
    *,
    tide_period: float,
    tide_value: float,
    hmin: float,
    hmax: float,
) -> NDArray[np.float64]:
    """Apply tidal-wavelength mesh-size contribution.

    Port of ``01_ADMESH_Library/07_Dominate_Tide/Dominate_tide.m`` @
    ``19b2eb9``.

    Parameters
    ----------
    h0 : (LY, LX) ndarray
        Current mesh-size field; composed via ``min(h_tide, h0)``
        (MATLAB line 44).
    Z : (LY, LX) ndarray
        Bathymetric elevation on the grid (signed depth; MATLAB uses
        ``abs(Z)`` in the wavelength formula).
    tide_period : float
        Dominant tidal period ``T`` (seconds). MATLAB arg
        ``Tide_Period``.
    tide_value : float
        Number of elements per tidal wavelength ``sz`` (MATLAB arg
        ``tide_value``).
    hmin, hmax : float
        Clipping bounds (MATLAB lines 40-41). Where ``Z == 0`` the
        formula yields ``h_tide = 0`` which MATLAB line 37 promotes
        to ``hmax``.

    Returns
    -------
    h_out : (LY, LX) ndarray
        Composed mesh-size field (new array).
    """
    h0 = np.asarray(h0, dtype=np.float64)
    Z = np.asarray(Z, dtype=np.float64)
    if h0.shape != Z.shape:
        raise ValueError("h0 and Z must share shape")
    if tide_value <= 0:
        raise ValueError("tide_value must be positive")

    # MATLAB line 35.
    h_tide = (tide_period / tide_value) * np.sqrt(_G * np.abs(Z))

    # MATLAB line 37: h_tide(h_tide == 0) = hmax (avoids zero-sizing in
    # land cells where Z == 0).
    h_tide = np.where(h_tide == 0.0, hmax, h_tide)

    # MATLAB lines 40-41.
    np.clip(h_tide, hmin, hmax, out=h_tide)

    # MATLAB line 44.
    return np.minimum(h_tide, h0)
