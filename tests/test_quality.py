"""Tests for admesh.quality."""

import numpy as np

from admesh.quality import mesh_quality


def test_triangle_equilateral() -> None:
    p = np.array([[0.0, 0.0], [1.0, 0.0], [0.5, np.sqrt(3) / 2]])
    t = np.array([[0, 1, 2]])
    min_q, mean_q, q = mesh_quality(p, t, element="triangle")
    np.testing.assert_allclose(q, 1.0, atol=1e-12)
    assert min_q == mean_q == q[0]


def test_triangle_degenerate_sliver() -> None:
    # Near-collinear: tiny y-offset.
    p = np.array([[0.0, 0.0], [1.0, 0.0], [0.5, 1e-6]])
    t = np.array([[0, 1, 2]])
    _, _, q = mesh_quality(p, t, element="triangle")
    assert q[0] < 0.01


def test_triangle_right_isoceles() -> None:
    # Right isoceles: sides 1, 1, sqrt(2). q = 8(s-a)(s-b)(s-c)/(abc).
    # Hand value: q ≈ 0.8284 (known)
    p = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    t = np.array([[0, 1, 2]])
    _, _, q = mesh_quality(p, t, element="triangle")
    np.testing.assert_allclose(q[0], 2.0 * (np.sqrt(2) - 1.0), atol=1e-12)


def test_triangle_multiple() -> None:
    p = np.array(
        [[0.0, 0.0], [1.0, 0.0], [0.5, np.sqrt(3) / 2], [2.0, 0.0], [2.0, 1e-6]]
    )
    t = np.array([[0, 1, 2], [1, 3, 4]])
    min_q, mean_q, q = mesh_quality(p, t, element="triangle")
    assert q.shape == (2,)
    np.testing.assert_allclose(q[0], 1.0, atol=1e-12)
    assert q[1] < 0.01
    assert min_q == q[1]
    np.testing.assert_allclose(mean_q, q.mean())


def test_quad_perfect_square() -> None:
    p = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    t = np.array([[0, 1, 2, 3]])
    min_q, mean_q, q = mesh_quality(p, t, element="quad")
    np.testing.assert_allclose(q, 1.0, atol=1e-12)
    assert min_q == mean_q == q[0]


def test_quad_degenerate() -> None:
    # Near-collinear quad.
    p = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 1e-6], [0.5, 1e-6]])
    t = np.array([[0, 1, 2, 3]])
    _, _, q = mesh_quality(p, t, element="quad")
    assert q[0] < 0.1
