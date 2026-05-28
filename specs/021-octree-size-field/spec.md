# Feature Specification: Octree Background Grid for Multi-Scale Size-Function & Medial-Axis Robustness

**Feature Branch**: `021-octree-size-field`
**Created**: 2026-05-28
**Status**: Draft
**Input**: User description: "compute the underlying size function using an octree grid instead of a cartesian grid because of the beneficial properties this spec will have on computing the medial axis. note that currently, the medial axis can sometimes fail to resolve properly when the smallest feature of a mesh is sufficiently dwarfed by the largest feature. also note that for the hydrodynamic computations performed on the subsequent mesh, we want at minimum four elements to span every feature, and that is contingent on the medial axis"

## Clarifications

### Session 2026-05-28

- Q: Constitution Principle I locks the faithful-port stage modules (including `background_grid.py`, `medial_axis.py`, and `mesh_size.py`) to numerical identity with MATLAB. Should the octree be a purely additive alternative that leaves those modules untouched, or may it modify the locked modules — which requires a Principle I exception? → A: The locked modules MAY be modified. The user granted explicit permission (2026-05-28) to create a feature branch that "unlocks the locked modules in order to implement this spec." This is a deliberate, scoped departure from Constitution Principle I and is ratified via a Constitution amendment delivered with this feature. The octree therefore supersedes the uniform cartesian grid as the substrate for size-function and medial-axis computation, rather than living purely in the additive layer.
- Q: How is "feature" defined for the "four elements span every feature" rule? → A: Via local feature size (distance to the nearest boundary plus distance to the medial axis), consistent with the existing medial-axis `R` parameter ("elements per local-feature-size unit"). The four-element minimum is therefore contingent on the medial axis being resolved at that location — which is exactly what User Story 1 makes reliable.
- Q: How is the "at least four elements span every feature" guarantee defined and verified? → A: Both the driver and the outcome. The size function targets an edge length no greater than one quarter of a feature's transverse width at the medial axis, AND an acceptance test counts at least four element edges across the feature's narrowest transverse extent in the output mesh.
- Q: What bounds the smallest resolvable feature (the octree refinement floor)? → A: The existing minimum edge length `h_min` only. Leaf cells refine until their size reaches approximately `h_min` and no finer; there is no separate maximum-depth cap, and memory is bounded implicitly by `h_min` and the domain extent.
- Q: Is the uniform/cartesian grid retained or fully replaced? → A: The octree is the default substrate, with an automatic fallback to the uniform grid if octree construction fails for a domain. The uniform path is retained as the fallback, not removed.
- Q: What is the primary validation benchmark for the multi-scale medial-axis fix? → A: Both a new synthetic basin+inlet fixture with a controllable L/W ratio (deterministic; exercises the `h_min` floor) and a real ADCIRC multi-scale mesh (realism).

## User Scenarios & Testing *(mandatory)*

<!--
  Stories ordered by priority. P1 is the headline robustness fix that motivates
  the feature; later stories build on it. Each story is independently testable.
-->

### User Story 1 — Medial axis resolves on multi-scale domains (Priority: P1)

A coastal modeller triangulates a domain whose smallest feature (a narrow inlet, channel mouth, or pinch between two islands, on the order of tens of metres) is dwarfed by the largest feature (an open-ocean or shelf extent on the order of hundreds of kilometres). Today the size function is built on a single uniform cartesian background grid whose spacing is constant across the whole domain. To keep the grid tractable over the large extent, that spacing is necessarily coarse — and at that spacing the medial-axis stage cannot detect the narrow feature: there are no interior cells inside the pinch, the medial-axis distance comes back empty there, and the stage silently falls back to "boundary distance only." The narrow feature is left under-resolved.

With the size function computed on an octree grid, cells refine locally where features are small and stay coarse in the open ocean. The medial axis is captured inside the narrow feature without forcing a globally fine grid, so triangulating the domain produces a size function that resolves the local feature size everywhere a feature exists.

**Why this priority**: This is the defect that motivates the feature. The user states the medial axis "can sometimes fail to resolve properly when the smallest feature of a mesh is sufficiently dwarfed by the largest feature." A size function that silently drops narrow features is a correctness gap, and every downstream guarantee — including the four-elements-per-feature rule in User Story 2 — is contingent on the medial axis being resolved first.

**Independent Test**: Construct a synthetic multi-scale domain — e.g. a large basin of extent L connected to a thin inlet of width W with L/W ≥ 1000. Build the size function on the octree path and confirm the medial axis is non-empty inside the inlet and the local feature size there drives a small target edge length. As a baseline, build the same domain's size function on a uniform cartesian grid at a spacing chosen to keep the cell count tractable for extent L, and confirm it fails to detect the medial axis inside the inlet. The octree path must succeed where the tractable-resolution cartesian baseline fails.

**Acceptance Scenarios**:

1. **Given** a basin-plus-inlet domain with feature-size ratio L/W ≥ 1000, **When** the size function is built on the octree grid, **Then** the medial-axis distance is defined (non-empty) along the inlet centreline and the target edge length inside the inlet tracks the local feature size rather than the global maximum edge length.
2. **Given** the same domain, **When** the size function is built on a uniform cartesian grid at a spacing that keeps the cell count tractable for extent L, **Then** the medial axis inside the inlet is empty and the size function falls back to boundary-distance-only there — demonstrating the baseline failure the octree path fixes.
3. **Given** a multiply-connected domain with a narrow channel between two island holes, **When** the size function is built on the octree grid, **Then** the medial axis is resolved within the channel and elements there are sized to the channel half-width.

### User Story 2 — At least four elements span every feature (Priority: P2)

A modeller preparing a mesh for hydrodynamic simulation needs every resolved feature to be spanned by at least four mesh elements across its narrowest transverse extent, because the downstream solver loses accuracy (or goes unstable) when a channel, gap, or headland is bridged by fewer elements. Because the target edge length in a feature is derived from the medial axis (local feature size), this guarantee is only achievable once User Story 1 ensures the medial axis is resolved there.

**Why this priority**: This is the acceptance bar the produced mesh must meet for its intended hydrodynamic use. It is P2 rather than P1 because it is strictly contingent on the medial axis (P1): you cannot guarantee four elements across a feature whose feature size was never computed.

**Independent Test**: For each benchmark domain with known narrow features, build the mesh via the octree size-function path and measure the number of element edges crossing the narrowest transverse extent of each feature. Every feature at or above the configured minimum resolvable size must be spanned by at least four elements.

**Acceptance Scenarios**:

1. **Given** a domain with a channel of uniform width W (above the minimum resolvable size), **When** meshed via the octree size function, **Then** a transverse cut across the channel crosses at least four element edges.
2. **Given** a domain with several features of different widths, **When** meshed, **Then** the four-element minimum holds for every feature simultaneously, without forcing a globally uniform fine mesh.
3. **Given** a feature narrower than the configured minimum resolvable size (the `h_min` resolution floor), **When** meshed, **Then** the system surfaces that the feature is below the resolution floor (documented warning) rather than silently producing fewer than four elements with no indication.

### User Story 3 — Large multi-scale domains stay tractable (Priority: P3)

A modeller works with a geographically large domain that nonetheless contains fine coastal detail. Resolving the fine detail with a uniform grid would require a cell count that grows with the square of (domain extent ÷ smallest feature), quickly exhausting memory and wall-clock budget. The octree grid refines only where needed, so the number of cells grows far more slowly with the feature-size ratio, making size-function computation feasible at scale ratios that would be intractable for a uniform grid.

**Why this priority**: This is what makes User Story 1 practical rather than theoretical. Without sub-quadratic growth, the alternative fix for the medial-axis failure would simply be "use a finer uniform grid," which does not scale. It is P3 because correctness (US1) and the hydrodynamic bar (US2) take precedence, but the efficiency is the reason an octree is the chosen structure.

**Independent Test**: For a family of domains with increasing feature-size ratio, record the octree cell count and peak memory and compare against the uniform-grid-at-finest-resolution baseline. The octree cell count must grow sub-quadratically (target: near-linear or logarithmic) in the feature-size ratio, and must complete within memory where the uniform baseline would exceed it.

**Acceptance Scenarios**:

1. **Given** a sequence of domains with feature-size ratios 10, 100, and 1000, **When** the octree size function is built, **Then** the cell count grows sub-quadratically with the ratio (substantially fewer cells than the uniform-at-finest baseline at the higher ratios).
2. **Given** a domain whose uniform-at-finest grid would exceed available memory, **When** the octree size function is built, **Then** it completes within memory and produces a valid size function.

### User Story 4 — Departure from the faithful-port baseline is deliberate and auditable (Priority: P2)

A maintainer needs the change in behaviour to be intentional and documented rather than an accidental regression. Because the octree changes how the size function and medial axis are computed, the faithful-port stage modules that previously reproduced MATLAB bit-for-bit will no longer do so for the affected stages. The user has authorized modifying those locked modules (see Clarifications), so this story ensures the departure is ratified through a Constitution amendment, the affected reference fixtures are updated with provenance, and stages unrelated to the octree remain numerically identical to MATLAB.

**Why this priority**: Numerical identity with MATLAB is the project's foundational rule (Constitution Principle I). Overriding it for the size-function/medial-axis stages must be explicit and auditable even though the user has granted permission. It is P2 because shipping the octree without ratifying the exception would leave the repository's governance inconsistent with its code.

**Independent Test**: Confirm the Constitution carries a ratified amendment scoping the Principle I exception to the named stages; confirm reference fixtures for stages changed by the octree are regenerated with documented provenance noting the intentional divergence; and confirm the reference tests for stages NOT involved in the octree path still pass unchanged.

**Acceptance Scenarios**:

1. **Given** the repository after this feature lands, **When** the Constitution is inspected, **Then** it contains a dated amendment naming the stages exempted from Principle I and the rationale (octree size-function/medial-axis robustness).
2. **Given** the test suite, **When** it runs, **Then** stages unaffected by the octree reproduce their MATLAB reference fixtures unchanged, and stages changed by the octree assert against regenerated fixtures whose provenance documents the deliberate divergence.

### Edge Cases

- **Feature below the resolution floor**: the octree refines no finer than the minimum edge length `h_min`; a feature narrower than `h_min` cannot be resolved. The system MUST surface this (documented warning identifying the under-resolved feature) rather than silently under-resolving it.
- **No multi-scale content** (a domain with no narrow features, or where the smallest and largest features are within a small ratio): the octree MUST degenerate to an essentially uniform grid and MUST NOT pay meaningful overhead versus a uniform grid — a uniform grid is just the no-refinement case of the octree.
- **Adjacent cells of very different size**: octree leaves of differing depth meet at feature boundaries; the medial-axis detection (which on a uniform grid assumes equal neighbour spacing) MUST handle variable cell sizes without spurious or missed skeleton pixels.
- **Smoothness of size transitions**: refinement level MUST change gradually (e.g. a 2:1 balance between neighbouring leaves) so the gradient-limited size field does not have to absorb abrupt jumps; gradient-limiting still applies on the octree.
- **Multiply-connected domains**: narrow channels between island holes are exactly the features most likely to be dwarfed; each ring drives refinement and medial-axis evaluation.
- **Reproducibility expectations**: because the octree grid differs from the previous uniform grid, the resulting size function (and therefore the final mesh) is intentionally not bit-identical to the prior cartesian/MATLAB output; this divergence is the authorized departure captured by the Constitution amendment, not a bug.
- **Extreme scale ratio beyond the resolution floor**: when a domain's smallest feature is finer than `h_min`, the system MUST behave predictably (resolve down to the `h_min` floor and warn) rather than failing or allocating unbounded memory.

## Requirements *(mandatory)*

### Functional Requirements

#### Octree grid construction

- **FR-001**: The system MUST compute the size function over a domain on an octree (hierarchically refined) background grid in place of the uniform cartesian background grid.
- **FR-002**: Octree cells MUST refine locally based on local feature size and the other active size drivers (boundary proximity, curvature, and optional bathymetry/tide), so that cell size is small where features are small and large where the domain is open.
- **FR-003**: The octree MUST enforce a bounded refinement transition between neighbouring leaf cells (e.g. a 2:1 size balance) so that size transitions are smooth.
- **FR-004**: The octree's refinement floor MUST be the existing minimum edge length `h_min`: leaf cells refine until their size reaches approximately `h_min` and no finer. There is no separate maximum-depth cap; memory is bounded implicitly by `h_min` and the domain extent.

#### Medial axis on the octree

- **FR-005**: The medial-axis computation MUST operate on the octree grid and MUST detect the medial axis inside narrow features that a tractable-resolution uniform grid fails to resolve.
- **FR-006**: The medial-axis result MUST yield a defined local feature size everywhere a feature exists above the resolution floor — no silent empty/boundary-distance-only fallback for features that are above the floor.
- **FR-007**: Where a uniform grid would already resolve a feature, the octree medial axis MUST agree with the resolved result to a documented tolerance (the octree must not degrade cases that are already handled).

#### Size-function composition

- **FR-008**: The size function built on the octree MUST compose the same drivers as today (curvature, medial-axis/local-feature-size, and optional bathymetry and tide), combined by the existing min-stacking rule.
- **FR-009**: The octree size function MUST be queryable at arbitrary points (interpolated from the octree) for use by the triangulation stage, with output clipped to the configured minimum/maximum edge length and gradient-limited as today.

#### Four elements per feature

- **FR-010**: The size function MUST target at least four elements across the narrowest transverse extent of every feature at or above the resolution floor — the medial-axis-derived target edge length there MUST be no greater than one quarter of the feature's transverse width — AND this MUST be verified by counting at least four element edges across that extent in the output mesh.
- **FR-011**: The minimum-elements-per-feature target MUST be configurable (default at least four) and MUST be defined relative to the medial-axis-derived local feature size.
- **FR-012**: When a feature is narrower than the resolution floor (`h_min`) and so cannot meet the four-element minimum, the system MUST emit a documented warning identifying the under-resolved feature rather than silently violating the minimum.

#### Tractability

- **FR-013**: The octree cell count MUST grow sub-quadratically with the domain's feature-size ratio (largest-to-smallest feature), in contrast to the quadratic growth of a uniform grid refined to the smallest feature.
- **FR-014**: For a domain whose uniform-at-finest grid would exceed available memory, the octree path MUST complete within memory and produce a valid size function.

#### Governance & migration

- **FR-015**: Modifying the locked faithful-port stage modules to implement the octree MUST be ratified by a dated Constitution amendment that names the stages exempted from Principle I and states the rationale.
- **FR-016**: Numerical changes to any ported stage caused by the octree MUST be deliberate and captured by regenerated reference fixtures whose provenance documents the divergence from MATLAB; stages NOT involved in the octree path MUST remain numerically identical to MATLAB and their reference tests MUST continue to pass.
- **FR-017**: When a domain has no meaningful multi-scale content, the octree MUST degenerate to an essentially uniform grid without meaningful overhead, so simple domains are unaffected in practice.
- **FR-018**: The octree MUST be the default substrate, and the uniform grid MUST be retained as an automatic fallback: if octree construction fails for a domain, the system MUST fall back to the uniform grid (with a documented warning) and still produce a valid size function.

### Key Entities

- **Octree Background Grid**: a hierarchically refined grid over the padded domain bounding box whose leaf cells vary in size; characterised by refinement criteria (local feature size plus the other size drivers), a resolution floor at the minimum edge length `h_min`, and a neighbour balance constraint (smooth transitions). It replaces the single uniform-spacing grid as the substrate on which the size function and medial axis are computed.
- **Local Feature Size**: distance to the nearest boundary plus distance to the medial axis, evaluated on octree leaves; the quantity that drives feature-aware refinement and the four-elements-per-feature target.
- **Feature-Size Ratio**: the ratio of the largest to the smallest feature in a domain; the multi-scale stress parameter that governs whether a uniform grid becomes intractable and whether the medial axis fails to resolve.
- **Minimum-Elements-Per-Feature Target**: the configurable lower bound (default ≥ 4) on the number of elements spanning a feature's narrowest extent, defined relative to local feature size and contingent on the medial axis being resolved.
- **Principle I Exception Record**: the dated Constitution amendment that authorizes and scopes the modification of the named faithful-port stage modules for this feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a synthetic basin+inlet benchmark with feature-size ratio ≥ 1000, the octree path resolves the medial axis inside the narrowest feature (non-empty local feature size there), whereas a uniform grid at a tractable spacing for the domain extent does not.
- **SC-002**: Across every benchmark domain, at least four element edges cross the narrowest transverse extent of every feature that is at or above the configured resolution floor.
- **SC-003**: For features below the resolution floor, the system emits a documented warning identifying the under-resolved feature in 100% of cases (no silent violations).
- **SC-004**: For a family of domains with feature-size ratios spanning at least 10×, 100×, and 1000×, the octree cell count grows sub-quadratically with the ratio and uses at least an order of magnitude fewer cells than the uniform-at-finest baseline at the 1000× ratio.
- **SC-005**: A domain whose uniform-at-finest grid would exceed available memory is meshed to completion via the octree path within the same memory budget.
- **SC-006**: Stages not involved in the octree path reproduce their MATLAB reference fixtures unchanged; stages changed by the octree assert against regenerated fixtures with documented provenance, and the full test suite passes.
- **SC-007**: On the test ladder (MVP polygons → WNAT coastline → the new synthetic basin+inlet fixture → a real multi-scale ADCIRC mesh), there are zero medial-axis resolution failures for features above the resolution floor (`h_min`).
- **SC-008**: When run on a domain with no multi-scale content, the octree path's wall-clock time is within a documented small margin of a uniform-grid run (no meaningful overhead).

## Assumptions

- **The octree is the default size-function/medial-axis substrate, with the uniform grid retained as an automatic fallback.** Per explicit user authorization (2026-05-28), the locked faithful-port stage modules (e.g. `background_grid.py`, `medial_axis.py`, and as needed `mesh_size.py`) MAY be modified to implement this, as a scoped exception to Constitution Principle I ratified by an amendment delivered with the feature. A uniform grid remains both the degenerate (no-refinement) case of the octree and the construction-failure fallback (FR-018), so simple domains are unaffected in practice and the legacy path stays available.
- **"Feature" is defined via local feature size** (distance to boundary + distance to medial axis), consistent with the existing medial-axis `R` parameter ("elements per local-feature-size unit"). "Four elements span a feature" means: across a feature's narrowest transverse extent, the target edge length yields at least four element edges. The exact formula relating the elements-per-feature target to the size function is an implementation detail for `/speckit-plan`.
- **Target multi-scale range**: the resolution floor is the minimum edge length `h_min`; the feature is validated across feature-size ratios up to roughly 10³–10⁴ (set by `h_min` relative to domain extent).
- **Validation benchmark set**: a new synthetic basin+inlet fixture with a controllable L/W ratio (deterministic; exercises the `h_min` floor) plus a real multi-scale ADCIRC mesh (realism). Both are required for SC-001/SC-007; the specific real mesh is selected during `/speckit-plan`.
- **Octree construction approach** (top-down refinement until the local target size is met or the `h_min` floor is reached, with neighbour balancing) is an implementation detail; the spec fixes the required *properties* (feature-driven refinement, bounded transitions, floor at `h_min`), not the algorithm.
- **Downstream stages are unchanged**: triangulation (distmesh), quality measurement, and fort.14 I/O consume the size function through the same query interface; the octree only changes how the size function and medial axis are computed and sampled.
- **The Principle I exception is scoped, not blanket**: only the stages whose computation moves onto the octree are exempted; the remaining faithful-port stages stay numerically identical to MATLAB.
- **Out of scope**: 3D meshing; changes to the distmesh force-balance algorithm itself; GPU acceleration; and the tri-to-quad path. Reproducing MATLAB bit-for-bit for the octree-affected stages is explicitly NOT a goal (it is the authorized departure).
