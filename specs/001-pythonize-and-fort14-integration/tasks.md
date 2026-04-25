---

description: "Tasks for: Pythonic API Layer + fort.14 I/O + chilmesh Integration"

---

# Tasks: Pythonic API Layer + fort.14 I/O + chilmesh Integration

**Input**: Design documents from `specs/001-pythonize-and-fort14-integration/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/python-api.md](contracts/python-api.md), [quickstart.md](quickstart.md)

**Tests**: Tests are MANDATORY for this feature. Constitution Principle III ("Reference-Test Discipline") is NON-NEGOTIABLE — every public symbol added by this feature requires test coverage. Round-trip and corpus tests are explicitly required by SC-002, SC-005, and SC-007.

**Organization**: Tasks are grouped by user story (US1 = P1 end-to-end pipeline; US2 = P2 chilmesh round-trip; US3 = P3 power-user custom size-field) so each story can be implemented and validated independently.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: User story this task serves — `[US1]`, `[US2]`, or `[US3]`
- File paths are absolute or repo-relative. Existing files are noted explicitly.

## Path Conventions

Single-project Python library, repo root = `/Users/domattioli/Projects/ADMESH/`. New library code lives under `admesh/`; new tests under `tests/`; new fixtures under `tests/fixtures/fort14/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Wire up the optional matplotlib extra and the test-fixture directory layout. No production code yet.

- [X] T001 Add `viz` optional extra to `pyproject.toml` `[project.optional-dependencies]` table: `viz = ["matplotlib>=3.7"]`. Bump `version` to `0.1.0` to mark the v1 development line.
- [X] T002 [P] Create the fort.14 fixture directory tree: `tests/fixtures/fort14/adcirc_examples/`, `tests/fixtures/fort14/community/`, `tests/fixtures/fort14/malformed/`, each with a placeholder `.gitkeep`.
- [X] T003 [P] Add `tests/fixtures/fort14/README.md` describing the three subdirectories, expected file count per directory (≥2 / ≥3 / ≥10), and the rules for adding new fixtures (size limit <2 MB combined, plain-text fort.14 only).

**Checkpoint**: Project metadata reflects v1 development; fixture layout is in place.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared types every user story depends on — `BoundaryType`, `BoundarySegment`, `Mesh`, `Domain`. Without these, none of the per-story tasks can compile.

**⚠️ CRITICAL**: No user-story work may begin until this phase is complete.

- [X] T004 Create `admesh/boundary_types.py` with `BoundaryType(IntEnum)` containing members `OPEN=0`, `MAINLAND=1`, `ISLAND=11`, `MAINLAND_FLUX=20`. Add `WALL` as a deliberate alias of `MAINLAND` (same int value) for backward compatibility with existing usage. Module docstring cites `data-model.md` and FR-022.
- [X] T005 [P] Add `tests/test_boundary_types.py` covering: each enum member has the documented int value; `BoundaryType.OPEN == 0` is True (IntEnum semantics); `WALL` and `MAINLAND` compare equal; iterating the enum yields the four canonical members (alias not duplicated).
- [X] T006 Create `admesh/api.py` with `BoundarySegment`, `Mesh`, and `Domain` frozen dataclasses per `data-model.md`. Include `Mesh.n_nodes`, `Mesh.n_elements`, `Mesh.n_boundaries` properties. Methods `to_fort14`, `plot`, `equals`, `__repr__`, `__str__` declared with `NotImplementedError` placeholders that the per-story tasks will fill in. No imports from `admesh/fort14.py` or `admesh/viz.py` yet (those are wired lazily later).
- [X] T007 [P] Add `tests/test_api_dataclass_shapes.py` covering: `Mesh` and `Domain` are `frozen` (assignment to a field raises `dataclasses.FrozenInstanceError`); `BoundarySegment` rejects out-of-range `node_ids` with a clear assertion in `__post_init__`; the `n_nodes` / `n_elements` / `n_boundaries` properties return the array shapes correctly.
- [X] T008 Update `admesh/__init__.py` to re-export the foundational symbols listed in `contracts/python-api.md` *that exist after Phase 2*: `Mesh`, `Domain`, `BoundarySegment`, `BoundaryType`. Leave the rest commented out with TODO references to the task IDs that will land them.
- [X] T009 [P] Add `tests/test_public_api_imports.py` asserting `from admesh import Mesh, Domain, BoundarySegment, BoundaryType` succeeds, and that `admesh.__all__` matches the expected v1 surface (subset for now — extended in later phases).

**Checkpoint**: Foundation in place — every user story can now begin in parallel.

---

## Phase 3: User Story 1 — End-to-End Pipeline: Domain → Mesh → fort.14 (Priority: P1) 🎯 MVP

**Goal**: A new user can go from a domain description to a `fort.14` file in three lines: `domain_from_polygon(...)` → `triangulate(domain)` → `mesh.to_fort14(path)`. Round-trip via `read_fort14` is lossless on the five canonical MVP domains.

**Independent Test**: Run the quickstart's three-line happy path on each MVP domain (unit_square, l_shape, unit_disk, annulus, notched_rectangle), serialize to `fort.14`, read back via `read_fort14`, and assert `mesh.equals(roundtripped)` succeeds. SC-001, SC-002, SC-005, and SC-007 should all pass at the end of this phase.

### Tests for User Story 1 (write FIRST, ensure they FAIL before implementation)

- [ ] T010 [P] [US1] `tests/test_api_triangulate.py` — assert `admesh.triangulate(domain)` on each of the 5 MVP domains returns a `Mesh` whose `min_q ≥ 0.30, mean_q ≥ 0.60` (matching the existing constitutional gate) and whose `boundaries` contains at least one segment with `bc_type == BoundaryType.OPEN` or `BoundaryType.MAINLAND` as appropriate to the domain.
- [ ] T011 [P] [US1] `tests/test_api_repr.py` — assert `repr(mesh)` includes `n_nodes=`, `n_elements=`, `min_q=`, `mean_q=`; assert `str(mesh)` includes a per-segment breakdown line for each boundary segment with its `BoundaryType` name (or numeric code if unmapped).
- [ ] T012 [P] [US1] `tests/test_api_equals.py` — assert `mesh.equals(mesh)` is True; assert a coordinate perturbation of `2 * atol` in any node trips the comparison; assert connectivity differences (any element row reordered) trip even at high tolerance; assert bathymetry-tolerance handling.
- [ ] T013 [P] [US1] `tests/test_api_domain_builders.py` — `domain_from_polygon` accepts a list of `(M,2)` rings and produces a `Domain` whose SDF is negative inside the outer ring and positive outside; `domain_from_sdf` accepts a callable + bbox and round-trips them as fields.
- [ ] T014 [P] [US1] `tests/test_fort14_roundtrip.py` — for each of the 5 MVP domains, build a mesh via `triangulate`, write to a temp file with `mesh.to_fort14`, read back with `read_fort14`, assert `mesh.equals(roundtripped, atol=1e-6)`. Connectivity (`elements`, BC labels per segment) compared exactly. SC-002.
- [ ] T015 [P] [US1] `tests/test_fort14_reader_errors.py` — load each fixture in `tests/fixtures/fort14/malformed/` and assert `read_fort14` raises `Fort14ParseError` with `.line_no`, `.expected`, `.actual` populated. Parametrize across at least 10 categories. SC-007.
- [ ] T016 [P] [US1] `tests/test_fort14_reference_corpus.py` — load every file under `tests/fixtures/fort14/adcirc_examples/` and `tests/fixtures/fort14/community/`, assert `read_fort14` succeeds and the returned `Mesh` round-trips. SC-005.
- [ ] T017 [P] [US1] `tests/test_fort14_index_and_sign_conventions.py` — assert the writer emits 1-based node IDs in the element block; assert the writer emits depth (positive-down) when given an internal `Mesh.bathymetry` of elevation (positive-up); assert the reader inverts both conventions.
- [ ] T018 [P] [US1] `tests/test_viz.py` — when matplotlib is installed: `mesh.plot()` returns a non-None Axes object and adds artists to it; when matplotlib is *not* installed (use `monkeypatch` to remove `matplotlib` from `sys.modules` and shadow imports): `mesh.plot()` raises `ImportError` whose message contains the substring `admesh2D[viz]`. FR-020/FR-021.
- [ ] T019 [P] [US1] `tests/test_backward_compat_full_suite.py` — meta-test: run the existing 142-test suite via `pytest --collect-only -q` and assert exit code 0 and the count of collected tests is `≥ 142` (will grow with new tests; the `≥` guards against accidental removal). FR-018, SC-003.

### Implementation for User Story 1

- [ ] T020 [US1] In `admesh/api.py`: implement `domain_from_polygon(rings, *, pfix=None, bc_segments=())` and `domain_from_sdf(sdf, bbox, *, pfix=None, pts=None, bc_segments=())`. Use Shapely for polygon-to-SDF; bbox is computed from ring extents.
- [ ] T021 [US1] In `admesh/api.py`: implement `triangulate(domain, *, h_max=None, h_min=None, size_field=None, user_contribs=(), combine=np.minimum.reduce, seed=None, max_iter=None, quality_gate=(0.30, 0.60)) -> Mesh`. The implementation calls into the existing `admesh.routine` faithful-port driver — *no* changes to faithful-port code; the new function adapts inputs/outputs only. Quality gate enforcement raises `ValueError` if not met.
- [ ] T022 [US1] In `admesh/api.py`: implement `Mesh.__repr__` (single-line summary), `Mesh.__str__` (multi-line breakdown with per-segment `BoundaryType` lines), and `Mesh.equals(other, *, atol=1e-10, rtol=0.0)` per the contract.
- [ ] T023 [P] [US1] Create `admesh/fort14.py` with `Fort14ParseError(ValueError)` (carries `line_no: int`, `expected: str`, `actual: str`); the v55-grammar parser `read_fort14(path) -> Mesh` (single-pass, line-oriented, raises on first error); and `write_fort14(mesh, path) -> None` (deterministic emit, 6-decimal coordinate default). Apply 1-based↔0-based conversion and elevation↔depth sign flip strictly inside this module (research.md decisions §4 and §5).
- [ ] T024 [US1] In `admesh/api.py`: wire `Mesh.to_fort14(path)` to call `admesh.fort14.write_fort14(self, path)`. Lazy import — no top-level import of `fort14` from `api.py` (avoids cycles if fort14 ever needs `Mesh`).
- [ ] T025 [US1] Author the malformed-input fixture corpus under `tests/fixtures/fort14/malformed/` (≥10 files): `missing_header.14`, `wrong_node_count.14`, `non_monotonic_node_ids.14`, `non_numeric_coordinate.14`, `negative_node_count.14`, `truncated_element_block.14`, `missing_open_boundary.14`, `wrong_segment_node_count.14`, `extra_garbage_at_eof.14`, `unicode_in_node_id.14`. Each ≤200 lines; total directory <100 KB.
- [ ] T026 [US1] Curate `tests/fixtures/fort14/adcirc_examples/`: at least 2 files. Acquire from the ADCIRC documentation example set (e.g. Shinnecock Inlet — a small, public-domain mesh). Include source-attribution comments in `tests/fixtures/fort14/README.md`. Each file's full path documented; size budget ≤500 KB combined.
- [ ] T027 [US1] Curate `tests/fixtures/fort14/community/`: at least 3 real-world meshes from public ADCIRC sources. If a full mesh exceeds the size budget, capture a header + first-100-nodes + first-100-elements + boundary-block excerpt that still round-trips structurally. Document provenance in `tests/fixtures/fort14/README.md`.
- [ ] T028 [P] [US1] Create `admesh/viz.py` with the implementation of `Mesh.plot(ax=None, **kwargs)`. Lazy `import matplotlib.pyplot as plt` inside the method body. On `ImportError`, raise a fresh `ImportError("matplotlib is required for mesh.plot(). Install with: pip install admesh2D[viz]")`. Wire `Mesh.plot` in `admesh/api.py` to call this helper.
- [ ] T029 [US1] Update `admesh/__init__.py` to re-export the now-implemented US1 surface: `triangulate`, `domain_from_polygon`, `domain_from_sdf`, `read_fort14`, `write_fort14`, `Fort14ParseError`. Update `__all__` accordingly. Remove the corresponding TODO comments from T008.

**Checkpoint**: User Story 1 is fully functional. The MVP can ship at the end of this phase: the quickstart 3-line happy path runs end-to-end on all 5 canonical domains, fort.14 round-trips losslessly, and the existing 142-test faithful-port suite continues to pass.

---

## Phase 4: User Story 2 — chilmesh Round-Trip (Priority: P2)

**Goal**: A chilmesh user can load an admesh2D-produced fort.14 file and see the same boundary segments, BC labels, and connectivity that admesh2D produced. The integration is exercised end-to-end without admesh2D taking a chilmesh dependency.

**Independent Test**: Produce a mesh containing each of `OPEN`, `MAINLAND`, `ISLAND`, `MAINLAND_FLUX`, plus at least one numeric (unmapped) BC code; write to fort.14; load via the spec's recommended path (chilmesh's existing `from_fort14` if available locally, else the admesh2D round-trip as a proxy); verify segment counts, per-segment BC code, per-segment node ordering, and total node/element counts all match.

### Tests for User Story 2

- [ ] T030 [P] [US2] `tests/test_fort14_chilmesh_compat.py` — construct a synthetic `Mesh` with a hand-crafted boundary list mixing `OPEN`, `MAINLAND`, `ISLAND`, `MAINLAND_FLUX`, and a numeric code (`bc_type=22`, an external-barrier code). Round-trip via fort.14 and assert: same segment count; same `bc_type` per segment (named codes preserve enum identity, numeric codes preserve int identity); same `node_ids` array per segment.
- [ ] T031 [P] [US2] `tests/test_fort14_chilmesh_compat.py` — verify the open vs land block placement: every segment with `bc_type == BoundaryType.OPEN` lands in the open-boundary block; every segment with any other code lands in the land-boundary block; numeric `bc_type` follows the segment's `is_open` flag.
- [ ] T032 [P] [US2] `tests/test_fort14_chilmesh_compat.py` — verify multiply-connected domain handling: build an annulus mesh (outer ring `OPEN`, inner ring `MAINLAND`); round-trip; assert each ring stays a separate segment with its own `bc_type`. Edge case from spec.
- [ ] T033 [P] [US2] `tests/test_fort14_chilmesh_compat.py` (or a new `tests/test_fort14_chilmesh_smoke.py`) — gated by `pytest.importorskip("chilmesh")`, exercise `chilmesh.ChilMesh.from_fort14("output.14")` on an admesh2D-produced file and confirm chilmesh's reported segment counts and node groupings match. Skipped cleanly when chilmesh is not installed in the dev env.

### Implementation for User Story 2

US2's implementation is largely covered by US1's `fort14.py` correctness. The remaining work is documentation and a worked round-trip example.

- [ ] T034 [US2] Add a `## chilmesh integration` H2 section to `quickstart.md` (already present from `/speckit-plan`; verify content matches the recommended Option A path and includes the `io.StringIO` in-process example).
- [ ] T035 [US2] Add a runnable script `scripts/chilmesh_roundtrip_demo.py` that produces an annulus mesh, writes to `fort.14`, and prints what chilmesh would see (segment-by-segment summary). Used in docs as a copy-modify starting point. Skipped from CI; the corresponding test (T033) covers verification.

**Checkpoint**: User Stories 1 AND 2 work independently. A user can pipe ADMESH output into a chilmesh-based workflow without writing a custom translator.

---

## Phase 5: User Story 3 — Power User: Custom Size-Field Contributions (Priority: P3)

**Goal**: An advanced user supplies a `(N, 2) -> (N,)` callable, passes it via `triangulate(..., user_contribs=[my_fn])`, and observes the resulting mesh refined according to their contribution. The Phase-1 built-in `min`-stack remains numerically identical to MATLAB.

**Independent Test**: For a fixed domain, run `triangulate(domain)` (no user contributions) and `triangulate(domain, user_contribs=[fn])` where `fn` returns a smaller size in a known sub-region. Assert: (a) without contributions, the output matches the existing MATLAB-faithful behavior bit-for-bit; (b) with a refining contribution, mean element size in the targeted sub-region is strictly smaller than without; (c) connectivity outside the sub-region is unchanged within numerical tolerance.

### Tests for User Story 3

- [ ] T036 [P] [US3] `tests/test_size_field_composition.py` — Phase-1 isolation: run `compose_size_field(builtins=[curvature_fn, medial_fn], user_contribs=[])` and verify the result matches the existing faithful-port `mesh_size_function` output exactly (`atol=1e-12`). Constitution Principle I.
- [ ] T037 [P] [US3] `tests/test_size_field_composition.py` — Phase-2 default combiner: `compose_size_field(builtins, user_contribs=[fn], combine=np.minimum.reduce)` returns elementwise `min` of the Phase-1 result and `fn`. Verify on a small synthetic point set.
- [ ] T038 [P] [US3] `tests/test_size_field_composition.py` — Phase-2 custom combiner: pass `combine=np.maximum.reduce`; verify the result is elementwise `max` between Phase-1 and the user contribution; verify the Phase-1 result itself is unchanged (i.e., the custom combiner does NOT leak into Phase-1).
- [ ] T039 [P] [US3] `tests/test_size_field_composition.py` — invalid user values: contribution returns NaN at some points and negative values at others. Verify the pipeline clamps to `[hmin, hmax]` and emits a `UserWarning` whose message names the contribution and the affected count. FR-005 + Story 3 AS-2.
- [ ] T040 [P] [US3] `tests/test_api_triangulate_user_contribs.py` — end-to-end: triangulate a unit-disk domain with a contribution that halves the size in a small disc; assert (a) min_q ≥ 0.30 still holds; (b) the mean inradius of elements whose centroid lies in the targeted region is strictly less than the mean inradius outside.

### Implementation for User Story 3

- [ ] T041 [US3] Create `admesh/size_field.py` with `SizeFieldFn` type alias and `compose_size_field(builtins, user_contribs=(), combine=np.minimum.reduce)` per `data-model.md` and the contract. Phase-1 always uses `np.minimum.reduce` regardless of `combine`. Inputs validated; output is a closure with stable signature `(N, 2) -> (N,)`.
- [ ] T042 [US3] In `admesh/size_field.py`: implement clamping/warning behavior — invalid contribution values (NaN, ≤0, > `hmax`) clamped to `[hmin, hmax]` and emit `warnings.warn(...)` with affected count and contribution `__qualname__`.
- [ ] T043 [US3] In `admesh/api.py`: wire `user_contribs` and `combine` kwargs of `triangulate()` through to `compose_size_field`. When the caller passes a pre-composed `size_field=`, ignore `user_contribs`/`combine` (they're already represented in the user's composition) and emit a `UserWarning` if both are given.
- [ ] T044 [US3] Update `admesh/__init__.py` to re-export `compose_size_field` and `SizeFieldFn`. Update `__all__`.
- [ ] T045 [US3] Add a runnable example `scripts/size_field_extension_demo.py` mirroring quickstart.md's wave-breaker example. Renders a before/after pair under `tests/output/` for manual inspection.

**Checkpoint**: All three user stories work independently and compose without breaking each other.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate cross-cutting acceptance, update docs, and propose the constitution amendment that lifts the deferred-list scope changes.

- [ ] T046 Run the full test suite (`pytest tests/ -q`) and verify: (a) all previously-existing 142 tests still pass with zero modifications to their files; (b) every new test from T005, T007, T009–T019, T030–T033, T036–T040 passes; (c) total collected tests ≥ 200.
- [ ] T047 [P] Run `quickstart.md`'s three-line happy path manually on each of the 5 MVP domains. Capture output, paste into `tests/output/quickstart_validation.txt`, commit as evidence. SC-001.
- [ ] T048 [P] Update `docs/PORTING_NOTES.md` with one-line entries for any non-obvious substitutions introduced (Shapely-based SDF in `domain_from_polygon`, lazy matplotlib import). Add a paragraph under a new `## v1 Pythonic layer (2026-04-XX)` heading recording that the layer is strictly additive over the faithful-port surface.
- [ ] T049 [P] Update `PROJECT_PLAN.md` "Where we are today" with v1 milestone status (Pythonic layer + fort.14 + chilmesh-export). Cross-link to this task list.
- [ ] T050 [P] Draft a PATCH amendment to `.specify/memory/constitution.md`: remove `ADCIRC .fort.14 I/O` from the "Out-of-scope (explicitly deferred)" list (line 259); reword the visualization line to `GUI / visualization beyond the mesh.plot() matplotlib helper`. Bump version to 1.0.1; append an Amendments-log entry citing this feature.
- [ ] T051 Bump `pyproject.toml` `version` to `0.1.0` (if not already done in T001) and update `README.md` install snippet to remove the "in progress" callout from the Quickstart once T046 passes.
- [ ] T052 Run `.venv/bin/python -m build` to verify the wheel still builds cleanly under the new module list. Smoke-test: `pip install --force-reinstall dist/admesh2D-0.1.0-*.whl` in a fresh venv, then `python -c "import admesh; m = admesh.triangulate(admesh.domain_from_polygon([np.array([[0,0],[1,0],[1,1],[0,1]])])); m.to_fort14('/tmp/smoke.14')"`.

**Final checkpoint**: v1 is releasable. All success criteria SC-001 through SC-007 are met; FR-001 through FR-022 are implemented and tested; the faithful-port surface is unchanged.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no dependencies — start immediately.
- **Phase 2 (Foundational)**: requires Phase 1. Blocks every user story.
- **Phase 3 (US1)**: requires Phase 2. Delivers the MVP.
- **Phase 4 (US2)**: requires Phase 2. Largely validates Phase 3's fort.14 work; can run in parallel with US3.
- **Phase 5 (US3)**: requires Phase 2. Independent of US2.
- **Phase 6 (Polish)**: requires all phases above.

### User Story Dependencies

- **US1 (P1)**: depends only on Foundational. **MVP ships at end of US1.**
- **US2 (P2)**: depends on Foundational AND on `fort14.py` from US1 (T023). Can begin in parallel with US3 once T023 is complete.
- **US3 (P3)**: depends only on Foundational. Can begin in parallel with US1's later tasks (T028 onward) and with US2.

### Within Each User Story

- All `[P]`-marked test tasks are independent — write them first, ensure they fail, then implement.
- Implementation tasks that touch the same file are NOT parallel: T020/T021/T022/T024 all touch `admesh/api.py` and run sequentially. T023 (`admesh/fort14.py`) and T028 (`admesh/viz.py`) are file-disjoint from `api.py` and from each other — those CAN run in parallel with the `api.py` work.
- Story 3 implementation: T041/T042 (size_field.py) → T043 (api.py wiring) → T044 (__init__.py) → T045 (demo script).

---

## Parallel Execution Examples

### Phase 2 Foundational — parallel batches

```text
After T004 (boundary_types.py) lands:
  - T005 [P] tests/test_boundary_types.py
  - T006   admesh/api.py (sequential — depends on T004 import)

After T006 (api.py dataclasses) lands:
  - T007 [P] tests/test_api_dataclass_shapes.py
  - T008   admesh/__init__.py (sequential — depends on T006)
  - T009 [P] tests/test_public_api_imports.py (after T008)
```

### Phase 3 US1 — tests in one batch, implementation in another

```text
Batch A (all tests, parallel — write first, expect failure):
  - T010 [P] [US1] tests/test_api_triangulate.py
  - T011 [P] [US1] tests/test_api_repr.py
  - T012 [P] [US1] tests/test_api_equals.py
  - T013 [P] [US1] tests/test_api_domain_builders.py
  - T014 [P] [US1] tests/test_fort14_roundtrip.py
  - T015 [P] [US1] tests/test_fort14_reader_errors.py
  - T016 [P] [US1] tests/test_fort14_reference_corpus.py
  - T017 [P] [US1] tests/test_fort14_index_and_sign_conventions.py
  - T018 [P] [US1] tests/test_viz.py
  - T019 [P] [US1] tests/test_backward_compat_full_suite.py

Batch B (parallel — file-disjoint implementation):
  - T023 [P] [US1] admesh/fort14.py
  - T028 [P] [US1] admesh/viz.py

Batch C (sequential — same file):
  - T020 → T021 → T022 → T024  (all in admesh/api.py)
  - T025, T026, T027 (fixture curation; can run alongside Batch C)
```

### Phase 4+5 in parallel (different developers)

After T023 (US1's fort14.py) lands:

```text
Developer A: US2 tasks T030–T035
Developer B: US3 tasks T036–T045
```

---

## Implementation Strategy

### MVP (US1 only)

1. Phase 1 + Phase 2 (small, fast).
2. Phase 3 (US1) — full triangulate() + fort.14 + viz.
3. Run T046 polish task; if green, **ship `admesh2D` 0.1.0 with quickstart.md as the user-facing doc**.
4. STOP and validate: 5 MVP domains round-trip via fort.14; existing 142 tests still green; matplotlib-optional import works.

### Incremental delivery

1. MVP (US1) → release as 0.1.0.
2. Add US2 → release as 0.2.0 (chilmesh round-trip explicitly tested; smoke test against chilmesh if available).
3. Add US3 → release as 0.3.0 (power-user composition).
4. Polish phase amendments → 0.3.1.

### Parallel team

- One dev: foundation → US1 → US2 → US3 → polish (≈ linear).
- Two devs after Phase 2: A on US1 → US2; B on US3 from start. Polish co-owned.

---

## Notes

- `[P]` ⇒ different files, no incomplete dependencies.
- Every new module under `admesh/` is *strictly additive*; no edit of the 13 faithful-port stage modules is permitted by this task list (Constitution Principle I + FR-008/FR-018/FR-019).
- Tests are mandatory per Constitution Principle III. Verify each test FAILS against an empty implementation before writing the implementation (TDD discipline).
- Commit cadence: at least one commit per task; squash-merge optional at phase boundaries.
- Stop at any checkpoint to validate independently — each user story's checkpoint is a deployable increment.
