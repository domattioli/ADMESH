"""Tests for admesh.distance."""

import numpy as np

from admesh import domains
from admesh.distance import eval_sdf_grid, grad_sdf


def test_eval_sdf_grid_unit_disk() -> None:
    X, Y, D = eval_sdf_grid(domains.UNIT_DISK.fd, (-1.0, -1.0, 1.0, 1.0), 0.1)
    assert X.shape == Y.shape == D.shape
    # Center is deepest inside.
    mid = (X.shape[0] // 2, X.shape[1] // 2)
    assert D[mid] < 0
    # Corner is outside.
    assert D[0, 0] > 0
    # Distance at center equals -1 (we're at (0, 0) for a unit-disk SDF).
    np.testing.assert_allclose(D[mid], -1.0, atol=1e-12)


def test_eval_sdf_grid_shape_matches_meshgrid() -> None:
    X, Y, D = eval_sdf_grid(domains.UNIT_SQUARE.fd, (-0.5, -0.5, 0.5, 0.5), 0.25)
    # With delta=0.25 over [-0.5, 0.5], expect 5 points each way.
    assert D.shape == (5, 5)
    # X varies along columns (MATLAB meshgrid convention).
    np.testing.assert_allclose(X[0, :], [-0.5, -0.25, 0.0, 0.25, 0.5])
    np.testing.assert_allclose(Y[:, 0], [-0.5, -0.25, 0.0, 0.25, 0.5])


def test_grad_sdf_linear_field() -> None:
    # D(x, y) = 3x + 0y → grad = (3, 0) everywhere in interior.
    delta = 0.1
    xs = np.arange(-1, 1 + 0.5 * delta, delta)
    ys = np.arange(-1, 1 + 0.5 * delta, delta)
    X, _ = np.meshgrid(xs, ys, indexing="xy")
    D = 3.0 * X
    gx, gy = grad_sdf(D, delta)
    # Central stencil region should be essentially exact.
    np.testing.assert_allclose(gx[2:-2, 2:-2], 3.0, atol=1e-12)
    np.testing.assert_allclose(gy[2:-2, 2:-2], 0.0, atol=1e-12)


def test_grad_sdf_magnitude_one_for_true_sdf() -> None:
    # A true SDF satisfies |grad D| = 1. Use a disk SDF on a fine grid.
    delta = 0.05
    X, Y, D = eval_sdf_grid(domains.UNIT_DISK.fd, (-2.0, -2.0, 2.0, 2.0), delta)
    gx, gy = grad_sdf(D, delta)
    # Sample interior points well away from origin singularity.
    mag = np.hypot(gx[3:-3, 3:-3], gy[3:-3, 3:-3])
    # Mask out near the origin (|p| ~ 0 has singular gradient).
    R = np.hypot(X[3:-3, 3:-3], Y[3:-3, 3:-3])
    ok = R > 0.3
    np.testing.assert_allclose(mag[ok], 1.0, atol=5e-3)
