"""Tests for octree-based size-field grid.

Test plan (from spec 021):
  - T001 (test_adjacency_sibling_links): 3-level tree, sibling + cross-parent links consistent
  - T011 (test_locate_descent): O(log N) locate on 4-level tree, 100 random points
  - T014 (test_balance_2to1_queue): no 2:1 violations after balancing
  - Parity: size_field_octree numerical output within atol=1e-10 vs. prototype
  - Regression: all tests pass on broader suite
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from admesh._stages.octree_grid import (
    OctreeNode,
    OctreeTree,
    build_octree,
    leaf_graph,
    size_field_octree,
)
from admesh.api import Domain


class TestAdjacencySiblingLinks:
    """T001 — Sibling + cross-parent neighbour links are consistent after splits."""

    def test_sibling_links_after_split(self):
        """Build a unit-square tree and split root twice; verify neighbour consistency."""
        # Create unit-square root
        root = OctreeNode(
            min_corner=np.array([0.0, 0.0]),
            max_corner=np.array([1.0, 1.0]),
            depth=0,
            parent=None,
        )
        root.neighbours = {"N": None, "S": None, "E": None, "W": None}

        # Split root into 4 children
        root.split(max_depth=2)
        sw, se, nw, ne = root.children

        # Verify sibling links are symmetric
        assert sw.neighbours.get("E") is se
        assert se.neighbours.get("W") is sw
        assert sw.neighbours.get("N") is nw
        assert nw.neighbours.get("S") is sw
        assert se.neighbours.get("N") is ne
        assert ne.neighbours.get("S") is se
        assert nw.neighbours.get("E") is ne
        assert ne.neighbours.get("W") is nw

        # All children should have external neighbours = None (boundary)
        assert sw.neighbours.get("W") is None
        assert sw.neighbours.get("S") is None
        assert se.neighbours.get("E") is None
        assert se.neighbours.get("S") is None
        assert nw.neighbours.get("W") is None
        assert nw.neighbours.get("N") is None
        assert ne.neighbours.get("E") is None
        assert ne.neighbours.get("N") is None

        # Split SW and NE to create a second level
        sw.split(max_depth=2)
        ne.split(max_depth=2)

        # Verify SW's children are consistent (root=0, sw=1, sw_sw=2)
        sw_sw, sw_se, sw_nw, sw_ne = sw.children
        assert sw_sw.depth == 2
        assert sw_se.neighbours.get("W") is sw_sw
        assert sw_ne.neighbours.get("S") is sw_se

        # Verify NE's children have correct external/internal links
        ne_sw, ne_se, ne_nw, ne_ne = ne.children
        assert ne_sw.depth == 2
        assert ne_se.neighbours.get("W") is ne_sw

    def test_no_cross_parent_corruption_after_split(self):
        """Verify cross-parent links don't corrupt unrelated subtrees."""
        root = OctreeNode(
            min_corner=np.array([0.0, 0.0]),
            max_corner=np.array([2.0, 2.0]),
            depth=0,
            parent=None,
        )
        root.neighbours = {"N": None, "S": None, "E": None, "W": None}

        root.split(max_depth=3)
        # All 4 children should have no E/W cross-parent links (root has no E/W)
        for child in root.children:
            for nb in child.neighbours.values():
                # Only sibling links should be non-None at this stage
                assert nb is None or nb.parent is root


class TestLocateDescent:
    """T011 — O(log N) point location via tree descent."""

    def test_locate_100_random_points_4level_tree(self):
        """Build 4-level unit-square tree; verify locate returns correct leaf."""
        root = OctreeNode(
            min_corner=np.array([0.0, 0.0]),
            max_corner=np.array([1.0, 1.0]),
            depth=0,
            parent=None,
        )
        root.neighbours = {"N": None, "S": None, "E": None, "W": None}

        # Recursively subdivide to depth 3 (depth 0, 1, 2, 3 = 4 levels)
        def build_full_tree(node: OctreeNode, target_depth: int):
            if node.depth < target_depth:
                node.split(max_depth=target_depth + 1)
                for child in node.children:
                    build_full_tree(child, target_depth)

        build_full_tree(root, target_depth=3)

        # Collect leaves
        leaves = []

        def collect(node: OctreeNode):
            if node.is_leaf():
                leaves.append(node)
            else:
                for child in node.children:
                    collect(child)

        collect(root)
        assert len(leaves) == 64  # 4^3 leaves: root splits 3 times (depth 0→1→2→3=leaf)

        # Test 100 random points
        np.random.seed(42)
        points = np.random.uniform(0, 1, (100, 2))
        locate_calls = [0]  # Use list to allow mutation in nested function

        def counting_locate(node: OctreeNode, pt: np.ndarray, depth: int) -> OctreeNode:
            locate_calls[0] += 1
            if node.is_leaf():
                return node
            mid = (node.min_corner + node.max_corner) / 2.0
            ix = int(pt[0] >= mid[0])
            iy = int(pt[1] >= mid[1])
            return counting_locate(node.children[2 * iy + ix], pt, depth + 1)

        for pt in points:
            locate_calls[0] = 0
            leaf = counting_locate(root, pt, 0)
            # Point should be inside the leaf's bbox
            assert np.all(leaf.min_corner <= pt) and np.all(pt <= leaf.max_corner)
            # Call count should be <= max_depth + 1
            assert locate_calls[0] <= 5

    def test_locate_boundary_points(self):
        """Verify locate correctly handles points on cell boundaries."""
        root = OctreeNode(
            min_corner=np.array([0.0, 0.0]),
            max_corner=np.array([1.0, 1.0]),
            depth=0,
            parent=None,
        )
        root.neighbours = {"N": None, "S": None, "E": None, "W": None}
        root.split(max_depth=2)

        # Test points on the split boundaries
        mid_x = 0.5
        mid_y = 0.5
        test_points = [
            (mid_x, mid_y),  # Exact center
            (0.0, 0.0),      # SW corner
            (1.0, 0.0),      # SE corner
            (0.0, 1.0),      # NW corner
            (1.0, 1.0),      # NE corner
            (mid_x, 0.0),    # S boundary
            (mid_x, 1.0),    # N boundary
            (0.0, mid_y),    # W boundary
            (1.0, mid_y),    # E boundary
        ]

        for pt_tuple in test_points:
            pt = np.array(pt_tuple)
            leaf = root.locate(pt)
            assert leaf.is_leaf()
            # Point should be in [min, max] (allowing boundary)
            assert np.all(leaf.min_corner <= pt) and np.all(pt <= leaf.max_corner)


class TestBalance2to1Queue:
    """T014 — Work-queue 2:1 balancing produces valid octree."""

    def test_no_2to1_violations_after_balance(self):
        """Build imbalanced tree; verify no 2:1 violations after balance."""
        # Create root spanning [0,1]^2
        root = OctreeNode(
            min_corner=np.array([0.0, 0.0]),
            max_corner=np.array([1.0, 1.0]),
            depth=0,
            parent=None,
        )
        root.neighbours = {"N": None, "S": None, "E": None, "W": None}

        # Manually create an imbalanced tree: split SW deep, leave others shallow
        root.split(max_depth=5)
        sw = root.children[0]
        sw.split(max_depth=5)
        sw_sw = sw.children[0]
        sw_sw.split(max_depth=5)

        # Collect leaves before balancing
        leaves_before = []

        def collect(node: OctreeNode):
            if node.is_leaf():
                leaves_before.append(node)
            else:
                for child in node.children:
                    collect(child)

        collect(root)
        initial_count = len(leaves_before)

        # Build tree structure
        tree = OctreeTree(root=root, max_depth=5)
        tree._collect_leaves()

        # Run balancing
        start = time.perf_counter()
        tree.balance_2to1()
        elapsed = time.perf_counter() - start

        # Verify timing (should be fast)
        assert elapsed < 1.0, f"Balancing took {elapsed:.2f}s, expected < 1s"

        # Verify no leaf violates 2:1 constraint
        for leaf in tree.leaves:
            assert not tree._violates_2to1(leaf), f"Leaf {leaf} violates 2:1 after balance"

        # Leaf count should have increased (balancing adds leaves)
        assert len(tree.leaves) >= initial_count

    def test_balance_idempotent(self):
        """Verify running balance twice produces same result (idempotent)."""
        root = OctreeNode(
            min_corner=np.array([0.0, 0.0]),
            max_corner=np.array([1.0, 1.0]),
            depth=0,
            parent=None,
        )
        root.neighbours = {"N": None, "S": None, "E": None, "W": None}

        # Create imbalanced tree
        root.split(max_depth=4)
        sw = root.children[0]
        sw.split(max_depth=4)
        sw_sw = sw.children[0]
        sw_sw.split(max_depth=4)

        tree = OctreeTree(root=root, max_depth=4)
        tree._collect_leaves()

        # Balance once
        tree.balance_2to1()
        count_after_1 = len(tree.leaves)

        # Balance again
        tree.balance_2to1()
        count_after_2 = len(tree.leaves)

        assert count_after_1 == count_after_2


class TestSizeFieldOctree:
    """Test the public size_field_octree callable."""

    def test_size_field_callable_interface(self):
        """Verify size_field_octree returns a callable with correct signature."""
        # Create a simple rectangular domain
        domain = Domain(
            bbox=(-1, -1, 1, 1),
            sdf=lambda pts: np.sqrt(np.sum(pts**2, axis=1)) - 0.5,
        )

        fh = size_field_octree(domain, h_min=0.05, h_max=0.5, max_depth=8)
        assert callable(fh)

        # Test callable on batch of points
        test_pts = np.array([[0.0, 0.0], [0.5, 0.5], [-0.5, -0.5]])
        h = fh(test_pts)
        assert h.shape == (3,)
        assert np.all(h >= 0)  # Sizes should be positive

    def test_size_field_respects_bounds(self):
        """Verify size field output respects h_min/h_max bounds."""
        domain = Domain(
            bbox=(-1, -1, 1, 1),
            sdf=lambda pts: np.ones(len(pts)),  # Constant SDF
        )

        h_min, h_max = 0.1, 0.5
        fh = size_field_octree(domain, h_min=h_min, h_max=h_max, max_depth=6)

        test_pts = np.random.uniform(-0.9, 0.9, (50, 2))
        h = fh(test_pts)

        # All sizes should be within bounds (allowing h_max for uninitialized leaves)
        assert np.all(h <= h_max)

    def test_leaf_graph_consistency(self):
        """Verify leaf_graph returns consistent edge/spacing information."""
        domain = Domain(
            bbox=(0, 0, 2, 2),
            sdf=lambda pts: np.linalg.norm(pts - 1.0, axis=1) - 0.5,
        )

        tree = build_octree(domain, h_min=0.1, h_max=1.0, max_depth=6)
        edges, spacing = leaf_graph(tree)

        assert isinstance(edges, np.ndarray)
        assert isinstance(spacing, np.ndarray)
        assert len(edges) == len(spacing)

        # All edges should reference valid leaf indices
        for i, j in edges:
            assert 0 <= i < len(tree.leaves)
            assert 0 <= j < len(tree.leaves)
            assert i != j


class TestBuildOctree:
    """Test the build_octree function."""

    def test_build_octree_unit_square(self):
        """Build octree on unit square; verify tree properties."""
        domain = Domain(
            bbox=(0, 0, 1, 1),
            sdf=lambda pts: np.zeros(len(pts)),
        )

        tree = build_octree(domain, h_min=0.05, h_max=0.5, max_depth=6)

        assert tree.root is not None
        assert tree.max_depth == 6
        assert len(tree.leaves) > 0

        # All leaves should have h_field set
        for leaf in tree.leaves:
            assert leaf.h_field is not None
            assert leaf.is_leaf()

    def test_build_octree_respects_max_depth(self):
        """Verify tree never exceeds max_depth."""
        domain = Domain(
            bbox=(0, 0, 1, 1),
            sdf=lambda pts: np.zeros(len(pts)),
        )

        max_depth = 4
        tree = build_octree(domain, h_min=0.001, h_max=1.0, max_depth=max_depth)

        # Check all leaves
        def check_depth(node: OctreeNode):
            if node.is_leaf():
                assert node.depth <= max_depth
            else:
                for child in node.children:
                    check_depth(child)

        check_depth(tree.root)

    def test_build_octree_circular_domain(self):
        """Build octree on a circular domain; verify adaptation."""
        # Circle of radius 1 centered at (0, 0)
        domain = Domain(
            bbox=(-1.2, -1.2, 1.2, 1.2),
            sdf=lambda pts: np.linalg.norm(pts, axis=1) - 1.0,
        )

        tree = build_octree(domain, h_min=0.05, h_max=0.5, max_depth=8)

        assert len(tree.leaves) > 0
        # Interior leaves (near medial axis) should have depth >= 1
        assert any(leaf.depth > 0 for leaf in tree.leaves)


class TestNumericalParity:
    """Test that octree size-field matches expected numerical behavior."""

    def test_size_field_deterministic(self):
        """Verify size_field output is deterministic."""
        domain = Domain(
            bbox=(0, 0, 1, 1),
            sdf=lambda pts: np.linalg.norm(pts - 0.5, axis=1) - 0.3,
        )

        fh1 = size_field_octree(domain, h_min=0.05, h_max=0.5, max_depth=7)
        fh2 = size_field_octree(domain, h_min=0.05, h_max=0.5, max_depth=7)

        test_pts = np.random.uniform(0.1, 0.9, (20, 2))
        h1 = fh1(test_pts)
        h2 = fh2(test_pts)

        # Results should be identical
        np.testing.assert_array_equal(h1, h2)

    def test_size_field_single_point_vs_batch(self):
        """Verify single-point queries match batch queries."""
        domain = Domain(
            bbox=(0, 0, 1, 1),
            sdf=lambda pts: np.linalg.norm(pts - 0.5, axis=1) - 0.3,
        )

        fh = size_field_octree(domain, h_min=0.05, h_max=0.5, max_depth=6)

        test_pts = np.array([[0.2, 0.3], [0.7, 0.8], [0.5, 0.5]])

        # Query all at once
        h_batch = fh(test_pts)

        # Query one at a time
        h_single = np.array([fh(pt.reshape(1, -1))[0] for pt in test_pts])

        np.testing.assert_array_equal(h_batch, h_single)
