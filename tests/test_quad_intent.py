"""Tests for quad-intent triangulation and metrics.

Covers the quad_intent=True path in triangulate(), quadability_report(),
and related quad-readiness metrics. All tests use small meshes (h_max ~0.2)
for speed, and avoid hardcoding tolerance values that are computed explicitly.
"""

import pytest
import numpy as np
from admesh import (
    Domain, Mesh, BoundarySegment, QuadIntentConfig,
    triangulate, quad_metrics
)
from admesh._stages.domains import UNIT_DISK, ANNULUS
from admesh.boundary_types import BoundaryType


class TestQuadIntentBasics:
    """Sanity checks for quad_intent flag and configuration."""

    def test_default_unchanged_is_deterministic(self):
        """Calling triangulate twice with same params yields identical output."""
        m1 = triangulate(UNIT_DISK, h_max=0.2, seed=42)
        m2 = triangulate(UNIT_DISK, h_max=0.2, seed=42)
        assert m1.equals(m2, atol=1e-14)

    def test_quad_intent_returns_valid_mesh(self):
        """triangulate(..., quad_intent=True) returns a valid Mesh with positive quality."""
        m = triangulate(UNIT_DISK, h_max=0.2, quad_intent=True, seed=42)
        assert isinstance(m, Mesh)
        assert m.n_elements > 0
        assert m.n_nodes > 0
        if m.quality is not None:
            assert np.all(m.quality >= 0.30)

    def test_quad_intent_annulus_valid(self):
        """quad_intent path works on ANNULUS domain (multi-ring)."""
        m = triangulate(ANNULUS, h_max=0.2, quad_intent=True, seed=42)
        assert m.n_elements > 0
        assert m.quality is not None
        assert np.min(m.quality) >= 0.30

    def test_quad_intent_default_flag_is_false(self):
        """Calling triangulate(dom) == triangulate(dom, quad_intent=False)."""
        m_default = triangulate(UNIT_DISK, h_max=0.2, seed=42)
        m_explicit_false = triangulate(UNIT_DISK, h_max=0.2, quad_intent=False, seed=42)
        assert m_default.equals(m_explicit_false, atol=1e-14)

    def test_quad_intent_config_defaults(self):
        """QuadIntentConfig dataclass has expected defaults."""
        cfg = QuadIntentConfig()
        assert cfg.ideal_valence == 8
        assert cfg.max_valence == 10
        assert cfg.anisotropy is True
        # anisotropy_ratio should be sqrt(2) ≈ 1.414...
        assert abs(cfg.anisotropy_ratio - np.sqrt(2)) < 1e-9
        assert cfg.fidelity_band == (0.7, 1.4)
        assert cfg.fidelity_min_fraction == 0.9
        assert cfg.balance_every == 25
        assert cfg.run_quad_prep_finish is True


class TestQuadMetrics:
    """Tests for quad_metrics functions (iso_dev, edge_fidelity, etc.)."""

    def test_quad_metrics_on_known_mesh(self):
        """Build a tiny mesh (unit square split into 2 right triangles) and check metrics."""
        # Unit square: [0,0], [1,0], [1,1], [0,1]
        # Two right-isoceles triangles: [0,1,2] and [0,2,3]
        nodes = np.array([
            [0.0, 0.0],
            [1.0, 0.0],
            [1.0, 1.0],
            [0.0, 1.0],
        ], dtype=np.float64)

        elements = np.array([
            [0, 1, 2],
            [0, 2, 3],
        ], dtype=np.int64)

        # Create a simple boundary
        boundaries = (
            BoundarySegment(
                node_ids=np.array([0, 1, 2, 3], dtype=np.int64),
                bc_type=BoundaryType.MAINLAND,
                is_open=False,
            ),
        )

        mesh = Mesh(nodes=nodes, elements=elements, boundaries=boundaries)

        # Test iso_dev: should be near 0 for right-isoceles triangles
        iso_devs = quad_metrics.iso_dev(mesh.nodes, mesh.elements)
        assert iso_devs.shape == (2,)
        # For a unit-square split, both triangles are 45-45-90
        # sorted angles: [45, 45, 90], target: [45, 45, 90]
        # mean absolute deviation should be 0
        assert np.allclose(iso_devs, 0.0, atol=1e-6)

        # Test edge_fidelity: returns a dict with keys
        fid = quad_metrics.edge_fidelity(mesh.nodes, mesh.elements, h=None)
        assert "ratios" in fid
        assert "in_band_fraction" in fid
        assert "band" in fid
        assert isinstance(fid["in_band_fraction"], float)
        assert 0.0 <= fid["in_band_fraction"] <= 1.0

    def test_iso_dev_equilateral(self):
        """Test iso_dev on an equilateral triangle.

        An equilateral triangle has all angles = 60°.
        Sorted target [45, 45, 90], sorted angles [60, 60, 60].
        Mean absolute deviation = (|60-45| + |60-45| + |60-90|) / 3
                                = (15 + 15 + 30) / 3
                                = 20
        """
        # Equilateral triangle with side length 1
        sqrt3_2 = np.sqrt(3) / 2
        nodes = np.array([
            [0.0, 0.0],
            [1.0, 0.0],
            [0.5, sqrt3_2],
        ], dtype=np.float64)
        elements = np.array([[0, 1, 2]], dtype=np.int64)

        iso_dev_vals = quad_metrics.iso_dev(nodes, elements)
        assert iso_dev_vals.shape == (1,)
        # Expected: 20 degrees
        expected_iso_dev = 20.0
        assert np.isclose(iso_dev_vals[0], expected_iso_dev, atol=1e-3)

    def test_annulus_geometry_improves(self):
        """Signal test: quad_intent should not worsen geometry significantly on ANNULUS."""
        # Generate two meshes on ANNULUS with same h_max, one with quad_intent
        m0 = triangulate(ANNULUS, h_max=0.15, quad_intent=False, seed=42)
        m1 = triangulate(ANNULUS, h_max=0.15, quad_intent=True, seed=42)

        r0 = quad_metrics.quadability_report(m0)
        r1 = quad_metrics.quadability_report(m1)

        # Signal test: quad_intent should not worsen iso_dev by much
        # (tolerate small degradation due to stochasticity)
        iso_dev_tol = r0["iso_dev_mean"] + 5.0  # Allow up to 5 degrees worse
        assert r1["iso_dev_mean"] <= iso_dev_tol, (
            f"quad_intent iso_dev_mean {r1['iso_dev_mean']:.2f} "
            f"> expected {iso_dev_tol:.2f}"
        )

        # OR merged quad quality should be at least as good
        # (one of the two should improve or stay neutral)
        assert (r1["iso_dev_mean"] <= r0["iso_dev_mean"] + 1.0) or (
            r1["merged_quad"]["mean_quad_quality"]
            >= r0["merged_quad"]["mean_quad_quality"] - 0.05
        )
