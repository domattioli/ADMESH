# Implementation Plan: Full C++ Rewrite of ADMESH

**Branch**: `cpp-distmesh` (spec dir `019-cpp-port-optimize`, rides on PR #103) | **Date**: 2026-05-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/019-cpp-port-optimize/spec.md`

## Summary

Rewrite all 13 ADMESH pipeline stages, the public API (`Domain`, `Mesh`,
`triangulate`), and fort.14 I/O as a native **C++17** library, buildable
standalone via CMake with no Python runtime. pybind11 bindings re-expose the
same surface so existing `import admesh` users are unaffected. The Python/Numba
path is retained **permanently** as a no-toolchain fallback. Each stage lands
behind a per-stage parity gate against the captured MATLAB `.npz` fixtures
(bit-parity where cheap, documented relaxed tolerance where costly). Extends the
`cpp-distmesh` foundation (PR #103: pybind11 build, Eigen, Triangle Delaunay,
distmesh force kernel).

## Technical Context

**Language/Version**: C++17 (native core), Python 3.10+ (binding + fallback layer)
**Primary Dependencies**: pybind11, Eigen3, Triangle (Shewchuk), delaunator (vendored); Python side retains NumPy / SciPy / Numba / Shapely for the fallback path
**Storage**: filesystem only — fort.14 (ADCIRC), JSON/TOML domain loaders; no DB
**Testing**: pytest (Python parity + API + fort.14 round-trip) + a standalone C++ test target (ctest) that links the library with no Python
**Target Platform**: linux / macOS / windows × CPython 3.10–3.13 (exact matrix DEFERRED to research, FR-006)
**Project Type**: native library + language bindings (compiler-adjacent numeric lib)
**Performance Goals**: measure + report per-stage and end-to-end speedup over the Numba baseline on WNAT (~49k nodes); **no fixed threshold gates acceptance** (SC-003 / Q4)
**Constraints**: bit-parity stages forbid `-ffast-math` and pin reduction/iteration order (FR-005); relaxed-tolerance stages carry a documented per-stage rationale (FR-003); pipeline MUST always run even with no wheel/toolchain (FR-004)
**Scale/Scope**: 13 stages + API + I/O; reference domain WNAT 144-ring coastline, ~49k nodes / ~93k elements

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / Article | Status | Notes |
|---|---|---|
| **Article II.2 — "No C/C++ extensions in first cut"** | ⚠️ DEFERRED (operator) | Blanket C++ backend exceeds the ">2× per-stage Numba underperformance" carve-out. Amendment authorizing a primary C++ backend is required but **explicitly deferred by operator direction** for this plan iteration. Tracked in Complexity Tracking; revisit before merge to `main`. |
| **Principle I — faithful-port numerical identity** | ✅ PASS | Per-stage parity gate (FR-003, US3): every C++ stage tested against the MATLAB `.npz` fixture. Bit-parity (`atol=1e-8`) where cheap; relaxed + documented rationale where costly. Divergence is a bug (Art IV.6). |
| **Article V — every stage ships a reference test** | ✅ PASS | Existing `tests/test_<stage>.py` fixtures reused unchanged as the parity oracle for the C++ stage. Standalone C++ test target added (SC-002). |
| **North star — `pip install` without C toolchain** | ✅ PASS | Numba path retained **permanently** (FR-004); prebuilt wheels + sdist accelerate but absence of a wheel/toolchain still meshes via pure-Python. |
| **Article VI — branch governance** | ✅ PASS | Rides on existing `cpp-distmesh` (PR #103); no new branch created (Art VI.7 reuse). |
| **Article VIII — DomI upstream** | ✅ PASS | `.domi-pin` current (synced this session). |

**Gate result**: PASS to proceed with research, with Article II.2 carried as an
acknowledged, operator-deferred violation (not silently ignored).

## Project Structure

### Documentation (this feature)

```text
specs/019-cpp-port-optimize/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (C++ public API + Python facade contracts)
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
admesh-cpp/                 # standalone native library (CMake find_package / add_subdirectory)
├── CMakeLists.txt          # top-level: builds libadmesh + ctest target, no Python
├── include/admesh/         # public C++ headers: Domain, Mesh, triangulate, Fort14
├── src/
│   ├── stages/             # 13 native stage implementations
│   ├── api/                # Domain / Mesh / triangulate
│   └── io/                 # fort.14 reader/writer, JSON/TOML domain loaders
├── tests/                  # standalone C++ parity + smoke tests (no Python)
└── vendor/                 # delaunator, Triangle

admesh/                     # Python package (binding dispatch + permanent Numba fallback)
├── _cpp/                   # pybind11 binding module over admesh-cpp
│   ├── CMakeLists.txt
│   └── *_module.cpp        # binds Domain/Mesh/triangulate/fort14 + per-stage entry points
├── _stages/                # existing locked Numba/NumPy fallback stages (UNCHANGED)
├── api.py, fort14.py, ...  # Python surface; dispatches C++ ⇄ fallback by backend select
└── _backend.py             # backend selector (env var / kwarg / build flag — DEFERRED FR-010)

tests/                      # existing pytest suite — runs unchanged against C++-backed build
├── test_<stage>.py         # parity oracle, reused for the C++ stage
└── fixtures/<stage>/*.npz  # MATLAB reference fixtures (authoritative)

benchmarks/                 # gains a C++ column (FR-009)
```

**Structure Decision**: Two cooperating trees. `admesh-cpp/` is the native
source of truth — a standalone CMake library with a pure C++ public API and its
own no-Python ctest target (satisfies US1/SC-002). `admesh/_cpp/` is a thin
pybind11 layer binding that library back into the existing `admesh/` Python
package, which keeps the locked `_stages/` Numba modules as the permanent
fallback (FR-004). The existing `tests/` suite is the parity oracle for both
paths (US2/US3). The current `admesh/_cpp/{distmesh_cpp,distmesh_module,pipeline}.cpp`
from PR #103 is the seed that grows into this layout.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Article II.2 — blanket C++ backend (not a >2× per-stage patch) | User intent is "all in C++": the native library is the deliverable (US1), not a hot-path optimization. A C++ public API + fort.14 I/O cannot exist as a Numba carve-out. | Numba-only cannot satisfy US1 (no-Python native consumer) or SC-002 (standalone C++ test). The carve-out language only covers per-stage hot loops, not API/IO. Amendment deferred by operator, not waived. |
| Two build systems (standalone CMake + pybind11 wheel) | US1 needs a Python-free CMake consumer path; US2/US4 need importable wheels. | A single setuptools build can't produce a `find_package`-able native lib; a single CMake build can't publish to PyPI ergonomically. scikit-build-core (research) bridges both from one CMakeLists. |
