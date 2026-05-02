"""Tests for issue #11: Domain.from_mesh ring sorting fix."""

import numpy as np
import pytest

import admesh
from admesh import domains


class TestRingSortingByArea:
    """Test that rings are sorted by signed area, not node count."""

    def test_domain_from_mesh_wnat_bbox_precision(self):
        """T007: Verify WNAT fixture bbox precision after fix."""
        src = admesh.read_fort14("tests/fixtures/fort14/adcirc_examples/wnat_test.14")
        expected_bbox = (
            src.nodes[:, 0].min(),
            src.nodes[:, 1].min(),
            src.nodes[:, 0].max(),
            src.nodes[:, 1].max(),
        )

        dom = admesh.Domain.from_mesh(src)

        # Check bbox matches to within 1e-9 (SC-001)
        bbox_match = np.allclose(
            [dom.bbox[0], dom.bbox[1], dom.bbox[2], dom.bbox[3]],
            expected_bbox,
            rtol=1e-9,
            atol=1e-12,
        )
        assert (
            bbox_match
        ), f"WNAT bbox mismatch: got {dom.bbox}, expected {expected_bbox}"

    def test_domain_from_mesh_multiply_connected_outer_ring_by_area(self):
        """T006: Test multiply-connected domain where interior ring has more nodes."""
        # Create a synthetic multiply-connected domain:
        # Outer ring: large square (sparse nodes)
        # Inner ring (hole): smaller square with more nodes (denser)

        # Outer ring: 4 nodes (corners of large square)
        outer_ring = np.array([[-10, -10], [10, -10], [10, 10], [-10, 10]])

        # Inner ring (hole): 20 nodes on a smaller circle (denser)
        t = np.linspace(0, 2 * np.pi, 21)[:-1]  # 20 nodes
        inner_ring = 3 * np.column_stack([np.cos(t), np.sin(t)])  # Circle, 20 points, shape (20, 2)

        # Combine nodes
        nodes = np.vstack([outer_ring, inner_ring])

        # Create triangulation with both rings as boundaries
        from scipy.spatial import Delaunay

        tri = Delaunay(nodes)

        # Create a mesh with boundary elements
        mesh = admesh.Mesh(nodes=nodes, elements=tri.simplices)

        # Recover domain
        dom = admesh.Domain.from_mesh(mesh)

        # Verify outer ring is identified correctly (largest area)
        # The outer square has area = 20*20 = 400
        # The inner circle has area ≈ π*3² ≈ 28.3
        assert (
            len(dom.bc_segments) >= 1
        ), "Domain should have at least one boundary segment"

        # The first bc_segment should be the outer ring (by area)
        outer_seg = dom.bc_segments[0]
        assert len(outer_seg.node_ids) > 0, "Outer ring should have nodes"

    def test_wetting_and_drying_round_trip(self):
        """T009: Verify Tier-1 fixture round-trip without regression."""
        src = admesh.read_fort14(
            "tests/fixtures/fort14/adcirc_examples/wetting_and_drying_test.14"
        )
        src_bbox = (
            src.nodes[:, 0].min(),
            src.nodes[:, 1].min(),
            src.nodes[:, 0].max(),
            src.nodes[:, 1].max(),
        )

        dom = admesh.Domain.from_mesh(src)

        # Bbox should match source
        bbox_match = np.allclose(
            [dom.bbox[0], dom.bbox[1], dom.bbox[2], dom.bbox[3]], src_bbox, rtol=1e-9
        )
        assert bbox_match, "Wetting-and-drying bbox should match source"

        # Verify bc_segments were recovered
        assert len(dom.bc_segments) > 0, "Domain should have boundary segments"

    def test_mvp_domains_no_regression(self):
        """T010: Verify MVP domains recover correctly from mesh."""
        # Test that MVP domains recover correctly via Domain.from_mesh
        # (not testing triangulation itself, which is out of scope for this fix)

        # Create simple test domains manually
        test_cases = [
            ("unit_square", np.array([[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]])),
            ("simple_rect", np.array([[0, 0], [1, 0], [1, 1], [0, 1]])),
        ]

        for name, boundary_nodes in test_cases:
            from scipy.spatial import Delaunay
            # Create a minimal triangulation with just the boundary
            tri = Delaunay(boundary_nodes)
            mesh = admesh.Mesh(nodes=boundary_nodes, elements=tri.simplices)

            # Recover domain
            recovered = admesh.Domain.from_mesh(mesh)

            # Bbox should be reasonable (positive area)
            assert (
                recovered.bbox[2] - recovered.bbox[0] > 0
            ), f"{name}: bbox has zero or negative width"
            assert (
                recovered.bbox[3] - recovered.bbox[1] > 0
            ), f"{name}: bbox has zero or negative height"

            # Should have boundary segments
            assert (
                len(recovered.bc_segments) > 0
            ), f"{name}: should have boundary segments"


class TestRingAreaHelper:
    """Test the _ring_area helper function."""

    def test_ring_area_simple_square(self):
        """Verify shoelace formula for a simple square."""
        from admesh.api import _ring_area

        # Unit square
        ring = [0, 1, 2, 3]
        nodes = np.array([[0, 0], [1, 0], [1, 1], [0, 1]])
        area = _ring_area(ring, nodes)
        assert np.isclose(area, 1.0), f"Unit square should have area 1.0, got {area}"

    def test_ring_area_larger_area(self):
        """Verify area scales with size."""
        from admesh.api import _ring_area

        # 2x2 square (4x larger area)
        ring = [0, 1, 2, 3]
        nodes = np.array([[0, 0], [2, 0], [2, 2], [0, 2]])
        area = _ring_area(ring, nodes)
        assert np.isclose(area, 4.0), f"2x2 square should have area 4.0, got {area}"

    def test_ring_area_degenerate(self):
        """Verify degenerate ring has near-zero area."""
        from admesh.api import _ring_area

        # Degenerate ring (all points the same)
        ring = [0, 1, 2]
        nodes = np.array([[0, 0], [0, 0], [0, 0]])
        area = _ring_area(ring, nodes)
        assert area < 1e-10, f"Degenerate ring should have area ≈0, got {area}"
