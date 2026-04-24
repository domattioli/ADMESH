"""Tests for :mod:`admesh.dominate_tide`.

Port-correctness cases for MATLAB ``Dominate_tide.m``.
"""

from __future__ import annotations

import numpy as np
import pytest

from admesh.dominate_tide import apply_tide


def test_apply_tide_wavelength_formula():
    """h_tide = (T/sz) * sqrt(g * |Z|), g=9.81."""
    T = 44712.0  # M2 semidiurnal period (s) ≈ 12.42 h
    sz = 100.0
    Z = np.array([[100.0, 25.0], [4.0, 0.0]])
    h0 = np.full_like(Z, 1e6)
    h = apply_tide(
        h0, Z, tide_period=T, tide_value=sz, hmin=0.0, hmax=1e6,
    )
    # At Z=100m: h = (44712/100) * sqrt(981) ≈ 447.12 * 31.32 ≈ 14003.
    assert h[0, 0] == pytest.approx(447.12 * np.sqrt(9.81 * 100.0), rel=1e-6)
    # At Z=0: h = 0 → promoted to hmax = 1e6.
    assert h[1, 1] == 1e6


def test_apply_tide_clipping():
    T = 10.0
    # Z values chosen so h_tide straddles hmin and hmax.
    # At Z=1000: h = 10*sqrt(9810) ≈ 990 → > hmax=10 → clipped.
    # At Z=1e-4: h = 10*sqrt(9.81e-4) ≈ 0.31 → < hmin=1 → clipped.
    Z = np.array([[1000.0], [1e-4]])
    h0 = np.full_like(Z, 1e6)
    h = apply_tide(
        h0, Z, tide_period=T, tide_value=1.0, hmin=1.0, hmax=10.0,
    )
    assert h[0, 0] == 10.0
    assert h[1, 0] == 1.0


def test_apply_tide_composes_with_min():
    """MATLAB line 44: h0 = min(h_tide, h0)."""
    Z = np.array([[1.0]])
    h0 = np.array([[0.5]])
    h = apply_tide(
        h0, Z, tide_period=10.0, tide_value=1.0, hmin=0.01, hmax=10.0,
    )
    # h_tide = 10 * sqrt(9.81) ≈ 31.3 → clipped to hmax=10 → min with h0=0.5 → 0.5.
    assert h[0, 0] == 0.5


def test_apply_tide_rejects_zero_tide_value():
    Z = np.ones((2, 2))
    h0 = np.ones((2, 2))
    with pytest.raises(ValueError):
        apply_tide(h0, Z, tide_period=1.0, tide_value=0.0, hmin=0.0, hmax=1.0)


def test_apply_tide_rejects_shape_mismatch():
    Z = np.ones((2, 3))
    h0 = np.ones((2, 2))
    with pytest.raises(ValueError):
        apply_tide(h0, Z, tide_period=1.0, tide_value=1.0, hmin=0.0, hmax=1.0)


def test_apply_tide_abs_Z_used():
    """MATLAB line 35 uses abs(Z); negative depths (sign convention) are fine."""
    Z = np.array([[-100.0, 100.0]])
    h0 = np.full_like(Z, 1e6)
    h = apply_tide(
        h0, Z, tide_period=100.0, tide_value=1.0, hmin=0.0, hmax=1e9,
    )
    # Both entries should be equal since |Z| is used.
    assert h[0, 0] == pytest.approx(h[0, 1], rel=1e-12)
