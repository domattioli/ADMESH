"""Tests for admesh.boundary_relax and triangulate(boundary=...) (API layer)."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

import admesh
from admesh.boundary_relax import relax_ring, relax_rings, ring_arclength
from admesh.loaders import _domain_from_polygon

SQUARE = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=float)
LSHAPE = np.array(
    [[0, 0], [2, 0], [2, 1], [1, 1], [1, 2], [0, 2]], dtype=float
)


def _graded(pts):
    pts = np.atleast_2d(pts)
    return 0.04 + 0.12 * np.clip(pts[:, 0] / 2.0, 0.0, 1.0)


def _bars(ring, xy):
    s = np.sort(ring_arclength(ring, xy))
    L = float(np.linalg.norm(np.diff(np.vstack([ring, ring[:1]]), axis=0), axis=1).sum())
    ext = np.append(s, s[0] + L)
    return ext[:-1], np.diff(ext), 0.5 * (ext[:-1] + ext[1:])


def _on_polyline(ring, xy):
    return float(_ring_dist(ring, xy).max())


def _ring_dist(ring, xy):
    a = ring
    b = np.roll(ring, -1, axis=0)
    d = b - a
    w = xy[:, None, :] - a[None]
    t = np.clip((w * d[None]).sum(2) / (d ** 2).sum(1)[None], 0, 1)
    q = a[None] + t[..., None] * d[None]
    return np.linalg.norm(xy[:, None, :] - q, axis=2).min(axis=1)


def test_uniform_square_spacing_converges_to_h():
    h = 0.07
    xy = relax_ring(SQUARE, None, h)
    assert _on_polyline(SQUARE, xy) < 1e-12
    s, l, _ = _bars(SQUARE, xy)
    ratio = l / h
    assert 0.6 <= ratio.min() and ratio.max() <= 1.6
    assert abs(ratio.mean() - 1.0) < 0.15


def test_graded_spacing_follows_size_field():
    xy = relax_ring(LSHAPE, _graded, 0.04)
    s, l, mid_s = _bars(LSHAPE, xy)
    # evaluate h at bar midpoints on the polyline
    cum = np.concatenate([[0], np.cumsum(np.linalg.norm(
        np.diff(np.vstack([LSHAPE, LSHAPE[:1]]), axis=0), axis=1))])
    closed = np.vstack([LSHAPE, LSHAPE[:1]])
    mid_xy = np.column_stack([np.interp(mid_s % cum[-1], cum, closed[:, 0]),
                              np.interp(mid_s % cum[-1], cum, closed[:, 1])])
    ratio = l / _graded(mid_xy)
    assert 0.6 <= ratio.min() and ratio.max() <= 1.6
    assert abs(ratio.mean() - 1.0) < 0.2


def test_corners_preserved_exactly():
    xy = relax_ring(LSHAPE, _graded, 0.04)
    for v in LSHAPE:
        assert np.min(np.linalg.norm(xy - v, axis=1)) == 0.0


def test_user_pin_on_ring_is_kept():
    pin = np.array([[0.5, 0.0]])
    xy = relax_ring(SQUARE, None, 0.07, pinned_points=pin)
    assert np.min(np.linalg.norm(xy - pin[0], axis=1)) < 1e-12


def test_history_and_relax_rings():
    xy, hist = relax_ring(SQUARE, None, 0.1, record_history=True)
    assert len(hist) >= 2 and np.array_equal(hist[-1], xy)
    out = relax_rings([SQUARE, 0.3 + 0.2 * SQUARE], None, 0.1)
    assert len(out) == 2


def _domain(ring):
    return dataclasses.replace(_domain_from_polygon([ring]), pts=ring)


def _check_valid(mesh):
    n, t = mesh.nodes, mesh.elements
    d1, d2 = n[t[:, 1]] - n[t[:, 0]], n[t[:, 2]] - n[t[:, 0]]
    assert ((d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / 2 > 0).all()
    e = np.sort(np.vstack([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]]), axis=1)
    _, cnt = np.unique(e, axis=0, return_counts=True)
    assert cnt.max() <= 2
    uniq, cnt = np.unique(e, axis=0, return_counts=True)
    bedges = uniq[cnt == 1]
    # watertight: boundary edges form closed loops (each node degree 2)
    deg = np.bincount(bedges.ravel(), minlength=len(n))
    assert set(np.unique(deg[deg > 0])) == {2}
    return n[np.unique(bedges)]


@pytest.mark.parametrize("ring", [SQUARE, LSHAPE])
def test_fixed_mode_keeps_vertices_and_boundary_on_polyline(ring):
    dom = _domain(ring)
    m = admesh.triangulate(dom, h_max=0.15, size_field=lambda p: np.full(len(p), 0.15),
                           seed=0, quality_gate=(0.0, 0.0))
    bnodes = _check_valid(m)
    for v in ring:
        assert np.min(np.linalg.norm(m.nodes - v, axis=1)) == 0.0
    assert _on_polyline(ring, bnodes) < 1e-9


def test_fixed_mode_graded():
    dom = _domain(LSHAPE)
    m = admesh.triangulate(dom, h_max=0.16, size_field=_graded, seed=0,
                           quality_gate=(0.0, 0.0))
    bnodes = _check_valid(m)
    assert _on_polyline(LSHAPE, bnodes) < 1e-9
    for v in LSHAPE:
        assert np.min(np.linalg.norm(m.nodes - v, axis=1)) == 0.0


def test_free_mode_still_works():
    dom = _domain(SQUARE)
    m = admesh.triangulate(dom, h_max=0.15, seed=0, boundary="free",
                           quality_gate=(0.0, 0.0))
    assert len(m.elements) > 0
    _check_valid(m)


def test_slide_and_bad_values_raise():
    dom = _domain(SQUARE)
    with pytest.raises(ValueError, match="not implemented"):
        admesh.triangulate(dom, h_max=0.2, boundary="slide")
    with pytest.raises(ValueError):
        admesh.triangulate(dom, h_max=0.2, boundary="bogus")


def test_fixed_mode_boundary_nodes_are_exactly_ring_nodes():
    from collections import Counter

    from scipy.spatial import cKDTree

    xy = relax_ring(LSHAPE, _graded, 0.15, init="random", rng_seed=7, max_iter=300)
    dom = dataclasses.replace(_domain_from_polygon([LSHAPE]), pts=xy)
    m = admesh.triangulate(dom, h_max=0.15, size_field=_graded, seed=0,
                           boundary="fixed", quality_gate=(0, 0))
    e = np.sort(np.vstack([m.elements[:, [0, 1]], m.elements[:, [1, 2]],
                           m.elements[:, [2, 0]]]), axis=1)
    cnt = Counter(map(tuple, e))
    bnd = np.unique([v for k, n in cnt.items() if n == 1 for v in k])
    assert (cKDTree(m.nodes).query(xy)[0] < 1e-9).all()  # no ring node lost
    assert (cKDTree(xy).query(m.nodes[bnd])[0] < 1e-9).all()  # no free boundary node
    assert len(bnd) == len(xy)
