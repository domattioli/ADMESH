# Investigation Specification: Verify h_min/h_max Parameter Usage in triangulate() API

**Feature Branch**: `006-verify-h-parameter-usage`  
**Created**: 2026-05-06  
**Status**: Investigation  
**Issue Reference**: #37

## Problem Statement

The `triangulate(domain, h_min=..., h_max=...)` API produces severely undersampled meshes on real-world fixtures (25× fewer elements than source on WNAT), suggesting that the `h_min`/`h_max` bounds may not be correctly honored when no explicit `size_field` callable is provided. This blocks the Tier-2 release gate test and prevents users from reliably controlling mesh density via the documented API parameters.

## Scope

This investigation focuses on verifying the parameter flow in the default size-field path:
- Parameter acceptance at the `triangulate()` API level
- Propagation through `routine.triangulate()` to `mesh_size.build_h()`
- Composition of the size field when `h_min`/`h_max` are provided without an explicit `size_field` callable
- Comparison of documented vs actual behavior
- Root cause identification (parameter not applied, misused, or correct but insufficient)

**Out of scope**: 
- Fixing the undersampling problem (that belongs to issue #10)
- Implementing a new size-field algorithm
- Modifying the distmesh solver itself

## User Scenarios & Testing

### User Story 1 - Developer Verifies Parameter Flow (Priority: P1)

A developer needs to understand whether `h_min`/`h_max` parameters passed to `triangulate()` are actually being applied to the size-field computation, or if they're being ignored/silently overridden.

**Why this priority**: Blocks Tier-2 test; critical for API correctness.

**Independent Test**: Trace the parameter from `triangulate(domain, h_min=0.1, h_max=2.0)` through `routine.triangulate()` and `mesh_size.build_h()` and verify each function accepts and forwards the parameters.

**Acceptance Scenarios**:

1. **Given** a `Domain` object and explicit `h_min=0.1, h_max=2.0` values, **When** `triangulate()` is called, **Then** these values are passed to `routine.triangulate()` without modification.
2. **Given** the call reaches `mesh_size.build_h()`, **When** the size-field composition begins, **Then** `h_min`/`h_max` are available and used in the composition logic.

---

### User Story 2 - Developer Verifies Size-Field Composition (Priority: P1)

A developer needs to confirm that when `h_min`/`h_max` are provided without an explicit `size_field` callable, they are correctly composed into the final size-field grid (i.e., not dropped, not used only as clipping bounds, but actively driving mesh density).

**Why this priority**: Core to understanding whether parameters have an effect.

**Independent Test**: Inspect the `build_h()` function's output grid when called with `h_min`/`h_max` and verify that the grid values are bounded by these limits and reflect the intended density.

**Acceptance Scenarios**:

1. **Given** a size-field composition without an explicit callable, **When** `h_min`/`h_max` bounds are provided, **Then** the resulting size-field grid `h(X, Y)` satisfies `h_min <= h(X, Y) <= h_max` everywhere (or at least in the domain interior).
2. **Given** two identical domains with different `h_min`/`h_max` pairs, **When** triangulated, **Then** the resulting mesh densities are visibly different (element count scales appropriately).

---

### User Story 3 - Developer Documents Expected vs Actual Behavior (Priority: P1)

A developer needs clear documentation of what the API promises (`h_min`/`h_max` control mesh density) vs what actually happens, so the gap (if any) is explicit and actionable.

**Why this priority**: Unblocks decision-making for issue #10 and future API improvements.

**Independent Test**: Compare the API documentation against the actual code behavior and document any discrepancies.

**Acceptance Scenarios**:

1. **Given** the published API documentation, **When** reviewed against the actual code, **Then** any claim about `h_min`/`h_max` is either verified or explicitly marked as a known limitation.
2. **Given** a user reading the documentation and following the instructions, **When** they call `triangulate(domain, h_min=0.1, h_max=2.0, ...)`, **Then** the resulting mesh respects the documented behavior (or the docs are updated to match reality).

---

### User Story 4 - Developer Identifies Root Cause (Priority: P2)

A developer needs to identify *why* the Tier-2 WNAT mesh is undersampled: is it because the parameters aren't applied, or because they're correct but the distmesh solver / SDF / size-field composition has other issues?

**Why this priority**: Informs the design of the fix for issue #10.

**Independent Test**: Using instrumentation or step-through debugging, trace a single call to `triangulate(domain, h_min=0.1, h_max=2.0, ...)` on the WNAT fixture and determine at which stage undersampling occurs.

**Acceptance Scenarios**:

1. **Given** the WNAT fixture with `h_min=0.1, h_max=2.0`, **When** the size-field stack executes, **Then** either the size-field grid is computed correctly and distmesh undersamples, or the size-field grid itself is pathological.
2. **Given** the investigation results, **When** documented, **Then** the root cause is traceable to a specific stage (parameter application, size-field composition, or solver behavior).

---

### Edge Cases

- What happens when `h_min > h_max`? (Should be caught at the API level or allowed with a warning?)
- What happens when `h_min` or `h_max` is zero or negative? (Should be rejected?)
- What happens when no `h_min`/`h_max` are provided to `triangulate()`? (Are there hardcoded defaults? Are they reasonable?)
- What happens on a domain where the SDF gradient is very steep or very flat? (Do h_min/h_max still drive spacing?)

## Requirements

### Functional Requirements

- **FR-001**: Parameter flow MUST be traced from `triangulate(domain, h_min=..., h_max=...)` through `routine.triangulate()` to `mesh_size.build_h()` with clear evidence of each step.
- **FR-002**: Size-field composition logic MUST be documented: how `h_min`/`h_max` are used (clipping, driving, ignored).
- **FR-003**: A diagnostic report MUST be generated showing (1) the size-field grid values on a regular sample, (2) how they compare to `h_min`/`h_max` bounds, (3) resulting mesh density on WNAT fixture.
- **FR-004**: Root cause MUST be identified and documented: either "parameters are correctly applied," or "parameters are applied but [specific issue] causes undersampling," or "parameters are not applied because [specific reason]."
- **FR-005**: API documentation MUST be reviewed and either verified correct or updated to reflect actual behavior.

### Key Entities

- **`triangulate()` API**: Entry point accepting `h_min`, `h_max` parameters
- **`routine.triangulate()`**: Driver that orchestrates the distmesh call
- **`mesh_size.build_h()`**: Size-field composition and grid generation
- **Size-field grid**: The computed `h(X, Y)` scalar field
- **WNAT fixture**: Real-world test case exhibiting undersampling

## Success Criteria

### Measurable Outcomes

- **SC-001**: Investigation report documents the complete parameter flow from `triangulate()` to `mesh_size.build_h()` with code references (file:line).
- **SC-002**: Size-field composition logic is documented such that a developer reading the explanation can predict whether the final grid will honor `h_min`/`h_max` bounds.
- **SC-003**: Diagnostic output shows the size-field grid values on a 10×10 sample across the WNAT domain, with statistics (min, max, mean) compared to the requested `h_min`/`h_max`.
- **SC-004**: Root cause is identified as one of: (A) parameters correctly applied, (B) parameters applied but insufficient due to [specific reason], (C) parameters not applied due to [specific bug].
- **SC-005**: API documentation status is clear: either confirmed correct, or identified for updating with a list of specific changes.
- **SC-006**: Investigation findings unblock decision-making on issue #10 (i.e., provide enough clarity to prioritize next steps).

## Assumptions

- The parameter-tracing investigation can be completed by code inspection + minimal instrumentation (no new testing framework required).
- The WNAT fixture is stable and reproducible (no external data dependencies).
- "Undersampling" is measured by element count / grid-to-mesh density ratio vs the source mesh.
- The API documentation (`admesh/api.py` docstrings and `docs/`) is the source of truth for "expected behavior."
- No changes to the core algorithm are in scope; this is a diagnostic exercise.
