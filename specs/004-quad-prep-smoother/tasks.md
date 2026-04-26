# Tasks: Pre-Quadrangulation Triangle Smoother

**Feature**: 004-quad-prep-smoother  
**Branch**: `claude/quad-prep-smoothing-lo7ZA`  
**Input**: Design documents from `/specs/004-quad-prep-smoother/`

**Dependencies**: All foundation tasks (Phase 1) MUST be complete before User Story work begins.

---

## Phase 1: Foundation & Infrastructure

**Purpose**: Core modules, helpers, and test scaffolding that all user stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### F001 — Create `admesh/quad_prep.py` module structure

- [X] **T001** Create `admesh/quad_prep.py` skeleton with module docstring and imports (NumPy, SciPy, Numba)
- [X] **T002** Add `_ElementStiffness` and `_GlobalSystem` type annotations as comments
- [X] **T003** Add `_PairingMap` structure for pair-hint pre-pass (internal only)

### F002 — Create test infrastructure

- [X] **T004** Create `tests/test_quad_prep.py` skeleton with imports and fixture loader
- [X] **T005** Create `tests/fixtures/quad_prep/` directory
- [X] **T006** Add `tests/fixtures/quad_prep/README.md` documenting fixture provenance (synthetic, not MATLAB-derived)
- [X] **T007** [P] Generate 5 MVP polygon domain fixtures: `square.npz`, `l_shape.npz`, `u_shape.npz`, `square_with_hole.npz`, `annulus.npz` (each with `p_in`, `t`, `fd_callable_id`)
- [X] **T008** Generate synthetic varying-`h` fixture: `varying_h.npz`

### F003 — Implement `right_iso_quality` metric in `admesh/quality.py`

- [X] **T009** Read `mesh_quality` implementation to understand pattern
- [X] **T010** Implement `right_iso_quality(p, t) -> float` per data-model.md spec:
  - Per-element score: product of leg-equality, right-angle, hypotenuse-fit terms
  - Mesh score: unweighted mean over all elements
  - Return scalar in [0, 1]
- [X] **T011** Add docstring per the public-api.md contract
- [X] **T012** Write unit tests for `right_iso_quality`: equilateral triangle (low), right-isoceles (high), degenerate cases
- [X] **T013** Re-export `right_iso_quality` from `admesh/__init__.py`

### F004 — Implement helper functions for the smoother

- [X] **T014** Implement `_compute_element_jacobian(p, t) -> (M, 2, 2)` — per-element Jacobian from node positions
- [X] **T015** Implement `_boundary_node_mask(p, fd, geps=1e-10) -> (N,) bool` — identify nodes within `geps` of SDF zero
- [X] **T016** Implement `_project_boundary_nodes(p, fd, geps=1e-10) -> (N, 2)` — Newton-step projection back to SDF zero level-set
- [X] **T017** Implement `_grad_sdf_numerical(fd, p, eps=1e-7) -> (N, 2)` — numerical gradient via central differences
- [X] **T018** [P] Write unit tests for each helper (T014–T017) on synthetic test cases

**Checkpoint**: Foundation ready — smoother entry point and all leaf helpers are testable independently.

---

## Phase 2: User Story 1 — Prepare a triangulation for quad fusion (Priority: P1) 🎯 MVP

**Goal**: Single preprocessing call that nudges ADMESH triangulations toward right-isoceles so they can be cleanly fused into quads downstream.

**Independent Test**: Run the smoother on each of the 5 MVP polygon domains. Verify: (a) same node count and triangle connectivity, (b) boundary nodes stay on SDF zero level-set within `geps`, (c) right-isoceles quality increases by ≥ 0.10 on every domain.

### US1.Tests — Acceptance test suite for P1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] **T019** [P] Test: smoother returns same connectivity on each MVP domain (assert `t_out is t`)
- [X] **T020** [P] Test: node count unchanged on each MVP domain (assert `len(p_out) == len(p_in)`)
- [X] **T021** [P] Test: boundary nodes stay within `geps` of SDF zero on each MVP domain
- [X] **T022** [P] Test: right-isoceles quality increases by ≥ 0.10 on each MVP domain (SC-001)
- [X] **T023** Test: smoother completes one run on 10K-node mesh in ≤ 10 seconds (SC-005 wall-clock)

### US1.Implementation — Core smoother for uniform meshes

- [X] **T024** Implement `_assemble_local_stiffness_uniform(p, t) -> (M, 6, 6)` — per-element 6×6 blocks from SVD-invariant right-isoceles target (Formulation 1, research.md):
  - Compute element Jacobian
  - SVD decomposition
  - Construct target Jacobian (right-isoceles shape)
  - Compute local stiffness via derivative wrt node positions
  - Apply boundary rotation cap for nodes within `2 * h_local` of SDF zero
- [X] **T025** Implement `_assemble_global_system_uniform(p, t, K_local) -> (A_sparse, b)` — assemble global stiffness matrix and RHS:
  - Initialize `(2N, 2N)` CSR sparse matrix
  - Loop over elements and scatter local stiffness into global
  - Apply kinf boundary pinning: for boundary nodes, set `A[2i:2i+2, 2i:2i+2] += kinf; b[2i:2i+2] += kinf * p[i]`
- [X] **T026** Implement `_solve_global_system(A, b) -> (N, 2)` — solve the global FEM system:
  - Call `scipy.sparse.linalg.spsolve(A, b)`
  - Reshape result to `(N, 2)`
- [X] **T027** Implement `smooth_for_quadrangulation(p, t, fd, h=None, pair_hint=False, n_outer=2)` main entry point:
  - Validate inputs: `fd` is not None (raise ValueError if missing), `p` and `t` shapes
  - Validate `n_outer >= 1`
  - Loop `n_outer` times:
    - Assemble and solve FEM system (T024, T025, T026)
    - Project boundary nodes back to SDF zero level-set (T016)
  - Return `(p_new, t)` where `t` is the input array object
- [X] **T028** Add comprehensive docstring per public-api.md contract
- [X] **T029** Re-export `smooth_for_quadrangulation` from `admesh/__init__.py`

**Checkpoint**: At this point, User Story 1 (uniform smoother, no pair-hint, no spatially varying `h`) should pass all P1 tests on the 5 MVP domains.

---

## Phase 3: User Story 2 — Couple smoother to spatially varying size field (Priority: P2)

**Goal**: When `h` is provided, per-element target leg length tracks `h` evaluated at the element centroid (not hypotenuse).

**Independent Test**: On a synthetic test domain with known spatially varying `h` (e.g. linear ramp), Pearson correlation of `(leg_length, h_centroid)` must be ≥ 0.8.

### US2.Tests

- [X] **T030** Test: `h=None` case returns valid output (uniform fallback, does not crash)
- [X] **T031** Test: `h` provided — per-element leg lengths correlate with `h(centroid)` with Pearson r ≥ 0.8 on `varying_h.npz` fixture (SC-003)

### US2.Implementation

- [X] **T032** Extend `_assemble_local_stiffness_uniform` → `_assemble_local_stiffness(p, t, h=None)`:
  - Compute element centroid
  - If `h` provided: `σ_k = h(centroid_k) / sqrt(2)` (leg, not hypotenuse — FR-004)
  - If `h` None: `σ_k = 1.0`
  - Scale per-element target shape by `σ_k` before Jacobian construction
- [X] **T033** Update `smooth_for_quadrangulation` to pass `h` through to stiffness assembly
- [X] **T034** Update docstring and example to show `h` usage

**Checkpoint**: User Stories 1 and 2 should both work independently — uniform case (P1) and size-field-coupled case (P2).

---

## Phase 4: User Story 3 — Bias smoother toward pairing-aware alignment (Priority: P3)

**Goal**: When `pair_hint=True`, apply a soft regularizer that biases geometry toward mutual longest-edge alignment, increasing the fraction of cleanly pairable triangles.

**Independent Test**: On a fixed reference triangulation, run the smoother twice (once with `pair_hint=False`, once with `pair_hint=True`, all else equal). Verify the `True` case has ≥ 25% relative increase in mutual longest-edge neighbours (SC-004).

### US3.Tests

- [X] **T035** Test: `pair_hint=False` baseline — measure fraction of mutual longest-edge pairings
- [X] **T036** Test: `pair_hint=True` — measure fraction of mutual longest-edge pairings and assert ≥ 25% relative increase over baseline (SC-004)
- [X] **T037** Test: `pair_hint=True` on degenerate input (one-element-wide strip where no pairing is possible) — smoother falls back gracefully and does not error

### US3.Implementation

- [X] **T038** Implement `_build_pairing_map(p, t) -> (M,) int64`:
  - For each triangle k, find its longest edge
  - Identify neighbour triangle across that edge
  - If neighbour's longest edge is also the shared edge: `pairs[k] = neighbour`; else `pairs[k] = -1`
- [X] **T039** Implement `_pair_hint_penalty(p, t, pairs) -> (M, 6, 6)` — soft per-element stiffness penalty:
  - For each paired element, add penalty term that biases hypotenuse alignment
  - Penalty scale per D-004 (research.md): soft constraint, never topology change
- [X] **T040** Extend `_assemble_local_stiffness` to accept optional `pairs` array and add penalty when `pairs is not None`
- [X] **T041** Update `smooth_for_quadrangulation` to:
  - Build pairing map when `pair_hint=True` (T038)
  - Pass pairs to stiffness assembly when provided
- [X] **T042** Update docstring to document `pair_hint` parameter

**Checkpoint**: All three user stories should work independently. User Story 3 (with pair-hint regularizer) should show measurable mutual-pairing improvement on representative inputs.

---

## Phase 5: Polish, Documentation & Validation

**Purpose**: Final touchups, documentation, and cross-cutting acceptance checks.

- [X] **T043** Write `docs/PORTING_NOTES.md` entry (one line, per plan.md):
  - Explain leg-not-hypotenuse `h` scaling convention for right-isoceles (FR-004)
  - Rationale: post-pairing quad inherits leg as edge length, not hypotenuse
- [X] **T044** Run quickstart.md examples end-to-end and verify all code blocks execute
- [X] **T045** [P] Validate Constitution Principle I — 13 faithful-port modules remain byte-identical:
  - Run `git diff admesh/{routine,background_grid,distance,curvature,medial_axis,bathymetry,dominate_tide,boundary,mesh_size,distmesh,in_polygon,inpaint}.py` and assert all diffs are empty
- [X] **T046** Validate mesh_quality drop is expected (SC-007):
  - Compute `mesh_quality(p_in, t)` vs `mesh_quality(p_out, t)` on all 5 MVP domains
  - Document the delta (drop expected; test does not gate on sign)
- [X] **T047** Verify `right_iso_quality` is independent of `mesh_quality`:
  - Confirm import does not pull in or modify `mesh_quality`
- [X] **T048** Optional: Implement and land `triangulate(..., for_quads=True)` extension (FR-011, SHOULD not MUST):
  - Add `for_quads=False`, `quad_prep_n_outer=2`, `quad_prep_pair_hint=True` kwargs
  - When `for_quads=True`, call `smooth_for_quadrangulation` as final stage of pipeline
  - Preserve default behaviour (bit-for-bit identical when `for_quads=False`)
- [X] **T049** Run full pytest suite: `pytest tests/test_quad_prep.py -v` — all P1, P2, P3 tests green
- [X] **T050** Run performance check on 10K-node mesh: wall-clock ≤ 10 s (SC-005)

**Checkpoint**: All 7 success criteria (SC-001 through SC-007) are satisfied. Feature ready for review and merge.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Foundation)**: No dependencies — can start immediately ✅
- **Phase 2 (US1 — P1)**: Depends on Phase 1 completion — BLOCKS all downstream work
- **Phase 3 (US2 — P2)**: Depends on Phase 1 + Phase 2
- **Phase 4 (US3 — P3)**: Depends on Phase 1 + Phase 2 (can start before Phase 3 if needed)
- **Phase 5 (Polish)**: Depends on all user stories (Phases 2, 3, 4)

### Within-Phase Parallelization

**Phase 1**:
- T007, T008 (fixture generation) can run in parallel
- T014–T017 (helper implementations) can run in parallel
- T018 (helper tests) can run after all helpers are written

**Phase 2**:
- T019–T022 (acceptance tests) can run in parallel (all share same MVP domains but test different assertions)
- T024–T027 (smoother core) must run sequentially (each builds on prior)

**Phase 3**:
- T030, T031 (US2 tests) can run after T032 (stiffness extension)

**Phase 4**:
- T035–T037 (US3 tests) can run after T038 (pairing map)

**Phase 5**:
- T043–T047 (documentation, validation) can run in parallel
- T048 (API extension) is optional and can land later
- T049–T050 (final suite + perf check) must run after all phases

---

## Implementation Strategy

### MVP Path (all P1)

Complete Phase 1 (Foundation) + Phase 2 (US1) → STOP and VALIDATE:

- All 5 MVP domains show ≥ 0.10 quality improvement
- Boundary nodes stay on SDF zero level-set
- Connectivity and node count preserved
- Wall-clock ≤ 10 s on 10K nodes

Declare MVP complete. Ship to users for feedback.

### Incremental Delivery (P1 → P2 → P3)

1. Complete Phase 1 (Foundation) + Phase 2 (US1) → Ship MVP
2. Add Phase 3 (US2 — size-field coupling) → Ship P1+P2
3. Add Phase 4 (US3 — pair-hint regularizer) → Ship P1+P2+P3
4. Polish (Phase 5) → Final release

### Parallel Team Strategy (if staffed)

With multiple developers:

1. One person: Complete Phase 1 (Foundation)
2. Once Phase 1 done:
   - Developer A: Phase 2 (US1 — P1 MVP)
   - Developer B: Phase 3 (US2 — size-field)
   - Developer C: Phase 4 (US3 — pair-hint)
3. Once all user stories complete: Phase 5 (Polish) together

---

## Notes

- [P] tasks = can run in parallel (different functions/files, no dependencies)
- Each phase is a logical checkpoint where the feature is independently testable
- Tests MUST be written first (T019–T022, T030–T031, T035–T037) and fail before implementation
- Commit after each task or logical group (e.g., after T003, T013, T031, T042, T050)
- Constitution Principle I gate (T045) is non-negotiable — 13 faithful-port modules must remain untouched
- Performance target SC-005 (10K nodes in 10 s) is measured, not gated on-demand during development; profiling happens after Phase 2 is green
