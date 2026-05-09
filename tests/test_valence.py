"""Tests for admesh.valence — edge-flip valence balancing.

Issue #27: balance node valence via edge flipping.
"""

from __future__ import annotations

import numpy as np
import pytest

from admesh.api import BoundarySegment, Mesh
from admesh.boundary_types import BoundaryType
from admesh.valence import (
    BalanceConfig,
    BalanceResult,
    balance_valence_triangles,
    compute_valence,
    get_valence_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_grid_mesh(with_boundary: bool = False) -> Mesh:
    """Return a 3x3 node grid mesh (8 triangles).

    Center node 4 already has ideal valence 6.  Corner nodes have valence <= 2.
    The mesh has no boundary segments by default so all 9 nodes are treated
    as interior during valence balancing.
    """
    nodes = np.array(
        [
            [0.0, 0.0], [1.0, 0.0], [2.0, 0.0],  # row 0
            [0.0, 1.0], [1.0, 1.0], [2.0, 1.0],  # row 1
            [0.0, 2.0], [1.0, 2.0], [2.0, 2.0],  # row 2
        ],
        dtype=np.float64,
    )
    elements = np.array(
        [
            [0, 1, 4], [0, 4, 3],  # lower-left cell
            [1, 2, 5], [1, 5, 4],  # lower-right cell
            [3, 4, 7], [3, 7, 6],  # upper-left cell
            [4, 5, 8], [4, 8, 7],  # upper-right cell
        ],
        dtype=np.int64,
    )
    if not with_boundary:
        return Mesh(nodes=nodes, elements=elements)

    perimeter = np.array([0, 1, 2, 5, 8, 7, 6, 3], dtype=np.int64)
    seg = BoundarySegment(
        node_ids=perimeter,
        bc_type=BoundaryType.MAINLAND,
        is_open=False,
    )
    return Mesh(nodes=nodes, elements=elements, boundaries=(seg,))


def _make_fan_mesh() -> Mesh:
    """Return a fan mesh: center node surrounded by 8 triangles (valence 8).

    Node 0 (center) has valence 8 (over-valenced vs ideal 6).
    Nodes 1-8 (ring) each have valence 2 (under-valenced).
    No boundary segments -- all nodes treated as interior.
    At least one edge flip should reduce center valence toward 6.
    """
    # 8 ring nodes (not 9) so nodes 0..8 are exactly 9 total
    angles = np.linspace(0, 2 * np.pi, 8, endpoint=False)
    ring = np.stack([np.cos(angles), np.sin(angles)], axis=1)
    nodes = np.vstack([[[0.0, 0.0]], ring]).astype(np.float64)  # shape (9, 2)
    elements = np.array(
        [[0, i, i % 8 + 1] for i in range(1, 9)],
        dtype=np.int64,
    )
    return Mesh(nodes=nodes, elements=elements)


# ---------------------------------------------------------------------------
# compute_valence
# ---------------------------------------------------------------------------

class TestComputeValence:
    def test_empty(self):
        val = compute_valence(np.zeros((0, 3), dtype=np.int64))
        assert val.shape == (0,)

    def test_known_grid_valences(self):
        mesh = _make_grid_mesh()
        val = compute_valence(mesh.elements)
        assert val.dtype == np.int32
        assert len(val) == 9
        # center node (4) has ideal valence 6
        assert val[4] == 6
        # corner nodes have low valence
        for corner in [0, 2, 6, 8]:
            assert val[corner] <= 2

    def test_fan_center_valence(self):
        mesh = _make_fan_mesh()
        val = compute_valence(mesh.elements)
        assert val[0] == 8   # center over-valenced
        for i in range(1, 9):
            assert val[i] == 2  # ring under-valenced

    def test_single_triangle(self):
        elems = np.array([[0, 1, 2]], dtype=np.int64)
        val = compute_valence(elems)
        assert val.tolist() == [1, 1, 1]


# ---------------------------------------------------------------------------
# balance_valence_triangles
# ---------------------------------------------------------------------------

class TestBalanceValenceTriangles:
    def test_returns_balance_result(self):
        mesh = _make_grid_mesh()
        result = balance_valence_triangles(mesh)
        assert isinstance(result, BalanceResult)

    def test_node_positions_unchanged(self):
        mesh = _make_grid_mesh()
        result = balance_valence_triangles(mesh)
        np.testing.assert_array_equal(result.mesh.nodes, mesh.nodes)

    def test_improves_overvalenced_center(self):
        """Fan-mesh center (valence=8) should be reduced toward 6."""
        mesh = _make_fan_mesh()
        result = balance_valence_triangles(mesh)
        val_after = compute_valence(result.mesh.elements)
        assert val_after[0] < 8

    def test_pct_at_ideal_improves_on_fan(self):
        mesh = _make_fan_mesh()
        result = balance_valence_triangles(mesh)
        assert result.stats_after.pct_at_ideal >= result.stats_before.pct_at_ideal

    def test_element_count_preserved(self):
        """Edge flipping never creates or removes triangles."""
        mesh = _make_fan_mesh()
        result = balance_valence_triangles(mesh)
        assert result.mesh.n_elements == mesh.n_elements

    def test_edges_flipped_positive_on_fan(self):
        """The over-valenced fan mesh should trigger at least one flip."""
        mesh = _make_fan_mesh()
        result = balance_valence_triangles(mesh)
        assert result.edges_flipped >= 1

    def test_boundary_nodes_mask_respected(self):
        """With perimeter as boundary, those nodes are excluded from improvement metric."""
        mesh = _make_grid_mesh(with_boundary=True)
        result = balance_valence_triangles(mesh)
        # Boundary node positions must be identical
        bnd_ids = mesh.boundaries[0].node_ids
        np.testing.assert_array_equal(
            result.mesh.nodes[bnd_ids], mesh.nodes[bnd_ids]
        )

    def test_already_balanced_converges(self):
        """A single equilateral triangle needs no flips."""
        s = 3.0 ** 0.5 / 2.0
        nodes = np.array([[0, 0], [1, 0], [0.5, s]], dtype=np.float64)
        elems = np.array([[0, 1, 2]], dtype=np.int64)
        mesh = Mesh(nodes=nodes, elements=elems)
        result = balance_valence_triangles(mesh)
        assert result.edges_flipped == 0
        assert result.converged

    def test_quality_gate_respected(self):
        """Very strict quality gate (1.0) should block all flips."""
        mesh = _make_grid_mesh()
        cfg = BalanceConfig(quality_gate=1.0)
        result = balance_valence_triangles(mesh, config=cfg)
        assert result.edges_flipped == 0

    def test_custom_config_max_iterations(self):
        mesh = _make_grid_mesh()
        cfg = BalanceConfig(max_iterations=1)
        result = balance_valence_triangles(mesh, config=cfg)
        assert result.iterations <= 1

    def test_output_mesh_quality_populated(self):
        """The returned mesh should have a quality array."""
        mesh = _make_fan_mesh()
        result = balance_valence_triangles(mesh)
        assert result.mesh.quality is not None
        assert len(result.mesh.quality) == mesh.n_elements


# ---------------------------------------------------------------------------
# get_valence_report
# ---------------------------------------------------------------------------

class TestGetValenceReport:
    def test_returns_string(self):
        mesh = _make_grid_mesh()
        report = get_valence_report(mesh)
        assert isinstance(report, str)

    def test_contains_ideal_line(self):
        mesh = _make_grid_mesh()
        report = get_valence_report(mesh)
        assert "ideal=6" in report

    def test_contains_at_ideal_percentage(self):
        mesh = _make_grid_mesh()
        report = get_valence_report(mesh)
        assert "At ideal" in report

    def test_custom_ideal_valence(self):
        mesh = _make_grid_mesh()
        cfg = BalanceConfig(ideal_valence=4)
        report = get_valence_report(mesh, config=cfg)
        assert "ideal=4" in report
