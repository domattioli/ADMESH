# Tasks: Full C++ Rewrite of ADMESH

**Input**: Design documents from `/specs/019-cpp-port-optimize/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: REQUIRED. The per-stage parity gate (US3) is the core deliverable —
tests are the contract, not optional (Principle I, FR-003).

**Branch**: `cpp-distmesh` (rides on PR #103). Seed: existing
`admesh/_cpp/{distmesh_cpp,distmesh_module,pipeline}.cpp`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency)
- Paths are concrete per plan.md Structure Decision.

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Create `admesh-cpp/` tree: `include/admesh/`, `src/{stages,api,io}/`, `tests/`, move vendored `delaunator.hpp`/Triangle into `admesh-cpp/vendor/`
- [ ] T002 Author top-level `admesh-cpp/CMakeLists.txt`: `libadmesh` target (C++17), `find_package(Eigen3)`, install rules + `admesh::admesh` export, ctest enable
- [ ] T003 [P] Migrate `pyproject.toml` build-backend `setuptools.build_meta` → `scikit_build_core.build`; wire root CMake to build `admesh/_cpp` module (R1)
- [ ] T004 [P] Add per-parity compiler-flag policy in CMake: bit-parity TUs get `-fno-fast-math -ffp-contract=off`, drop `-march=native` for fixed baseline ISA (R3, FR-005)
- [ ] T005 [P] Add `clang-format`/`.clang-tidy` for `admesh-cpp/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ No stage/API work until complete.**

- [ ] T006 Define public headers `include/admesh/admesh.hpp`: `Domain`, `Mesh`, `BoundarySegment`, `TriangulateOptions` per [data-model.md](./data-model.md) + [contracts/cpp-public-api.md](./contracts/cpp-public-api.md)
- [ ] T007 Implement `BoundaryType` mapping (IBTYPE 0/1/11/20 named; 3/4/13/24 + unmapped preserved as int) in `src/io/boundary_type.{hpp,cpp}` (FR-008)
- [ ] T008 [P] Eigen↔NumPy zero-copy buffer bridge in `admesh/_cpp/buffer.hpp` (raw-buffer access from PR #103)
- [ ] T009 [P] Batched Python-callback bridge (`size_field`/SDF: array→array, one crossing per batch) in `admesh/_cpp/callback.hpp` (R6, FR-007)
- [ ] T010 Backend selector `admesh/_backend.py`: kwarg > `ADMESH_BACKEND` env > auto; `cpp` w/o module ⇒ raise (R5, FR-010)
- [ ] T011 [P] Parity test harness: parametrize `tests/test_<stage>.py` over `backend=["python","cpp"]`, `PARITY_MODE` table + `assert_parity(mode=)` helper in `tests/conftest.py` ([contracts/parity-gate.md](./contracts/parity-gate.md))

**Checkpoint**: native types, bridges, backend dispatch, parity harness ready.

---

## Phase 3: User Story 1 — Native C++ meshing library (P1) 🎯 MVP

**Goal**: standalone C++ lib meshes a domain + fort.14 round-trip, no Python.
**Independent Test**: `ctest` in `admesh-cpp/build` meshes MVP + WNAT.

- [ ] T012 [US1] `src/io/fort14.cpp`: byte-faithful `read_fort14`/`write_fort14` incl. IBTYPE 3/4/13/24 (FR-008)
- [ ] T013 [P] [US1] `src/io/loaders.cpp`: `load_domain` for fort.14 / JSON / TOML by extension (edge case: no-Python domain input)
- [ ] T014 [US1] `src/api/triangulate.cpp`: native `triangulate(Domain, TriangulateOptions)` orchestrating the stage pipeline (seeds from `pipeline.cpp`)
- [ ] T015 [P] [US1] Standalone C++ test `admesh-cpp/tests/test_fort14_roundtrip.cpp`: byte-faithful assertion (US1 scenario 2)
- [ ] T016 [P] [US1] Standalone C++ test `admesh-cpp/tests/test_mesh_mvp.cpp`: mesh MVP domains + WNAT, assert counts + quality, **no Python** (SC-002)
- [ ] T017 [US1] `find_package(admesh)` smoke consumer in `admesh-cpp/tests/consumer/` proving `add_subdirectory` + link path (US1 scenario 1)

**Checkpoint**: native library meshes + round-trips fort.14 with zero Python.

---

## Phase 4: User Story 3 — Per-stage parity gate (P1)

**Goal**: each C++ stage green against the MATLAB `.npz` fixture at its mode.
**Independent Test**: `pytest tests/test_<stage>.py -q` (both backends) per stage.
**Note**: ordered leaf→integrator (Art IV.4). Each task = port stage to
`admesh-cpp/src/stages/<stage>.cpp`, bind it, turn its parity test green.

- [ ] T018 [P] [US3] `in_polygon` (12) — bit-parity
- [ ] T019 [P] [US3] `quality` (11) — bit-parity
- [ ] T020 [P] [US3] `inpaint` (13) — bit-parity, pin iteration order
- [ ] T021 [P] [US3] `curvature` (04) — bit-parity
- [ ] T022 [P] [US3] `background_grid` (02) — bit-parity
- [ ] T023 [P] [US3] `bathymetry` (06) — bit-parity, pin interpolation order
- [ ] T024 [P] [US3] `dominate_tide` (07) — bit-parity
- [ ] T025 [P] [US3] `boundary` (08) — bit-parity
- [ ] T026 [US3] `distance` (03) — **relaxed**: document SDF-eval tolerance + rationale (R8/FR-003)
- [ ] T027 [US3] `medial_axis` (05) — **relaxed**: document geometry-lib tolerance + rationale
- [ ] T028 [US3] `mesh_size` (09) — bit-parity (already Numba↔NumPy at 1e-10); reuse pinned reduction order
- [ ] T029 [US3] `distmesh` (10) — **relaxed**: count + `min_q`/`mean_q` within tol (Triangle ≠ scipy Delaunay); document it is algorithmic not a port bug (R8)
- [ ] T030 [US3] `routine` (01) — bit-parity orchestration; wires all stages end-to-end

**Checkpoint**: all 13 stages parity-green (cpp + python both vs same fixture).

---

## Phase 5: User Story 2 — Drop-in Python compatibility (P1)

**Goal**: `import admesh` unchanged; dispatches to C++; numerically equivalent.
**Independent Test**: existing `tests/` suite passes unchanged (SC-001).

- [ ] T031 [US2] `admesh/_cpp/*_module.cpp`: bind `Domain`/`Mesh`/`triangulate`/`read_fort14`/`write_fort14` + per-stage entry points to match the frozen Python surface (FR-002)
- [ ] T032 [US2] Wire `admesh/api.py` `triangulate(..., backend="auto")` to dispatch C++⇄fallback via `_backend.py` (additive kwarg, non-breaking)
- [ ] T033 [US2] Equivalence test `tests/test_cpp_python_equivalence.py`: same `(domain,args,seed)` ⇒ counts + quality match within tol (US2 scenario 1, SC-005)
- [ ] T034 [US2] Run full `pytest tests/ -q` against C++-backed build; fix regressions to zero (SC-001)

**Checkpoint**: PyPI contract intact; C++ core active under the Python surface.

---

## Phase 6: User Story 4 — Reproducible cross-platform build (P2)

**Goal**: wheels + standalone lib build & smoke-pass on every target.
**Independent Test**: CI matrix green; install-and-mesh in clean env.

- [ ] T035 [US4] `cibuildwheel` config: linux(manylinux2014 x86_64+aarch64) / macos(x86_64+arm64) / windows(AMD64) × CPython 3.10–3.13 (R2, FR-006)
- [ ] T036 [P] [US4] CI job: build standalone `admesh-cpp` (CMake) + run `ctest` per OS (SC-004)
- [ ] T037 [P] [US4] CI job: build wheels, `pip install` in clean env, import-and-mesh smoke (SC-004, US2 scenario 2 — no compiler runs)
- [ ] T038 [US4] sdist soft-degrade test: no-compiler env installs + meshes via Numba fallback (R4, FR-004)

**Checkpoint**: every declared target ships a building lib + importable wheel.

---

## Phase 7: Polish & Cross-Cutting

- [ ] T039 [P] Benchmark: add C++ column to `benchmarks/compare_versions.py`; report per-stage + e2e speedup vs Numba on WNAT, **no threshold gate** (FR-009, SC-003)
- [ ] T040 [P] Docs: update `README.md` Performance table + `docs/` C++ build/consume guide; record per-stage parity modes
- [ ] T041 Run `quickstart.md` end-to-end (all 3 paths) as acceptance
- [ ] T042 **[OPERATOR]** Resolve R7 Triangle license vs Apache-2.0 before wheel publish (gate Triangle as optional, default `delaunator`)
- [ ] T043 **[OPERATOR]** Article II.2 Constitution amendment authorizing primary C++ backend — required before merge to `main` (deferred this iteration)

---

## Dependencies & Execution Order

- **Phase 1 → 2**: setup before foundational.
- **Phase 2 blocks all stories** (types, bridges, dispatch, harness).
- **US1 (P3 here = Phase 3)** and **US3 (Phase 4)** can proceed in parallel after Phase 2; US3 stages T018–T029 are mostly `[P]` (distinct files). T030 (routine) depends on all other stages. T014 (triangulate) depends on T030 for full pipeline.
- **US2 (Phase 5)** depends on US3 stages being bindable (T031 needs the native stages) and on T010 backend selector.
- **US4 (Phase 6)** depends on a buildable lib + wheel (Phases 1–5).
- **Polish (Phase 7)** last; T042/T043 are operator gates, not code.

### MVP

Phases 1–2 → **US1 (Phase 3)** = native lib meshes + fort.14 round-trip, no
Python. Stop and validate (`ctest`) before broadening to US3/US2.

### Parallel opportunities

- T003/T004/T005 (setup) parallel.
- T008/T009/T011 (foundational bridges) parallel.
- T018–T025 (bit-parity leaf stages) parallel — distinct `src/stages/*.cpp` + distinct test files.
- T036/T037 (CI jobs) parallel.

---

## Notes

- A stage is "done" only at parity-green for the `cpp` backend (US3); the
  `python` fallback stays green throughout (Art VI.6, FR-004).
- Relaxed stages (T026/T027/T029) MUST carry a written rationale in the test
  docstring or the gate rejects them ([contracts/parity-gate.md](./contracts/parity-gate.md)).
- Commit per task or logical group; reference MATLAB source path when porting (Art VI.2).
