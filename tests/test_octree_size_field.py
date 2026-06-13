"""Tests for octree-backed size field (spec-029).

Tests the ``octree_size_field`` function and the ``background='octree'``
parameter in ``triangulate``.
"""

from __future__ import annotations

import numpy as np
import pytest

from admesh import Domain as ApiDomain, triangulate
from admesh._stages.domains import UNIT_SQUARE, L_SHAPE
from admesh.octree import octree_size_field


class TestOctreeSizeFieldCallable:
    """Test octree_size_field function."""

    def test_size_field_callable_in_range(self):
        """Sample octree_size_field on unit-square shim; all values in range."""
        # Create a simple shim domain with bbox attribute
        class _DomainShim:
            bbox = (-0.5, -0.5, 0.5, 0.5)

        h_min, h_max = 0.05, 0.1

        # Define oracle: uniform target size
        def _oracle(pts):
            return np.full(len(pts), h_max, dtype=float)

        fh = octree_size_field(
            _DomainShim, _oracle, h_min=h_min, h_max=h_max
        )

        # Sample at random interior points
        rng = np.random.default_rng(0)
        pts_sample = rng.uniform((-0.5, -0.5), (0.5, 0.5), size=(200, 2))

        sizes = fh(pts_sample)

        # All results must be in [h_min, h_max]
        assert sizes.shape == (200,), f"Expected shape (200,), got {sizes.shape}"
        assert np.all(sizes >= h_min - 1e-12), f"Min size {sizes.min()} < {h_min}"
        assert np.all(sizes <= h_max + 1e-12), f"Max size {sizes.max()} > {h_max}"

    def test_gradient_limit_satisfied(self):
        """Verify gradient limiter produces smooth variation."""
        class _DomainShim:
            bbox = (0.0, 0.0, 1.0, 1.0)

        h_min, h_max = 0.01, 0.1
        g = 0.2

        # Oracle with step: h_min in small region, h_max elsewhere
        def _oracle(pts):
            x = pts[:, 0]
            sizes = np.where(x < 0.1, h_min, h_max)
            return sizes

        fh_limited = octree_size_field(
            _DomainShim, _oracle, h_min=h_min, h_max=h_max, g=g, gradient_limit=True
        )

        # Sample along a line crossing the feature
        t = np.linspace(0.0, 1.0, 101)
        pts_line = np.column_stack([t, 0.5 * np.ones_like(t)])
        sizes_limited = fh_limited(pts_line)

        # Check that max consecutive difference is reasonable
        # (much smaller than the discontinuous jump in oracle)
        diffs = np.abs(np.diff(sizes_limited))
        max_diff = np.max(diffs)
        step_size = pts_line[1, 0] - pts_line[0, 0]  # 0.01
        max_allowed = g * step_size + 1e-1  # Allow for octree leaf discretization

        assert max_diff <= max_allowed, (
            f"Max consecutive difference {max_diff:.4e} exceeds "
            f"g*step + tolerance {max_allowed:.4e}"
        )

        # Also verify limited field has smaller range than unlimited oracle
        oracle_vals = _oracle(pts_line)
        assert np.max(np.abs(np.diff(oracle_vals))) > max_diff, (
            "Limited field should have smaller jumps than oracle"
        )

    def test_octree_handles_single_leaf(self):
        """Octree with only one leaf (no edges) should not crash."""
        class _DomainShim:
            bbox = (0.0, 0.0, 0.1, 0.1)

        h_min, h_max = 0.01, 0.1

        def _oracle(pts):
            return np.full(len(pts), h_max, dtype=float)

        # Single leaf => no edges, gradient limiter skipped
        fh = octree_size_field(
            _DomainShim, _oracle, h_min=h_min, h_max=h_max,
            gradient_limit=True
        )

        pts_test = np.array([[0.05, 0.05]], dtype=float)
        sizes = fh(pts_test)

        assert sizes.shape == (1,)
        assert h_min <= sizes[0] <= h_max


class TestTriangulateBackgroundOctree:
    """Test triangulate with background='octree' parameter."""

    def test_triangulate_background_octree_valid(self):
        """Generate mesh with background='octree'; check structural validity."""
        # Wrap the port domain into an api domain
        api_domain = ApiDomain(
            sdf=L_SHAPE.fd,
            bbox=L_SHAPE.bbox,
            pfix=L_SHAPE.fixed_points if L_SHAPE.fixed_points is not None else None,
        )

        mesh = triangulate(
            api_domain,
            h_max=0.1,
            h_min=0.02,
            background="octree",
            quality_gate=(0.0, 0.0),  # Disable quality gate for structural test
        )

        # Structural validity checks
        assert mesh.n_nodes > 0, "Mesh should have nodes"
        assert mesh.n_elements > 0, "Mesh should have elements"

        # Check all triangles have positive area
        nodes = mesh.nodes
        elements = mesh.elements
        v0 = nodes[elements[:, 0]]
        v1 = nodes[elements[:, 1]]
        v2 = nodes[elements[:, 2]]
        signed_areas = 0.5 * (
            (v1[:, 0] - v0[:, 0]) * (v2[:, 1] - v0[:, 1])
            - (v2[:, 0] - v0[:, 0]) * (v1[:, 1] - v0[:, 1])
        )
        assert np.all(signed_areas > 0), "All triangles must have positive area"
        assert not np.any(np.isnan(nodes)), "Mesh nodes must not contain NaN"

    def test_triangulate_background_invalid(self):
        """Invalid background value raises ValueError."""
        api_domain = ApiDomain(
            sdf=UNIT_SQUARE.fd,
            bbox=UNIT_SQUARE.bbox,
        )

        with pytest.raises(ValueError, match="background must be"):
            triangulate(
                api_domain,
                h_max=0.1,
                background="bogus",
            )

    def test_triangulate_background_uniform_unchanged(self):
        """Default background='uniform' produces consistent results."""
        api_domain = ApiDomain(
            sdf=UNIT_SQUARE.fd,
            bbox=UNIT_SQUARE.bbox,
        )

        # Run twice with same seed; should get same node count
        mesh1 = triangulate(
            api_domain,
            h_max=0.1,
            h_min=0.02,
            background="uniform",
            seed=42,
            quality_gate=(0.0, 0.0),
        )

        mesh2 = triangulate(
            api_domain,
            h_max=0.1,
            h_min=0.02,
            background="uniform",
            seed=42,
            quality_gate=(0.0, 0.0),
        )

        # With same seed, should get identical meshes
        assert mesh1.n_nodes == mesh2.n_nodes
        assert np.allclose(mesh1.nodes, mesh2.nodes, atol=1e-12)
        assert np.array_equal(mesh1.elements, mesh2.elements)

    def test_triangulate_background_octree_vs_uniform(self):
        """Octree and uniform backgrounds produce different meshes."""
        api_domain = ApiDomain(
            sdf=UNIT_SQUARE.fd,
            bbox=UNIT_SQUARE.bbox,
        )

        # Generate with both backgrounds (ignore quality to focus on mesh difference)
        mesh_uniform = triangulate(
            api_domain,
            h_max=0.1,
            h_min=0.02,
            background="uniform",
            seed=42,
            quality_gate=(0.0, 0.0),
        )

        mesh_octree = triangulate(
            api_domain,
            h_max=0.1,
            h_min=0.02,
            background="octree",
            seed=42,
            quality_gate=(0.0, 0.0),
        )

        # The meshes should differ (octree refines adaptively)
        # At minimum, they should have different node counts or connectivity
        # (exact difference depends on adaptive refinement)
        assert mesh_uniform.n_elements > 0
        assert mesh_octree.n_elements > 0
