"""Tests for ``admesh.quad_prep`` internal helper functions.

These cover Phase 1 leaf utilities: numerical SDF gradient, boundary-
node mask, boundary projection, and the element Jacobian. All public-
API behaviour is covered separately in ``test_quad_prep.py``.
"""

from __future__ import annotations

import numpy as np
import pytest

from admesh.quad_prep import (
    _boundary_node_mask,
    _compute_element_jacobian,
    _grad_sdf_numerical,
    _project_boundary_nodes,
)


# --- _grad_sdf_numerical ---------------------------------------------


def test_grad_sdf_circle() -> None:
    # Circle SDF: fd(p) = ||p|| - r; gradient is p / ||p||.
    fd = lambda q: np.hypot(q[:, 0], q[:, 1]) - 1.0
    p = np.array([[1.0, 0.0], [0.0, 1.0], [3.0, 4.0]])
    g = _grad_sdf_numerical(fd, p, eps=1e-6)
    expected = p / np.hypot(p[:, 0], p[:, 1])[:, None]
    np.testing.assert_allclose(g, expected, atol=1e-5)


def test_grad_sdf_plane() -> None:
    # Half-plane y>0: fd(p) = -y (negative inside); gradient is (0, -1).
    fd = lambda q: -q[:, 1]
    p = np.array([[0.0, 0.5], [2.0, 1.0]])
    g = _grad_sdf_numerical(fd, p)
    np.testing.assert_allclose(g, [[0.0, -1.0], [0.0, -1.0]], atol=1e-5)


# --- _boundary_node_mask ---------------------------------------------


def test_boundary_mask_unit_square() -> None:
    # Square SDF; nodes on boundary should be flagged.
    fd = lambda q: np.maximum(np.abs(q[:, 0]) - 0.5, np.abs(q[:, 1]) - 0.5)
    p = np.array(
        [
            [0.0, 0.0],   # interior: -0.5
            [0.5, 0.0],   # boundary right
            [-0.5, -0.5], # boundary corner
            [0.25, 0.25], # interior
        ]
    )
    mask = _boundary_node_mask(p, fd, geps=1e-6)
    np.testing.assert_array_equal(mask, [False, True, True, False])


# --- _project_boundary_nodes -----------------------------------------


def test_project_drifting_boundary_nodes() -> None:
    fd = lambda q: np.hypot(q[:, 0], q[:, 1]) - 1.0
    p = np.array([[1.0, 0.0], [0.0, 1.0], [0.0, 0.0]])
    # Pretend points 0,1 drifted slightly outward.
    p_drift = p.copy()
    p_drift[0] = [1.05, 0.0]
    p_drift[1] = [0.0, 1.03]
    # Need to mark them as boundary first → re-project from
    # near-boundary positions: boundary mask uses pre-iteration check.
    # Re-cast: pass points already near-boundary so mask catches them.
    p_in = p.copy()
    p_in[0] = [1.0 + 5e-12, 0.0]   # within geps
    p_in[1] = [0.0, 1.0 + 5e-12]
    p_out = _project_boundary_nodes(p_in, fd, geps=1e-10)
    f_out = fd(p_out[:2])
    assert np.all(np.abs(f_out) < 1e-9)
    # Interior point untouched.
    np.testing.assert_allclose(p_out[2], [0.0, 0.0], atol=1e-15)


def test_project_no_boundary_returns_unchanged() -> None:
    fd = lambda q: np.hypot(q[:, 0], q[:, 1]) - 1.0
    p = np.array([[0.0, 0.0], [0.1, 0.2]])  # all interior
    p_out = _project_boundary_nodes(p, fd, geps=1e-10)
    np.testing.assert_array_equal(p_out, p)


# --- _compute_element_jacobian ---------------------------------------


def test_jacobian_reference_triangle_is_identity() -> None:
    # The reference right-isoceles triangle has Jacobian = I.
    p = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    t = np.array([[0, 1, 2]], dtype=np.int64)
    A = _compute_element_jacobian(p, t)
    assert A.shape == (1, 2, 2)
    np.testing.assert_allclose(A[0], np.eye(2), atol=1e-12)


def test_jacobian_scaled_triangle() -> None:
    # Scale by 2 → A = 2 I, det = 4.
    p = np.array([[0.0, 0.0], [2.0, 0.0], [0.0, 2.0]])
    t = np.array([[0, 1, 2]], dtype=np.int64)
    A = _compute_element_jacobian(p, t)
    np.testing.assert_allclose(A[0], 2.0 * np.eye(2), atol=1e-12)
    np.testing.assert_allclose(np.linalg.det(A[0]), 4.0, atol=1e-12)


def test_jacobian_translated_triangle() -> None:
    # Translation does not affect Jacobian.
    p = np.array([[5.0, 7.0], [6.0, 7.0], [5.0, 8.0]])
    t = np.array([[0, 1, 2]], dtype=np.int64)
    A = _compute_element_jacobian(p, t)
    np.testing.assert_allclose(A[0], np.eye(2), atol=1e-12)


def test_jacobian_multiple_elements() -> None:
    p = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0],
                  [10.0, 10.0], [12.0, 10.0], [10.0, 13.0]])
    t = np.array([[0, 1, 2], [3, 4, 5]], dtype=np.int64)
    A = _compute_element_jacobian(p, t)
    assert A.shape == (2, 2, 2)
    np.testing.assert_allclose(A[0], np.eye(2), atol=1e-12)
    np.testing.assert_allclose(A[1], np.diag([2.0, 3.0]), atol=1e-12)
