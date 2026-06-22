# Feature Specification: Default Size-Field Stack & 0.1.0 Release Readiness

**Feature Branch**: `002-size-field-defaults`
**Created**: 2026-04-25
**Status**: Draft
**Input**: User description: "Wire the built-in MATLAB-faithful size-field stack into admesh.triangulate() as the default Phase-1 size source. This is a release-blocker for 0.1.0."

## Clarifications

### Session 2026-04-25

- Q: Should `Domain` gain optional `bathymetry`/`tide_period` fields, or should those stay as `triangulate()`-only kwargs? → A: `Domain` carries bathymetry/tide; `triangulate(domain)` is the simple single-arg call. Rationale: the fort.14 format already treats depth as a mandatory per-node geometric attribute (4th column of every node record), and `Mesh.bathymetry` is already an `ndarray | None` field on the spec-001 dataclass — putting `Domain.bathymetry` alongside is the symmetric design and keeps the call site to one argument.
- Q: What's the WNAT acceptance threshold for the 0.1.0 release gate? → A: Structural validity only — boundaries preserved, full domain coverage, no degenerate elements. No numeric quality threshold (e.g. `min_q ≥ X`) is required. Figure-8-quality aesthetic match is a roadmap target, not a CI gate. Rationale: the user's bar is "produce a valid mesh that covers the entire domain and respects all boundaries", which is testable via three deterministic structural asserts (positive signed area, boundary-edge preservation, union-of-triangles covers domain) — independent of any quality metric tuning.
- Q: When `tide_period` is supplied but `Domain.bathymetry` is `None`, should the tide stage silently skip, hard-error, or auto-derive a default depth and run? → A: Warn (`UserWarning: tide_period set but Domain.bathymetry is None; using constant default depth`) and run the tide stage with a constant default depth. The stage never silently drops the user's intent. The exact default-depth value (e.g. `1.0 m`, `h_max`-derived, or a `default_depth=` kwarg) is an implementation detail to lock in during `/speckit-plan`.

## User Scenarios & Testing *(mandatory)*

<!--
  Stories ordered by priority. P1 stories must ship for 0.1.0;
  P2/P3 are additive. Each story is independently testable.
-->

### User Story 1 — Default feature-aware mesh from any 2D shallow-water domain (Priority: P1)

A coastal modeller has a polygonal domain (outer coastline, optionally with island holes) and wants to triangulate it. They write:

```python
mesh = admesh.triangulate(domain)
```

…with no further configuration. The result is a feature-aware mesh: edges are short near concave corners and narrow channels (curvature + local-feature-size resolution), and edges grow gracefully toward the interior with a bounded gradient. The mesh is suitable for ADCIRC simulation without manual sizing tuning.

The current behaviour (uniform edge length everywhere) is the failure mode that motivates this story.

**Why this priority**: This is the headline of the 0.1.0 release. Without it, the package's name (ADMESH = *advanced* automatic mesh generator) is misleading: the published 2012 paper's central contribution is the size-field stack, and a release that hides it behind a manual `size_field=` argument fails the package's own promise.

**Independent Test**: Given any of the 5 MVP domains used in spec 001 (square, L-shape, U-shape, square-with-hole, doughnut) plus the canonical WNAT coastline (`tests/fixtures/fort14/adcirc_examples/wnat_test.14`), invoke `admesh.triangulate(domain)` with no size-field arguments. For each domain, verify (a) the call returns a `Mesh` without error, (b) every element passes a documented minimum-quality gate, and (c) for WNAT specifically, the resulting mesh visibly resolves the local feature size of the coastline (verified by node count concentration in narrow channels and around capes, plus the regression check in Acceptance Scenario 3).

**Acceptance Scenarios**:

1. **Given** an L-shape domain with `h_min=0.05`, `h_max=0.5`, **When** the user calls `admesh.triangulate(domain)`, **Then** the returned mesh has visibly smaller elements at the concave corner than along straight edges, and every element's quality metric is above the documented gate.
2. **Given** a domain with one outer ring and two island holes, **When** the user calls `admesh.triangulate(domain)`, **Then** all three boundaries (outer + 2 holes) are resolved with feature-size-aware edge lengths and no degenerate elements appear in narrow channels between holes.
3. **Given** the WNAT canonical coastline, **When** the user calls `admesh.triangulate(domain)` with default arguments suitable for the domain's geographic scale, **Then** the resulting mesh has a minimum element quality at or above the documented WNAT acceptance threshold and matches the qualitative refinement pattern of the published Figure 8 from Conroy et al. (2012) (the current README hero image): finer near the coast and along the continental shelf break, coarser in the open ocean.

---

### User Story 2 — Bathymetry-driven refinement when depth data is available (Priority: P2)

A user with bathymetric data (a depth-sampling callable or a depth-aware domain) wants the mesher to refine wherever depth gradients are large — e.g. along the continental shelf break or near submerged ridges. They write:

```python
mesh = admesh.triangulate(domain, bathymetry=lambda x, y: depth_grid_interp(x, y))
```

…and the bathymetry stage activates automatically alongside the always-on curvature + LFS stages. Optionally they can also specify a tidal period to activate the tidal-wavelength stage.

**Why this priority**: Bathymetry-driven refinement is a flagship capability of the 2012 paper (§4 of Conroy et al.) and a primary differentiator between ADMESH and generic 2D mesh generators. It is not part of the P1 minimum because most users come to ADMESH via a polygon-only domain first, then add bathymetry as a follow-up.

**Independent Test**: Given a synthetic test domain with an analytic bathymetry function that has a sharp ridge in a known location, invoke `admesh.triangulate(domain, bathymetry=...)`. Verify that the mean edge length within the ridge zone is materially smaller (e.g. ≥ 30% reduction) than the mean edge length in the flat-bottom zone, and that the mesh outside the bathymetry-influenced region is unchanged from the bathymetry-disabled baseline.

**Acceptance Scenarios**:

1. **Given** a domain with a depth function that varies smoothly from 0 to 1000 m, **When** the user calls `admesh.triangulate(domain, bathymetry=fn)`, **Then** the mesh has edge lengths inversely proportional to local depth gradient.
2. **Given** the same domain with `bathymetry=fn, tide_period=43200`, **When** triangulated, **Then** the mesh additionally resolves the tidal wavelength (edge length ≈ √(g·|Z|)·T / N for documented N elements per wavelength).
3. **Given** a depth callable that returns NaN over part of the domain, **When** triangulated with `bathymetry=fn`, **Then** the missing depths are inpainted automatically (existing `inpaint_nans` behaviour), and triangulation completes without error.

---

### User Story 3 — Backward-compatible custom size-field override (Priority: P3)

An advanced user has a custom size-field callable (perhaps from external simulation output, or a domain-specific heuristic) and wants to bypass the new default stack entirely without affecting the contract they already wrote against spec 001. They write:

```python
mesh = admesh.triangulate(domain, size_field=my_custom_fh)
```

…and the result is byte-identical to what spec 001's `triangulate(domain, size_field=my_custom_fh)` produced. The default stack does not run; the user's `fh` is the single source of truth.

**Why this priority**: Backward compatibility is non-negotiable, but no new code is required to deliver it: spec 001's `triangulate()` already accepts `size_field=`. The work here is *not regressing* that path. Verification is regression testing only.

**Independent Test**: Re-run all spec 001 round-trip tests with their existing `size_field=` arguments. Verify that the resulting `Mesh` objects are equal (`mesh.equals(...)`) to the spec 001 outputs. No code change should be required to make these tests pass.

**Acceptance Scenarios**:

1. **Given** a script that calls `admesh.triangulate(domain, size_field=lambda p: 0.1*np.ones(len(p)))`, **When** run before vs. after this feature lands, **Then** the resulting `Mesh` is structurally identical (same nodes, elements, boundary segments).
2. **Given** a script that calls `admesh.triangulate(domain, user_contribs=[my_refinement])` (no `size_field=`), **When** run after this feature lands, **Then** the user's contribution composes on top of the new built-in default stack via the existing Phase-2 combiner (i.e. user_contribs continues to refine *over* the default, rather than replacing it).

---

### User Story 4 — 0.1.0 release readiness (cleanup + walkbacks) (Priority: P2)

A maintainer (or a user inspecting the repo before adopting it) wants the repository to look like a release candidate: no half-finished framing in docs, no stray build artifacts, no premature governance amendments. Concretely, before the 0.1.0 tag:

- The constitution amendment from the previous session that reframed fort.14 as "shipped" is walked back to a more honest "in progress" stance.
- The README's install snippet and quickstart restore the "in progress" callouts that were prematurely removed.
- Generated artefacts from the previous session's wheel smoke (`dist/`, `build/`, `papers/wnat_admesh.png`, `tests/output/` stale demos) are cleaned up.

**Why this priority**: Independent of the size-field work. A user could clone the repo today and find the cleanup state misleading. Bundled into this spec because both items gate the same release tag.

**Independent Test**: A fresh `git clone` followed by `pip install .` and `pytest` should produce no warnings about stale artefacts and the repo's top-level documentation should accurately reflect what ships in 0.1.0.

**Acceptance Scenarios**:

1. **Given** the constitution at session start, **When** spec 002 lands, **Then** the constitution either reverts the v1.0.1 amendment or supersedes it with language that acknowledges the size-field work as a precondition for the fort.14 contract being "release-ready".
2. **Given** the README at session start, **When** spec 002 lands, **Then** the install + quickstart sections include a brief, honest "0.1.0-in-progress" note (without the "v1 ships" framing) until the 0.1.0 tag is cut.
3. **Given** a `git status` after the spec 002 implementation phase, **When** inspected, **Then** there are no untracked `dist/`, `build/`, or stale demo artefacts; only intended deliverables remain.

---

### Edge Cases

- **Tide without bathymetry**: A user supplies `tide_period=` but `Domain.bathymetry` is `None`. The system MUST emit a `UserWarning("tide_period set but Domain.bathymetry is None; using constant default depth")` and run the tide stage anyway with a constant default depth. The stage never silently drops the user's intent; the warning surfaces the likely-mistake; a sensible constant (e.g. `1.0 m`, an `h_max`-derived depth, or a caller-overridable `default_depth=` kwarg) keeps the meshing pipeline going.
- **Very small domain where stages would no-op**: A domain where `h_max / h_min < 2` leaves little dynamic range; the curvature and medial-axis stages will return values close to `h_max` everywhere. The default stack should not consume measurable wall-clock time in this case — it should detect the degenerate case and short-circuit to the uniform fallback.
- **Domain with extremely many vertices** (e.g. WNAT with > 1000 coastline points): the medial-axis stage's grid resolution scales with the bbox, not the vertex count, but the smoothing solver iteration count may grow. No correctness issue — just a wall-clock concern out of scope for this spec.
- **Bathymetry callable returns NaN**: Existing `bathymetry.create_elevation_grid` calls `inpaint_nans` automatically; the default stack inherits this behaviour without new logic.
- **Custom `user_contribs=` plus the new default builtins**: User contributions continue to compose *on top of* the default builtins via the existing Phase-2 combiner. No change in semantics; just that the Phase-1 builtins now have content (curvature + LFS + maybe bathymetry/tide) instead of being uniform.
- **Multiply-connected domain (island holes)**: Each ring is treated as a boundary for both the curvature stage and the medial-axis stage. The existing `Domain` dataclass already supports this via Shapely; no new logic needed.
- **WNAT with default arguments not chosen for the geographic scale**: If the user calls `triangulate(domain)` on a 37° × 37° domain with `h_max=0.5` (degrees) but expects metric-scale defaults, the result will not match Figure 8. The acceptance test must specify scale-appropriate kwargs for WNAT; the spec does not promise that scale-free defaults reproduce Figure 8 for arbitrary CRS.

## Requirements *(mandatory)*

### Functional Requirements

#### Default size-field stack

- **FR-001**: `admesh.triangulate(domain, ...)` invoked with no `size_field=` argument and no `user_contribs=` argument MUST construct a default size-field callable that composes the curvature + medial-axis (local-feature-size) stages from the existing MATLAB-faithful port.
- **FR-002**: The default size-field callable MUST clip its output to `[h_min, h_max]` using the existing `triangulate()` keyword arguments. When `h_target` (the un-reduced edge length where no stage applies) is not specified, it MUST default to `h_max`.
- **FR-003**: `admesh.triangulate()` MUST accept new keyword arguments `enable_curvature: bool = True`, `enable_medial_axis: bool = True`, `bathymetry: Callable[[X, Y], Z] | None = None`, `tide_period: float | None = None`, `tide_elements_per_wavelength: float | None = None`. These are additive to existing kwargs.
- **FR-004**: The bathymetry stage MUST activate automatically when `bathymetry` is supplied (or when the domain carries depth data — see FR-013).
- **FR-005**: The tide stage MUST activate automatically when `tide_period` is supplied. When `Domain.bathymetry` is also present, the stage uses that depth. When `Domain.bathymetry` is `None`, the stage MUST emit a `UserWarning` and run with a constant default depth (the specific constant locked in during `/speckit-plan` — candidates: `1.0 m`, `h_max`-derived, or a `default_depth=` kwarg). The tide stage MUST NOT silently skip when `tide_period` is set.
- **FR-006**: The default stack's user-facing kwargs (`enable_*`, `bathymetry`, `tide_*`, `h_target`) MUST auto-derive the MATLAB-internal scale parameters (the K, R, s, sz, g of the underlying ports) using a documented mapping. The mapping MUST be visible in the public API documentation; the underlying scale parameters MAY also be exposed as advanced overrides for users who want to reproduce specific MATLAB runs.
- **FR-007**: Multiply-connected domains (one outer ring with one or more interior holes) MUST be supported by the default stack. All boundary rings drive curvature and medial-axis evaluation.
- **FR-008**: When `h_max / h_min < 2` (or another small ratio documented in the implementation), the default stack MUST short-circuit to the existing uniform-`h` fallback to avoid unnecessary grid construction.

#### Backward compatibility

- **FR-009**: `admesh.triangulate(domain, size_field=<callable>)` MUST behave byte-for-byte identically to its spec 001 behaviour (the user-supplied callable is the only source of edge sizing; default stack does not run).
- **FR-010**: `admesh.triangulate(domain, user_contribs=<list>)` (no `size_field=`) MUST compose the user's contributions on top of the new default builtins via the existing Phase-2 combiner — preserving spec 001 user_contribs semantics.
- **FR-011**: All 142 faithful-port tests that pass today MUST continue to pass.
- **FR-012**: The faithful-port `admesh/mesh_size.py::build_h(...)` composer MUST continue to work unchanged for direct callers.

#### Domain dataclass shape

- **FR-013**: `Domain` MUST gain optional fields `bathymetry: Callable[[X, Y], Z] | None` and `tide_period: float | None`. The fort.14 format already treats depth as a mandatory per-node geometric attribute (every node line is `id x y depth`), and `Mesh.bathymetry` is already an `ndarray | None` field on the spec-001 dataclass — putting `Domain.bathymetry` alongside is the symmetric design. `triangulate(domain)` reads bathymetry/tide from `Domain` directly; the call site stays one argument. The chosen design MUST be backward-compatible with spec 001's `Domain` API (existing `Domain(fd, bbox)` constructions continue to work; the new fields default to `None`).
- **FR-013a**: A helper (e.g. `Domain.from_mesh(mesh)` or `domain_from_mesh(mesh)`) MUST exist to bridge a `read_fort14`-loaded `Mesh` (per-node depth samples) into a `Domain` with a callable `bathymetry` interpolant. This closes the round-trip story: load → re-mesh with default stack → write.

#### Release-gating regression test

- **FR-014**: A new structural-validity test MUST re-triangulate every fixture in the test ladder (Tier 0 MVP polygons → Tier 1 `wetting_and_drying_test.14` → Tier 2 `wnat_test.14`; Tier 1.5 added when acquired) using the default stack and assert: (a) every element has strictly positive signed area (no inverted, zero-area, or sliver-collapsed triangles, beyond a documented numerical-tolerance threshold); (b) every input boundary edge from the source domain (outer ring and every island hole) appears as an edge in the output triangulation; (c) the union of output triangles covers the input domain to within a documented tolerance (no interior gaps, no elements outside the polygon).
- **FR-014a**: Tier 1 (`wetting_and_drying_test.14`) is the **first BC-coverage gate** — it must round-trip and re-triangulate cleanly *before* the Tier 2 WNAT gate is evaluated. Failure at Tier 1 short-circuits the rest of the ladder.
- **FR-014b**: Loading `wetting_and_drying_test.14` requires extending the spec 001 fort.14 reader to handle (i) IBTYPE 3 (external weir/barrier) records — single-node + crest-elevation columns — and (ii) IBTYPE 24 (internal barrier with supercritical flow) records — node-PAIR format with crest + coefficient columns. The current reader (`admesh/fort14.py`) reads only the first integer per line and would silently drop the paired-node and crest data. This expansion MAY require new `BoundaryType` enum members or a paired-node sub-type on `BoundarySegment`; the design choice is locked during `/speckit-plan`.
- **FR-015**: No numeric element-quality threshold (e.g. `min_q ≥ X.Y`) is required for the 0.1.0 release gate. Aspirational quality matching Figure 8 of Conroy et al. (2012) is a roadmap target tracked outside this spec. The structural-validity asserts in FR-014 ARE the gate.
- **FR-016**: The full ladder regression test (Tier 0 + Tier 1 + Tier 2, plus Tier 1.5 when present) MUST be marked release-gating in CI; failing any tier MUST block the 0.1.0 tag. The test MUST run in under 60 seconds wall-clock on a developer laptop with no special hardware.

#### Release-readiness rider

- **FR-017**: The constitution amendment (`constitution.md` v1.0.1 from the prior session) that reframes the fort.14 contract as shipped MUST be walked back. Either revert to v1.0.0 or supersede with v1.0.2 language that acknowledges the size-field work as a precondition for the fort.14 contract being "release-ready".
- **FR-018**: README install + quickstart sections MUST restore an honest "0.1.0 in progress" callout. The hero image and the round-trip example may stay; the "v1 ships" framing must not.
- **FR-019**: Pre-tag cleanup: `dist/`, `build/`, `papers/wnat_admesh.png` (the rough render the user rejected), and stale demo artefacts under `tests/output/` MUST be removed from the working tree.
- **FR-020**: A pre-tag verification script MUST exist (or a checklist in this spec's `tasks.md`) to confirm FR-017 through FR-019 before the 0.1.0 tag is cut.

### Key Entities *(include if feature involves data)*

- **Default Size-Field Stack**: A composition of (curvature, medial-axis) — always-on — plus (bathymetry, tide) — opt-in. Outputs a `(N, 2) -> (N,)` callable suitable as `distmesh2d`'s `fh` argument. Backed by the existing `admesh.mesh_size.build_h(...)` composer.
- **Test Fixture Ladder**: A graduated set of regression fixtures, each tier strictly broader than the prior. The default-stack regression test MUST exercise every tier already present in `tests/fixtures/`; tiers may be added incrementally during implementation.
  - **Tier 0 — MVP synthetic** (already in repo): the 5 hand-crafted polygons from spec 001 (square, L-shape, U-shape, square-with-hole, doughnut). Pure geometry; no BC variety.
  - **Tier 1 — BC-coverage** (NEW, just added): `tests/fixtures/fort14/adcirc_examples/wetting_and_drying_test.14` — ADCIRC's official "Example 10" wetting-and-drying tutorial domain (`example10n`), 2716 nodes / 4978 elements. Carries 2 open boundaries + 9 land boundaries spanning IBTYPE 0 (mainland), IBTYPE 3 (external weir, single-node + crest data), and IBTYPE 24 (internal barrier with supercritical-flow node-PAIR records). Surfaces two known gaps in spec 001's fort.14 reader (see FR-014b).
  - **Tier 1.5 — small real-world** (acquisition deferred to implementation): an additional small bay or inlet from ADCIRC's official examples catalogue (`https://adcirc.org/home/documentation/example-problems/`) — Shinnecock Bay or Idealized Inlet are good candidates. Goal: real-coastline + real-BC-mix at < 10K nodes. Tracked in `tasks.md`.
  - **Tier 2 — release gate** (already in repo): `tests/fixtures/fort14/adcirc_examples/wnat_test.14` — the public-domain Hagen-et-al. WNAT mesh (9934 nodes, 18578 elements). Geographic-scale stress test; simpler BC shape than Tier 1 (only IBTYPE 0/-1).
- **Release-Readiness Bundle**: The set of repo edits that gate the 0.1.0 tag — constitution walkback, README walkback, repo cleanup. Lives alongside the size-field work in spec 002 because both gate the same release.
- **Public Knob → Internal Scale Mapping**: The documented translation from user-facing kwargs (`h_target`, `enable_*`, `bathymetry`, `tide_*`) to MATLAB-internal scale parameters (`K`, `R`, `s`, `sz`, `g`). Already partially exists in `mesh_size.build_h` docstrings (e.g. `K = π / curvature_scale`); spec 002 promotes this to top-level user documentation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For each of the 5 MVP domains and the WNAT canonical, `admesh.triangulate(domain)` with no size-field arguments returns a `Mesh` whose triangulation is structurally valid: every element has strictly positive signed area, every input boundary edge is preserved as a triangle edge, and the union of triangles covers the input domain to within tolerance.
- **SC-002**: For the WNAT canonical, the produced mesh has zero degenerate elements (zero or near-zero signed area beyond documented numerical tolerance).
- **SC-003**: For the WNAT canonical and any multiply-connected MVP domain, every island hole present in the input is faithfully preserved (no triangle overlaps the hole interior).
- **SC-004**: All 142 faithful-port tests still pass post-implementation.
- **SC-005**: A user can produce a structurally-valid WNAT mesh in ≤ 5 lines of Python from `import admesh` (target: 3-line idiom — read the fort.14, call `triangulate(domain)`, write back).
- **SC-006**: The 0.1.0 wheel installs in a clean Python ≥ 3.10 venv and the WNAT regression test runs in under 60 seconds wall-clock on a developer laptop (no special hardware).
- **SC-007**: Backward compat: every spec 001 quickstart-validation example produces a `Mesh` that compares equal (`mesh.equals(...)`) to the spec 001 baseline.
- **SC-008**: Repo cleanliness post-implementation: zero stale build artefacts, README accurately describes 0.1.0 scope, constitution stance on fort.14 is honest about the size-field-default precondition.

## Assumptions

- **Constitution Principle I (Faithful Port Before Optimization) still applies**: the 13 faithful-port stage modules in `admesh/*.py` MUST stay numerically identical. The default-size-field wiring is additive — it composes existing stages, does not modify them.
- **The `admesh/mesh_size.py::build_h(...)` composer is the authoritative composition logic**: spec 002 wraps `build_h` with a public-API surface; it does NOT reimplement composition. If `build_h` has a bug, the bug is fixed in `build_h` (faithful-port territory) — spec 002 only adds wrapping.
- **The WNAT_Test.14 fixture is representative of the hardness class** that 0.1.0 needs to handle. If a domain class outside this scope (e.g. inland flood mapping with 100 m feature size on a 1000 km domain) breaks, that is out of scope for 0.1.0 and becomes a separate spec.
- **`wetting_and_drying_test.14` provenance**: ADCIRC's official "Example 10" (Wetting and Drying with Weirs) tutorial domain. Public-domain like the rest of ADCIRC's example problems catalogue. The file's AGRID identifier is literally `example10n`. Sourced via `/Users/domattioli/Projects/MADMESHR/01_.14_Files/` for spec 002; the canonical upstream is `https://adcirc.org/home/documentation/example-problems/` and `adcirc/adcirc-cg` repo's `work/example/` directory. Provenance to be documented in `tests/fixtures/fort14/adcirc_examples/PROVENANCE.md` during `/speckit-implement`.
- **Tier 1.5 fixture acquisition is deferred to implementation phase**: a small real-coastline ADCIRC example (Shinnecock Bay or Idealized Inlet) will be pulled from the ADCIRC examples catalogue during `/speckit-implement` and added to the test ladder. Captured as a `tasks.md` entry rather than a spec-level commitment because it's a deterministic chore, not a design decision.
- **Domain/mesh registry as a long-term research direction**: the broader question of how to discover, classify, and package test fixtures across all ADCIRC-compatible mesh sources is tracked in GitHub issue [#6](https://github.com/domattioli/ADMESH/issues/6) ("Investigate community-driven domain/mesh registry concept"). Out of scope for 0.1.0.
- **0.1.0 will be the first PyPI-tagged release** since v0.0.2. The version string already set in `__init__.py` from spec 001 (`__version__ = "0.1.0"`) becomes the actual published tag once this spec lands.
- **The MATLAB Figure 8 reproduction is qualitative, not bit-exact**: the goal is "the same kind of mesh" as the published reference, not a node-for-node match. Bit-exact match would require matching MATLAB's distmesh seed and is out of scope for 0.1.0.
- **Existing `Mesh.equals(...)` and per-element quality computation are sufficient** for the regression test's acceptance criteria. If a richer comparison primitive is needed (e.g. structural similarity score), it lands as part of this spec's implementation.
- **Out of scope (deferred to later specs)**: performance optimization of any individual stage; new stages beyond the 5 already ported; GUI; Gmsh I/O (already logged as feature 003 in GH issue #5); generalisation to 3D or non-Cartesian CRS handling.
