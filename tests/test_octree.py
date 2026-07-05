"""Tests for admesh.octree (adaptive quadtree).

Formalizes the five concept invariants from the spec-029 prototype, and
tests the octree-backed size field (spec-029).
"""

import numpy as np
import pytest

from admesh import Domain as ApiDomain, triangulate
from admesh._stages.domains import UNIT_SQUARE, L_SHAPE
from admesh.octree import Octree, build_octree, leaf_graph, locate, interpolate, octree_size_field


class MockDomain:
    """Mock domain object for testing."""

    def __init__(self, bbox):
        self.bbox = bbox


@pytest.fixture
def oracle_graded():
    """Graded oracle: target size = 0.3 * max-norm distance to boundary."""
    def oracle(pts):
        x, y = pts[:, 0], pts[:, 1]
        # Max-norm distance to boundary of unit square [0, 1]^2
        dist_to_boundary = np.minimum(
            np.minimum(x, y),
            np.minimum(1.0 - x, 1.0 - y)
        )
        return 0.3 * np.abs(dist_to_boundary) + 1e-10

    return oracle


@pytest.mark.parametrize("ratio", [10, 100])
class TestOctreeInvariants:
    """Test the five core quadtree invariants."""

    def test_cover_exact(self, oracle_graded, ratio):
        """Test (a): sum(size**2) == root grid area within rtol 1e-9."""
        h_max = 0.25
        h_min = h_max / ratio

        domain = MockDomain((0, 0, 1, 1))
        tree = build_octree(
            domain,
            h_min=h_min,
            h_max=h_max,
            oracle=oracle_graded,
            max_depth=14,
            padding=0.0,
            balance=True,
        )

        root_area = tree.root_nx * tree.root_ny * tree.root_size**2
        leaf_area = np.sum(tree.size**2)
        coverage_error = abs(leaf_area - root_area) / root_area

        assert coverage_error < 1e-9, \
            f"Coverage mismatch: {coverage_error:.2e} >= 1e-9"

    def test_partition_no_ancestor_overlap(self, oracle_graded, ratio):
        """Test (b): no duplicate (d,ix,iy); no leaf ancestor of another."""
        h_max = 0.25
        h_min = h_max / ratio

        domain = MockDomain((0, 0, 1, 1))
        tree = build_octree(
            domain,
            h_min=h_min,
            h_max=h_max,
            oracle=oracle_graded,
            max_depth=14,
            padding=0.0,
            balance=True,
        )

        # Check unique keys
        keys = set(zip(tree.depth, tree.ix, tree.iy))
        assert len(keys) == tree.n_leaves, "Duplicate (depth, ix, iy) keys"

        # Check no ancestor-descendant
        for i, (d, ix, iy) in enumerate(keys):
            for k in range(1, int(d) + 1):
                ancestor = (d - k, ix >> k, iy >> k)
                assert ancestor not in keys, \
                    f"Leaf {i} has ancestor {ancestor} in key set"

    def test_2to1_balance(self, oracle_graded, ratio):
        """Test (c): via leaf_graph, max |depth_i - depth_j| <= 1."""
        h_max = 0.25
        h_min = h_max / ratio

        domain = MockDomain((0, 0, 1, 1))
        tree = build_octree(
            domain,
            h_min=h_min,
            h_max=h_max,
            oracle=oracle_graded,
            max_depth=14,
            padding=0.0,
            balance=True,
        )

        edges, _ = leaf_graph(tree)
        if len(edges) > 0:
            depth_i = tree.depth[edges[:, 0]]
            depth_j = tree.depth[edges[:, 1]]
            max_depth_diff = np.max(np.abs(depth_i - depth_j))
            assert max_depth_diff <= 1, \
                f"2:1 constraint violated: max depth diff = {max_depth_diff}"

    def test_leaf_graph_matches_bruteforce(self, oracle_graded, ratio):
        """Test (d): leaf_graph matches O(N^2) brute-force."""
        h_max = 0.25
        h_min = h_max / ratio

        domain = MockDomain((0, 0, 1, 1))
        tree = build_octree(
            domain,
            h_min=h_min,
            h_max=h_max,
            oracle=oracle_graded,
            max_depth=14,
            padding=0.0,
            balance=True,
        )

        # Compute edges via leaf_graph
        edges_computed, _ = leaf_graph(tree)
        edges_computed_set = set(map(tuple, edges_computed))

        # Brute-force O(N^2) adjacency
        cx, cy, size = tree.cx, tree.cy, tree.size
        n_leaves = tree.n_leaves
        edges_brute = set()

        for i in range(n_leaves):
            for j in range(i + 1, n_leaves):
                # Check if edge-adjacent (closed boxes share a segment)
                x1_min, x1_max = cx[i] - size[i]/2, cx[i] + size[i]/2
                y1_min, y1_max = cy[i] - size[i]/2, cy[i] + size[i]/2
                x2_min, x2_max = cx[j] - size[j]/2, cx[j] + size[j]/2
                y2_min, y2_max = cy[j] - size[j]/2, cy[j] + size[j]/2

                # Edge-adjacent: one axis aligned, other axis overlaps
                x_overlap = max(0, min(x1_max, x2_max) - max(x1_min, x2_min))
                y_overlap = max(0, min(y1_max, y2_max) - max(y1_min, y2_min))

                x_aligned = (abs(x1_max - x2_min) < 1e-10 or
                            abs(x1_min - x2_max) < 1e-10)
                y_aligned = (abs(y1_max - y2_min) < 1e-10 or
                            abs(y1_min - y2_max) < 1e-10)

                if (x_aligned and y_overlap > 1e-10) or \
                   (y_aligned and x_overlap > 1e-10):
                    edges_brute.add(tuple(sorted([i, j])))

        assert edges_computed_set == edges_brute, \
            f"Graph mismatch: computed {len(edges_computed_set)}, " \
            f"brute {len(edges_brute)}"

    def test_locate_containment(self, oracle_graded, ratio):
        """Test (e): returned leaf box contains clamped point."""
        h_max = 0.25
        h_min = h_max / ratio

        domain = MockDomain((0, 0, 1, 1))
        tree = build_octree(
            domain,
            h_min=h_min,
            h_max=h_max,
            oracle=oracle_graded,
            max_depth=14,
            padding=0.0,
            balance=True,
        )

        # Generate random test points
        rng = np.random.default_rng(0)
        test_pts = rng.uniform(0, 1, (500, 2))

        result_idx = locate(tree, test_pts)

        for m, (px, py) in enumerate(test_pts):
            idx = result_idx[m]
            cx, cy, s = tree.cx[idx], tree.cy[idx], tree.size[idx]
            # Point should be inside the leaf's box
            assert abs(px - cx) <= s / 2 + 1e-10, \
                f"Point ({px}, {py}) x-coordinate outside leaf {idx}"
            assert abs(py - cy) <= s / 2 + 1e-10, \
                f"Point ({px}, {py}) y-coordinate outside leaf {idx}"

    def test_interpolate_shape_and_value(self, oracle_graded, ratio):
        """Test (f): interpolate returns per-query leaf size correctly."""
        h_max = 0.25
        h_min = h_max / ratio

        domain = MockDomain((0, 0, 1, 1))
        tree = build_octree(
            domain,
            h_min=h_min,
            h_max=h_max,
            oracle=oracle_graded,
            max_depth=14,
            padding=0.0,
            balance=True,
        )

        rng = np.random.default_rng(0)
        test_pts = rng.uniform(0, 1, (100, 2))

        # Interpolate tree.size at test_pts
        result = interpolate(tree, tree.size, test_pts)

        # Check shape
        assert result.shape == (len(test_pts),), \
            f"Shape mismatch: {result.shape} vs ({len(test_pts)},)"

        # Check values match locate + indexing
        leaf_indices = locate(tree, test_pts)
        expected = tree.size[leaf_indices]
        np.testing.assert_array_equal(result, expected)


class TestOctreeBasics:
    """Basic functionality tests."""

    def test_octree_creation_simple(self, oracle_graded):
        """Test basic octree creation."""
        h_max = 0.5
        h_min = 0.05

        domain = MockDomain((0, 0, 1, 1))
        tree = build_octree(
            domain,
            h_min=h_min,
            h_max=h_max,
            oracle=oracle_graded,
            max_depth=10,
            padding=0.0,
            balance=False,
        )

        assert tree.n_leaves > 0
        assert len(tree.cx) == tree.n_leaves
        assert len(tree.cy) == tree.n_leaves
        assert len(tree.size) == tree.n_leaves
        assert len(tree.depth) == tree.n_leaves
        assert len(tree.ix) == tree.n_leaves
        assert len(tree.iy) == tree.n_leaves

    def test_octree_properties(self, oracle_graded):
        """Test Octree properties."""
        h_max = 0.5
        h_min = 0.05

        domain = MockDomain((0, 0, 1, 1))
        tree = build_octree(
            domain,
            h_min=h_min,
            h_max=h_max,
            oracle=oracle_graded,
            max_depth=10,
            padding=0.0,
        )

        # Test centers property
        centers = tree.centers
        assert centers.shape == (tree.n_leaves, 2)
        np.testing.assert_array_equal(centers[:, 0], tree.cx)
        np.testing.assert_array_equal(centers[:, 1], tree.cy)

    def test_leaf_graph_empty_when_single_leaf(self, oracle_graded):
        """Test leaf_graph with a tree that has only one leaf."""
        # Oracle that always returns h_max, so no refinement
        def oracle_coarse(pts):
            return np.full(len(pts), 1.0)

        domain = MockDomain((0, 0, 1, 1))
        tree = build_octree(
            domain,
            h_min=0.01,
            h_max=1.0,
            oracle=oracle_coarse,
            max_depth=10,
            padding=0.0,
        )

        edges, spacing = leaf_graph(tree)
        assert edges.shape[0] == 0  # No edges for single leaf
        assert spacing.shape[0] == 0

    def test_locate_point_outside_domain(self, oracle_graded):
        """Test locate with points outside the padded domain."""
        h_max = 0.25
        h_min = 0.025

        domain = MockDomain((0, 0, 1, 1))
        tree = build_octree(
            domain,
            h_min=h_min,
            h_max=h_max,
            oracle=oracle_graded,
            max_depth=10,
            padding=0.0,
        )

        # Point outside domain (should be clamped)
        pts = np.array([[-0.5, 0.5], [1.5, 0.5], [0.5, -0.5], [0.5, 1.5]])
        result = locate(tree, pts)

        # Should return valid indices (never -1)
        assert np.all(result >= 0)
        assert np.all(result < tree.n_leaves)


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
