# Feature Specification: Pythonic API Layer + fort.14 I/O + chilmesh Integration

**Feature Branch**: `001-pythonize-and-fort14-integration`
**Created**: 2026-04-24
**Status**: Draft
**Input**: User description: Take the faithful MATLAB port of ADMESH and layer a more Pythonic API over it without breaking the port guarantee; spec fort.14 I/O (ADCIRC mesh format); explore how admesh2D integrates with a sibling `chilmesh` project that consumes .14 files.

## Clarifications

### Session 2026-04-24

- Q: How does the public `Mesh` object expose boundary-condition information — per-node, per-segment, or both? → A: Per-segment only. The mesh holds an ordered list of `BoundarySegment` objects (node-id sequence + `BoundaryType` code), mirroring fort.14's native shape. A per-node view is not a first-class attribute; if needed, it is a derived helper added later.
- Q: How does a user-supplied size-field contribution combine with the built-in stages? → A: Two-phase composition. Built-in stages (curvature, medial axis, bathymetry, tide) always `min`-stack — MATLAB-faithful, non-negotiable. User contributions are applied *after* the built-in stack via a user-chosen combiner (default `np.minimum.reduce`). This preserves Constitution Principle I on the faithful surface while giving power users flexibility on top.
- Q: What visualization surface ships in v1? → A: Minimal — `__repr__`/`__str__` plus a single `mesh.plot(ax=None, **kwargs)` matplotlib helper that draws nodes, elements, and boundary segments coloured by `BoundaryType`. matplotlib is an optional extra (`pip install admesh2D[viz]`). Future direction (out of scope for this spec): a full visualization module with `plot_size_field()`, `plot_quality_histogram()`, `animate_iterations()` etc. — to be specced separately once v1 lands.
- Q: Which chilmesh integration direction does the spec recommend? → A: Option A — admesh2D owns fort.14 export; chilmesh reads fort.14 independently. No cross-imports, no install-graph entanglement, fort.14 is the contract. (See `chilmesh Integration — Options & Recommendation` section for full trade-off analysis.)
- Q: How aggressive is v1's `BoundaryType` enum coverage? → A: Common-use only — OPEN (0), MAINLAND (1), MAINLAND_FLUX (20), ISLAND (11), plus the existing WALL semantics mapped to its correct ADCIRC code. ~5 named codes. Any additional ADCIRC code (barriers, weirs, river inflows, etc.) is preserved as a numeric value per FR-012 and round-trips losslessly without a symbolic name. Adding more named codes later is a non-breaking change — explicitly *not* a v1 commitment.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - End-to-End Pipeline: Domain → Mesh → .14 File (Priority: P1)

A scientist or engineer has a 2D domain (bounding box + boundary polygon + optional holes, bathymetry, and tidal data) and wants the canonical ADMESH output: a quality triangular mesh serialized as an ADCIRC `fort.14` file. They should be able to go from inputs to `.14` on disk in three readable lines of Python, with no knowledge of MATLAB conventions, the 13-stage internal pipeline, or fort.14 column layouts.

**Why this priority**: This is the dominant use of the package. Every other user story inherits from this being pleasant. If the "happy path" is verbose or exposes internal seams, every downstream integration feels it.

**Independent Test**: Produce a mesh on each of the five canonical MVP domains (unit_square, L-shape, unit_disk, annulus, notched_rectangle), serialize to `fort.14`, read it back, and assert round-trip equality of node coordinates, element connectivity, and boundary-condition labels. Delivered value: a user can produce simulation-ready meshes without reading any internal module documentation.

**Acceptance Scenarios**:

1. **Given** a domain description (bounding box + SDF or polygon rings), **When** the user invokes the top-level triangulation API with default parameters, **Then** they receive a mesh object with typed attributes (nodes, elements, boundary labels, quality metrics) and a `.to_fort14(path)` method writes a valid ADCIRC mesh file.
2. **Given** a mesh object produced by the pipeline, **When** the user reads the `.14` file back via the public API, **Then** the reloaded mesh is equal (within floating-point tolerance) to the original in nodes, elements, and boundary labels.
3. **Given** the user inspects the mesh object in a REPL or notebook, **When** they print it, **Then** the `__repr__` shows a human-readable summary (node count, element count, quality metrics, boundary-condition breakdown) — not raw NumPy arrays.

---

### User Story 2 - chilmesh Round-Trip (Priority: P2)

A user of the sibling `chilmesh` project wants to consume an ADMESH mesh. Since chilmesh already reads `fort.14` files, the integration should not require either project to take a hard dependency on the other. The user should be able to write `chilmesh.ChilMesh.from_fort14("admesh_output.14")` — or whatever chilmesh's existing factory is — and have the boundary-condition labels, element connectivity, and bathymetry survive the round-trip intact.

**Why this priority**: Integration is the reason the user is investing in the fort.14 path at all. But it's P2 because it's a consumer-side concern — the admesh2D side of the contract (correct, spec-conformant fort.14 output) is what this spec owns; the chilmesh side is evaluated, not built.

**Independent Test**: Produce a mesh with each supported boundary-condition type (OPEN, WALL, and any future types) via admesh2D, write to `.14`, read with chilmesh, and confirm that chilmesh's internal representation carries the same BC labels and the same per-node coordinates and per-element vertex indices. Deliver value: the user can pipe ADMESH output into a downstream chilmesh-based workflow without a custom translator.

**Acceptance Scenarios**:

1. **Given** an admesh2D mesh with mixed OPEN and WALL boundary segments, **When** it is written to `.14` and loaded by chilmesh, **Then** chilmesh's boundary-segment queries return the same segment counts and node groupings as admesh2D produced.
2. **Given** the user asks "should admesh2D export to .14, or should chilmesh have an `.admesh()` constructor that calls admesh2D directly?", **When** they read this spec, **Then** they find a clear recommendation with documented trade-offs (coupling, install graph, API-surface ownership) — not a decision, but enough context to make one informed.

---

### User Story 3 - Power User: Custom Size-Field Contributions (Priority: P3)

An advanced user wants to plug a domain-specific sizing rule into the ADMESH pipeline — e.g., refine the mesh near a computed wave-breaking line, or honor an external hazard map. They should be able to compose their custom contribution with ADMESH's existing curvature, medial-axis, bathymetry, and tide stages without monkey-patching internals or vendoring the library.

**Why this priority**: This audience is small but influential; these are the users who will drive feedback about whether the Pythonic layer is actually better than the MATLAB port for real work. It's P3 because User Stories 1 and 2 must land first — a power-user API on a rough happy path doesn't help anyone.

**Independent Test**: Provide a documented extension point (a callable, a protocol, a plugin registry — TBD by implementation). A user can supply an arbitrary `(points) -> size` function, compose it with the built-in stages, and observe the final size field reflect the contribution. Value: one extension example in the docs that a user can copy-modify.

**Acceptance Scenarios**:

1. **Given** a user-supplied size-field contribution callable, **When** the user passes it into the pipeline, **Then** the final size field is computed in two phases: first the built-in stages (curvature, medial axis, bathymetry, tide) are `min`-stacked exactly as in the MATLAB port, then the user's contribution is combined with that result via the user-supplied combiner (default elementwise `min`).
2. **Given** the user's contribution produces invalid values (NaN, negative, above `hmax`), **When** the pipeline runs, **Then** the pipeline clamps values to `[hmin, hmax]` and emits a documented warning rather than failing silently or crashing.

---

### Edge Cases

- **Multiply-connected domains** (annulus, domains with holes): fort.14 boundary segments must distinguish the outer boundary from hole boundaries, and the BC label must be preserved per-ring on round-trip.
- **Ill-formed fort.14 input** (wrong node count in header, non-monotonic node IDs, missing boundary block): the reader must report *which line* and *what was expected*, not fail with a cryptic parser error.
- **Bathymetry sign convention**: ADCIRC convention is depth-below-datum (positive down); our internal convention is elevation (positive up). The writer must apply the sign flip; the reader must invert it. Round-trip must preserve the physical field exactly.
- **1-based vs. 0-based indexing**: fort.14 is 1-based; our internal arrays are 0-based per the constitution. The boundary between the two must be exactly at the I/O layer — no internal leak.
- **BC label values not in our `BoundaryType` enum**: fort.14 supports BC codes we don't model (e.g., code 22 = external barrier). The reader must preserve the numeric code without dropping it, even if we don't have a symbolic name yet.
- **Fixed-precision round-trip**: fort.14 stores coordinates as decimal text; reading and re-writing should not accumulate drift past the file's documented precision.
- **Extremely large meshes** (>10M nodes): the reader/writer must stream, not load the whole file into memory at once. Not an immediate requirement but the API must not foreclose it.
- **Backward-compatibility contract**: any user who is today calling the module-level MATLAB-mirror functions (e.g., `admesh.distmesh.distmesh2d_admesh`) must continue to get identical numerical behavior after the Pythonic layer lands.

## Requirements *(mandatory)*

### Functional Requirements

**Pythonic API layer:**

- **FR-001**: The package MUST expose a top-level triangulation entry point that accepts a domain specification (SDF + bounding box + optional PTS) and returns a typed mesh object. The entry point MUST accept keyword-only optional parameters for all tuning knobs (size-field stages, seed, iteration count, quality gates).
- **FR-002**: The returned mesh object MUST expose typed attributes: nodes (N×2 float), elements (M×3 int), an ordered list of boundary segments (each a node-id sequence plus a `BoundaryType` code), per-element quality, and per-ring boundary metadata. No MATLAB-style tuple returns at public boundaries. Per-node BC labels are NOT a first-class attribute — segments are the source of truth.
- **FR-003**: The mesh object MUST implement `__repr__` and `__str__` that produce human-readable summaries including node/element counts, min/mean quality, and BC-label breakdown.
- **FR-004**: The mesh object MUST provide an `.to_fort14(path)` method and a complementary top-level `read_fort14(path) -> Mesh` function.
- **FR-005**: Pipeline stages MUST follow a two-phase size-field composition. Phase 1: the built-in stages (curvature, medial axis, bathymetry, tide, boundary enforcement) MUST be `min`-stacked, producing numerically identical output to the MATLAB faithful port. Phase 2: zero or more user-supplied contributions MUST be combined with the Phase-1 result via a user-chosen combiner callable (default `np.minimum.reduce`). User contributions MUST NOT alter Phase-1 output.
- **FR-006**: The public API MUST accept array-likes (list, tuple, NumPy array, any `__array_interface__`-compatible object) anywhere a coordinate array is expected, not only pre-allocated `np.ndarray`.
- **FR-007**: All user-facing docstrings MUST use a consistent format with parameter types, return types, and at least one executable example.
- **FR-008**: The package MUST preserve the existing module-level, snake_case, MATLAB-mirroring functions as a documented "faithful port" surface — these functions MUST continue to be callable and produce numerically identical output to today's behavior.

**fort.14 I/O:**

- **FR-009**: The fort.14 writer MUST emit a file that passes structural validation against the ADCIRC v55.xx specification (header line, node block, element block, boundary blocks in canonical order).
- **FR-010**: The writer MUST serialize per-node depth (bathymetry) using ADCIRC's sign convention (positive-down). When the internal mesh has no bathymetry field, the writer MUST emit zeros with a documented default.
- **FR-011**: The writer MUST serialize boundary segments grouped by BC type: open-ocean segments in the "open boundary" block, wall/land segments in the "land boundary" block. Each segment MUST carry the BC-type code in its block header per ADCIRC format.
- **FR-012**: The reader MUST parse any well-formed fort.14 file and return a `Mesh` object with nodes, elements, and boundary segments populated. BC-type codes the package doesn't have a symbolic name for MUST be preserved as numeric codes.
- **FR-013**: The reader MUST convert 1-based indices in the file to 0-based indices at the I/O boundary. The writer MUST apply the inverse conversion.
- **FR-014**: Round-tripping (`mesh → write → read → mesh'`) MUST produce `mesh'` that is equal to `mesh` in: node coordinates (within documented float precision), element connectivity (exact), per-segment BC labels (exact), and bathymetry (within documented precision).
- **FR-015**: The reader MUST report parse errors with the offending line number and a description of what was expected, not a bare stack trace.

**chilmesh integration (exploratory — the spec answers, does not implement):**

- **FR-016**: This spec MUST document at least three integration options for admesh2D ↔ chilmesh (e.g., (a) admesh2D owns the export, chilmesh reads fort.14 independently; (b) chilmesh has a `.from_admesh()` factory; (c) a thin adapter package), each with coupling, install-graph, and API-ownership trade-offs.
- **FR-017**: This spec MUST include a recommendation with justification. Implementation of the recommendation is out of scope for this spec (see Assumptions).

**Backward compatibility:**

- **FR-018**: The full existing test suite (142 tests as of feature creation) MUST continue to pass after the Pythonic layer lands, with no changes to the test files that exercise the faithful-port surface.
- **FR-019**: The Pythonic layer MUST be additive. No currently-callable function may be removed or have its signature changed. Deprecations (if any) MUST ship with clear migration guidance and a documented sunset horizon.

**Visualization (minimal v1):**

- **FR-020**: The mesh object MUST provide a `mesh.plot(ax=None, **kwargs)` method that, when matplotlib is available, draws nodes, elements, and boundary segments (coloured by `BoundaryType`) on the supplied or a newly-created `Axes`. matplotlib MUST be an optional dependency installable via `pip install admesh2D[viz]`; importing the package without matplotlib MUST NOT fail.
- **FR-021**: When `mesh.plot()` is called without matplotlib installed, it MUST raise an `ImportError` whose message names the optional extra to install. No silent no-op.

**`BoundaryType` enum scope (v1):**

- **FR-022**: The `BoundaryType` enum in v1 MUST include symbolic members for the ADCIRC codes most commonly encountered in real fort.14 files: OPEN (0), MAINLAND (1), MAINLAND_FLUX (20), ISLAND (11), and WALL (mapped to its correct ADCIRC code). Any other numeric code present in a fort.14 input MUST round-trip via FR-012 as a numeric value without a symbolic alias. Adding new members to the enum later is a backward-compatible change.

### Key Entities

- **Mesh**: The primary output. Holds nodes (coordinates), elements (triangle connectivity), an ordered list of boundary segments (each a node-id sequence with a `BoundaryType` code), per-node bathymetry (optional), per-element quality metrics, and boundary-ring metadata. Supports round-trip to fort.14 and a minimal set of inspection/visualization methods.
- **BoundarySegment**: An ordered sequence of node IDs forming a connected polyline on a boundary ring, paired with a single `BoundaryType` code. Mirrors ADCIRC's native segment shape.
- **Domain**: The input. A description of the geometric region to mesh, carrying an SDF, a bounding box, fixed points, and optionally boundary-condition metadata (which segments are OPEN vs. WALL).
- **SizeField**: A callable returning a target element size at arbitrary query points. Produced by composing built-in stages (curvature, medial axis, bathymetry, tide) and user-supplied contributions.
- **Fort14File**: The canonical ADCIRC serialization. Consists of a header, a node block, an element block, and boundary blocks for open and land boundaries.
- **BoundaryType**: An enumeration of supported BC-type codes. v1 names: OPEN (0), MAINLAND (1), MAINLAND_FLUX (20), ISLAND (11), WALL (mapped to its ADCIRC code). Codes outside this set are preserved as numeric values on round-trip (FR-012) and may be added as named members in later releases without breaking existing API.

## chilmesh Integration — Options & Recommendation

Per FR-016 and FR-017, three integration paths were considered. Each is summarized below with its trade-offs, followed by the recommendation. Implementation of the recommended path is out of scope for this spec — a follow-up spec will own that work once v1 of the Pythonic layer + fort.14 I/O lands.

### Option A — admesh2D owns fort.14 export; chilmesh reads fort.14

**Mechanism**: admesh2D produces a `.14` file (or string buffer); chilmesh's existing `from_fort14` path consumes it. Neither project imports the other.

**Pros**:
- Zero install-graph coupling. Either project can release on its own cadence.
- The contract is a stable, documented file format (ADCIRC v55.xx), not a Python API surface.
- chilmesh continues to work with fort.14 files from any source, not just admesh2D.
- Surface area to test is small and well-defined: just round-trip fidelity.

**Cons**:
- In-memory workflows pay a (small) serialization cost — though `io.StringIO` keeps it bounded.
- Users who want `mesh = admesh.triangulate(...); chilmesh.from_admesh(mesh)` must instead write `mesh.to_fort14(buf); chilmesh.from_fort14(buf)`.

### Option B — chilmesh adds `ChilMesh.from_admesh(mesh)` factory

**Mechanism**: chilmesh takes a soft dependency on admesh2D's `Mesh` type and adds a constructor that consumes it directly.

**Pros**:
- Cleanest user-facing call site for in-process pipelines.
- Avoids any serialization round-trip.

**Cons**:
- chilmesh is now coupled to admesh2D's `Mesh` shape; any change to `Mesh` ripples into chilmesh.
- Install graph: chilmesh users now pull in admesh2D even if they never produce meshes themselves.
- Symmetry is awkward — chilmesh has special handling for one source format (admesh) but not others.

### Option C — Third-party adapter package `admesh-chilmesh-bridge`

**Mechanism**: A small adapter library owns the conversion in both directions, depending on both projects.

**Pros**:
- Both projects stay clean.
- Conversion logic has a clear home.

**Cons**:
- Third repo, third release pipeline, third issue tracker.
- Three-way version compatibility matrix to maintain.
- Where do bugs get filed? Discoverability is worse.

### Recommendation: Option A

admesh2D should own fort.14 export. chilmesh should read fort.14 independently as it already does. This minimizes coupling, leverages an existing industry-standard contract, and keeps both projects' release cadences and dependency graphs decoupled. The "cost" is one extra line of user code (`mesh.to_fort14(buf); chilmesh.from_fort14(buf)`) in exchange for full architectural decoupling — a trade that pays off the first time either project ships a breaking change to internal types.

A follow-up spec may revisit this once v1 ships and real users hit ergonomic friction. If the friction is real, the natural escalation is **not** Option B (which couples too tightly) but a small in-process helper inside admesh2D (`admesh.to_chilmesh(mesh) -> bytes`) that emits a fort.14-format buffer the user can pipe straight into chilmesh — preserving the file-format contract while eliminating disk I/O.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user who has never seen the library can produce a mesh on any of the five canonical test domains and write it to fort.14 in ≤5 lines of Python, following only the top-level quickstart documentation.
- **SC-002**: Round-trip tests (`mesh → fort.14 → mesh'`) on all five canonical test domains show exact connectivity agreement and coordinate agreement within fort.14's documented precision (six decimal places by default).
- **SC-003**: The existing 142-test suite continues to pass with zero modifications to test files that exercise the faithful-port surface.
- **SC-004**: A user of `chilmesh` can load an admesh2D-produced fort.14 file and query boundary segments by type with outputs that match what admesh2D produced (same segment counts, same node groupings per ring).
- **SC-005**: 100% of fort.14 files in a curated reference set (the ADCIRC documentation examples plus at least three community-provided real-world meshes) parse without error via the reader.
- **SC-006**: A power user can add a custom size-field contribution in ≤20 lines of code and see its effect reflected in the resulting mesh, with one worked example in the documentation.
- **SC-007**: Error messages from the fort.14 reader cite line numbers and expected content for at least 10 categories of malformed input (verified by a fuzzing / negative-test corpus).

## Assumptions

- **Implementation is out of scope for this spec.** This document defines WHAT; the `/speckit-plan` phase defines HOW and on what schedule.
- **The chilmesh decision is exploratory.** This spec documents trade-offs and recommends a direction; actually wiring the integration lives in a follow-up spec once a direction is chosen.
- **fort.14 target spec is ADCIRC v55.xx.** Earlier variants may be supported on best-effort; later variants are a future concern.
- **Bathymetry is optional.** Most ADMESH MVP test domains do not carry bathymetry; the writer emits zeros when absent, which is valid ADCIRC.
- **The Pythonic layer builds on, not replaces, the faithful-port surface.** Constitution Principle I (Faithful Port Before Optimization) continues to govern the MATLAB-mirror modules; the Pythonic layer is a new surface that composes over them.
- **Existing PyPI package name `admesh2D` is preserved.** No rename is in scope.
- **Streaming I/O for multi-gigabyte meshes is not an immediate requirement**, but the reader/writer design must not foreclose streaming. Treat as a "non-breaking future extension."
- **The `BoundaryType` enum is the authoritative symbolic-name source.** Numeric ADCIRC codes outside the enum are preserved but not symbolically named until they are added to the enum in a separate change.
- **Visualization is intentionally minimal in v1.** A single `mesh.plot()` matplotlib helper covers the inspection use case. A richer visualization module (size-field heatmaps, quality histograms, iteration animations) is a known follow-up — out of scope for this spec, to be specced separately once v1 lands.
