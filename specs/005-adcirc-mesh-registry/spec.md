# Feature Specification: ADCIRC Mesh Registry

**Feature Branch**: `005-adcirc-mesh-registry`  
**Created**: 2026-04-25  
**Status**: Draft  
**Input**: Federated mesh registry for coastal-simulation meshes (ADCIRC)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discover Meshes by Geographic Region and Features (Priority: P1)

A coastal researcher needs to find existing meshes covering a specific region (e.g., Gulf of Mexico) that include particular physical features (e.g., levees, breakwaters). Currently they search across scattered sources; a registry should enable searchable discovery.

**Why this priority**: Discovery is the core pain point. Without this, users still resort to manual searching across 5-6 sources. Solving discoverability unlocks all downstream value.

**Independent Test**: Can be tested by querying the registry with bounding box and feature filters and getting back matching mesh results.

**Acceptance Scenarios**:

1. **Given** a researcher wants meshes in the Gulf of Mexico region, **When** they query by bounding box `(-97, 25, -80, 30)`, **Then** they receive all registered meshes that overlap that region, sorted by mesh size.
2. **Given** a researcher needs meshes with levee or breakwater features, **When** they filter by features `["levee", "breakwater"]`, **Then** only meshes tagged with those features are returned.
3. **Given** a user wants to constrain by mesh size, **When** they filter by `max_triangles=10000`, **Then** only meshes with ≤10,000 triangles are returned.
4. **Given** a user is license-conscious, **When** they filter by license `"public-domain"`, **Then** only public-domain meshes are returned (no uncertain/unknown licenses).

---

### User Story 2 - Track Mesh Lineage and Provenance (Priority: P1)

When a researcher refines an existing mesh for a specific region or adds new features, they create a derived mesh. Future users must be able to trace the provenance: what was the parent mesh, what operations were applied, and who made the changes.

**Why this priority**: Without lineage, duplicate/conflicting versions accumulate and users can't trust which is authoritative. Provenance tracking prevents mesh proliferation and enables reproducibility.

**Independent Test**: Can be tested by tracing a derived mesh back to its parent and viewing the transformation operations in the registry.

**Acceptance Scenarios**:

1. **Given** a mesh is derived from a parent mesh, **When** viewing the derived mesh metadata, **Then** the registry displays the parent mesh ID and a link to it.
2. **Given** a derived mesh was created by refining a region, **When** examining the lineage, **Then** the operation `refine_box(bbox=...)` is recorded with its parameters.
3. **Given** a user views a mesh, **When** they click "view ancestry", **Then** a lineage DAG shows all ancestors and their operations up to the root mesh.

---

### User Story 3 - Submit New Meshes via Pull Request Workflow (Priority: P1)

Contributors (researchers, agencies) should be able to add new meshes to the registry using a familiar GitHub PR workflow. The system validates the submission against the schema automatically.

**Why this priority**: Community contribution model ensures sustainability and growth. Familiar Git/GitHub workflow lowers the barrier to entry.

**Independent Test**: Can be tested by submitting a PR with a new mesh entry, running CI validation, and confirming the entry is added after merge.

**Acceptance Scenarios**:

1. **Given** a contributor wants to add a mesh, **When** they create a PR that adds an entry to the manifest file, **Then** CI validation runs automatically.
2. **Given** a manifest entry is submitted, **When** CI runs, **Then** validation checks that all required fields are present and correctly formatted.
3. **Given** validation passes, **When** the PR is merged, **Then** the mesh entry is published to HuggingFace Datasets on the next release.

---

### User Story 4 - Programmatically Query Registry from Downstream Tools (Priority: P2)

Tools that consume ADCIRC meshes (mesh generators, simulators, visualization tools) should be able to query the registry programmatically to find and load appropriate meshes for their tasks.

**Why this priority**: Enables integration with the broader ADCIRC ecosystem. Supports automation of mesh selection and reduces manual effort in workflows.

**Independent Test**: Can be tested by importing the Python package and executing a query that returns mesh objects ready to use.

**Acceptance Scenarios**:

1. **Given** a tool imports the Python registry package, **When** it calls `registry.find(bbox=..., features=..., max_size=..., license=...)`, **Then** it receives mesh objects with file paths and metadata.
2. **Given** a mesh is found, **When** the tool requests to load it, **Then** the mesh file is automatically downloaded (if not cached) and opened.

---

### User Story 5 - Resolve License and Attribution Issues (Priority: P2)

Downstream users need clear license information to know if they can use, modify, or redistribute a mesh. Currently many meshes lack license metadata.

**Why this priority**: Solves a compliance risk. Enables confident reuse and commercial applications.

**Independent Test**: Can be tested by querying meshes and confirming license field is populated and queryable.

**Acceptance Scenarios**:

1. **Given** every mesh in the registry, **When** viewing its metadata, **Then** a license field is always present (one of: public-domain, MIT, CC-BY, CC-BY-SA, CC0, proprietary, or unknown with citation requirement).
2. **Given** a user searches by license, **When** they filter by license type, **Then** results are restricted to that license category.

---

### Edge Cases

- What happens when a mesh has been deleted or removed from a source? How is its record handled in the registry (tombstone vs. hard delete)?
- How does the system handle duplicate mesh entries pointing to the same content hash (deduplication)?
- What if a mesh's source URL becomes unavailable — is the mesh still discoverable and how does the system signal unavailability?
- How are mesh files versioned if the same mesh is updated in-place at its source URL?
- What happens when provenance data for an old mesh is incomplete or missing?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST maintain a structured manifest (TOML/JSON/YAML, format TBD) with one entry per mesh containing: name, source URL, content hash (SHA-256 or similar), license, geographic bounding box (min_lon, min_lat, max_lon, max_lat), number of triangles, physical features list, derived-from pointer (optional), contributor name/email, and review state (draft/approved/deprecated).

- **FR-002**: System MUST support a GitHub repository as the source of truth, accepting new mesh entries via pull requests against the manifest file.

- **FR-003**: System MUST validate manifest entries on PR submission via GitHub Actions CI, checking: required field presence, field format validity, valid bounding box coordinates, non-negative triangle count, valid license identifier, and valid SHA-256 hash format.

- **FR-004**: System MUST support querying meshes by: geographic bounding box (spatial overlap), physical features (multi-select), triangle count range (min/max), license type, and contributor.

- **FR-005**: System MUST display mesh deduplication signal: when multiple entries point to the same content hash, system flags them and indicates which is authoritative.

- **FR-006**: System MUST track and expose provenance: for each derived mesh, store its parent mesh ID and a list of operations applied (operation_type: string, parameters: dict, timestamp: ISO-8601).

- **FR-007**: System MUST publish the manifest and mesh files to HuggingFace Datasets on each GitHub release, generating a dataset card with search metadata, citation information, and download counts.

- **FR-008**: System MUST provide a Python package (thin loader) exposing an API: `registry.find(bbox=..., features=..., max_size=..., license=...) -> List[Mesh]`, where Mesh objects include metadata and a method to load the mesh file locally.

- **FR-009**: System MUST support license field validation: accepts one of a predefined list (public-domain, MIT, CC-BY, CC-BY-SA, CC0, proprietary) or "unknown" with a note on required attribution.

- **FR-010**: System MUST provide a web search and filter interface on HuggingFace Datasets, leveraging HF's native tooling for browsing, filtering, and downloading.

- **FR-011**: System MUST seed the registry with approximately 5 initial meshes from diverse sources (e.g., NOAA, academic corpora, GitHub repos) to demonstrate coverage and value.

- **FR-012**: System MUST handle mesh file versioning or URL changes gracefully: support fallback URLs and indicate file availability status.

### Key Entities

- **Mesh**: Represents a single coastal-simulation mesh. Attributes: id (unique identifier), name, source_url, content_hash (SHA-256), num_triangles, license, bounding_box (4-tuple), features (list of tags), created_by (contributor), created_date (ISO-8601), review_state (draft/approved/deprecated), derived_from (optional parent mesh ID), provenance_history (list of operations).

- **MeshFeature**: Represents a physical or geographic characteristic of a mesh. Examples: "levee", "breakwater", "open_ocean", "inlet", "estuary", "tidal_flat", "barrier_island". Attributes: name, description.

- **MeshOperation**: Represents a transformation applied to a parent mesh to create a derived mesh. Attributes: operation_type (e.g., "refine_box", "add_island", "remove_region"), parameters (dict of operation-specific args), applied_date (ISO-8601), applied_by (contributor).

- **License**: Represents licensing metadata. Attributes: identifier (string from predefined list or "unknown"), full_name (human-readable), is_open_source (boolean), allows_redistribution (boolean), attribution_required (boolean).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Time to discover a suitable mesh is reduced from ~2 hours (manual search across scattered sources) to under 5 minutes using the registry search interface.

- **SC-002**: Registry includes at least 5 seed meshes at launch (Phase 1), with a clear path to grow to 50+ meshes within 6 months through community submissions.

- **SC-003**: At least 80% of registered meshes have complete, valid license metadata (not "unknown" or blank).

- **SC-004**: New mesh contributions via PR workflow take under 30 minutes to validate and merge, with zero critical validation errors escaping CI.

- **SC-005**: Downstream tools (mesh generators, simulators) can programmatically query and load meshes using the Python API without custom parsing logic.

- **SC-006**: The HuggingFace Datasets interface is live and publicly accessible, with search/filter functionality working for all supported query types.

- **SC-007**: Lineage tracing is enabled for at least 3 derived-mesh examples, showing a clear parent→child relationship and recorded operations.

- **SC-008**: Zero duplicate entries in the registry (all unique meshes have distinct IDs; duplicates are flagged and consolidated).

## Assumptions

- **Scope**: The registry focuses on ADCIRC-compatible meshes in ASCII fort.14 format (or equivalent). Other mesh formats are out of scope for Phase 1.

- **Geographic Focus**: While the registry is open-ended, the initial 5 seed meshes will emphasize U.S. coastal regions (Atlantic, Gulf of Mexico, Pacific) and academic examples, as these have the highest discoverability problem.

- **Schema Stability**: The manifest schema is designed to be extensible; contributors can add optional fields without breaking existing consumers. Adding new required fields is a breaking change and requires a major version bump.

- **Data Ownership**: Contributors retain ownership of their mesh files; the registry catalogs and links to them but does not host the files (unless explicitly deposited to HuggingFace Datasets via CI).

- **Mesh Availability**: Source URLs may change or become unavailable over time. The registry records last-known URLs and availability status but does not guarantee perpetual hosting.

- **No Machine Learning at Phase 1**: AI-assisted bundle generation (clustering, similarity search, LLM queries) is explicitly deferred to Phase 3. Phase 1 focuses on declarative metadata and human-driven discovery.

- **Community Moderation**: Submissions are reviewed by maintainers or designated reviewers before merge. The bar is schema compliance + basic sanity checks (valid mesh file, reasonable metadata), not scientific review of mesh quality.

- **Platform**: The registry is web-first and platform-agnostic. Python package support is provided but not mandated for consumption; users can also browse and download via HuggingFace Datasets web UI.
