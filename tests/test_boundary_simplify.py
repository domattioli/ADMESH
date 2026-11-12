"""Tests for triangulate(boundary='fixed', simplify=...)."""
import dataclasses
import warnings

import numpy as np
import pytest
from scipy.spatial import cKDTree

import admesh
from admesh.boundary_relax import _simplify_ring
from admesh.loaders import _domain_from_polygon


def _dense_square(n=200):
    t = np.linspace(0, 1, n, endpoint=False)
    z, o = np.zeros(n), np.ones(n)
    return np.vstack([np.c_[t, z], np.c_[o, t], np.c_[1 - t, o], np.c_[z, 1 - t]])


def _dom(ring):
    return _domain_from_polygon([ring])


def _boundary_nodes(m):
    e = np.sort(np.vstack([m.elements[:, [0, 1]], m.elements[:, [1, 2]],
                           m.elements[:, [2, 0]]]), 1)
    u, c = np.unique(e, axis=0, return_counts=True)
    return np.unique(u[c == 1])


def test_subset_and_spacing():
    rng = np.random.default_rng(0)
    th = np.sort(rng.uniform(0, 2 * np.pi, 400))
    ring = np.c_[np.cos(th), np.sin(th)]
    tol = 0.05
    out = _simplify_ring(ring, tol)
    assert len(out) < len(ring)
    assert cKDTree(ring).query(out)[0].max() == 0.0
    d = np.linalg.norm(np.diff(out, axis=0), axis=1)
    assert d.min() >= tol - 1e-12


def test_collinear_collapses_to_corners():
    out = _simplify_ring(_dense_square(), 1e-3)
    assert len(out) == 4
    assert {tuple(p) for p in out} == {(0, 0), (1, 0), (1, 1), (0, 1)}


def test_fixed_simplify_dense_square():
    ring = _dense_square()
    h = 0.1
    m = admesh.triangulate(_dom(ring), h_max=h, seed=0, boundary="fixed",
                           simplify=0.5 * h, quality_gate=(0, 0))
    b = m.nodes[_boundary_nodes(m)]
    # every boundary node lies on the original square outline
    on = (np.isclose(b[:, 0], 0) | np.isclose(b[:, 0], 1)
          | np.isclose(b[:, 1], 0) | np.isclose(b[:, 1], 1))
    assert on.all()
    assert m.quality.min() > 0.3


def test_warning_dense_vs_coarse():
    with pytest.warns(UserWarning, match="Pass simplify="):
        admesh.triangulate(_dom(_dense_square()), h_max=0.1, seed=0,
                           boundary="fixed", quality_gate=(0, 0), channel_refine=False)
    coarse = np.array([[0, 0], [1, 0], [1, 1], [0, 1.0]])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        admesh.triangulate(_dom(coarse), h_max=0.2, seed=0,
                           boundary="fixed", quality_gate=(0, 0))


@pytest.mark.parametrize("bad", [0, -1.0])
def test_nonpositive_raises(bad):
    with pytest.raises(ValueError):
        admesh.triangulate(_dom(_dense_square(10)), h_max=0.2, simplify=bad)
