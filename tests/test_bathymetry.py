"""Tests for :mod:`admesh.bathymetry`.

Port-correctness cases for MATLAB ``BathymetryFunction.m`` +
``CreateElevationGrid.m``.
"""

from __future__ import annotations

import numpy as np
import pytest

from admesh.bathymetry import apply_bathymetry, create_elevation_grid


def test_create_elevation_grid_none_returns_none():
    X, Y = np.meshgrid(np.linspace(0, 1, 5), np.linspace(0, 1, 5))
    assert create_elevation_grid(X, Y, None) is None


def test_create_elevation_grid_samples_function():
    X, Y = np.meshgrid(np.linspace(0, 1, 5), np.linspace(0, 1, 5))
    Z = create_elevation_grid(X, Y, lambda xx, yy: 2.0 * xx + yy)
    np.testing.assert_allclose(Z, 2.0 * X + Y)


def test_create_elevation_grid_inpaints_nans():
    X, Y = np.meshgrid(np.linspace(0, 1, 7), np.linspace(0, 1, 5))
    def xyz(xx, yy):
        Z = 2.0 * xx + yy
        Z[2, 3] = np.nan
        return Z
    Z = create_elevation_grid(X, Y, xyz)
    assert not np.isnan(Z).any()
    # Linear field → inpaint reconstructs exactly.
    np.testing.assert_allclose(Z[2, 3], 2.0 * X[2, 3] + Y[2, 3], atol=1e-8)


def test_apply_bathymetry_zero_gradient_leaves_h0_alone():
    """|∇Z| = 0 everywhere → h_bathy = inf → clipped to hmax → min(hmax, h0)=h0."""
    xs = np.linspace(0, 1, 10)
    X, Y = np.meshgrid(xs, xs)
    Z = np.full_like(X, 5.0)  # constant depth
    D = -np.ones_like(X)  # deep interior everywhere
    h0 = np.full_like(X, 0.3)
    h = apply_bathymetry(
        h0, D, Z, delta=xs[1] - xs[0], s=0.1, hmin=0.01, hmax=1.0,
        mask_boundary_band=False,
    )
    np.testing.assert_allclose(h, h0)


def test_apply_bathymetry_formula_reduces_h_on_gradient():
    """MATLAB line 112: h_bathy = s * |Z| / |∇Z|.

    Linear ramp Z = 10x, |∇Z|=10 (x-direction), |Z|=|10x|. In the
    interior (4th-order stencil window), h_bathy = s * |x|. So near
    x=0, h_bathy → 0 (clipped to hmin); near x=1, h_bathy → s.
    """
    xs = np.linspace(0.0, 1.0, 15)
    ys = np.linspace(0.0, 1.0, 15)
    X, Y = np.meshgrid(xs, ys, indexing="xy")
    Z = 10.0 * X
    D = -np.ones_like(X)
    h0 = np.full_like(X, 1.0)
    s = 0.2
    hmin, hmax = 0.01, 1.0
    h = apply_bathymetry(
        h0, D, Z, delta=xs[1] - xs[0], s=s, hmin=hmin, hmax=hmax,
        mask_boundary_band=False,
    )
    # Interior cell at x≈1 (col LX-3): h ≈ s * 1.0 = 0.2 (within clip).
    LY, LX = Z.shape
    ic_far = LX - 3
    ic_near = 2  # left interior col
    jc = LY // 2
    # At x≈0 (col 2, x≈0.143): h ≈ s * 0.143 ≈ 0.029.
    assert h[jc, ic_near] < 0.1
    # At x≈1: h ≈ 0.2.
    assert abs(h[jc, ic_far] - s * X[jc, ic_far]) < 0.05


def test_apply_bathymetry_mask_boundary_band():
    """MATLAB line 121: D >= -4*hmin cells forced to hmax when mask on."""
    xs = np.linspace(0.0, 1.0, 15)
    X, Y = np.meshgrid(xs, xs, indexing="xy")
    Z = 10.0 * X
    # Near-boundary strip: rightmost cells have D ~ -0.01 (shallow interior).
    D = np.full_like(X, -1.0)
    D[:, -3:] = -0.02  # shallow near right edge
    hmin, hmax = 0.05, 1.0
    h0 = np.full_like(X, 0.5)
    h = apply_bathymetry(
        h0, D, Z, delta=xs[1] - xs[0], s=0.1, hmin=hmin, hmax=hmax,
        mask_boundary_band=True,
    )
    # Shallow cells: D = -0.02 >= -4*hmin = -0.2 → h_bathy[these] = hmax = 1.
    # After min(h_bathy, h0=0.5): h = 0.5. Deep cells may get reduced by
    # the bathymetry gradient term.
    assert (h[:, -3:] == 0.5).all()


def test_apply_bathymetry_rejects_shape_mismatch():
    h0 = np.zeros((3, 3))
    D = np.zeros((3, 3))
    Z = np.zeros((4, 4))
    with pytest.raises(ValueError):
        apply_bathymetry(h0, D, Z, delta=1.0, s=0.1, hmin=0.01, hmax=1.0)
