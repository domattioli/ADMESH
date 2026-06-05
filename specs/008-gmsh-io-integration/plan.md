# Implementation Plan: Gmsh `.msh` I/O Integration

**Branch**: `008-gmsh-io-integration` (logical; physical work lands on `daily-maintenance`)
**Date**: 2026-05-10
**Spec**: [spec.md](./spec.md)
**Tracks**: domattioli/ADMESH#5

## Summary

Mirror the existing `admesh.fort14` module in a new `admesh.gmsh` module: hand-rolled ASCII parser/serializer for Gmsh `.msh` v2.2 and v4.1, exposing `read_msh`, `write_msh`, `GmshParseError`, and `Mesh.to_msh` as a method alias. No new hard dependencies — the upstream `gmsh` PyPI package (~400 MB) is opt-in via a future `[gmsh]` extra only if a feature genuinely needs it. Boundary semantics ride on Gmsh's `$PhysicalNames` block via a documented `PHYSICAL_GROUP_MAP`; unmapped names round-trip as numeric IBTYPE codes, mirroring the fort.14 lossless-numeric path. Bathymetry is exchanged via a `$NodeData` view named `"bathymetry"` in ADCIRC sign convention. The faithful-port surface and the Pythonic `Mesh`/`Domain` API from spec 001 are untouched.

## Technical Context

**Language/Version**: Python ≥3.10 (existing pin)
**Primary Dependencies**: NumPy ≥1.24 (existing). No new runtime dependency.
**Optional Dependency**: `gmsh` PyPI package as `[gmsh]` extra — *not* added in v1; reserved namespace for forward features (CAD import, programmatic geometry building).
**Storage**: Gmsh ASCII `.msh` files (v2.2 or v4.1).
**Testing**: pytest. New tests sit alongside `tests/test_fort14_*.py`. Fixtures under `tests/fixtures/gmsh/` (5 MVP domains × 2 versions = 10 base files plus negative-case fixtures).
**External Tool**: Gmsh CLI binary used in CI for `gmsh -check <path>` writer-validation step. Test marked `pytest.mark.skipif(not shutil.which("gmsh"))`.
**Target Platform**: Linux, macOS, Windows (pure Python).
**Project Type**: Python library — single project.
**Performance Goals**: No new perf gates. v1 is in-memory; design must not foreclose streaming for >10M-node meshes (mirrors fort.14 commitment).
**Constraints**:
- Hand-rolled parser only (FR-005); the `gmsh` PyPI package MUST NOT be a hard dependency.
- 1-based ↔ 0-based conversion at the I/O boundary only (FR-006).
- Bathymetry sign flip at the I/O boundary only (FR-007).
- `import admesh` MUST succeed without `gmsh` PyPI installed (SC-004).
- Numerical equivalence on round-trip (FR-013) at `1e-9` absolute tolerance for nodes; exact integer match for connectivity and labels.
**Scale/Scope**: MVP fixtures <10k nodes. Streaming-capable design forward-compatible but not implemented.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Principles I–V from `.specify/memory/constitution.md`:

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Faithful Port Before Optimization | ✅ Preserved | Feature is purely additive on top of the spec-001 Pythonic layer. The MATLAB-mirror surface is untouched. The 308-test suite continues to gate `main` (SC-007). |
| II. Pure-Python First (No C Extensions) | ✅ Preserved | No C extensions. Hand-rolled parser is pure Python. The `gmsh` PyPI package — which is a C/C++ binding — is *not* added even as optional in v1. |
| III. Reference-Test Discipline | ✅ Preserved | Fixtures land in `tests/fixtures/gmsh/`. Each MVP domain × each Gmsh version is a curated reference file. Round-trip parity tests use the same `assert_mesh_equal` predicate already used for fort.14. |
| IV. Stage-by-Stage Bottom-Up Porting | ✅ N/A | The faithful port is complete. No porting work in scope. |
| V. Report-and-Advance Session Cadence | ✅ Preserved | Standard cadence applies. |

**Deviations from the constitution's "Out-of-scope" list:**

The constitution's `Article VI — Development Workflow & Quality Gates` (or its successor section after spec-001's amendment) lists I/O formats beyond fort.14 as deferred. This feature lifts that deferral for Gmsh ASCII v2.2/v4.1 only. Binary `.msh`, periodic-mesh blocks, higher-order elements, and CAD geometry import remain deferred.

**Result**: Constitution Check passes. One documented deferred-list scope change (Gmsh ASCII I/O), tracked in **Complexity Tracking**.

## Project Structure

```
specs/008-gmsh-io-integration/
├── spec.md                          # User-facing spec (this feature)
├── plan.md                          # This file
├── research.md                      # Format-bridge research, version comparison
├── data-model.md                    # GmshFile / PhysicalGroup / NodeDataView entities
├── quickstart.md                    # Three-line user examples
├── tasks.md                         # Atomic task list with dependencies
├── contracts/
│   └── python-api.md                # Public-API signatures and exceptions
└── checklists/
    └── (parity, edge-case, performance — added during /tasks pass)
```

Implementation surface (created/modified in implementation phase, not in this planning pass):

```
admesh/
├── gmsh.py                          # NEW — hand-rolled parser + writer
├── api.py                           # MODIFIED — add Mesh.to_msh method
└── __init__.py                      # MODIFIED — re-export read_msh/write_msh/GmshParseError

tests/
├── fixtures/gmsh/                   # NEW — 10 base + ≥3 negative fixtures
│   ├── unit_square_v22.msh
│   ├── unit_square_v41.msh
│   ├── L_shape_v22.msh
│   ├── ... (per MVP domain × version)
│   ├── nonplanar.msh                # negative — non-zero z
│   ├── quad9.msh                    # negative — higher-order
│   └── malformed_header.msh         # negative — broken $MeshFormat
├── test_gmsh_read.py                # NEW — read tests across versions
├── test_gmsh_write.py               # NEW — write tests + gmsh -check
└── test_gmsh_roundtrip.py           # NEW — Gmsh↔fort.14 round-trip on MVP domains

docs/
└── PORTING_NOTES.md                 # MODIFIED — Gmsh I/O subsection

pyproject.toml                       # MODIFIED — reserve `[gmsh]` extra namespace (empty for v1)
```

## Phase 0: Research (output → research.md)

Topics to resolve before design:

1. **Gmsh ASCII v2.2 vs v4.1 grammar differences.** v2 is single-pass: `$Nodes`/`$Elements` blocks contain everything. v4 introduces an `$Entities` block grouping geometric entities (points/curves/surfaces/volumes), and `$Nodes`/`$Elements` are organized in entity-blocks. Reader needs a small AST-like state machine to handle both.
2. **Physical-group ↔ entity-block linkage.** In v2, each element line ends with `(numTags, tag1, tag2, ...)` where tag1 is the physical group. In v4, physical groups attach to entities, and elements in an entity block inherit the entity's physical-group set.
3. **Boundary inference.** Gmsh stores 1D line elements with physical tags as boundaries. Our model wants ordered ring segments. Algorithm: collect line elements per physical tag → build adjacency map per tag → walk to extract closed rings (or open chains, which we reject as malformed).
4. **`gmsh -check` exit semantics.** Confirm Gmsh's return codes and warning channels for our writer-validation gate.
5. **Z-coordinate flatness convention.** Adopted: drop `z` if `|z| < 1e-12`, raise otherwise. Confirm `1e-12` is robust against double-precision text round-trip.
6. **`$NodeData` views.** Adopted: `"bathymetry"` is the well-known name; case-insensitive read; ADCIRC sign convention. Confirm view-block grammar in both versions.
7. **Existing fort.14 patterns to mirror.** Re-read `admesh/fort14.py` to lift the parsing-error-with-line-number pattern, the round-trip equality predicate, and the index-conversion boundary placement.

Deliverable: `research.md` answers each topic with a concrete decision and a citation (Gmsh manual section, file path, or test fixture name).

## Phase 1: Design (output → data-model.md, contracts/python-api.md, quickstart.md)

### data-model.md

- `GmshFile` — top-level container; tracks version, ASCII/binary flag, raw blocks. Internal-only; not part of public API.
- `PhysicalGroup` — `(dim: int, tag: int, name: str | None)`. Drives `BoundaryType` resolution.
- `GmshElement` — typed connectivity record with `(element_type: int, node_ids: tuple[int, ...], physical_tag: int | None, entity_tag: int | None)`. v1 supports types 1 (line) and 2 (triangle).
- `NodeDataView` — `(name: str, num_components: int, values: ndarray[N])`. v1 reads/writes only `"bathymetry"`.

Cross-references the `Mesh`, `Domain`, `BoundarySegment`, `BoundaryType` entities from `specs/001-pythonize-and-fort14-integration/data-model.md` — does not redefine them.

### contracts/python-api.md

Exact public signatures:

```python
def read_msh(path: str | os.PathLike) -> Mesh: ...
def write_msh(mesh: Mesh, path: str | os.PathLike, *, version: str = "4.1") -> None: ...
class GmshParseError(ValueError):
    line_number: int | None
    detail: str
class Mesh:
    def to_msh(self, path: str | os.PathLike, *, version: str = "4.1") -> None: ...
```

Plus the module constant:

```python
PHYSICAL_GROUP_MAP: dict[str, BoundaryType] = {
    "open":          BoundaryType.OPEN,
    "mainland":      BoundaryType.MAINLAND,
    "island":        BoundaryType.ISLAND,
    "mainland_flux": BoundaryType.MAINLAND_FLUX,
}
```

### quickstart.md

Three-line examples for each user story (read, write, round-trip), runnable against the fixtures directory.

### Constitution re-check after design

Re-evaluate Principles I–V after `data-model.md` and `contracts/python-api.md` exist. Expected: still passes. If not, list deviations and stop.

## Phase 2: Tasks (output → tasks.md)

Task decomposition follows the standard spec-kit pattern. Headline groups:

1. **Phase 0: Research** — one task per research topic (7 tasks).
2. **Phase 1: Design** — `data-model.md`, `contracts/python-api.md`, `quickstart.md` (3 tasks).
3. **Phase 2: Test scaffolding** — fixtures, test files (8 tasks).
4. **Phase 3: Reader implementation** — header, nodes, elements, physical groups, node data (5 tasks).
5. **Phase 4: Writer implementation** — header, nodes, elements, physical groups, node data (5 tasks).
6. **Phase 5: API wiring** — `__init__.py` exports, `Mesh.to_msh` method, `pyproject.toml` reserved extra (3 tasks).
7. **Phase 6: Documentation** — `docs/PORTING_NOTES.md` Gmsh section, `CHANGELOG.md` entry (2 tasks).
8. **Phase 7: Validation** — full test-suite run, `gmsh -check` CI gate, round-trip parity assertion (3 tasks).

Each task: tied to one or more SC/FR; dependency edges explicit; checked off in tasks.md as it lands.

## Complexity Tracking

| Concern | Severity | Mitigation |
|---------|----------|------------|
| Two Gmsh ASCII versions (v2.2, v4.1) double the parser surface | Medium | Single internal AST with version-tagged dispatch; ≤500 SLOC budget (SC-005). |
| Boundary inference from line elements is non-trivial for multiply-connected domains | Medium | Reuse the ring-walk + leftmost-turn heuristic added for fort.14 in commit `c7c6568` (issue #38/#39); covered by annulus and notched_rectangle MVP fixtures. |
| Constitution deferred-list scope change | Low | Documented above; pattern matches spec 001's fort.14 lift; PATCH amendment to constitution after feature lands. |
| `gmsh -check` requires Gmsh CLI in CI | Low | Test marked `skipif` when binary absent; CI image gets `gmsh` apt-installed. |
| Higher-order elements explicitly rejected | Low | Documented forward-compat path; `GmshParseError` with actionable message; no silent dropping. |

## Out of Scope (Forward-Compat Notes)

Explicitly **not** in v1; future features may lift one at a time:

- Binary `.msh` format
- Higher-order elements (`Triangle6`, `Quad9`, etc.)
- Mixed-element 2D meshes (triangle + quad)
- Periodic-mesh blocks
- CAD geometry import (`.brep`, `.step`) via `gmsh` PyPI package
- Streaming reader/writer for >10M-node meshes (design must not foreclose, but no implementation)
- Programmatic Gmsh model construction via the `gmsh` Python API
- Element-data views (only node-data `"bathymetry"` is wired)

Each of the above warrants its own follow-up issue if/when a user need surfaces.
