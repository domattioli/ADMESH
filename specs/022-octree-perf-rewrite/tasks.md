# Tasks: Spec 022 — Scalable Octree Performance Rewrite

**Input**: spec.md, plan.md, research.md, data-model.md, contracts/octree-scalable.md  
**Branch**: `022-octree-perf-rewrite`  
**File**: `admesh/_stages/octree_grid.py` (sole rewrite target)

---

## Phase 1: Setup

- [ ] T001 Confirm branch is `022-octree-perf-rewrite`; run `pytest tests/ -q` baseline (must green)
- [ ] T002 [P] Read `admesh/_stages/octree_grid.py` in full; note O(N²) loops line numbers

---

## Phase 2: Foundational — Pointer-Bearing OctreeLeaf

**Purpose**: Extend `OctreeLeaf` dataclass with internal pointer fields. No behavior change yet;
existing code still works. This unblocks all subsequent phases.

**⚠️ CRITICAL**: Phases 3–6 cannot start until `OctreeLeaf` has the pointer fields.

- [ ] T003 Add `_parent_idx: int = -1` field to `OctreeLeaf` in `octree_grid.py`
- [ ] T004 Add `_children_idx: list[int] = field(default_factory=lambda: [-1,-1,-1,-1])` to `OctreeLeaf`
- [ ] T005 Add `_neighbor_idx: list[int] = field(default_factory=lambda: [-1,-1,-1,-1])` to `OctreeLeaf`
- [ ] T006 Add `neighbors` property to `OctreeLeaf` that reconstructs list of live neighbor objects
  from `_neighbor_idx` via a module-level `_nodes` ref (or pass the list explicitly — see
  data-model.md for design). **Must preserve back-compat**: `lf.neighbors` returns same type as spec 021
- [ ] T007 Add `_is_leaf(node)` module-level predicate: returns True if all `_children_idx == -1`
- [ ] T008 Update `OctreeGrid` to store `_nodes: list[OctreeLeaf]` (all nodes, internal + leaf);
  change `leaves` to a property that returns `[n for n in _nodes if _is_leaf(n)]`

**Checkpoint**: Run `pytest tests/ -q` — must still green. `grid.leaves` returns same set as before.

---

## Phase 3: US1 — O(N log N) Build

**Goal**: Replace O(N²) `_build_adjacency` + O(N³) `_balance_2to1` with pointer-wiring build.

**Independent Test**: Build octree on ratio-100 river domain; assert < 5 s; assert no `_build_adjacency` call inside balance loop.

- [ ] T009 Implement `_find_neighbor_of_greater_depth(nodes, idx, direction) -> int` (Samet 1990; see plan.md + research.md R3)
- [ ] T010 Implement `_split_leaf(nodes, idx, domain, size_oracle) -> list[int]`:
  - Compute 4 child centers; eval fd + oracle at each
  - Append 4 new `OctreeLeaf` to `nodes` with correct `_parent_idx`
  - Wire sibling neighbors (direct index arithmetic, no descent needed for siblings)
  - Wire external neighbors via `_find_neighbor_of_greater_depth` for each child's outward-facing directions
  - Mark parent as internal by setting `_children_idx`
  - Return list of 4 child indices
- [ ] T011 Rewrite `build_octree` top-down loop to call `_split_leaf` instead of appending to flat list manually; build `OctreeGrid._nodes` incrementally
- [ ] T012 Rewrite `_balance_2to1` using `collections.deque` work queue (plan.md §Key Algorithms); delete old `_build_adjacency`-inside-loop pattern
- [ ] T013 Delete `_build_adjacency` function (or keep as dead code with a `# DELETED` comment for one release, then remove)

**Checkpoint**: `pytest tests/ -q` green. Build ratio=40 domain; verify < 5 s. Leaf set same as before (within ~5%).

---

## Phase 4: US2 — O(log N) `locate` + `leaf_graph`

**Goal**: Replace O(N) linear scans with tree descent and pointer-derived edge list.

**Independent Test**: Build 50 k-leaf octree; time 100 k queries; assert total < 1 s.

- [ ] T014 Rewrite `locate(grid, p)` using tree descent via `_children_idx`; clamp p to bbox before descent
- [ ] T015 Verify `interpolate(grid, values, p)` still works (delegates to `locate`; values indexed parallel to `grid.leaves` which is now a property — ensure index alignment correct)
- [ ] T016 Rewrite `leaf_graph(grid)` to iterate `grid.leaves` and read `_neighbor_idx` directly; no all-pairs comparison

**Checkpoint**: `pytest tests/ -q` green. 100 k queries against 50 k leaves: total < 1 s.

---

## Phase 5: US3 + US4 — Parity Verification + Scalability Benchmark

**Goal**: Confirm numerical agreement with spec 021 and empirically measure O(N log N).

- [ ] T017 [P] Run parity check (quickstart.md §2) on notch domain; log max|Δh|/h_max; assert < 0.05
- [ ] T018 [P] Run parity check on river-bay SC-001 domain; compare element counts; assert within 10%
- [ ] T019 Update `scripts/render_scalability.py` to extend ratio range to [10, 100, 1000]; add wall-clock comparison vs spec 021 prototype (if tractable)
- [ ] T020 Run `python scripts/render_scalability.py`; verify power-law exponent < 1.5; save new `output/octree_scalability.png`
- [ ] T021 Run `python scripts/render_sizefield_diff.py`; verify river mesh >= 3 nodes; save figure
- [ ] T022 Run `python scripts/render_octree_proof.py`; verify no errors; save figure

---

## Phase 6: Tests

- [ ] T023 Create/update `tests/test_octree_grid.py` with:
  - T023a: invariant test — after build, all leaf pairs that are neighbors satisfy `|depth_a - depth_b| <= 1`
  - T023b: invariant test — neighbor pointers symmetric
  - T023c: build speed smoke — ratio=10 build < 2 s
  - T023d: locate correctness — query points known to be inside/outside; check correct leaf returned
  - T023e: parity test — notch domain, max|Δh|/h_max < 0.05 vs spec 021 output (if fixture available)
- [ ] T024 Run full `pytest tests/ -q`; all green

---

## Phase 7: Polish + Handoff

- [ ] T025 Update CLAUDE.md SPECKIT block: add `022-octree-perf-rewrite` to in-flight specs
- [ ] T026 Update `admesh/_stages/octree_grid.py` module docstring: document complexity, pointer design
- [ ] T027 Commit all changes with message "perf(octree): O(N log N) pointer quadtree — closes #115"
- [ ] T028 Push branch; verify PR #113 (spec 021) or create new PR #022 if needed
- [ ] T029 Close issue #115 with a comment summarizing the fix (SC-001–SC-004 measurements)

---

## Dependencies & Execution Order

- T001–T002: no deps; start immediately
- T003–T008: sequential (each adds to OctreeLeaf); checkpoint before Phase 3
- T009–T013: T009 and T010 can go in parallel; T011 needs T010; T012 needs T009+T011
- T014–T016: T014 first; T015+T016 in parallel after T014
- T017–T022: T017+T018 parallel; T019→T020→T021→T022 sequential (render scripts)
- T023–T024: all T023 subtasks parallel; T024 after all T023
- T025–T029: sequential
