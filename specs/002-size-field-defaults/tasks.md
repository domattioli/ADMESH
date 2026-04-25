---
description: "Task list for spec-002: default size-field stack + 0.1.0 release readiness"
---

# Tasks: Default Size-Field Stack & 0.1.0 Release Readiness

**Input**: Design documents from `/specs/002-size-field-defaults/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Required — the spec mandates a structural-validity regression test (FR-014, FR-016) as the 0.1.0 release gate. Test tasks are first-class implementation deliverables, not optional polish.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently. US4 (release readiness) runs in parallel with US1's code work.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User-story label (US1, US2, US3, US4); omitted for Setup/Foundational/Polish phases
- File paths are absolute-style relative to repo root

## Path Conventions

Single-package Python library, flat layout under `admesh/`. Tests live under `tests/`. Specs live under `specs/`. No `src/` indirection.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify the working tree is in a known-good state before extending it.

- [X] T001 Verify branch state, existing test baseline, and editable-install: confirm `git branch --show-current` is `002-size-field-defaults`, run `pytest tests/ -q` and confirm all 142 spec-001 tests pass, confirm `pip install -e ".[dev]"` is satisfied (no missing deps)
  - **Result**: branch confirmed `002-size-field-defaults`; baseline `pytest tests/ -q` → **237 passed, 8 skipped, 1 failed**. The single failure is `test_reference_fort14_round_trips[wetting_and_drying_test.14]` — the spec-001 reader cannot parse IBTYPE 3/24 records, which is the documented gap that T011–T013 will close. Treated as the regression target, not a regression.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Extend the entity dataclasses (Domain, BoundarySegment, BoundaryType) that every user story depends on. All 5 tasks here MUST land before any US1/US2/US3 implementation begins.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

- [X] T002 Extend `Domain` dataclass in `admesh/api.py` per `data-model.md`: add optional fields `bathymetry: Callable[[NDArray, NDArray], NDArray] | None = None` and `tide_period: float | None = None`; add `__post_init__`-style validation (`tide_period > 0` when not `None`); confirm existing `Domain(fd=, bbox=)` constructions still work; update `Domain.__repr__` if it exists to surface the new fields when set
- [X] T003 Extend `BoundarySegment` dataclass in `admesh/api.py` per `data-model.md`: add optional fields `paired_node_ids: NDArray[np.int64] | None = None` and `barrier_data: NDArray[np.float64] | None = None`; add validation that `len(paired_node_ids) == len(node_ids)` when not `None` and that `barrier_data.shape[0] == len(node_ids)` when not `None`; update `Mesh.equals(...)` to compare `paired_node_ids` (exact int) and `barrier_data` (`atol`/`rtol`-aware)
- [X] T004 [P] Extend `BoundaryType` enum in `admesh/boundary_types.py`: add four members `EXTERNAL_BARRIER = 3`, `EXTERNAL_BARRIER_FLUX = 4`, `INTERNAL_BARRIER_PIPE = 13`, `INTERNAL_BARRIER = 24`; preserve existing values (0, 1, 11, 20) and the `WALL = 1` alias; update the docstring's "Members" list
- [X] T005 [P] Update `admesh/__init__.py` public re-exports: confirm `BoundaryType` re-export covers the four new members (no code change needed if re-export is the enum class itself); add `Domain.from_mesh` to documented public surface in module docstring
- [X] T006 Extend `domain_from_polygon` and `domain_from_sdf` in `admesh/api.py` to accept the new `bathymetry=` and `tide_period=` kwargs (default `None`), passing them through to the `Domain(...)` constructor

**Checkpoint**: All Phase-2 tasks complete; `pytest tests/ -q` still green; entity dataclasses ready for US1/US2/US3 to consume.

---

## Phase 3: User Story 1 — Default feature-aware mesh from any 2D shallow-water domain (Priority: P1) 🎯 MVP

**Goal**: `admesh.triangulate(domain)` with no size-field arguments produces a feature-aware mesh (curvature + medial-axis always-on; bathymetry + tide opt-in via `Domain` fields). Structural validity verified across the test ladder (Tier 0 → Tier 1 → Tier 2).

**Independent Test**: For each fixture in `tests/test_default_size_field.py`, calling `admesh.triangulate(domain)` returns a `Mesh` that passes `assert_structurally_valid(mesh, domain)` per `contracts/python-api-default-stack.md`.

### Implementation for User Story 1

- [X] T007 [US1] Add `Domain.from_mesh(cls, mesh, *, tide_period=None, bbox_pad=0.0)` classmethod in `admesh/api.py` per `contracts/python-api-default-stack.md`: walk `mesh.boundaries` to recover ring polygons (re-use spec-001's `_derive_boundary_segments` helper in reverse), build `LinearNDInterpolator` over `(mesh.nodes, mesh.bathymetry)` if `mesh.bathymetry is not None`, return a `Domain` with all fields populated; raise `ValueError` if mesh has zero boundary segments
- [X] T008 [US1] Add private `_build_default_size_field(domain, *, h_min, h_max, h_target, enable_curvature, enable_medial_axis, default_depth, tide_elements_per_wavelength) -> Callable` helper in `admesh/api.py` per `data-model.md`'s mapping table: maps public kwargs to `admesh.mesh_size.build_h(...)` parameters; handles the constant-`default_depth` fallback path with `UserWarning` when `tide_period` set without `bathymetry`; short-circuits to uniform-`h` callable when `h_max/h_min < 2` or all stages disabled
- [X] T009 [US1] Wire `admesh.triangulate(...)` in `admesh/api.py` to call `_build_default_size_field(domain, ...)` when neither `size_field=` nor `user_contribs=` is supplied; preserve all spec-001 behaviour for the other branches (size_field= bypasses default, user_contribs= composes on top via existing Phase-2 combiner, both supplied warns and ignores user_contribs)
- [X] T010 [US1] Add new keyword arguments to `admesh.triangulate(...)` signature in `admesh/api.py`: `h_target: float | None = None`, `enable_curvature: bool = True`, `enable_medial_axis: bool = True`, `default_depth: float = 1.0`, `tide_elements_per_wavelength: float = 100.0`; document each in the docstring with the public-knob → MATLAB-internal mapping reference to `contracts/python-api-default-stack.md`
- [ ] T011 [US1] Extend fort.14 reader in `admesh/fort14.py` for IBTYPE 3 / 13 / 23 (single-node barrier with crest data + 2 coefficients): add `_SINGLE_NODE_BARRIER_IBTYPES = frozenset({3, 13, 23})` constant, branch `_read_land_segment` on IBTYPE, parse 4-token records `(node_id, hbar, coef_sub, coef_super)`, populate `BoundarySegment.barrier_data` as `(N, 3)` float64; preserve existing `Fort14ParseError` machinery for malformed records
- [ ] T012 [US1] Extend fort.14 reader in `admesh/fort14.py` for IBTYPE 4 / 14 / 24 / 25 (paired-node barrier records): add `_PAIRED_NODE_BARRIER_IBTYPES = frozenset({4, 14, 24, 25})` constant, parse 5-token records `(node_id, paired_id, hbar, coef_sub, coef_super)`, populate both `BoundarySegment.node_ids` AND `BoundarySegment.paired_node_ids` (1-based → 0-based for both) AND `BoundarySegment.barrier_data` as `(N, 3)` float64
- [ ] T013 [US1] Extend fort.14 writer in `admesh/fort14.py` to emit single-node and paired-node barrier records: when `BoundarySegment.barrier_data is None`, emit single-integer-per-line (existing path); when `barrier_data` set and `paired_node_ids is None`, emit `nid+1 hbar coef_sub coef_super` (single-node barrier); when both set, emit `nid+1 pid+1 hbar coef_sub coef_super` (paired); use `%.3f` float format for crest+coeffs to match the example10n fixture
- [ ] T014 [US1] Implement structural-validity helper `assert_structurally_valid(mesh, domain, *, tol=1e-9)` per `contracts/python-api-default-stack.md` in a new module `tests/_structural_validity.py` (private to test code): three asserts (positive signed area, boundary-edge preservation, full-domain coverage); plus internal helpers `_polygon_edges(polygons, tol)` and `_triangle_edges(elements)` for edge-set comparison
- [ ] T015 [US1] Tier 0 acceptance tests in `tests/test_default_size_field.py`: parametrized test that calls `admesh.triangulate(domain)` (no size-field args) on each of the 5 spec-001 MVP polygons (square, L-shape, U-shape, square-with-hole, doughnut) and runs `assert_structurally_valid` against each result
- [ ] T016 [US1] Tier 1 acceptance test in `tests/test_default_size_field.py`: load `tests/fixtures/fort14/adcirc_examples/wetting_and_drying_test.14` via `read_fort14`, build `Domain.from_mesh(src)`, call `triangulate(domain, h_min=10.0, h_max=200.0)`, assert structural validity AND assert input boundary segments (open + 9 land) are recovered with correct IBTYPE codes and `barrier_data` preserved within `atol=1e-3` after a fort.14 round-trip
- [ ] T017 [US1] Tier 2 acceptance test in `tests/test_default_size_field.py` (the release gate): load `tests/fixtures/fort14/adcirc_examples/wnat_test.14`, build `Domain.from_mesh(src)`, call `triangulate(domain, h_min=0.05, h_max=2.0)`, assert structural validity; the test MUST run in under 60 seconds wall-clock on a developer laptop (FR-016) and is marked release-gating in CI
- [ ] T018 [US1] Fort.14 paired-edge unit tests in `tests/test_fort14_paired.py`: five tests per `contracts/fort14-paired-edge.md` § "Fixture coverage" — `test_fort14_paired_round_trip[example10n]` (full round-trip on the Tier 1 fixture), `test_fort14_ibtype_3_external_weir` (synthetic single-segment IBTYPE 3 mesh, exact round-trip), `test_fort14_ibtype_24_internal_barrier` (synthetic IBTYPE 24, paired IDs preserved), `test_fort14_unknown_ibtype_falls_back` (IBTYPE 99 single-node, parses with `bc_type=int(99)`), `test_fort14_malformed_paired_record` (IBTYPE 24 with 3 tokens raises `Fort14ParseError`)
- [ ] T019 [US1] Update `docs/PORTING_NOTES.md` with a new entry for the spec-002 fort.14 paired-edge BC support: document the IBTYPE → token-count mapping table from `contracts/fort14-paired-edge.md`, note the unknown-IBTYPE fallback heuristic, and any deviation from ADCIRC v55 grammar that was deliberate

**Checkpoint**: User Story 1 complete. All structural-validity tests pass on Tier 0 + Tier 1 + Tier 2 fixtures. Fort.14 round-trip preserves `wetting_and_drying_test.14`'s 9 land segments with correct IBTYPE codes. The 0.1.0 release gate is functionally satisfied (modulo Tier 1.5 acquisition in US4).

---

## Phase 4: User Story 2 — Bathymetry-driven refinement when depth data is available (Priority: P2)

**Goal**: A user with bathymetric data calls `admesh.triangulate(domain, bathymetry=fn)` (or sets `Domain.bathymetry` directly) and the bathymetry stage activates automatically alongside curvature + medial-axis. Tide stage activates when `tide_period` is also set.

**Independent Test**: Synthetic test domain with a known sharp-ridge bathymetry — `admesh.triangulate(domain, bathymetry=ridge_fn)` produces a mesh with mean edge length within the ridge zone at least 30% smaller than mean edge length in the flat-bottom zone.

### Implementation for User Story 2

- [ ] T020 [P] [US2] Bathymetry-refinement test in `tests/test_default_size_field.py`: build a synthetic L-shape `Domain` with `bathymetry=lambda X, Y: 100.0 + 50.0 * np.exp(-(X - 1500.0)**2 / 200.0**2)` (ridge at x=1500); call `triangulate(domain)`; assert mean edge length in `|x - 1500| < 100` zone is at least 30% smaller than mean edge length in `|x - 1500| > 500` zone; also assert structural validity
- [ ] T021 [P] [US2] Bathymetry NaN-inpainting test in `tests/test_default_size_field.py`: bathymetry callable returns `np.nan` over part of the domain; assert `triangulate(domain, bathymetry=fn)` completes without error and produces a structurally-valid mesh (the NaN handling is delegated to `bathymetry.create_elevation_grid` which already calls `inpaint_nans`)
- [ ] T022 [US2] Tide-stage-with-default-depth-fallback test in `tests/test_default_size_field.py`: `Domain` with `tide_period=43200.0` but `bathymetry=None`; assert `triangulate(domain)` emits `UserWarning` matching pattern `"tide_period set but Domain.bathymetry is None"`; assert resulting mesh is structurally valid; assert overriding via `triangulate(domain, default_depth=10.0)` changes the mesh (different edge lengths in tide-influenced regions)

**Checkpoint**: User Story 2 complete. Bathymetry and tide stages activate from `Domain` fields; the constant-default-depth warning + override path works.

---

## Phase 5: User Story 4 — 0.1.0 release readiness (cleanup + walkbacks) (Priority: P2)

**Goal**: Repository is in a coherent shippable state for the 0.1.0 tag — constitution honest, README honest, no stray build artefacts, Tier 1.5 fixture acquired.

**Independent Test**: After this phase, `git status` shows zero untracked `dist/`, `build/`, or stale demo PNGs; constitution v1.0.2 amendment is in place; README install + quickstart restore "0.1.0 in progress" callouts; Tier 1.5 fixture round-trips cleanly.

**Note**: This phase runs in parallel with US1's code work (different files; independent verification).

### Implementation for User Story 4

- [ ] T023 [P] [US4] Walk back the constitution amendment in `.specify/memory/constitution.md`: append a v1.0.2 amendment to the Amendments log explicitly noting the size-field default as a precondition for the fort.14 contract being release-ready; update the version banner at the bottom of the file from `1.0.1` to `1.0.2`; preserve the v1.0.1 entry for transparency (per spec FR-017)
- [ ] T024 [P] [US4] Restore "0.1.0 in progress" callout in `README.md` install section (currently spec-001's polish removed it): add a brief note like "Spec 002 in progress — 0.1.0 will be the first PyPI tag of the new Pythonic API"; do NOT undo the ADCIRC compatibility tagline added earlier in this session
- [ ] T025 [P] [US4] Restore "API in progress" framing in `README.md` Quickstart section: add a short callout that `triangulate()` defaults are stabilizing across spec 002; preserve the 3-line idiom example
- [ ] T026 [P] [US4] Remove `papers/wnat_admesh.png` if present in the working tree: this is the rough WNAT render the user rejected; it was never committed. Log a single-line justification in the commit message
- [ ] T027 [P] [US4] Remove `dist/` and `build/` directories from the working tree if present (artefacts from spec-001's wheel smoke); add to `.gitignore` if not already covered (verify spec-001 left them ignored)
- [ ] T028 [P] [US4] Clean stale demo artefacts under `tests/output/`: enumerate files, delete those that are not regression baselines for the spec-002 acceptance tests; preserve `tests/output/quickstart_validation.txt` if it's still spec-001's reference output
- [ ] T029 [P] [US4] Acquire the Tier 1.5 Shinnecock Bay fixture per `research.md` Decision 6: download the ADCIRC official Example "Shinnecock Bay" fort.14 from `https://adcirc.org/home/documentation/example-problems/` (or equivalent canonical mirror at `adcirc/adcirc-cg` GitHub repo's `work/example/shinnecock/` directory); save to `tests/fixtures/fort14/adcirc_examples/shinnecock.14`; verify file size and AGRID identifier match the canonical source
- [ ] T030 [US4] Create `tests/fixtures/fort14/adcirc_examples/PROVENANCE.md` documenting source, license, mesh stats (NN, NE, BC IBTYPE coverage), and reason-for-inclusion for each fixture in the directory: `wnat_test.14`, `wetting_and_drying_test.14`, `shinnecock.14`
- [ ] T031 [US4] Tier 1.5 acceptance test in `tests/test_default_size_field.py`: load `shinnecock.14`, build `Domain.from_mesh(src)`, call `triangulate(domain, h_min=20.0, h_max=500.0)`, assert structural validity; depends on T029 + T030
- [ ] T032 [US4] Pre-tag verification script `scripts/pre_tag_check.sh` (or equivalent pytest hook): asserts FR-017 through FR-019 — constitution version is `>=1.0.2`, README has "0.1.0 in progress" callout, no `papers/wnat_admesh.png` in working tree, no `dist/` or `build/` directories. Failing this script blocks the 0.1.0 tag.

**Checkpoint**: User Story 4 complete. Repo is shippable. Tier 1.5 fixture is in the test ladder. Pre-tag verification script passes.

---

## Phase 6: User Story 3 — Backward-compatible custom size-field override (Priority: P3)

**Goal**: Every spec-001 caller pattern keeps working byte-identically. Verification only; no new code (the spec-001 code paths are already in place).

**Independent Test**: `tests/test_backward_compat.py` replays each spec-001 quickstart-validation example and asserts `mesh.equals(spec_001_baseline)` returns `True`.

### Implementation for User Story 3

- [ ] T033 [US3] Custom-size-field bypass test in `tests/test_backward_compat.py`: call `triangulate(domain, size_field=lambda p: 0.1 * np.ones(len(p)))` on the L-shape MVP polygon; assert the resulting `Mesh` matches the spec-001 baseline (the spec-001 quickstart-validation captured these meshes; load and compare via `Mesh.equals(atol=1e-9)`)
- [ ] T034 [US3] User-contribs-on-top test in `tests/test_backward_compat.py`: call `triangulate(domain, user_contribs=[my_refinement])` where `my_refinement` is a Phase-2 contribution; assert the resulting mesh shows the refinement composed on top of the new default stack (mean edge length in refined region < unrefined region) AND that backward-compat with the spec-001 user_contribs semantics (Phase-2 combiner) is preserved
- [ ] T035 [US3] Both-supplied-warning test in `tests/test_backward_compat.py`: call `triangulate(domain, size_field=fh1, user_contribs=[fh2])`; assert `UserWarning` fires matching spec-001's pattern "ignoring `user_contribs`"; assert the resulting mesh equals what `triangulate(domain, size_field=fh1)` produces (user_contribs ignored)
- [ ] T036 [US3] Spec-001 quickstart-validation regression: read `tests/output/quickstart_validation.txt` (if it captured baseline meshes — check spec-001 task T047) and replay each entry through the spec-002 `triangulate()` with the same arguments; assert `mesh.equals(baseline)` in every case

**Checkpoint**: User Story 3 complete. Spec-001 callers are protected; the spec-002 default-stack change is purely additive in observable behaviour for them.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final integration, documentation, and the "ship it" checklist.

- [ ] T037 [P] Run `pytest tests/ -q` and confirm all tests pass: 142 spec-001 tests + new spec-002 test modules (`test_default_size_field.py`, `test_fort14_paired.py`, `test_backward_compat.py`); zero tolerance for new failures
- [ ] T038 [P] Update `PROJECT_PLAN.md` "Where we are today" section: note spec-002 shipped, default size-field stack is the headline behaviour, 0.1.0 tag is unblocked
- [ ] T039 [P] Update `CLAUDE.md` SPECKIT marker block to reflect "spec 002 shipped" status (still leave spec-002 as the "active" feature reference until the next spec opens)
- [ ] T040 Run `quickstart.md` validation manually: execute each Tier 0 → Tier 2 example and confirm the printed output is consistent with the documented expectations; capture any discrepancies as follow-up issues
- [ ] T041 Final commit + push to `origin/002-size-field-defaults`; reference each completed FR in the commit body for traceability; do NOT tag 0.1.0 in this commit (that's a separate explicit step gated on T032's verification script)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS US1, US2, US3
- **Phase 3 (US1)**: Depends on Phase 2 — primary release-gating work
- **Phase 4 (US2)**: Depends on Phase 2 + Phase 3 (uses default stack); independently testable
- **Phase 5 (US4)**: Depends on Phase 2 only for the test-ladder portions; the cleanup tasks (T023-T028) can run **in parallel with all of Phase 3-4**; T029-T031 (Tier 1.5) sequence after T029 acquires the fixture
- **Phase 6 (US3)**: Depends on Phase 3 (uses the extended `triangulate()`); independently testable
- **Phase 7 (Polish)**: Depends on Phases 1–6

### User Story Dependencies

- **US1 (P1)** is the MVP. All other stories depend logically on it (or are independent).
- **US2 (P2)** uses US1's `_build_default_size_field` infrastructure but tests independently.
- **US3 (P3)** is regression-only; no new code; verifies US1 didn't break spec-001.
- **US4 (P2)** is independent of code work; runs in parallel with US1/US2.

### Within Each User Story

- Tests are first-class deliverables (not optional polish), per FR-014 / FR-016.
- Models / dataclass extensions before service / wiring layers.
- Within a story, tasks marked [P] can run in parallel.

### Parallel Opportunities

- T004 (BoundaryType) parallel with T002/T003 (different files).
- T005 (`__init__.py`) parallel with T002/T003.
- US4 cleanup tasks (T023-T028) almost entirely [P] — different files.
- Test tasks within US1 (T015, T016, T017, T018) are [P]-eligible — they touch test files only.
- Phase 7 final polish tasks T037-T039 are [P].

---

## Parallel Example: Phase 2 Foundational

```bash
# Sequential within api.py (T002 → T003), parallel elsewhere:
Task: "T002 Extend Domain in admesh/api.py"
# After T002 completes:
Task: "T003 Extend BoundarySegment in admesh/api.py"

# In parallel with T002 (different file):
Task: "T004 Extend BoundaryType in admesh/boundary_types.py"
Task: "T005 Update admesh/__init__.py re-exports"
```

## Parallel Example: US1 + US4 in flight together

```bash
# US1's code work in admesh/ (sequential within api.py and fort14.py):
Task: "T007 Domain.from_mesh in admesh/api.py"
Task: "T008 _build_default_size_field in admesh/api.py"
Task: "T011 fort14 reader IBTYPE 3 in admesh/fort14.py"

# In parallel: US4 cleanup tasks in unrelated files:
Task: "T023 Walk back constitution v1.0.1 in .specify/memory/constitution.md"
Task: "T024 Restore README install callout in README.md"
Task: "T026 Remove papers/wnat_admesh.png"
Task: "T027 Remove dist/ + build/ directories"
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1 Setup (1 task)
2. Phase 2 Foundational (5 tasks) — blocks everything
3. Phase 3 US1 (12 tasks: T007 → T019) — produces a working default-stack mesher with Tier 0 + Tier 1 + Tier 2 acceptance tests passing
4. **Stop and validate**: `pytest tests/test_default_size_field.py -v` — release gate satisfied
5. Open a draft PR; functional MVP shipped

### Incremental Delivery toward 0.1.0

1. MVP (US1) → demo: "default `triangulate(domain)` produces feature-aware meshes"
2. Add US2 (3 tasks) → demo: "with bathymetry, depth-gradient regions get refined"
3. Add US4 cleanup (T023-T028; can run in parallel with US1) → demo: "repo is shippable"
4. Add US4 Tier 1.5 (T029-T031) → demo: "Shinnecock real-world bay round-trips"
5. Add US3 regression (T033-T036) → demo: "spec-001 callers unaffected"
6. Phase 7 polish + run pre-tag verification (T032) → tag 0.1.0

### Single-developer sequential pacing

Approximate effort estimates (LLM-paced; full-auto cycle including tests + verification):

| Phase | Tasks | Estimated effort |
|---|---|---|
| 1 Setup | T001 | < 5 min |
| 2 Foundational | T002–T006 | ~1 hour |
| 3 US1 | T007–T019 | ~4–6 hours |
| 4 US2 | T020–T022 | ~1 hour |
| 5 US4 | T023–T032 | ~2 hours (mostly cleanup + 1 fixture acquire) |
| 6 US3 | T033–T036 | ~1 hour |
| 7 Polish | T037–T041 | ~30 min |
| **Total** | **41 tasks** | **~10–12 hours of LLM-driven work** |

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable; you can demo at every checkpoint
- US4 (release readiness) is partially file-independent of US1/US2 — run cleanup in parallel
- Verify tests fail before implementing (TDD-style); the structural-validity tests SHOULD fail today on the bad WNAT mesh, then pass after T009 lands
- Commit after each task or logical group; reference the task ID in the commit message for traceability
- Stop at any checkpoint to validate the story's MVP slice
- Avoid: vague tasks, same-file conflicts marked [P], cross-story dependencies that break independence
