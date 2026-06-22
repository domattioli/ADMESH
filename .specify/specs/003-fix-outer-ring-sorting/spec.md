# Feature Specification: Fix Domain.from_mesh Ring Sorting

**Feature Branch**: `claude/pensive-goodall-r2Td2`  
**Created**: 2026-04-26  
**Status**: Draft  
**Input**: Issue #11 - Domain.from_mesh picks wrong outer ring (sorts by node count, not area)

## User Scenarios & Testing

### User Story 1 - Recover Multiply-Connected Domains from Real-World Meshes (Priority: P1)

A user has a real-world coastal ADCIRC mesh with multiply-connected topology (outer ocean boundary + multiple interior island/coastline rings). They call `Domain.from_mesh(mesh)` to recover the domain geometry and create a fresh triangulation.

**Why this priority**: This is the core use case that is currently broken. Real-world fixtures like WNAT (Western North Atlantic) fail outright, producing empty meshes or nonsensical results.

**Independent Test**: Can be fully tested by calling `Domain.from_mesh(wnat_test_mesh)` and verifying the returned domain's bbox matches the source mesh's actual extent.

**Acceptance Scenarios**:

1. **Given** a multiply-connected mesh where the internal coastline has MORE nodes than the outer ocean ring, **When** `Domain.from_mesh(src)` is called, **Then** the outer ring (by area) is correctly identified and the domain's bbox spans the entire source mesh extent.
2. **Given** a source mesh with bbox `[-97.85, 8.00]` to `[-60.04, 45.77]`, **When** `Domain.from_mesh(src)` is called, **Then** the returned domain's bbox matches the source to within relative tolerance `1e-9`.
3. **Given** the recovered domain and a downstream `triangulate(domain, h_min=0.05, h_max=2.0, ...)` call, **When** executed, **Then** a non-empty mesh is produced (not a ValueError from a zero-size array).

---

### User Story 2 - Tier-1 ADCIRC Fixture Round-Trip (Priority: P1)

A user loads the Tier-1 acceptance test fixture (wetting-and-drying coastal example with internal weirs) via `Domain.from_mesh`, then re-triangulates. The fresh mesh should preserve the domain extent and structure.

**Why this priority**: Tier-1 is a release-gate requirement. This fixture is relatively small (2700 nodes) and is the primary validation target before v0.1.0 ships.

**Independent Test**: `Domain.from_mesh(tier1_mesh)` followed by `triangulate(domain, ...)` produces a valid mesh with area ≥95% of the original domain area.

**Acceptance Scenarios**:

1. **Given** the wetting-and-drying-test.14 fixture, **When** loaded and passed through `Domain.from_mesh`, **Then** the recovered domain bbox matches the fixture's original extent.
2. **Given** a fresh `triangulate(domain, ...)` call, **When** executed, **Then** the new mesh has at least 85% of the original mesh's area (trade-off: new mesh is usually slightly smaller due to refinement constraints, but not drastically).

---

### User Story 3 - No Regression on Simple Polygon Domains (Priority: P2)

Existing tests on synthetic 5-domain suite (square, L-shape, U-shape, square-with-hole, annulus) must continue to pass. These domains are typically constructed as explicit polygons, not recovered from meshes, so they should not be affected by the ring-sorting change. However, we verify no regression.

**Why this priority**: Medium priority—these are MVPs and should already work, but we want to ensure the fix doesn't break existing happy paths.

**Independent Test**: All 5 synthetic domains continue to round-trip: `Domain.from_polygon(...)` → `triangulate(...)` → results match expectations.

**Acceptance Scenarios**:

1. **Given** any of the 5 MVP polygon domains, **When** passed through `Domain.from_mesh(triangulated_version)`, **Then** the recovered domain's bbox and topology match the original.

---

### Edge Cases

- What happens when a domain has multiple rings with identical node counts? (Solution: tie-break by area; largest area wins as outer ring.)
- What happens when a multiply-connected domain is read from a file that lists rings in an arbitrary order? (Solution: the sort-by-area guarantees a canonical ordering independent of input order.)
- What happens when a ring is degenerate (e.g., a single repeated node)? (Solution: the signed area formula returns 0 or very small values; correctly ranks below valid rings.)

## Requirements

### Functional Requirements

- **FR-001**: `Domain.from_mesh(src)` MUST identify the outer boundary ring as the ring with the **largest signed area** (not node count).
- **FR-002**: The function MUST rank interior rings (holes) by **decreasing area** so that larger holes are processed before smaller ones (preserves geometric intent).
- **FR-003**: The recovered domain's bounding box MUST match the source mesh's node extent to within `1e-9` relative tolerance.
- **FR-004**: `admesh.triangulate(Domain.from_mesh(src), ...)` MUST produce a non-empty mesh when invoked on real-world multiply-connected fixtures (e.g., wnat_test.14, wetting-and-drying-test.14).
- **FR-005**: The ring-sorting criterion MUST use the **2D signed area formula** (shoelace formula) applied to the ring node coordinates to determine ring size.

### Key Entities

- **Ring**: An ordered sequence of node IDs forming a closed boundary. Attributes: `node_ids`, `signed_area`.
- **Domain**: A multiply-connected polygonal region. Attributes: `outer_ring` (the ring with max area), `holes` (rings with smaller areas), `bbox`.

## Success Criteria

### Measurable Outcomes

- **SC-001**: `Domain.from_mesh(wnat_test.14)` produces a domain bbox that matches the source mesh extent to within `|delta_bbox| / mesh_diag < 1e-9`.
- **SC-002**: `triangulate(Domain.from_mesh(wnat_test.14), h_min=0.05, h_max=2.0, ...)` completes without raising `ValueError: zero-size array to reduction operation minimum`.
- **SC-003**: The recovered mesh from `triangulate(...)` has area ≥ 95% of the original domain area (acceptable trade-off for re-refinement).
- **SC-004**: All 5 MVP synthetic domains (square, L-shape, U-shape, square-with-hole, annulus) continue to pass their existing acceptance tests with no regression.
- **SC-005**: A new unit test explicitly covering the "longest-ring-is-a-hole" failure mode (multiply-connected domain with interior ring having more nodes than outer) passes.

## Assumptions

- The 2D **shoelace formula** for signed area is the appropriate metric for determining ring size in a 2D mesh topology.
- Ring node coordinates are stored as a simple Nx2 array (x, y) with no 3D component (or z is ignored).
- The SDF (Signed Distance Function) returned by `Domain.from_mesh` is used only for mesh generation, so long as the outer boundary is correctly identified, interior geometry will follow naturally.
- The `_derive_boundary_segments` function returns rings in an arbitrary order; the sort is the only place where order is determined.
- Real-world ADCIRC fixtures have a clear area disparity between outer and inner rings (outer ≈ 100-1000x larger by area), making area sorting robust against floating-point noise.
