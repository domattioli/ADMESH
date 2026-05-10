# Tasks: Gmsh `.msh` I/O Integration

**Feature**: 008-gmsh-io-integration
**Date**: 2026-05-10
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)
**Tracks**: domattioli/ADMESH#5

## Conventions

- `[ ]` = open · `[x]` = done · `[-]` = skipped (with reason)
- `→ FR-NNN`/`SC-NNN` ties task to a spec acceptance criterion
- `dep:` lists task ids that must complete first
- Each task is **atomic** — completable in a single short focused session

## Phase 0 — Research (output: research.md)

Already complete in this planning pass.

- [x] **T001** Decide v2.2 + v4.1 grammar dispatch strategy → R1, FR-001
- [x] **T002** Decide physical-group ↔ entity-block linkage → R2, FR-008
- [x] **T003** Decide boundary-inference algorithm (reuse fort.14 ring-walk) → R3, data-model boundary-inference
- [x] **T004** Decide `gmsh -check` gate semantics → R4, FR-002, SC-002
- [x] **T005** Decide z-flatness rule (`1e-12` threshold) → R5, FR-010
- [x] **T006** Decide `$NodeData` bathymetry channel → R7, FR-015, FR-016
- [x] **T007** Decide hard-pass on `gmsh` PyPI package → R9, FR-005, SC-004

## Phase 1 — Design (output: data-model.md, contracts/python-api.md, quickstart.md)

Already complete in this planning pass.

- [x] **T010** Write `data-model.md` — internal entities + boundary algorithms · dep: T001-T007
- [x] **T011** Write `contracts/python-api.md` — public signatures · dep: T010
- [x] **T012** Write `quickstart.md` — three-line user examples · dep: T011

## Phase 2 — Test scaffolding (no production code yet)

- [ ] **T020** Add `tests/fixtures/gmsh/geo/` with five `.geo` source files (one per MVP domain) · → SC-006
- [ ] **T021** Add `Makefile` target `gmsh-fixtures` that regenerates the 10 base `.msh` fixtures via `gmsh -2 -format mshNN`
- [ ] **T022** Generate the 10 base fixtures and commit · dep: T020, T021
- [ ] **T023** Hand-craft three negative fixtures (`nonplanar.msh`, `quad9.msh`, `malformed_header.msh`) · dep: T022
- [ ] **T024** Add `tests/_round_trip_helpers.py` with the `assert_mesh_equal` predicate (shared with fort.14 round-trip tests) · → data-model equality predicate
- [ ] **T025** Stub `tests/test_gmsh_read.py` with one xfail test per acceptance scenario from User Story 1 (4 tests) · dep: T024
- [ ] **T026** Stub `tests/test_gmsh_write.py` with one xfail test per User Story 2 acceptance scenario (3 tests) · dep: T024
- [ ] **T027** Stub `tests/test_gmsh_roundtrip.py` with one xfail test per MVP domain (5 tests) · dep: T024

## Phase 3 — Reader implementation (`admesh/gmsh.py`)

- [ ] **T030** Skeleton: `admesh/gmsh.py` module, `GmshParseError` class, top-level `read_msh` stub raising NotImplementedError · → FR-004, FR-019
- [ ] **T031** `_parse_v22(lines)`: header, `$Nodes`, `$Elements`, `$PhysicalNames` blocks · → FR-001, R1 · dep: T030
- [ ] **T032** `_parse_v41(lines)`: header, `$Entities`, `$Nodes`, `$Elements`, `$PhysicalNames` blocks · → FR-001, R1 · dep: T030
- [ ] **T033** `_resolve_physical_groups(gmsh_file)`: build `tag → BoundaryType` via `PHYSICAL_GROUP_MAP`; numeric fallback per FR-009 · → FR-008, FR-009 · dep: T031, T032
- [ ] **T034** `_walk_boundary_rings(line_elements_by_tag)`: ring-walk + leftmost-turn at junctions; orientation normalization · → R3, data-model boundary-inference · dep: T033
- [ ] **T035** `_load_node_data_views(gmsh_file)`: pick up `"bathymetry"`, sign-flip to internal positive-up, ignore other views · → FR-016 · dep: T031, T032
- [ ] **T036** Wire `read_msh(path)` end-to-end: open, dispatch by version, project to `Mesh` · dep: T030-T035 · convert T025 stubs to passing
- [ ] **T037** Z-flatness check: raise `GmshParseError` if `|z| ≥ 1e-12` · → FR-010, R5 · part of T036 implementation
- [ ] **T038** Higher-order element check: raise `GmshParseError` for element types ∉ {1, 2} · → FR-011 · part of T036 implementation
- [ ] **T039** Missing-physical-groups fallback: emit `UserWarning`, return single `MAINLAND` ring · → FR-012 · part of T036 implementation

## Phase 4 — Writer implementation (`admesh/gmsh.py`)

- [ ] **T040** Skeleton: `write_msh(mesh, path, *, version="4.1")` dispatching to v2.2 / v4.1 emitters · → FR-002 · dep: T036
- [ ] **T041** `_emit_v22(mesh, fh)`: header, `$PhysicalNames`, `$Nodes`, `$Elements` (triangles + boundary lines) · → FR-002, FR-006 (1-based on emit) · dep: T040
- [ ] **T042** `_emit_v41(mesh, fh)`: header, `$PhysicalNames`, `$Entities`, `$Nodes`, `$Elements` · → FR-002 · dep: T040
- [ ] **T043** Bathymetry `$NodeData` emission · → FR-015, FR-007 (sign flip on emit) · dep: T041, T042
- [ ] **T044** Multiply-connected emission: holes get `ISLAND` tag and CW orientation · → data-model boundary-emission · dep: T043
- [ ] **T045** Wire `Mesh.to_msh(path, *, version="4.1")` method on `admesh/api.py::Mesh` · → FR-003 · dep: T040
- [ ] **T046** Convert T026 + T027 stubs to passing tests · dep: T044, T045

## Phase 5 — API wiring & packaging

- [ ] **T050** Re-export `read_msh`, `write_msh`, `GmshParseError`, `PHYSICAL_GROUP_MAP` from `admesh/__init__.py` · → FR-017 · dep: T036, T045
- [ ] **T051** Reserve empty `[gmsh]` extra in `pyproject.toml` (forward-compat namespace per R9) · → FR-005, SC-004
- [ ] **T052** Add `gmsh -check` validation gate to `tests/test_gmsh_write.py` (xfail when `gmsh` CLI absent) · → SC-002, R4 · dep: T046

## Phase 6 — Documentation

- [ ] **T060** Add `Gmsh I/O` subsection to `docs/PORTING_NOTES.md` covering: version policy, physical-group convention, z-flatness rule, bathymetry view, fallback behavior, known divergences from upstream Gmsh writers · → FR-018
- [ ] **T061** Add CHANGELOG entry under `[Unreleased]` for `Add Gmsh ASCII v2.2/v4.1 read/write support`

## Phase 7 — Validation

- [ ] **T070** Run full test suite; assert ≥308 + ≥15 = ≥323 tests pass · → SC-007, SC-006
- [ ] **T071** Run `python -c "import admesh"` in a venv with `gmsh` PyPI package uninstalled and assert success · → SC-004
- [ ] **T072** Run round-trip predicate on each MVP domain × each version combination · → FR-013, FR-014, SC-003
- [ ] **T073** Confirm hand-rolled parser ≤500 SLOC via `cloc admesh/gmsh.py` · → SC-005

## Phase 8 — Constitution amendment (post-implementation)

- [ ] **T080** PATCH amendment to `.specify/memory/constitution.md` removing Gmsh from the "deferred I/O formats" list (parallel to spec 001's fort.14 lift) · → plan.md "Constitution Check"

## Dependency Graph (Mermaid-style summary)

```
Phase 0 (T001-T007) ─┐
                     ├─→ Phase 1 (T010-T012) ──→ Phase 2 (T020-T027) ──┐
                     │                                                  │
                     │                                                  ▼
                     │                                              Phase 3 (T030-T039)
                     │                                                  │
                     │                                                  ▼
                     │                                              Phase 4 (T040-T046)
                     │                                                  │
                     │                                                  ▼
                     │                                              Phase 5 (T050-T052)
                     │                                                  │
                     │                                                  ▼
                     │                                              Phase 6 (T060-T061)
                     │                                                  │
                     │                                                  ▼
                     │                                              Phase 7 (T070-T073)
                     │                                                  │
                     │                                                  ▼
                     └────────────────────────────────────────────→  Phase 8 (T080)
```

## Cross-Repo Integration Points

- **MADMESHR / CHILMESH**: No direct integration. Both consume fort.14, which is unaffected by this feature. Round-trip parity (FR-013) ensures Gmsh-authored meshes routed *through* admesh and out to fort.14 remain valid for downstream consumers.
- **ADMESH-Domains**: No coupling. `Domain` builders are unchanged. Domain definitions can optionally be sourced from Gmsh `.geo` scripts (`tests/fixtures/gmsh/geo/`), but this is a fixture-generation convenience, not an API surface.
- **DomI**: No coupling.

## Token Budget

**MEDIUM**. Single new spec dir, single new module (≤500 SLOC), ≤15 new tests, two doc updates. Decomposable below the spec/plan/tasks granularity only by user-story (P1 read, P1 write, P2 round-trip) — and even that decomposition is sequential since round-trip depends on read+write. Not a candidate for breaking into separate issues.
