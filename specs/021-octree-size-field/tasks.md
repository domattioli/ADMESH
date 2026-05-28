# Tasks: Octree Background Grid for Multi-Scale Size-Function & Medial-Axis Robustness

**Input**: Design documents from `/specs/021-octree-size-field/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/octree-size-field.md

**Tests**: INCLUDED — Constitution Principle III (reference-test discipline) is non-negotiable, and the spec defines explicit Independent Tests + measurable Success Criteria.

**Organization**: Grouped by user story (US1–US4) for independent implementation and testing. Canonical code lives in `admesh/_stages/` (top-level `admesh/*.py` are auto-reflecting shims — do NOT edit them).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1–US4 (maps to spec user stories); Setup/Foundational/Polish have no story label

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Module scaffolding for the new octree substrate.

- [ ] T001 Create `admesh/_stages/octree_grid.py` with `OctreeGrid` + `OctreeLeaf` dataclasses and public function stubs (`build_octree`, `locate`, `interpolate`, `leaf_graph`) per contracts/octree-size-field.md C2
- [ ] T002 [P] Add `OctreeConstructionError` exception and a `_warn_under_resolved(...)` helper in `admesh/_stages/octree_grid.py`
- [ ] T003 [P] Create test scaffold `tests/test_octree_grid.py` and fixture dir `tests/fixtures/multiscale/` with a `make_basin_inlet(L, W)` domain generator

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The octree core that every user story depends on.

**⚠️ CRITICAL**: No user-story work begins until this phase is complete.

- [ ] T004 Implement top-down quadtree construction in `build_octree(domain, *, h_min, h_max, size_oracle, padding=None, balance=True)` — subdivide each cell while `cell_size > size_oracle(center)` and `cell_size/2 >= h_min`; floor at `h_min` (research R2, FR-004) in `admesh/_stages/octree_grid.py`
- [ ] T005 Implement the 2:1 neighbour-balance pass (FR-003, research R3) in `admesh/_stages/octree_grid.py`
- [ ] T006 [P] Implement `locate(grid, p)` O(log) point-location in `admesh/_stages/octree_grid.py`
- [ ] T007 [P] Implement `interpolate(grid, values, p)` within-leaf interpolation in `admesh/_stages/octree_grid.py`
- [ ] T008 Implement `leaf_graph(grid) -> (edges, spacing)` edge-adjacency + centre-to-centre spacing in `admesh/_stages/octree_grid.py`
- [ ] T009 [P] Tests for construction (leaf size ∈ `[h_min, root]`, non-overlap tiling), 2:1 balance invariant, `locate`, `interpolate`, and `leaf_graph` in `tests/test_octree_grid.py`

**Checkpoint**: octree primitives exist and are tested — stories can begin.

---

## Phase 3: User Story 1 — Medial axis resolves on multi-scale domains (Priority: P1) 🎯 MVP

**Goal**: Octree-backed size function whose medial axis resolves inside narrow features that a tractable uniform grid misses.

**Independent Test**: On a basin+inlet domain with L/W ≥ 1000, the octree path yields non-empty MAD inside the inlet while the uniform baseline does not (SC-001).

### Tests for User Story 1

- [ ] T010 [P] [US1] Fixture: deterministic basin+inlet generator with controllable L/W in `tests/fixtures/multiscale/` (used by SC-001)
- [ ] T011 [P] [US1] Test: octree resolves medial axis in inlet (finite MAD on inlet-interior leaves; target h ≈ inlet half-width/R) AND uniform baseline at tractable spacing returns empty medial axis there, in `tests/test_medial_axis.py`

### Implementation for User Story 1

- [ ] T012 [US1] Implement generalised average-outward-flux medial-leaf detection over leaf neighbours (replaces 8-neighbour pixel stencil, research R4) in `admesh/_stages/medial_axis.py`
- [ ] T013 [US1] Compute MAD via `medial_distance_fmm` on the variable-spacing leaf graph (edge cost = centre distance) in `admesh/_stages/medial_axis.py`
- [ ] T014 [US1] Implement `apply_medial_axis_octree(h, D_leaves, grid, *, R, hmax, hmin)` (`LFS=|D|+MAD`, `h_lfs=clip(LFS/R)`, return `min(h_lfs, h)`) per contract C3 in `admesh/_stages/medial_axis.py`; leave uniform `apply_medial_axis(...)` unchanged
- [ ] T015 [US1] Wire octree substrate into `build_h` — build `OctreeGrid`, evaluate `D` per leaf, min-stack curvature/medial(octree)/bathymetry/tide — in `admesh/_stages/mesh_size.py`
- [ ] T016 [US1] Implement octree-backed `fh(p)` via `locate`+`interpolate`, preserving the `(N,2)->(N,)` callable contract C1, in `admesh/_stages/mesh_size.py`
- [ ] T017 [US1] Add `resolved` flag + below-floor `UserWarning` (FR-006) in `admesh/_stages/medial_axis.py`

**Checkpoint**: US1 functional and independently testable (SC-001).

---

## Phase 4: User Story 2 — At least four elements span every feature (Priority: P2)

**Goal**: Size function targets ≥ 4 elements across every resolved feature, verified on the output mesh.

**Independent Test**: A transverse cut across each known feature crosses ≥ 4 element edges (SC-002); below-floor features warn (SC-003).

### Tests for User Story 2

- [ ] T018 [P] [US2] Test: build mesh on basin+inlet and assert ≥ 4 element edges cross each feature's narrowest transverse extent; assert below-`h_min` feature emits the warning, in `tests/test_mesh_size.py`

### Implementation for User Story 2

- [ ] T019 [US2] Implement configurable `min_elements` target (default 4) so the medial-derived target h ≤ feature_width / min_elements at the medial axis (FR-010, FR-011) in `admesh/_stages/medial_axis.py` / `mesh_size.py`
- [ ] T020 [US2] Implement an output-mesh verification helper (count element edges across a feature extent) for the acceptance test and the FR-012 unmet-minimum warning, in `admesh/_stages/mesh_size.py`

**Checkpoint**: US1 + US2 both work (SC-002, SC-003).

---

## Phase 5: User Story 3 — Large multi-scale domains stay tractable (Priority: P3)

**Goal**: Sub-quadratic cell growth + robust fallback so the octree is practical at scale.

**Independent Test**: Leaf count grows sub-quadratically across ratios 10/100/1000 and is ≥ 10× smaller than uniform-at-finest at 1000 (SC-004); fallback works (FR-018).

### Tests for User Story 3

- [ ] T021 [P] [US3] Test: record leaf counts for ratios 10/100/1000, assert sub-quadratic growth and ≥ 10× fewer leaves than uniform-at-finest at 1000, in `tests/test_octree_grid.py` (SC-004)
- [ ] T022 [P] [US3] Test: forced `OctreeConstructionError` ⇒ `build_h` warns and still returns a valid `fh`; degenerate no-multi-scale domain build time within margin of uniform (SC-008), in `tests/test_mesh_size.py`

### Implementation for User Story 3

- [ ] T023 [US3] Implement leaf-graph gradient limiter `solve_iter_graph` with `_py` + `@njit _nb` variants and `atol=1e-10` parity test (Principle II, contract C5) in `admesh/_stages/mesh_size.py`
- [ ] T024 [US3] Implement uniform fallback in `build_h` on `OctreeConstructionError` (warn + run existing uniform path, FR-018/C6) in `admesh/_stages/mesh_size.py`

**Checkpoint**: US1–US3 independently functional.

---

## Phase 6: User Story 4 — Departure from the faithful-port baseline is deliberate and auditable (Priority: P2)

**Goal**: Ratify the Principle I exception and keep governance consistent with the code.

**Independent Test**: Constitution carries the dated v2.0.0 amendment naming the exempted stages; non-octree stages still reproduce their fixtures; octree-changed stages assert against provenance-tagged fixtures (SC-006).

### Implementation for User Story 4

- [ ] T025 [US4] Author Constitution amendment v2.0.0 in `docs/governance/CONSTITUTION.md` — carve `background_grid` / `medial_axis` / `mesh_size` out of Principle I, with rationale + Amendments-log entry (FR-015)
- [ ] T026 [US4] Mirror the amendment + a Sync Impact Report in `.specify/memory/constitution.md` (bump 1.0.2 → 2.0.0)
- [ ] T027 [P] [US4] Record the deliberate divergence for the three stages in `docs/PORTING_NOTES.md`
- [ ] T028 [US4] Regenerate/annotate octree-affected stage fixtures with provenance; confirm stages NOT on the octree keep `atol=1e-8/rtol=1e-6` parity green (FR-016, SC-006) under `tests/`

**Checkpoint**: governance ratified; `pytest tests/ -q` green on the branch.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T029 [P] Add a real multi-scale ADCIRC mesh to the test ladder for SC-007 in `tests/fixtures/multiscale/` (select per data-model.md)
- [ ] T030 [P] Docstrings on new/changed functions (cite octree design, not MATLAB parity for changed stages) + brief note in relevant `docs/`
- [ ] T031 Run the `quickstart.md` validation steps end-to-end
- [ ] T032 Full `pytest tests/ -q` green; confirm no regressions in non-octree stages and no public-API change (`api.triangulate` signature unchanged)

---

## Dependencies & Execution Order

- **Setup (P1)** → **Foundational (P2)** blocks everything.
- **US1 (P1)** depends only on Foundational — the MVP.
- **US2 (P2)** depends on US1 (its target/verify needs the octree medial axis).
- **US3 (P3)** depends on Foundational; the gradient limiter (T023) and fallback (T024) integrate with US1's `build_h` wiring (T015/T016).
- **US4 (P2)** is governance — can proceed in parallel with US1–US3 but MUST land before the feature ships in a tagged release.
- **Polish (P7)** after the desired stories.

### Within each story

- Tests written and failing before implementation (Principle III).
- In `octree_grid.py`: construction (T004) before balance (T005) before graph (T008); `locate`/`interpolate` (T006/T007) independent `[P]`.
- Medial detection (T012) → MAD (T013) → `apply_medial_axis_octree` (T014) → `build_h` wiring (T015) → query (T016).

### Parallel opportunities

- T002/T003 (setup) in parallel.
- T006/T007 in parallel; T009 test groups in parallel.
- T010/T011 (US1 tests) in parallel; T021/T022 (US3 tests) in parallel.
- US4 docs/governance (T025–T028) largely parallel with the implementation stories.

---

## Implementation Strategy

**MVP = Setup + Foundational + US1.** Deliver the medial-axis robustness fix first (SC-001), validate on the basin+inlet fixture, then layer US2 (≥4 elements), US3 (tractability + fallback), and US4 (governance). Keep the uniform fallback green throughout so `pytest tests/ -q` never breaks on the branch.

## Notes

- Edit only `admesh/_stages/*.py`; never the top-level shims.
- `api.py` and the public `triangulate()` contract stay untouched (Contract C1).
- The v2.0.0 Constitution amendment (T025/T026) is a hard release gate (FR-015) — implementation may proceed on the branch before it merges, but the feature does not ship without it.
- Commit after each task or logical group; reference task IDs.
