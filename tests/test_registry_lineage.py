"""Contract tests for mesh lineage and provenance tracking (User Story 2).

Tests the ability to:
- Trace mesh ancestry (lineage DAG)
- Resolve parent mesh IDs
- Detect cycles in derivation graph
- Access provenance history
"""

import pytest
from datetime import datetime

from mesh_registry.schema import (
    Mesh, BoundingBox, License, MeshFeature, Manifest, MeshOperation, OperationKind
)
from mesh_registry.manifest import load_manifest
from pathlib import Path


@pytest.fixture
def lineage_manifest() -> Manifest:
    """Load lineage test fixture with 3 entries (parent/child/grandchild)."""
    fixture_path = Path("tests/fixtures/registry/with_lineage.toml")
    return load_manifest(fixture_path)


class TestLineageResolution:
    """Test lineage DAG traversal and ancestor resolution."""

    def test_mesh_lineage_from_grandchild(self, lineage_manifest):
        """Verify Mesh.lineage() returns ancestors up to root."""
        grandchild = lineage_manifest.get_mesh_by_id("test/grandchild-v1")
        assert grandchild is not None

        # Get lineage: should return [derived, parent]
        ancestors = grandchild.lineage(manifest=lineage_manifest)

        assert len(ancestors) == 2, "Grandchild should have 2 ancestors"
        assert ancestors[0].id == "test/derived-v1", "First ancestor should be immediate parent"
        assert ancestors[1].id == "test/parent-v1", "Second ancestor should be grandparent"

    def test_mesh_lineage_from_derived(self, lineage_manifest):
        """Verify lineage from derived mesh returns only parent."""
        derived = lineage_manifest.get_mesh_by_id("test/derived-v1")
        assert derived is not None

        ancestors = derived.lineage(manifest=lineage_manifest)

        assert len(ancestors) == 1, "Derived should have 1 ancestor"
        assert ancestors[0].id == "test/parent-v1"

    def test_mesh_lineage_from_root(self, lineage_manifest):
        """Verify lineage from root mesh returns empty list."""
        parent = lineage_manifest.get_mesh_by_id("test/parent-v1")
        assert parent is not None

        ancestors = parent.lineage(manifest=lineage_manifest)

        assert len(ancestors) == 0, "Root mesh should have no ancestors"

    def test_lineage_preserves_order(self, lineage_manifest):
        """Verify lineage is ordered from immediate parent to root."""
        grandchild = lineage_manifest.get_mesh_by_id("test/grandchild-v1")

        ancestors = grandchild.lineage(manifest=lineage_manifest)

        # Should be [immediate parent, grandparent, ...]
        for i in range(len(ancestors) - 1):
            current_parent = ancestors[i].id
            next_ancestor_parent = ancestors[i + 1].id
            # Verify the next ancestor is actually the parent of the current one
            assert ancestors[i].derived_from == ancestors[i + 1].id


class TestParentResolution:
    """Test resolving parent mesh IDs to actual Mesh objects."""

    def test_resolve_parent_by_derived_from(self, lineage_manifest):
        """Verify derived_from ID resolves to parent Mesh object."""
        derived = lineage_manifest.get_mesh_by_id("test/derived-v1")
        assert derived is not None
        assert derived.derived_from == "test/parent-v1"

        parent = lineage_manifest.get_mesh_by_id(derived.derived_from)

        assert parent is not None, "Parent should be resolved"
        assert parent.id == "test/parent-v1"

    def test_parent_resolution_chain(self, lineage_manifest):
        """Verify multi-level parent resolution works."""
        # Grandchild → derived → parent
        mesh = lineage_manifest.get_mesh_by_id("test/grandchild-v1")
        assert mesh.derived_from == "test/derived-v1"

        derived = lineage_manifest.get_mesh_by_id(mesh.derived_from)
        assert derived.derived_from == "test/parent-v1"

        parent = lineage_manifest.get_mesh_by_id(derived.derived_from)
        assert parent.derived_from is None, "Root should have no parent"

    def test_dangling_parent_reference_fails(self):
        """Verify dangling derived_from raises error during manifest validation."""
        from mesh_registry.schema import BoundingBox
        from pydantic import ValidationError

        bad_mesh = Mesh(
            id="test/orphan",
            name="Orphan Mesh",
            source_url="https://example.com/orphan.fort.14",
            content_hash="sha256:orphan001",
            num_triangles=1000,
            license=License.PUBLIC_DOMAIN,
            created_by="Test",
            created_date=datetime.now(),
            derived_from="test/nonexistent-parent",  # This parent doesn't exist
            bounding_box=BoundingBox(
                min_lon=-90, min_lat=25, max_lon=-80, max_lat=30
            ),
        )

        # Creating a manifest with dangling ref should fail
        with pytest.raises((ValueError, ValidationError)):
            Manifest(meshes=[bad_mesh])


class TestDAGCycleDetection:
    """Test detection of cycles in derivation DAG."""

    def test_cycle_detection_simple(self):
        """Verify simple cycle (A→B→A) is detected."""
        from mesh_registry.schema import BoundingBox
        from pydantic import ValidationError

        bbox = BoundingBox(min_lon=-90, min_lat=25, max_lon=-80, max_lat=30)

        mesh_a = Mesh(
            id="test/a",
            name="Mesh A",
            source_url="https://example.com/a.fort.14",
            content_hash="sha256:a001",
            num_triangles=1000,
            license=License.PUBLIC_DOMAIN,
            created_by="Test",
            created_date=datetime.now(),
            derived_from="test/b",  # Points to B
            bounding_box=bbox,
        )

        mesh_b = Mesh(
            id="test/b",
            name="Mesh B",
            source_url="https://example.com/b.fort.14",
            content_hash="sha256:b001",
            num_triangles=1000,
            license=License.PUBLIC_DOMAIN,
            created_by="Test",
            created_date=datetime.now(),
            derived_from="test/a",  # Points back to A (cycle!)
            bounding_box=bbox,
        )

        # Creating manifest with cycle should fail
        with pytest.raises((ValueError, ValidationError)):
            Manifest(meshes=[mesh_a, mesh_b])

    def test_cycle_detection_self_reference(self):
        """Verify self-reference cycle (A→A) is detected."""
        from mesh_registry.schema import BoundingBox
        from pydantic import ValidationError

        bbox = BoundingBox(min_lon=-90, min_lat=25, max_lon=-80, max_lat=30)

        mesh_self = Mesh(
            id="test/self-ref",
            name="Self-Referencing Mesh",
            source_url="https://example.com/self.fort.14",
            content_hash="sha256:self001",
            num_triangles=1000,
            license=License.PUBLIC_DOMAIN,
            created_by="Test",
            created_date=datetime.now(),
            derived_from="test/self-ref",  # Self-reference!
            bounding_box=bbox,
        )

        with pytest.raises((ValueError, ValidationError)):
            Manifest(meshes=[mesh_self])

    def test_cycle_detection_long_chain(self):
        """Verify cycle in longer chain (A→B→C→A) is detected."""
        from mesh_registry.schema import BoundingBox
        from pydantic import ValidationError

        bbox = BoundingBox(min_lon=-90, min_lat=25, max_lon=-80, max_lat=30)

        meshes = []
        for i, letter in enumerate(["a", "b", "c"]):
            next_letter = ["b", "c", "a"][i]  # a→b, b→c, c→a (cycle!)
            mesh = Mesh(
                id=f"test/{letter}",
                name=f"Mesh {letter.upper()}",
                source_url=f"https://example.com/{letter}.fort.14",
                content_hash=f"sha256:{letter}001",
                num_triangles=1000,
                license=License.PUBLIC_DOMAIN,
                created_by="Test",
                created_date=datetime.now(),
                derived_from=f"test/{next_letter}",
                bounding_box=bbox,
            )
            meshes.append(mesh)

        with pytest.raises((ValueError, ValidationError)):
            Manifest(meshes=meshes)


class TestProvenanceHistory:
    """Test access to provenance (operations) history."""

    def test_provenance_history_access(self, lineage_manifest):
        """Verify provenance_history is accessible and populated."""
        derived = lineage_manifest.get_mesh_by_id("test/derived-v1")
        assert derived is not None

        # Should have one operation: refine_box
        assert len(derived.provenance_history) >= 1

        op = derived.provenance_history[0]
        assert op.operation_type == OperationKind.REFINE_BOX
        assert "bbox" in op.parameters
        assert "target_resolution" in op.parameters

    def test_provenance_history_ordering(self, lineage_manifest):
        """Verify provenance history is ordered by applied_date."""
        grandchild = lineage_manifest.get_mesh_by_id("test/grandchild-v1")
        assert grandchild is not None

        # Should have operations in chronological order
        history = grandchild.provenance_history
        for i in range(len(history) - 1):
            assert history[i].applied_date <= history[i + 1].applied_date

    def test_provenance_operation_parameters(self, lineage_manifest):
        """Verify operation parameters are preserved correctly."""
        derived = lineage_manifest.get_mesh_by_id("test/derived-v1")

        op = derived.provenance_history[0]
        assert op.operation_type == OperationKind.REFINE_BOX
        assert op.applied_by == "Test Suite <test@example.com>"
        assert isinstance(op.parameters, dict)
        assert "bbox" in op.parameters
        assert isinstance(op.parameters["bbox"], list)
        assert len(op.parameters["bbox"]) == 4

    def test_lineage_includes_operations(self, lineage_manifest):
        """Verify that lineage resolution also provides operation context."""
        grandchild = lineage_manifest.get_mesh_by_id("test/grandchild-v1")

        ancestors = grandchild.lineage(manifest=lineage_manifest)

        # Both ancestors should be accessible with their full history
        for ancestor in ancestors:
            assert hasattr(ancestor, "provenance_history")
            # Intermediate ancestors may have operations
            if ancestor.id == "test/derived-v1":
                assert len(ancestor.provenance_history) > 0


class TestAuthoritativeVersionResolution:
    """Test authoritative mesh detection for deduplication."""

    def test_authoritative_flag_preserved(self, lineage_manifest):
        """Verify authoritative flag is accessible on mesh objects."""
        parent = lineage_manifest.get_mesh_by_id("test/parent-v1")
        assert hasattr(parent, "authoritative")
        # Default should be False unless explicitly set
        assert isinstance(parent.authoritative, bool)

    def test_multiple_authoritative_per_hash_fails(self):
        """Verify manifest rejects multiple authoritative entries for same hash."""
        from mesh_registry.schema import BoundingBox
        from pydantic import ValidationError

        bbox = BoundingBox(min_lon=-90, min_lat=25, max_lon=-80, max_lat=30)
        same_hash = "sha256:duplicate001"

        mesh1 = Mesh(
            id="test/dup1",
            name="Duplicate 1",
            source_url="https://example.com/dup1.fort.14",
            content_hash=same_hash,
            num_triangles=1000,
            license=License.PUBLIC_DOMAIN,
            created_by="Test",
            created_date=datetime.now(),
            authoritative=True,
            bounding_box=bbox,
        )

        mesh2 = Mesh(
            id="test/dup2",
            name="Duplicate 2",
            source_url="https://example.com/dup2.fort.14",
            content_hash=same_hash,
            num_triangles=1000,
            license=License.PUBLIC_DOMAIN,
            created_by="Test",
            created_date=datetime.now(),
            authoritative=True,  # Also authoritative (conflict!)
            bounding_box=bbox,
        )

        with pytest.raises((ValueError, ValidationError)):
            Manifest(meshes=[mesh1, mesh2])
