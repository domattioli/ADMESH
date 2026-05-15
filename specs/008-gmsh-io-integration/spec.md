# Feature Specification: Gmsh `.msh` I/O Integration

**Feature Branch**: `008-gmsh-io-integration`
**Created**: 2026-05-10
**Status**: Draft
**Input**: GitHub issue #5 — "Add Gmsh .msh I/O as feature 003"
**Tracks**: domattioli/ADMESH#5

## Clarifications

### Session 2026-05-10

- Q: Which Gmsh ASCII versions must v1 support? → A: **v2.2 and v4.1 ASCII**, both readable; writer emits v4.1 by default with a `version="2.2"` opt-in. Binary `.msh` is out of scope for v1.
- Q: How does the format-bridge handle Gmsh's 3D node coordinates when our internal model is 2D? → A: Reader drops `z` if `|z| < 1e-12` for every node (true planar mesh); otherwise raises `GmshParseError("non-planar mesh; admesh is 2D")`. Writer always emits `z = 0.0`. The third coordinate is *not* repurposed for bathymetry — bathymetry stays a separate per-node field.
- Q: How are bathymetry values exchanged? → A: As a Gmsh `NodeData` view named `"bathymetry"` (positive-down, ADCIRC-convention) when the mesh has bathymetry; absent otherwise. Reader picks up any view named `"bathymetry"` and applies the sign flip; writer emits when bathymetry is present.
- Q: How does the reader infer boundary segments when physical groups are absent? → A: It does not. Without a physical-group block, all boundary nodes are returned as a single anonymous ring labelled `BoundaryType.MAINLAND` (the same default fort.14 uses for unlabelled land boundary), with a documented warning. Power users wanting structured boundaries supply physical groups.
- Q: Does this feature change the public top-level API? → A: Additive only. New names: `admesh.read_msh`, `admesh.write_msh`, `admesh.GmshParseError`, plus method `Mesh.to_msh(path, version="4.1")`. The spec-001 fort.14 surface is untouched.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Read a Gmsh-Authored Mesh (Priority: P1)

A practitioner has a triangular mesh authored in Gmsh (point-and-click GUI or `.geo` script) and wants to feed it into the admesh pipeline — quality smoothing, fort.14 export to ADCIRC, or downstream chilmesh consumption. They should be able to call `admesh.read_msh("my_mesh.msh")` and receive a `Mesh` object with the same shape and guarantees as one produced by `admesh.triangulate(...)` or `admesh.read_fort14(...)`.

**Why this priority**: This is the entry point. Without read support there is no Gmsh integration, full stop. The fort.14 sibling already covers write-only sources; symmetric read coverage for Gmsh closes the most-requested gap.

**Independent Test**: Author a 5-node triangle in Gmsh (`gmsh -format msh22` and `-format msh41`), call `read_msh`, assert the returned `Mesh` has the expected node coordinates, element connectivity, and an empty-but-valid boundary block. No physical groups required for this minimal test.

**Acceptance Scenarios**:

1. **Given** a Gmsh ASCII v2.2 file with `$Nodes` and `$Elements` blocks, **When** the user calls `admesh.read_msh(path)`, **Then** the returned `Mesh` has `len(mesh.nodes) == header.numNodes` and 2D node coordinates with `z` dropped.
2. **Given** the same logical mesh saved as both v2.2 and v4.1, **When** read, **Then** both produce `Mesh` objects equal in nodes and elements (boundary labels may differ only if the v4 file has additional entity-block context).
3. **Given** a Gmsh file containing `$PhysicalNames` mapping `"open" → tag 100`, `"mainland" → tag 200`, **When** read, **Then** boundary segments are returned with `BoundaryType.OPEN` and `BoundaryType.MAINLAND` respectively.
4. **Given** a Gmsh file with a non-planar node (`|z| ≥ 1e-12`), **When** read, **Then** the call raises `GmshParseError` with the offending node id and `z` value in the message.

---

### User Story 2 — Write an admesh Mesh as Gmsh (Priority: P1)

A user has produced a mesh via `admesh.triangulate(...)` and wants to inspect it in the Gmsh GUI, or hand it off to a collaborator using a Gmsh-centric workflow. They call `mesh.to_msh("out.msh")` (or `admesh.write_msh(mesh, "out.msh")`) and the resulting file opens in Gmsh without warnings, preserves boundary labels via physical groups, and round-trips back through `read_msh` with no loss.

**Why this priority**: The output side is the practical reason most users care: they trust admesh's quality numerics and want to view/edit the result in a familiar GUI.

**Independent Test**: Triangulate `unit_square`, write to `.msh`, open in `gmsh -check out.msh` (CI step), and read back via `admesh.read_msh`. Assert node, element, and boundary-label parity within float tolerance.

**Acceptance Scenarios**:

1. **Given** a `Mesh` produced by `admesh.triangulate(unit_square_domain)`, **When** the user calls `mesh.to_msh("out.msh")`, **Then** `gmsh -check out.msh` exits 0 and emits no `Warning:` lines.
2. **Given** a `Mesh` with mixed `OPEN`, `MAINLAND`, `ISLAND` boundary segments, **When** written to `.msh`, **Then** the `$PhysicalNames` block contains entries for each used `BoundaryType` and each boundary 1D element references the correct physical tag.
3. **Given** a `Mesh` with bathymetry, **When** written to `.msh`, **Then** the file contains a `$NodeData` block named `"bathymetry"` with one scalar per node in positive-down ADCIRC convention.

---

### User Story 3 — Round-Trip Parity Across Formats (Priority: P2)

A user wants to convert between Gmsh and ADCIRC fort.14 in either direction with no loss of structural information. They run `Gmsh → admesh → fort.14 → admesh → Gmsh` and the final `.msh` is structurally equal to the original (nodes, elements, boundary labels, bathymetry).

**Why this priority**: Format-bridge guarantees are the value proposition of any I/O feature. Without proven round-trip parity, users will not trust the integration for production runs.

**Independent Test**: For each of the 5 MVP domains (`unit_square`, `L_shape`, `unit_disk`, `annulus`, `notched_rectangle`), run the round-trip and assert deep equality (nodes within `1e-9` absolute tolerance, exact integer match on element/boundary connectivity, exact match on `BoundaryType` codes).

**Acceptance Scenarios**:

1. **Given** any of the 5 MVP domains meshed via `admesh.triangulate`, **When** the user runs Gmsh → admesh → fort.14 → admesh → Gmsh, **Then** the final mesh is equal to the start mesh on nodes, elements, and boundary labels.
2. **Given** an external Gmsh-authored file with mixed physical groups, **When** read by admesh and rewritten, **Then** the rewritten file is byte-identical *or* differs only in whitespace, comments, and key ordering as documented in `PORTING_NOTES.md`.
3. **Given** a numeric IBTYPE code (e.g., `22` for external barrier) without a symbolic `BoundaryType` name, **When** read from fort.14, written to Gmsh, read back, and written to fort.14 again, **Then** the numeric code survives all four translations losslessly.

---

### Edge Cases

- **Mesh without physical groups**: Single-ring `MAINLAND` fallback with a `UserWarning`. Documented; not an error.
- **Non-planar node** (`|z| ≥ 1e-12`): `GmshParseError` with node id and z. No silent flattening.
- **Higher-order Gmsh elements** (`Triangle6`, `Quad9`): v1 raises `GmshParseError("higher-order elements not supported in v1; please use linear triangles")`. Forward-compat note in `PORTING_NOTES.md`.
- **Mixed-element meshes** (triangles + quads + lines): triangles are the primary 2D element; line elements drive boundary inference; quads and points raise the same higher-order error path. v1 is triangle-only on the 2D side.
- **Multiply-connected domains** (annulus, holes): each hole is its own `EntitySurface` in Gmsh v4 / its own line-loop in v2; the reader must distinguish outer ring from holes by orientation (CCW outer, CW holes per Gmsh convention) and tag them with `BoundaryType.ISLAND` if the physical name is `"island"` else `MAINLAND`.
- **Gmsh comment lines / empty blocks**: tolerated and ignored. The reader does not error on optional blocks (`$Periodic`, `$NodeData` other than `bathymetry`, `$ElementData`).
- **Duplicate physical-group names**: the reader takes the first definition and warns; the writer rejects duplicate `BoundaryType` → name conflicts at construction time.
- **Very large meshes** (>10M nodes): out of scope for v1 streaming; same forward-compat note as fort.14 — design must not foreclose streaming.
- **Index base**: Gmsh is 1-based like fort.14. Conversion happens strictly at the I/O boundary (FR-006). No 1-based indices leak into in-memory structures.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `admesh.read_msh(path) -> Mesh` MUST parse Gmsh ASCII v2.2 and v4.1 files containing linear triangles.
- **FR-002**: `admesh.write_msh(mesh, path, version="4.1")` MUST produce a file that `gmsh -check <path>` accepts with exit 0 and zero `Warning:` lines on stderr.
- **FR-003**: `Mesh.to_msh(path, version="4.1")` MUST be a thin alias for `admesh.write_msh(self, path, version)`.
- **FR-004**: A `GmshParseError` exception MUST be raised on malformed input, identifying the offending line number and the missing/invalid token (mirrors `Fort14ParseError`).
- **FR-005**: The `gmsh` PyPI package MUST NOT be a hard dependency. Hand-rolled parser. If a future feature genuinely requires it, expose as `pip install admesh2D[gmsh]` extra.
- **FR-006**: 1-based ↔ 0-based index conversion MUST live strictly at the I/O boundary. No 1-based indices leak into `Mesh` attributes.
- **FR-007**: Bathymetry sign flip (positive-up internal ↔ positive-down ADCIRC/Gmsh-NodeData) MUST live strictly at the I/O boundary.
- **FR-008**: A canonical physical-group-name → `BoundaryType` mapping MUST be defined, documented, and exposed as a module-level constant `admesh.gmsh.PHYSICAL_GROUP_MAP`. Initial mapping:
  - `"open"` → `BoundaryType.OPEN`
  - `"mainland"` → `BoundaryType.MAINLAND`
  - `"island"` → `BoundaryType.ISLAND`
  - `"mainland_flux"` → `BoundaryType.MAINLAND_FLUX`
- **FR-009**: Physical group names not in `PHYSICAL_GROUP_MAP` MUST round-trip as a numeric IBTYPE code (the original Gmsh tag if it is an integer, or a hash-derived stable id otherwise) — the same lossless-numeric path fort.14 uses for unmapped codes.
- **FR-010**: A non-planar input (`|z| ≥ 1e-12` on any node) MUST raise `GmshParseError` rather than silently flatten.
- **FR-011**: Higher-order elements (any element type other than 2-node line and 3-node triangle in v1) MUST raise `GmshParseError`. Forward-compat is documented.
- **FR-012**: A mesh missing `$PhysicalNames` MUST be readable; the reader emits a `UserWarning` and returns a single `MAINLAND` ring spanning all boundary nodes.
- **FR-013**: Round-trip Gmsh → admesh → fort.14 → admesh → Gmsh MUST preserve nodes (within `1e-9` absolute tolerance), elements (exact), and boundary labels (exact, including unmapped numeric codes).
- **FR-014**: Round-trip on each of the 5 MVP domains (`unit_square`, `L_shape`, `unit_disk`, `annulus`, `notched_rectangle`) MUST pass the same equality predicate as FR-013.
- **FR-015**: The writer MUST emit a `$NodeData` view named `"bathymetry"` when and only when the mesh has bathymetry, with `numScalarComponents = 1` and ADCIRC sign convention.
- **FR-016**: The reader MUST recognize a `$NodeData` view named `"bathymetry"` (case-insensitive) and apply the inverse sign convention; other `$NodeData` views are ignored without warning.
- **FR-017**: The public top-level API MUST add `read_msh`, `write_msh`, `GmshParseError` to `admesh/__init__.py` and `Mesh.to_msh` as a method. No existing public name is renamed or removed.
- **FR-018**: `docs/PORTING_NOTES.md` MUST gain a `Gmsh I/O` subsection covering: version policy, physical-group convention, z-flatness rule, bathymetry view, fallback behavior, and known divergences from upstream Gmsh writers.
- **FR-019**: A new contract document `specs/008-gmsh-io-integration/contracts/python-api.md` MUST list the exact public signatures and exceptions (mirrors `specs/001-pythonize-and-fort14-integration/contracts/python-api.md`).
- **FR-020**: The reader and writer MUST tolerate optional Gmsh blocks (`$Periodic`, `$Entities` in v4, comments) without raising and without losing primary data.

### Key Entities *(include if feature involves data)*

- **GmshFile**: The on-disk artifact. Header gives version (2.2 or 4.1) and ASCII/binary flag; v1 only handles ASCII. Composed of mandatory `$MeshFormat`, `$Nodes`, `$Elements` and optional `$PhysicalNames`, `$Entities` (v4), `$NodeData`, `$ElementData`, `$Periodic`.
- **PhysicalGroup**: A named collection of geometric entities. Carries `(dim, tag, name)`. The reader builds `tag → BoundaryType` via `PHYSICAL_GROUP_MAP`; unmapped names become numeric IBTYPE codes preserved through round-trip.
- **GmshElement**: A typed connectivity record. v1 understands element types 1 (2-node line, used for boundaries), 2 (3-node triangle, used for 2D body), and 15 (1-node point, ignored unless tied to a physical-group corner annotation). All other types raise.
- **NodeDataView**: A scalar field over nodes. v1 attends to `"bathymetry"` only; other views pass through silently.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `admesh.read_msh` parses every fixture in `tests/fixtures/gmsh/` (≥10 fixtures: 5 MVP domains × 2 versions) without error.
- **SC-002**: `admesh.write_msh` outputs that `gmsh -check` accepts with zero warnings, on each of the 5 MVP domains, both `version="2.2"` and `version="4.1"`.
- **SC-003**: Round-trip Gmsh → admesh → fort.14 → admesh → Gmsh on each MVP domain produces a final mesh structurally equal to the start mesh (FR-013 predicate).
- **SC-004**: `import admesh` succeeds with `gmsh` PyPI package uninstalled (FR-005 enforced).
- **SC-005**: The hand-rolled parser fits in ≤500 SLOC across `admesh/gmsh.py` (excluding tests). Comparable to `admesh/fort14.py` budget.
- **SC-006**: New tests added: ≥1 read test per version (v2.2, v4.1), ≥1 write+`gmsh -check` test per version, ≥1 round-trip test per MVP domain, ≥3 negative tests (non-planar, higher-order, malformed). Total ≥15 new tests.
- **SC-007**: Existing 308-test suite continues to pass — feature is purely additive (Constitution Principle I).

## Assumptions

- The user has either authored Gmsh files manually, generated them via Gmsh CLI/GUI, or received them from a collaborator. Programmatic Gmsh API generation (via the `gmsh` PyPI package) is out of scope.
- A Gmsh CLI binary is available in CI for the `gmsh -check` validation step. If not available, that step is skipped with a documented warning (test marked `xfail` on environments without Gmsh).
- The 5 MVP domains already have stable triangulations under `admesh.triangulate(...)` (covered by spec 001 acceptance tests).
- The constitution's "Out-of-scope" list (deferred items) will be patch-amended after this feature ships, similar to how spec 001 lifted the `fort.14 I/O` deferral.
- `BoundaryType` enum is stable — this feature uses but does not extend it. Future code additions (e.g., barriers, weirs) are non-breaking and would auto-extend `PHYSICAL_GROUP_MAP` via FR-009's numeric round-trip path.
