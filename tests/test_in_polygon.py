"""Tests for admesh.in_polygon."""

import numpy as np

from admesh.in_polygon import in_polygon


SQUARE_XV = np.array([0.0, 1.0, 1.0, 0.0])
SQUARE_YV = np.array([0.0, 0.0, 1.0, 1.0])


def test_point_strictly_inside() -> None:
    inside, on = in_polygon(0.5, 0.5, SQUARE_XV, SQUARE_YV)
    assert inside
    assert not on


def test_point_outside() -> None:
    inside, on = in_polygon(1.5, 0.5, SQUARE_XV, SQUARE_YV)
    assert not inside
    assert not on


def test_point_on_edge() -> None:
    inside, on = in_polygon(0.5, 0.0, SQUARE_XV, SQUARE_YV)
    assert inside  # MATLAB inpolygon: boundary points are "in"
    assert on


def test_point_on_vertex() -> None:
    inside, on = in_polygon(0.0, 0.0, SQUARE_XV, SQUARE_YV)
    assert inside
    assert on


def test_vectorized() -> None:
    xq = np.array([0.5, 1.5, 0.5, -0.1])
    yq = np.array([0.5, 0.5, 0.0, 0.5])
    inside, on = in_polygon(xq, yq, SQUARE_XV, SQUARE_YV)
    np.testing.assert_array_equal(inside, [True, False, True, False])
    np.testing.assert_array_equal(on, [False, False, True, False])


def test_nonconvex_l_shape() -> None:
    # L: square [0,2]^2 minus the top-right (1,2]x(1,2] quadrant.
    xv = [0.0, 2.0, 2.0, 1.0, 1.0, 0.0]
    yv = [0.0, 0.0, 1.0, 1.0, 2.0, 2.0]
    # (1.5, 1.5) is inside the notch (outside the L).
    inside, _ = in_polygon(1.5, 1.5, xv, yv)
    assert not inside
    # (0.5, 1.5) is inside the upper-left arm.
    inside, _ = in_polygon(0.5, 1.5, xv, yv)
    assert inside


def test_closed_polygon_accepted() -> None:
    # Explicit closing vertex must not break the test.
    xv = np.array([0.0, 1.0, 1.0, 0.0, 0.0])
    yv = np.array([0.0, 0.0, 1.0, 1.0, 0.0])
    inside, _ = in_polygon(0.5, 0.5, xv, yv)
    assert inside


def test_shape_preserved() -> None:
    xq = np.array([[0.5, 1.5], [0.2, -0.5]])
    yq = np.array([[0.5, 0.5], [0.2, 0.2]])
    inside, on = in_polygon(xq, yq, SQUARE_XV, SQUARE_YV)
    assert inside.shape == xq.shape
    assert on.shape == xq.shape
