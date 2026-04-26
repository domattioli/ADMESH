"""Pydantic v2 schema models for ADCIRC mesh registry.

Entities:
- Mesh: Main entity representing a coastal-simulation mesh
- BoundingBox: Geographic extent (antimeridian-safe)
- MeshOperation: Transformation applied to create derived mesh
- MeshFeature: Physical/geographic characteristic (controlled vocabulary)
- License: Licensing metadata
- Manifest: Container for mesh entries with invariant validation
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class BoundingBox(BaseModel):
    """Geographic bounding box with antimeridian crossing support."""

    min_lon: float = Field(..., description="Minimum longitude (westernmost)")
    min_lat: float = Field(..., description="Minimum latitude (southernmost)")
    max_lon: float = Field(..., description="Maximum longitude (easternmost)")
    max_lat: float = Field(..., description="Maximum latitude (northernmost)")

    @field_validator("min_lon", "max_lon")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not -180 <= v <= 180:
            raise ValueError(f"Longitude must be in [-180, 180], got {v}")
        return v

    @field_validator("min_lat", "max_lat")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not -90 <= v <= 90:
            raise ValueError(f"Latitude must be in [-90, 90], got {v}")
        return v


class MeshFeature(str, Enum):
    """Controlled vocabulary of mesh features."""

    OPEN_OCEAN = "open_ocean"
    INLET = "inlet"
    ESTUARY = "estuary"
    TIDAL_FLAT = "tidal_flat"
    BARRIER_ISLAND = "barrier_island"
    LEVEE = "levee"
    BREAKWATER = "breakwater"
    WETLAND = "wetland"
    SHIPPING_CHANNEL = "shipping_channel"
    RIVER_OUTFLOW = "river_outflow"
    BAY = "bay"
    LAGOON = "lagoon"
    REEF = "reef"


class License(str, Enum):
    """License identifiers with redistribution semantics."""

    PUBLIC_DOMAIN = "public-domain"
    MIT = "MIT"
    CC_BY_40 = "CC-BY-4.0"
    CC_BY_SA_40 = "CC-BY-SA-4.0"
    CC0_10 = "CC0-1.0"
    PROPRIETARY = "proprietary"
    UNKNOWN = "unknown"


class OperationKind(str, Enum):
    """Types of mesh transformations."""

    REFINE_BOX = "refine_box"
    COARSEN_BOX = "coarsen_box"
    ADD_ISLAND = "add_island"
    REMOVE_REGION = "remove_region"
    ADD_LEVEE = "add_levee"
    SPLICE = "splice"
    OTHER = "other"


class MeshOperation(BaseModel):
    """Transformation applied to parent mesh to create derived mesh."""

    operation_type: OperationKind = Field(..., description="Type of transformation")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Operation-specific parameters")
    applied_date: datetime = Field(..., description="When this operation was applied")
    applied_by: str = Field(..., description="Who applied this operation (name/email)")


class Mesh(BaseModel):
    """Coastal-simulation mesh with metadata and provenance."""

    # Primary identifier
    id: str = Field(..., description="Composite slug: <namespace>/<name>@<version>")
    name: str = Field(..., description="Human-readable mesh name")

    # Source and content
    source_url: str = Field(..., description="URL to canonical mesh file")
    content_hash: str = Field(..., description="SHA-256 hash of canonical mesh file")

    # Characteristics
    num_triangles: int = Field(..., ge=100, le=5e7, description="Triangle count")
    license: License = Field(..., description="License identifier")
    bounding_box: BoundingBox = Field(..., description="Geographic extent")
    features: List[MeshFeature] = Field(default_factory=list, description="Physical features")

    # Mirroring eligibility
    mirror_eligible: bool = Field(default=False, description="Can be mirrored to HuggingFace (derived from license)")

    # Provenance and attribution
    created_by: str = Field(..., description="Contributor name/email")
    created_date: datetime = Field(..., description="When mesh was created")
    derived_from: Optional[str] = Field(default=None, description="Parent mesh ID (if derived)")
    provenance_history: List[MeshOperation] = Field(default_factory=list, description="Transformations from parent")

    # Review workflow
    review_state: str = Field(default="draft", description="draft, approved, or deprecated")
    deprecation_reason: Optional[str] = Field(default=None, description="Why this mesh was deprecated")
    deprecated_date: Optional[datetime] = Field(default=None, description="When deprecated")

    # Deduplication
    authoritative: bool = Field(default=False, description="Is this the authoritative entry for its content_hash?")

    @field_validator("mirror_eligible", mode="before")
    @classmethod
    def set_mirror_eligible(cls, v: Any, info) -> bool:
        """Derive mirror_eligible from license if not explicitly set."""
        if v is not None:
            return v
        license_field = info.data.get("license")
        if license_field:
            redistributable = license_field in {
                License.PUBLIC_DOMAIN,
                License.MIT,
                License.CC_BY_40,
                License.CC_BY_SA_40,
                License.CC0_10,
            }
            return redistributable
        return False

    @field_validator("review_state")
    @classmethod
    def validate_review_state(cls, v: str) -> str:
        if v not in {"draft", "approved", "deprecated"}:
            raise ValueError(f"review_state must be draft, approved, or deprecated, got {v}")
        return v

    @model_validator(mode="after")
    def validate_deprecation_consistency(self):
        """Ensure deprecation fields are consistent."""
        if self.review_state == "deprecated":
            if not self.deprecation_reason:
                raise ValueError("deprecation_reason required when review_state=deprecated")
            if not self.deprecated_date:
                raise ValueError("deprecated_date required when review_state=deprecated")
        else:
            if self.deprecation_reason or self.deprecated_date:
                raise ValueError("deprecation fields only allowed when review_state=deprecated")
        return self

    def lineage(self, manifest: Optional["Manifest"] = None) -> List["Mesh"]:
        """Return list of ancestor meshes up to root.

        Requires manifest to resolve parent IDs.
        Returns ancestors in order from immediate parent to root.
        """
        if manifest is None:
            raise ValueError("manifest required to resolve lineage")

        ancestors = []
        current = self
        visited = {current.id}

        while current.derived_from:
            parent = manifest.get_mesh_by_id(current.derived_from)
            if not parent:
                raise ValueError(f"Parent mesh {current.derived_from} not found")
            if parent.id in visited:
                raise ValueError(f"Cycle detected in lineage: {parent.id}")
            ancestors.append(parent)
            visited.add(parent.id)
            current = parent

        return ancestors


class Manifest(BaseModel):
    """Container for mesh entries with schema version and validation."""

    schema_version: str = Field(default="1.0", description="Manifest schema version")
    meshes: List[Mesh] = Field(default_factory=list, description="Array of mesh entries")

    @model_validator(mode="after")
    def validate_invariants(self):
        """Validate manifest-level invariants.

        Checks:
        - Unique IDs
        - No dangling derived_from references
        - No cycles in derived_from DAG
        - At most one authoritative per content_hash
        - Tombstone consistency
        """
        mesh_by_id = {m.id: m for m in self.meshes}

        # Check unique IDs
        if len(mesh_by_id) != len(self.meshes):
            raise ValueError("Duplicate mesh IDs found")

        # Check no dangling derived_from
        for mesh in self.meshes:
            if mesh.derived_from and mesh.derived_from not in mesh_by_id:
                raise ValueError(f"Dangling derived_from: {mesh.derived_from} (from {mesh.id})")

        # Check no cycles
        def has_cycle(mesh_id: str, visited: set, path: set) -> bool:
            if mesh_id in path:
                return True
            if mesh_id in visited:
                return False
            visited.add(mesh_id)
            path.add(mesh_id)

            mesh = mesh_by_id[mesh_id]
            if mesh.derived_from:
                if has_cycle(mesh.derived_from, visited, path):
                    return True

            path.remove(mesh_id)
            return False

        visited = set()
        for mesh in self.meshes:
            if mesh.id not in visited and has_cycle(mesh.id, visited, set()):
                raise ValueError(f"Cycle detected in derived_from DAG starting from {mesh.id}")

        # Check at most one authoritative per content_hash
        hash_to_authoritative = {}
        for mesh in self.meshes:
            if mesh.authoritative:
                if mesh.content_hash in hash_to_authoritative:
                    raise ValueError(f"Multiple authoritative entries for hash {mesh.content_hash}")
                hash_to_authoritative[mesh.content_hash] = mesh.id

        # Check tombstone consistency
        for mesh in self.meshes:
            if mesh.review_state == "deprecated":
                if not mesh.deprecation_reason or not mesh.deprecated_date:
                    raise ValueError(f"Incomplete deprecation for {mesh.id}")

        return self

    def get_mesh_by_id(self, mesh_id: str) -> Optional[Mesh]:
        """Find mesh by composite ID."""
        for mesh in self.meshes:
            if mesh.id == mesh_id:
                return mesh
        return None

    def get_schema_json(self) -> Dict[str, Any]:
        """Export schema as JSON-Schema for HuggingFace dataset card."""
        return Mesh.model_json_schema()
