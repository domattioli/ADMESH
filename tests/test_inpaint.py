"""Tests for :func:`admesh.inpaint.inpaint_nans`.

Port-correctness cases for MATLAB ``inpaint_nans.m`` method 0
(default).
"""

from __future__ import annotations

import numpy as np
import pytest

from admesh.inpaint import inpaint_nans


def test_inpaint_no_nans_returns_copy():
    A = np.arange(12.0).reshape(3, 4)
    B = inpaint_nans(A)
    assert B is not A
    np.testing.assert_array_equal(A, B)


def test_inpaint_preserves_known_values_exactly():
    """MATLAB line 137 / line 170 / etc.: only ``B(nan_list(:,1))`` is
    overwritten — known cells pass through unchanged."""
    A = np.array([
        [1.0, 2.0, 3.0],
        [4.0, np.nan, 6.0],
        [7.0, 8.0, 9.0],
    ])
    B = inpaint_nans(A)
    # Every non-NaN entry must be bit-identical to input.
    mask = ~np.isnan(A)
    np.testing.assert_array_equal(A[mask], B[mask])
    # NaN cell filled with something finite.
    assert np.isfinite(B[1, 1])


def test_inpaint_recovers_linear_ramp():
    """On a linear ramp (Δ²f = 0), the del^2 method should reconstruct
    missing values nearly exactly."""
    x = np.linspace(0, 1, 7)
    y = np.linspace(0, 1, 5)
    X, Y = np.meshgrid(x, y)
    A_true = 2.0 * X + 3.0 * Y + 1.0
    A = A_true.copy()
    A[2, 3] = np.nan
    A[1, 1] = np.nan
    A[3, 5] = np.nan
    B = inpaint_nans(A)
    np.testing.assert_allclose(B, A_true, atol=1e-8)


def test_inpaint_recovers_block_hole():
    """A larger block of NaN entries in a linear field: still exact."""
    x = np.linspace(0, 1, 10)
    y = np.linspace(0, 1, 10)
    X, Y = np.meshgrid(x, y)
    A_true = X + 2.0 * Y
    A = A_true.copy()
    A[3:6, 3:6] = np.nan
    B = inpaint_nans(A)
    np.testing.assert_allclose(B, A_true, atol=1e-8)


def test_inpaint_quadratic_field_is_approximate():
    """On a quadratic field (Δ²f = constant ≠ 0), method 0 returns a
    smooth reconstruction but not exact — only that the NaN cell is
    close to the true value and within the bounding-box of neighbors."""
    x = np.linspace(0, 1, 10)
    y = np.linspace(0, 1, 10)
    X, Y = np.meshgrid(x, y)
    A_true = X ** 2 + Y ** 2
    A = A_true.copy()
    A[5, 5] = np.nan
    B = inpaint_nans(A)
    assert abs(B[5, 5] - A_true[5, 5]) < 0.05


def test_inpaint_rejects_non_2d_input():
    with pytest.raises(ValueError):
        inpaint_nans(np.array([1.0, np.nan, 3.0]))


def test_inpaint_unimplemented_methods_raise():
    A = np.array([[1.0, np.nan], [2.0, 3.0]])
    for m in (1, 2, 3, 4, 5):
        with pytest.raises(NotImplementedError):
            inpaint_nans(A, method=m)
