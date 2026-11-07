"""Unit tests on toy cases.  Run: python -m pytest benchmarks/exact_coast/test_metrics.py"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import metrics as M  # noqa: E402
from fields import GridField  # noqa: E402

SQUARE = [np.array([[0.0, 0], [1, 0], [1, 1], [0, 1]])]
NODES = np.array([[0.0, 0], [1, 0], [1, 1], [0, 1]])
TRIS = np.array([[0, 1, 2], [0, 2, 3]])
H1 = lambda p: np.full(len(np.atleast_2d(p)), 1.0)  # noqa: E731


def test_quality_equilateral_and_degenerate():
    n = np.array([[0, 0], [1, 0], [0.5, np.sqrt(3) / 2], [2, 0]])
    q = M.triangle_quality(n, np.array([[0, 1, 2], [0, 1, 3]]))
    assert abs(q[0] - 1.0) < 1e-12 and q[1] == 0.0


def test_quality_matches_admesh():
    from admesh._stages.quality import mesh_quality

    rng = np.random.default_rng(0)
    n = rng.random((20, 2))
    t = np.array([[0, 1, 2], [3, 4, 5], [6, 7, 8]])
    assert np.allclose(M.triangle_quality(n, t), mesh_quality(n, t)[2])


def test_boundary_and_exact_square():
    be = M.boundary_edges(TRIS)
    assert len(be) == 4
    assert M.hausdorff(NODES, be, SQUARE) < 1e-12
    assert M.vertex_retention(NODES, SQUARE) == 100.0
    le, ae = M.length_area_errors(NODES, TRIS, be, SQUARE)
    assert le < 1e-12 and ae < 1e-12
    med, p95 = M.edge_length_error(NODES, be, H1)
    assert med < 1e-12 and p95 < 1e-12  # all boundary edges are length 1


def test_shifted_vertex_hausdorff_and_retention():
    n = NODES.copy()
    n[2] = [1.1, 1.0]
    be = M.boundary_edges(TRIS)
    hd = M.hausdorff(n, be, SQUARE)
    assert 0.09 < hd < 0.11
    assert M.vertex_retention(n, SQUARE) == 75.0
    le, ae = M.length_area_errors(n, TRIS, be, SQUARE)
    assert ae > 0.04 and le > 0


def test_edge_length_error_scaling():
    be = M.boundary_edges(TRIS)
    med, _ = M.edge_length_error(NODES, be, lambda p: np.full(len(p), 0.5))
    assert abs(med - 1.0) < 1e-12  # L/h - 1 = 1


def test_sliver_rate():
    # two triangles, one a sliver touching the coast
    n = np.array([[0.0, 0], [1, 0], [0.5, 0.001], [0.5, 1]])
    t = np.array([[0, 1, 2], [0, 2, 3]])
    q = M.triangle_quality(n, t)
    assert q[0] < 0.3
    r = M.sliver_rate(n, t, q, [np.array([[0.0, 0], [1, 0], [1, 1], [0, 1]])], H1)
    assert abs(r - 0.5) < 1e-12 if q[1] >= 0.3 else r >= 0.5


def test_signed_area_orientation():
    assert np.all(M.signed_areas(NODES, TRIS) > 0)
    assert np.all(M.signed_areas(NODES, TRIS[:, ::-1]) < 0)


def test_gridfield_scalar_matches_vector_and_bilinear():
    x = np.linspace(0, 1, 5)
    y = np.linspace(0, 2, 7)
    X, Y = np.meshgrid(x, y)
    F = GridField(x, y, 1 + 2 * X + 3 * Y)  # linear -> bilinear is exact
    pts = np.array([[0.13, 0.77], [0.9, 1.9], [-1.0, 5.0]])
    v = F(pts)
    assert np.allclose(v[:2], 1 + 2 * pts[:2, 0] + 3 * pts[:2, 1])
    assert np.allclose(v, [F.at(*p) for p in pts])
    assert np.allclose(F.scaled(2.0)(pts), 2 * v)
