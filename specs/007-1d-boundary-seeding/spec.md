# Feature Specification: 1D Distmesh Boundary Seeding

**Feature Branch**: `daily-maintenance`
**Created**: 2026-05-07
**Status**: Draft
**Issue**: #2

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Uniform Coverage on Short Segments (Priority: P1)

A mesh engineer calls `triangulate(NOTCHED_RECTANGLE, h0=0.05)` and expects
nodes to be placed along the narrow notch walls (x=+/-0.05, height=0.25) and
floor (y=0.25, width=0.1) at approximately `h0` spacing. Currently nodes
are sparse or absent on these short edges, causing uneven coverage and poor
triangle quality near the notch.

**Why this priority**: The notch is the primary stress test for the pipeline.
Reliable boundary coverage is a prerequisite for mesh validity and quality.

**Independent Test**: Run `triangulate(NOTCHED_RECTANGLE, h0=0.05)` and count
nodes within epsilon of each notch-wall segment. Delivers value (correct mesh) on its own.

**Acceptance Scenarios**:

1. **Given** `NOTCHED_RECTANGLE` and `h0=0.05`, **When** `triangulate()` is
   called, **Then** each notch-wall segment (length~0.25) has >=4 boundary nodes
   spaced within 1.5*h0 of each other.
2. **Given** `NOTCHED_RECTANGLE` and `h0=0.05`, **When** `triangulate()` is
   called, **Then** the notch-floor segment (length~0.1) has >=1 boundary node
   between the two wall endpoints.
3. **Given** a domain where `boundary_polygon` is `None`, **When**
   `triangulate()` is called, **Then** behavior is identical to the current
   implementation (no regression).

---

### User Story 2 - Adaptive Spacing with Non-Uniform Size Field (Priority: P2)

A mesh engineer provides a custom `fh` that assigns smaller element sizes near
the notch tip. The 1D seeder should honour `fh` by placing more nodes near
the fine-size region of each boundary segment.

**Why this priority**: Real-world domains use graded size fields. The seeder
must respect them, not just uniform spacing.

**Independent Test**: Pass a `fh` that returns `0.03` near the notch and `0.07`
far from it. Verify node spacing on the notch walls is <=0.05 (finer than `h0`).

**Acceptance Scenarios**:

1. **Given** a graded `fh` and `NOTCHED_RECTANGLE`, **When** `triangulate()` is
   called, **Then** boundary seed spacing along each segment is proportional to
   the local `fh` value at midpoints.
2. **Given** a uniform `fh=None`, **When** `triangulate()` is called, **Then**
   seeds are placed at approximately `h0` intervals along every boundary segment.

---

### User Story 3 - Other Canonical Domains Unaffected (Priority: P3)

Running `triangulate()` on `UNIT_SQUARE`, `L_SHAPE`, `UNIT_DISK`, `ANNULUS`
with or without a `boundary_polygon` field should produce meshes statistically
equivalent to the pre-feature baseline.

**Why this priority**: Regression safety — existing test suite must stay green.

**Independent Test**: Run the full test suite on all five canonical domains.

**Acceptance Scenarios**:

1. **Given** any domain without `boundary_polygon` set, **When** `triangulate()`
   is called, **Then** all existing tests pass without modification.

---

### Edge Cases

- What happens when a boundary edge is shorter than `h0`? Seed only the two
  endpoints (already covered by `fixed_points`); no additional seeds added.
- What happens when `boundary_polygon` has coincident consecutive vertices?
  Skip zero-length edges silently.
- What if `fh` returns values <=0 on a segment midpoint? Clamp to `h0` minimum
  to avoid division errors.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `Domain` MUST support an optional `boundary_polygon` field.
- **FR-002**: When `boundary_polygon` is set, `triangulate()` MUST run a 1D
  seeding pass along each edge to produce evenly-spaced boundary nodes.
- **FR-003**: Boundary seeds MUST be prepended to `pfix`.
- **FR-004**: `NOTCHED_RECTANGLE` MUST have `boundary_polygon` set.
- **FR-005**: The 1D seeder MUST honour a non-uniform `fh`.
- **FR-006**: When `boundary_polygon` is `None`, `triangulate()` MUST behave
  exactly as before this feature.
- **FR-007**: Edge segments shorter than one seed interval MUST be skipped.

### Key Entities

- **`Domain.boundary_polygon`**: Optional ordered `(M, 2)` float64 array.
- **`_seed_boundary_1d(polygon, fh, h0)`**: Pure function returning `(K, 2)` seeds.

## Success Criteria *(mandatory)*

- **SC-001**: NOTCHED_RECTANGLE at h0=0.05 produces >=4 nodes on each notch wall.
- **SC-002**: NOTCHED_RECTANGLE at h0=0.05 produces >=1 node on notch floor.
- **SC-003**: All pre-existing tests pass (zero regressions).
- **SC-004**: `_seed_boundary_1d` runs in under 10ms for 100-vertex polygon.
- **SC-005**: Seeded nodes are within 10% of local target spacing.

## Assumptions

- `boundary_polygon` vertices are in order (CW or CCW).
- Uniform subdivision at midpoint spacing is sufficient (no full 1D truss-force solver).
- `fixed_points` corners are already present; seeder does not re-add them.
- Only `NOTCHED_RECTANGLE` gets `boundary_polygon` in this feature.
