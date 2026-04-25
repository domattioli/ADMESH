"""Tests for ``admesh.quality.right_iso_quality`` (spec-004 FR-006)."""

from __future__ import annotations

import numpy as np
import pytest

from admesh.quality import mesh_quality, right_iso_quality


def _tri_indices() -> np.ndarray:
    return np.array([[0, 1, 2]], dtype=np.int64)


def test_right_isoceles_unit_legs() -> None:
    # Legs of length 1 along x and y; hypotenuse = sqrt(2).
    p = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    q = right_iso_quality(p, _tri_indices())
    np.testing.assert_allclose(q, 1.0, atol=1e-12)


def test_right_isoceles_scaled() -> None:
    # Same shape, scaled by 7.5 — quality should still be 1.0.
    p = np.array([[10.0, -3.0], [17.5, -3.0], [10.0, 4.5]])
    q = right_iso_quality(p, _tri_indices())
    np.testing.assert_allclose(q, 1.0, atol=1e-12)


def test_right_isoceles_rotated() -> None:
    # Rotated by 30 degrees; quality is rotation-invariant.
    theta = np.deg2rad(30.0)
    R = np.array([[np.cos(theta), -np.sin(theta)],
                  [np.sin(theta), np.cos(theta)]])
    p_base = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    p = p_base @ R.T
    q = right_iso_quality(p, _tri_indices())
    np.testing.assert_allclose(q, 1.0, atol=1e-12)


def test_equilateral_score_below_right_iso() -> None:
    # Equilateral scores well below 1 (different target shape).
    p = np.array([[0.0, 0.0], [1.0, 0.0], [0.5, np.sqrt(3) / 2]])
    q = right_iso_quality(p, _tri_indices())
    assert 0.0 < q < 0.5  # measurably worse than right-isoceles
    # Sanity: mesh_quality (equilateral target) is ~1.0 on the same input.
    _, mq, _ = mesh_quality(p, _tri_indices(), element="triangle")
    assert mq > 0.99


def test_degenerate_collinear_low_score() -> None:
    p = np.array([[0.0, 0.0], [1.0, 0.0], [0.5, 1e-10]])
    q = right_iso_quality(p, _tri_indices())
    assert q < 1e-3


def test_empty_mesh_returns_one() -> None:
    p = np.zeros((0, 2))
    t = np.zeros((0, 3), dtype=np.int64)
    assert right_iso_quality(p, t) == 1.0


def test_mean_over_multiple_elements() -> None:
    # Two right-isoceles triangles → mean is 1.0.
    p = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0],
                  [2.0, 2.0], [3.0, 2.0], [2.0, 3.0]])
    t = np.array([[0, 1, 2], [3, 4, 5]], dtype=np.int64)
    np.testing.assert_allclose(right_iso_quality(p, t), 1.0, atol=1e-12)


def test_score_in_unit_interval_random() -> None:
    rng = np.random.default_rng(0)
    p = rng.uniform(-5.0, 5.0, size=(50, 2))
    # Build a random valid triangle index set (any 30 triples).
    idx = rng.integers(0, 50, size=(30, 3))
    # Filter degenerate (repeated index) triangles to keep input valid.
    mask = (idx[:, 0] != idx[:, 1]) & (idx[:, 1] != idx[:, 2]) & (idx[:, 0] != idx[:, 2])
    t = idx[mask].astype(np.int64)
    q = right_iso_quality(p, t)
    assert 0.0 <= q <= 1.0


def test_input_validation() -> None:
    with pytest.raises(ValueError, match=r"p must be"):
        right_iso_quality(np.zeros(5), _tri_indices())
    with pytest.raises(ValueError, match=r"t must be"):
        right_iso_quality(np.zeros((3, 2)), np.zeros((1, 4), dtype=int))


def test_does_not_mutate_inputs() -> None:
    p = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    t = _tri_indices()
    p_copy = p.copy()
    t_copy = t.copy()
    right_iso_quality(p, t)
    np.testing.assert_array_equal(p, p_copy)
    np.testing.assert_array_equal(t, t_copy)
