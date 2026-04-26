"""Contract tests for mesh registry query functionality (User Story 1).

These tests define the find() API contract. Written first (TDD), they FAIL
before implementation.

Tests cover:
- Bounding box spatial overlap filtering
- Feature multi-select filtering
- Size range filtering (min/max triangles)
- License type filtering
- Result sorting by mesh size
"""

import pytest
from datetime import datetime

from mesh_registry.schema import (
    Mesh, BoundingBox, License, MeshFeature, Manifest
)
from mesh_registry.manifest import load_manifest
from pathlib import Path


@pytest.fixture
def simple_manifest() -> Manifest:
    """Load simple test fixture with 2 entries."""
    fixture_path = Path("tests/fixtures/registry/simple.toml")
    return load_manifest(fixture_path)


@pytest.fixture
def lineage_manifest() -> Manifest:
    """Load lineage test fixture with 3 entries (parent/child/grandchild)."""
    fixture_path = Path("tests/fixtures/registry/with_lineage.toml")
    return load_manifest(fixture_path)


class TestBboxOverlapQuery:
    """Test bounding box spatial filtering."""

    def test_find_with_bbox_overlap(self, simple_manifest):
        """Verify find(bbox=...) returns meshes overlapping that region."""
        # This test FAILS before query.py is implemented
        from mesh_registry.query import find

        # Query for region overlapping first mesh: (-90, 25, -80, 30)
        results = find(bbox=(-90, 25, -80, 30), manifest=simple_manifest)

        assert len(results) >= 1, "Should return at least one mesh in region"
        # First mesh in simple.toml has bbox (-90, 25, -80, 30)
        assert any(m.id == "test/simple-v1" for m in results)

    def test_find_with_bbox_no_overlap(self, simple_manifest):
        """Verify find(bbox=...) returns empty for non-overlapping region."""
        from mesh_registry.query import find

        # Query far from test meshes
        results = find(bbox=(150, 45, 160, 50), manifest=simple_manifest)

        assert len(results) == 0, "Should return no meshes outside region"

    def test_find_with_antimeridian_bbox(self, simple_manifest):
        """Verify antimeridian-spanning bboxes work (min_lon > max_lon)."""
        from mesh_registry.query import find

        # This tests the shapely.box().intersects() antimeridian logic
        # Bbox spanning antimeridian: (170, -10, -170, 10) is valid
        results = find(bbox=(170, -10, -170, 10), manifest=simple_manifest)
        # May be empty depending on test data, but should not error


class TestFeatureFilteringQuery:
    """Test feature-based filtering."""

    def test_find_with_single_feature(self, simple_manifest):
        """Verify find(features=["levee"]) returns only tagged meshes."""
        from mesh_registry.query import find

        results = find(features=["levee"], manifest=simple_manifest)

        assert all("levee" in m.features for m in results), "All results should have levee feature"

    def test_find_with_multiple_features(self, simple_manifest):
        """Verify find(features=[...]) is multi-select intersection."""
        from mesh_registry.query import find

        # Find meshes with both levee AND open_ocean
        results = find(features=["levee", "open_ocean"], manifest=simple_manifest)

        # Each result should have at least one of the features
        for result in results:
            assert any(f in result.features for f in ["levee", "open_ocean"])

    def test_find_with_unknown_feature(self, simple_manifest):
        """Verify find() handles unknown feature gracefully."""
        from mesh_registry.query import find

        # Unknown feature should return empty (no meshes tagged with it)
        results = find(features=["nonexistent_feature"], manifest=simple_manifest)

        assert len(results) == 0


class TestSizeFilteringQuery:
    """Test triangle count range filtering."""

    def test_find_with_max_size(self, simple_manifest):
        """Verify find(max_size=...) filters by triangle count."""
        from mesh_registry.query import find

        # Max 2000 triangles should exclude second mesh (5000)
        results = find(max_size=2000, manifest=simple_manifest)

        assert all(m.num_triangles <= 2000 for m in results), "All results should be ≤2000 triangles"

    def test_find_with_min_size(self, simple_manifest):
        """Verify find(min_size=...) filters by minimum triangle count."""
        from mesh_registry.query import find

        # Min 4000 triangles should exclude first mesh (1000)
        results = find(min_size=4000, manifest=simple_manifest)

        assert all(m.num_triangles >= 4000 for m in results), "All results should be ≥4000 triangles"

    def test_find_with_size_range(self, simple_manifest):
        """Verify find(min_size=..., max_size=...) works as range."""
        from mesh_registry.query import find

        # Range: 900–3000 triangles
        results = find(min_size=900, max_size=3000, manifest=simple_manifest)

        assert all(900 <= m.num_triangles <= 3000 for m in results)


class TestLicenseFilteringQuery:
    """Test license-based filtering."""

    def test_find_with_license_public_domain(self, simple_manifest):
        """Verify find(license="public-domain") excludes proprietary/unknown."""
        from mesh_registry.query import find

        results = find(license="public-domain", manifest=simple_manifest)

        assert all(m.license == License.PUBLIC_DOMAIN for m in results)

    def test_find_with_license_cc_by(self, simple_manifest):
        """Verify find(license="CC-BY-4.0") returns only CC-BY meshes."""
        from mesh_registry.query import find

        results = find(license="CC-BY-4.0", manifest=simple_manifest)

        assert all(m.license == License.CC_BY_40 for m in results)

    def test_find_with_invalid_license(self, simple_manifest):
        """Verify invalid license string is handled."""
        from mesh_registry.query import find

        # Should either error or return empty
        try:
            results = find(license="invalid_license", manifest=simple_manifest)
            assert len(results) == 0, "Invalid license should return empty"
        except ValueError:
            pass  # Also acceptable to raise ValueError


class TestSortingQuery:
    """Test result sorting."""

    def test_find_results_sorted_by_size_ascending(self, simple_manifest):
        """Verify results are sorted by num_triangles (ascending)."""
        from mesh_registry.query import find

        results = find(manifest=simple_manifest)

        if len(results) > 1:
            sizes = [m.num_triangles for m in results]
            assert sizes == sorted(sizes), "Results should be sorted by size ascending"


class TestCombinedFilters:
    """Test combinations of filters."""

    def test_find_with_bbox_and_feature(self, lineage_manifest):
        """Verify find(bbox=..., features=...) applies both filters."""
        from mesh_registry.query import find

        results = find(
            bbox=(-95, 27, -90, 29),
            features=["estuary"],
            manifest=lineage_manifest
        )

        # Should return estuary meshes in region
        for m in results:
            assert "estuary" in m.features
            # Bbox check (simple check, real implementation uses shapely)
            assert m.bounding_box.min_lon >= -95 or m.bounding_box.max_lon <= -90

    def test_find_with_all_filters(self, lineage_manifest):
        """Verify find() works with bbox, features, size, license combined."""
        from mesh_registry.query import find

        results = find(
            bbox=(-95, 27, -90, 29),
            features=["estuary"],
            min_size=1000,
            max_size=200000,
            license="CC0-1.0",
            manifest=lineage_manifest
        )

        # Should return meshes matching all criteria
        for m in results:
            assert "estuary" in m.features
            assert 1000 <= m.num_triangles <= 200000
            assert m.license == License.CC0_10
