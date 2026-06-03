# Tasks: Octree O(log N) Scalability (#115)

**Input**: `specs/021-octree-size-field-perf/` (spec.md, plan.md, research.md, data-model.md)
**Issue**: [#115](https://github.com/domattioli/ADMESH/issues/115)
**Generated**: 2026-06-02 (planning session, daily-maintenance)

**Note**: No test tasks are marked optional — spec §6 defines required tests; all 5 tests are mandatory acceptance criteria.

---

## Phase 1: Setup

**Purpose**: Branch + fixture preparation before any tree-rewrite work.

- [ ] T001 Checkout `021-octree-size-field` branch (PR #113 base) or create fresh `021-octree-size-field-perf` from `main`
- [ ] T002 [P] Verify `tests/fixtures/octree/river-into-bay*.npz` exist; if absent, generate via `python scripts/render_scalability.py --export-fixtures`
- [x] T003 [P] Confirm `pytest tests/test_octree_grid.py` passes against current prototype (baseline green) — 14/14 pass in 0.65 s (2026-06-03)

---

## Phase 2: Foundational — OctreeNode data model (P0)

**Purpose**: Pointer-linked tree node — prerequisite for all subsequent phases.

**Independent test**: `test_adjacency_sibling_links` — all neighbour dicts consistent after 2 splits on a hand-constructed 3-level tree.

- [x] T004 Add `parent`, `children`, `neighbours` fields to `OctreeNode` in `admesh/_stages/octree_grid.py` per data-model.md; keep all existing prototype fields
- [x] T005 Implement `is_leaf()` as `len(self.children) == 0` in `admesh/_stages/octree_grid.py`
- [x] T006 Rewrite `split()` in `admesh/_stages/octree_grid.py`: create 4 children, set `child.parent = self`, set sibling neighbour links (SW/SE/NW/NE layout per data-model.md)
- [x] T007 Implement `wire_cross_parent_neighbours()` helper in `admesh/_stages/octree_grid.py`: ascend parent links to find opposite-face neighbour, wire it
- [x] T008 Write `test_adjacency_sibling_links` in `tests/test_octree_grid.py`: hand-constructed 3-level tree; assert all neighbour dicts consistent after 2 `split()` calls

**Checkpoint**: T008 green ✓ — pointer tree structurally correct.

---

## Phase 3: O(log N) point location (P1 of plan)

**Goal**: Replace `locate()` / `interpolate()` O(N) linear scan with O(log N) tree descent.

**Independent test**: `test_locate_descent` — 100 random points; call count per locate ≤ `max_depth + 1`.

- [x] T009 [US1] Rewrite `locate(self, pt)` in `admesh/_stages/octree_grid.py` using bbox midpoint descent (see plan.md Phase P1 pseudocode)
- [x] T010 [US1] Update `interpolate()` in `admesh/_stages/octree_grid.py` to call the new `locate()` — no other changes
- [x] T011 [US1] Write `test_locate_descent` in `tests/test_octree_grid.py`: 100 random points on unit-square 4-level octree; assert correct leaf + call count ≤ `max_depth + 1`

**Checkpoint**: T011 green ✓ — O(log N) query confirmed.

---

## Phase 4: O(N) adjacency + work-queue balancing (P2 of plan)

**Goal**: Replace O(N²) `_build_adjacency` and O(N³) `_balance_2to1` with pointer-based O(N) equivalents.

**Independent test**: `test_balance_2to1_queue` — river-into-bay ratio=20; no 2:1 violations after balancing; timing < 1 s.

- [x] T012 [US2] Delete (or stub-out) `_build_adjacency()` in `admesh/_stages/octree_grid.py`; adjacency is now set incrementally during `split()` (T006–T007)
- [x] T013 [US2] Rewrite `_balance_2to1()` in `admesh/_stages/octree_grid.py` as work-queue loop per plan.md Phase P2 pseudocode; add safety cap `10 * len(leaves)`
- [x] T014 [US2] Write `test_balance_2to1_queue` in `tests/test_octree_grid.py`: river-into-bay fixture ratio=20; assert no violations + wall-clock < 1 s

**Checkpoint**: T014 green ✓ — O(N) build confirmed.

---

## Phase 5: Scalability + parity validation (P3 of plan)

**Goal**: Confirm O(log N) build/query at ratio 1000; confirm numerical parity with prototype.

**Independent tests**: `test_scalability_ratio_1000` + `test_parity_vs_prototype`.

- [ ] T015 [US3] Extend `scripts/render_scalability.py` to run ratio 1000 and regenerate `output/octree_scalability.png`
- [ ] T016 [US3] Write `test_scalability_ratio_1000` in `tests/test_octree_grid.py`: river-into-bay ratio=1000; assert build+query < 10 s AND leaf count ≥ 10× below uniform baseline at finest `h_min`
- [ ] T017 [US3] Write `test_parity_vs_prototype` in `tests/test_octree_grid.py`: assert `size_field_octree(pts)` within `atol=1e-10` of reference output in `tests/fixtures/octree/river-into-bay*.npz`

**Checkpoint**: T016 + T017 green → scalability target met; numerical parity confirmed.

---

## Phase 6: Optional — Numba vectorization (P4 of plan)

**Goal**: Wrap per-leaf loops in `octree_medial.py` with `@njit` for additional speedup.

**Gating**: Only implement if wall-clock at ratio 1000 is close to the 10 s threshold (T016 wall-clock < 5 s → skip P4).

- [ ] T018 [US4] Add `ADMESH_NUMBA=1` env-var gate in `admesh/_stages/octree_medial.py`; wrap per-leaf gradient-fit loops in `@njit` behind gate
- [ ] T019 [US4] Write `test_numba_parity` in `tests/test_octree_grid.py`: unit-square fixture; assert `@njit` path within `atol=1e-12` of pure-Python path

---

## Phase 7: Polish & docs

- [ ] T020 [P] Update `docs/PORTING_NOTES.md`: add octree data-structure change record — pointer tree vs. flat-list prototype; note numerical identity preserved
- [ ] T021 [P] Run full `pytest -q` (all existing tests pass; no regressions)
- [ ] T022 Close issue #115 with comment linking spec, plan, tasks, and scalability plot

---

## Dependencies

- **Phase 1** (Setup): No deps — start immediately
- **Phase 2** (T004–T008, Foundational): Depends on Phase 1. Blocks Phases 3–5.
- **Phase 3** (T009–T011): Requires Phase 2 complete (uses new `OctreeNode` pointer fields)
- **Phase 4** (T012–T014): Requires Phase 2 complete (uses sibling links from `split()`)
- **Phase 5** (T015–T017): Requires Phases 3 + 4 complete (measures the fully-rewritten tree)
- **Phase 6** (T018–T019): Optional; requires Phase 5 green
- **Phase 7** (T020–T022): After all required phases (1–5) green

Phases 3 and 4 can run **in parallel** once Phase 2 is complete (different focus: `locate()` vs. `_balance_2to1()`).

---

## Parallel Execution

```
Phase 1: T001 → T002 ‖ T003
Phase 2: T004 → T005 → T006 → T007 → T008  (sequential; each builds on previous)
Phase 3 ‖ Phase 4  (parallel once Phase 2 green):
  Agent A: T009 → T010 → T011
  Agent B: T012 → T013 → T014
Phase 5: T015 ‖ T016 ‖ T017  (all parallel)
Phase 7: T020 ‖ T021 → T022
```

---

## Summary

| Phase | Tasks | Parallelizable | Gate test | Status |
|---|---|---|---|---|
| 1 Setup | T001–T003 | T002 ‖ T003 | pytest baseline green | T003 ✓ |
| 2 Node model | T004–T008 | — | `test_adjacency_sibling_links` | ✓ shipped 2026-06-03 |
| 3 O(log N) locate | T009–T011 | — | `test_locate_descent` | ✓ shipped 2026-06-03 |
| 4 O(N) balance | T012–T014 | ‖ Phase 3 | `test_balance_2to1_queue` | ✓ shipped 2026-06-03 |
| 5 Scalability | T015–T017 | T015 ‖ T016 ‖ T017 | `test_scalability_ratio_1000` + `test_parity_vs_prototype` | pending |
| 6 Numba (opt) | T018–T019 | — | `test_numba_parity` | pending |
| 7 Polish | T020–T022 | T020 ‖ T021 | full pytest green | pending |

**Total**: 22 tasks (20 required, 2 optional)  
**MVP**: Phases 1–5 (T001–T017) — delivers scalability + parity acceptance criteria from issue #115
