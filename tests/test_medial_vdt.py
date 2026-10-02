"""Tests for the vector-distance-transform medial axis and ``medial_method``.

Reference: Kang and Kubatko (2024), Geosci. Model Dev. 17, 1603-1625,
https://doi.org/10.5194/gmd-17-1603-2024 (Eqs. 7-14).
"""

from __future__ import annotations

import json
from collections import Counter

import numpy as np
import pytest

import admesh
from admesh import Domain, triangulate
from admesh.medial_vdt import compute_vdt_medial_axis, vdt_size_field


def _rect_sdf(x0: float, y0: float, x1: float, y1: float):
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    hx, hy = 0.5 * (x1 - x0), 0.5 * (y1 - y0)

    def sdf(p: np.ndarray) -> np.ndarray:
        dx = np.abs(p[:, 0] - cx) - hx
        dy = np.abs(p[:, 1] - cy) - hy
        outside = np.hypot(np.maximum(dx, 0.0), np.maximum(dy, 0.0))
        return outside + np.minimum(np.maximum(dx, dy), 0.0)

    return sdf


# Wide room joined to a narrow channel (an "L"), as a polygon ring.
_L_RING = [[0, 0], [2, 0], [2, 0.4], [1.2, 0.4], [1.2, 1.0], [0, 1.0]]
_L_AREA = 2.0 * 0.4 + 1.2 * 0.6


@pytest.fixture
def l_domain(tmp_path) -> Domain:
    path = tmp_path / "l_domain.json"
    path.write_text(json.dumps({"name": "l", "rings": [_L_RING]}))
    return admesh.load_domain_from_json(str(path))


def _assert_structurally_valid(mesh, domain: Domain, area: float) -> None:
    nodes, elems = mesh.nodes, mesh.elements
    assert len(elems) > 0
    v0, v1, v2 = nodes[elems[:, 0]], nodes[elems[:, 1]], nodes[elems[:, 2]]
    signed = 0.5 * (
        (v1[:, 0] - v0[:, 0]) * (v2[:, 1] - v0[:, 1])
        - (v1[:, 1] - v0[:, 1]) * (v2[:, 0] - v0[:, 0])
    )
    assert (signed > 0).all(), "triangles must have positive area"
    tol = 1e-6 * (domain.bbox[2] - domain.bbox[0])
    assert (domain.sdf(nodes) < tol).all(), "nodes must lie inside the domain"
    centroids = (v0 + v1 + v2) / 3.0
    assert (domain.sdf(centroids) < 0.0).all(), "centroids must lie inside"
    # Watertight: every boundary edge (used once) meets exactly two boundary
    # edges at each of its nodes, and the triangles tile the domain area.
    edges = Counter()
    for a, b in ((0, 1), (1, 2), (2, 0)):
        for i, j in zip(elems[:, a], elems[:, b]):
            edges[(min(i, j), max(i, j))] += 1
    assert max(edges.values()) <= 2, "an edge is shared by more than two triangles"
    degree = Counter()
    for (i, j), count in edges.items():
        if count == 1:
            degree[i] += 1
            degree[j] += 1
    assert degree and set(degree.values()) == {2}, "boundary is not a closed loop set"
    assert abs(signed.sum() - area) / area < 0.03, "mesh area differs from domain"


def test_straight_channel_width_matches_analytic():
    """Mean f_w on the channel centre region equals the width (Eq. 14)."""
    w, length, delta = 0.1, 1.0, 0.005
    res = compute_vdt_medial_axis(
        _rect_sdf(0.0, 0.0, length, w), (0.0, 0.0, length, w), delta, delta_w=w
    )
    X, Y = np.meshgrid(res.xs, res.ys, indexing="xy")
    region = (X > 0.3) & (X < 0.7) & (np.abs(Y - 0.5 * w) < 0.25 * w)
    assert region.sum() > 100
    mean_fw = float(res.width[region].mean())
    assert abs(mean_fw - w) <= 2.0 * delta


def test_square_corner_pruning_removes_corner_branches():
    """After pruning, no branch end lies within 2*delta_w of a corner.

    Eq. 12 is evaluated on the grid, so the surviving ends sit at 2*delta_w
    to within one cell; one grid cell is the tolerance used here.
    """
    delta, delta_w = 0.01, 0.1
    res = compute_vdt_medial_axis(
        _rect_sdf(0.0, 0.0, 1.0, 1.0), (0.0, 0.0, 1.0, 1.0), delta, delta_w=delta_w
    )
    corners = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])

    def corner_distance(points: np.ndarray) -> np.ndarray:
        return np.min(np.linalg.norm(points[:, None, :] - corners[None], axis=2), axis=1)

    # Non-vacuous: the unpruned axis reaches the corners and pruning removed it.
    rr, cc = np.nonzero(res.pruned)
    assert len(rr) > 0
    pruned_pts = np.column_stack([res.xs[cc], res.ys[rr]])
    assert corner_distance(pruned_pts).min() < 0.05
    assert len(res.endpoints) == 4
    assert corner_distance(res.endpoints).min() >= 2.0 * delta_w - delta


def test_vdt_size_field_is_bounded_and_refines_narrow_channel(l_domain):
    field = vdt_size_field(l_domain, 0.025, hmin=0.02, hmax=0.1)
    pts = np.array([[0.5, 0.5], [1.6, 0.2], [0.3, 0.9]])
    h = field(pts)
    assert h.shape == (3,)
    assert np.all(h >= 0.02 - 1e-12) and np.all(h <= 0.1 + 1e-12)


def test_triangulate_vdt_structurally_valid(l_domain):
    mesh = triangulate(
        l_domain, h_max=0.1, h_min=0.02, seed=1, medial_method="vdt",
        quality_gate=(0.0, 0.0),
    )
    _assert_structurally_valid(mesh, l_domain, _L_AREA)


@pytest.mark.parametrize("method", ["grid", "octree"])
def test_triangulate_grid_and_octree_smoke(l_domain, method):
    mesh = triangulate(
        l_domain, h_max=0.1, h_min=0.02, seed=1, medial_method=method,
        quality_gate=(0.0, 0.0),
    )
    _assert_structurally_valid(mesh, l_domain, _L_AREA)


def test_medial_method_none_matches_call_without_keyword(l_domain):
    base = triangulate(l_domain, h_max=0.1, h_min=0.02, seed=3)
    same = triangulate(l_domain, h_max=0.1, h_min=0.02, seed=3, medial_method=None)
    assert np.array_equal(base.nodes, same.nodes)
    assert np.array_equal(base.elements, same.elements)


def test_medial_method_unknown_value_raises(l_domain):
    with pytest.raises(ValueError, match="medial_method"):
        triangulate(l_domain, h_max=0.1, seed=1, medial_method="bogus")
