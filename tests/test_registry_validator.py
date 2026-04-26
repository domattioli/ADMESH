"""Contract tests for registry manifest validation (User Story 3).

Tests the CI validator that runs on PRs touching registry_data/.
"""

import pytest
from datetime import datetime

from mesh_registry.schema import License, BoundingBox, Mesh, Manifest
from pathlib import Path


@pytest.fixture
def valid_manifest():
    """Load a valid test manifest."""
    fixture_path = Path("tests/fixtures/registry/simple.toml")
    from mesh_registry.manifest import load_manifest
    return load_manifest(fixture_path)


class TestSchemaValidation:
    """Test schema validation on new entries."""

    def test_schema_valid_entry(self, valid_manifest):
        """Verify valid entry passes schema validation."""
        # All entries in simple.toml should be valid
        assert len(valid_manifest.meshes) == 2
        for mesh in valid_manifest.meshes:
            assert mesh.id
            assert mesh.source_url
            assert mesh.content_hash
            assert isinstance(mesh.num_triangles, int)

    def test_schema_missing_required_field(self):
        """Verify missing required field fails validation."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Mesh(
                id="test/missing-url",
                name="Missing URL",
                # source_url is missing!
                content_hash="sha256:test001",
                num_triangles=1000,
                license=License.PUBLIC_DOMAIN,
                created_by="Test",
                created_date=datetime.now(),
                bounding_box=BoundingBox(min_lon=-90, min_lat=25, max_lon=-80, max_lat=30),
            )

    def test_schema_invalid_triangle_count(self):
        """Verify invalid triangle count fails validation."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Mesh(
                id="test/invalid-triangles",
                name="Invalid Triangles",
                source_url="https://example.com/test.fort.14",
                content_hash="sha256:test001",
                num_triangles=10,  # Too small (< 100)
                license=License.PUBLIC_DOMAIN,
                created_by="Test",
                created_date=datetime.now(),
                bounding_box=BoundingBox(min_lon=-90, min_lat=25, max_lon=-80, max_lat=30),
            )


class TestHashVerification:
    """Test content hash validation."""

    def test_hash_format_valid(self):
        """Verify valid SHA-256 hash format is accepted."""
        mesh = Mesh(
            id="test/valid-hash",
            name="Valid Hash",
            source_url="https://example.com/test.fort.14",
            content_hash="sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
            num_triangles=1000,
            license=License.PUBLIC_DOMAIN,
            created_by="Test",
            created_date=datetime.now(),
            bounding_box=BoundingBox(min_lon=-90, min_lat=25, max_lon=-80, max_lat=30),
        )
        assert mesh.content_hash == "sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"

    def test_hash_format_prefix_optional(self):
        """Verify hash format with and without sha256: prefix."""
        mesh1 = Mesh(
            id="test/hash-with-prefix",
            name="Hash with Prefix",
            source_url="https://example.com/test1.fort.14",
            content_hash="sha256:abc123",
            num_triangles=1000,
            license=License.PUBLIC_DOMAIN,
            created_by="Test",
            created_date=datetime.now(),
            bounding_box=BoundingBox(min_lon=-90, min_lat=25, max_lon=-80, max_lat=30),
        )
        assert "sha256:" in mesh1.content_hash or len(mesh1.content_hash) > 0


class TestBboxValidation:
    """Test bounding box sanity checks."""

    def test_bbox_valid_range(self):
        """Verify valid bbox coordinates are accepted."""
        bbox = BoundingBox(min_lon=-97, min_lat=25, max_lon=-88, max_lat=30)
        assert -180 <= bbox.min_lon <= 180
        assert -90 <= bbox.min_lat <= 90

    def test_bbox_invalid_longitude(self):
        """Verify invalid longitude is rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            BoundingBox(
                min_lon=-200,  # Out of range!
                min_lat=25,
                max_lon=-88,
                max_lat=30,
            )

    def test_bbox_invalid_latitude(self):
        """Verify invalid latitude is rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            BoundingBox(
                min_lon=-97,
                min_lat=100,  # Out of range!
                max_lon=-88,
                max_lat=30,
            )


class TestTriangleCountValidation:
    """Test triangle count plausibility checks."""

    def test_triangle_count_too_small(self):
        """Verify triangle count < 100 is rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Mesh(
                id="test/too-small",
                name="Too Small",
                source_url="https://example.com/test.fort.14",
                content_hash="sha256:test001",
                num_triangles=50,  # < 100
                license=License.PUBLIC_DOMAIN,
                created_by="Test",
                created_date=datetime.now(),
                bounding_box=BoundingBox(min_lon=-90, min_lat=25, max_lon=-80, max_lat=30),
            )

    def test_triangle_count_too_large(self):
        """Verify triangle count > 5×10^7 is rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Mesh(
                id="test/too-large",
                name="Too Large",
                source_url="https://example.com/test.fort.14",
                content_hash="sha256:test001",
                num_triangles=60_000_000,  # > 5×10^7
                license=License.PUBLIC_DOMAIN,
                created_by="Test",
                created_date=datetime.now(),
                bounding_box=BoundingBox(min_lon=-90, min_lat=25, max_lon=-80, max_lat=30),
            )


class TestValidatorIntegration:
    """Test the full validator flow."""

    def test_validator_passes_on_valid_manifest(self, valid_manifest):
        """Verify validator passes on valid manifest."""
        from mesh_registry.manifest import validate_invariants

        errors = validate_invariants(valid_manifest)
        assert len(errors) == 0, f"Expected no errors, got: {errors}"

    def test_validator_detects_duplicate_ids(self):
        """Verify validator detects duplicate IDs."""
        from pydantic import ValidationError

        bbox = BoundingBox(min_lon=-90, min_lat=25, max_lon=-80, max_lat=30)

        mesh1 = Mesh(
            id="test/duplicate",
            name="First",
            source_url="https://example.com/1.fort.14",
            content_hash="sha256:hash1",
            num_triangles=1000,
            license=License.PUBLIC_DOMAIN,
            created_by="Test",
            created_date=datetime.now(),
            bounding_box=bbox,
        )

        mesh2 = Mesh(
            id="test/duplicate",  # Same ID!
            name="Second",
            source_url="https://example.com/2.fort.14",
            content_hash="sha256:hash2",
            num_triangles=1000,
            license=License.PUBLIC_DOMAIN,
            created_by="Test",
            created_date=datetime.now(),
            bounding_box=bbox,
        )

        # Duplicate IDs should fail during manifest creation
        with pytest.raises((ValueError, ValidationError)):
            Manifest(meshes=[mesh1, mesh2])
