# Feature Specification: Full C++ Rewrite of ADMESH

**Feature Branch**: `019-cpp-port-optimize`
**Created**: 2026-05-25
**Status**: Draft
**Input**: User description: "entirely port and optimize admesh in cpp" + "i want it all in cpp"

## Clarifications

### Session 2026-05-25

- Q: Python bindings fate? → A: Retain pybind11 bindings as a drop-in facade
  for current PyPI users (C++ core, Python surface preserved).
- Q: Numba fallback lifecycle? → A: Keep the Python/Numba path **permanently**
  as a no-toolchain fallback (not removed after the port). This preserves the
  "no compile step at install" north star — wheels accelerate, but a
  toolchain-free pure-Python install still meshes.
- Q: Parity strategy vs MATLAB fixtures? → A: Per-stage — hold bit-parity
  (`atol=1e-8`, forbid `-ffast-math`, pin reduction order) where cheap;
  relax tolerance with a documented per-stage rationale where bit-parity is
  costly. No single global tolerance.
- Q: SC-003 speedup target over Numba (WNAT)? → A: No fixed multiple — measure
  and report per-stage + end-to-end speedup; do not gate on a threshold.
- Deferred to plan phase: wheel platform/Python matrix, backend-select
  mechanism (env var / kwarg / build flag), and the Article II.2 Constitution
  amendment authorizing a full C++ backend.

## Overview

Rewrite ADMESH **entirely in C++** — all 13 pipeline stages, the public API
(`Domain`, `Mesh`, `triangulate`, fort.14 read/write, domain loaders), and
the hot paths — as a native C++ library. The C++ surface is the primary
implementation, not a hot-path patch behind Python. Optional pybind11
bindings expose the same calls to Python so existing `import admesh` users
keep working, but the source of truth is C++.

This extends the partial C++ work on `cpp-distmesh` (PR #103: distmesh force
kernel + Triangle Delaunay) into a complete native port.

## Governance Tensions

Most tensions resolved in clarify (see Clarifications). One operator decision
remains and blocks the plan phase.

- **[DEFERRED — operator] Article II.2 — "No C/C++ extensions in first cut."**
  C/C++ is permitted only where Numba underperforms > 2× per-stage. A blanket
  rewrite needs an explicit Constitution amendment authorizing C++ as the
  primary backend. Retained Numba fallback (Q2) softens the conflict but does
  not remove it — amendment still required before `/speckit-plan`.
- **[RESOLVED] Principle I — faithful-port numerical identity.** Per-stage
  parity (clarify Q3): hold bit-parity (`atol=1e-8`, forbid `-ffast-math`,
  pin reduction order) where cheap; relax tolerance with documented per-stage
  rationale where bit-parity is costly. Each stage records its parity mode.
- **[RESOLVED] Distribution north star.** The Python/Numba path is retained
  **permanently** as a no-toolchain fallback (clarify Q2), so "no compile step
  at install" holds. Prebuilt wheels (cibuildwheel) + a standalone CMake build
  accelerate; absent a wheel/toolchain, the pure-Python path still meshes.
- **[RESOLVED] Python parity surface.** pybind11 bindings retained as a
  drop-in facade for current PyPI users (clarify Q1); C++ is the source of
  truth, Python API surface unchanged.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Native C++ meshing library (Priority: P1)

A C++ application links the ADMESH library directly (CMake `find_package` /
`add_subdirectory`), constructs a domain, calls `triangulate`, and gets a
mesh struct back — no Python runtime involved.

**Why this priority**: This is the "all in C++" core deliverable. ADMESH
becomes a native library, usable without Python.

**Independent Test**: A standalone C++ test target builds against the library,
meshes the MVP domains, and asserts node/element counts + quality.

**Acceptance Scenarios**:

1. **Given** the built C++ library, **When** a C++ program meshes a domain,
   **Then** it returns a mesh with quality matching the MATLAB reference
   within tolerance — no Python in the process.
2. **Given** a fort.14 file, **When** the C++ reader/writer round-trips it,
   **Then** the output is byte-faithful (incl. paired-edge IBTYPE records).

---

### User Story 2 - Drop-in Python compatibility (Priority: P1)

An existing PyPI user upgrades and keeps calling `admesh.triangulate(...)`
unchanged. The call now dispatches into the C++ core via bindings; output is
numerically equivalent to the prior release and runs faster.

**Why this priority**: Protects the current user base. The rewrite must not
break the published Python contract.

**Independent Test**: The existing `tests/` suite passes unchanged against the
binding-backed build; mesh output matches within parity tolerance.

**Acceptance Scenarios**:

1. **Given** a domain meshed under the Python/Numba release, **When** meshed
   under the C++ build with the same args/seed, **Then** node/element counts
   and per-element quality match within tolerance.
2. **Given** a platform with a published wheel, **When** the user installs and
   imports admesh, **Then** no compiler runs and the C++ core is active.

---

### User Story 3 - Per-stage parity gate (Priority: P1)

A maintainer porting one stage to C++ verifies it against the captured MATLAB
`.npz` fixtures stage-by-stage, so each stage lands behind a green parity test.

**Why this priority**: Faithful identity is non-negotiable (Principle I); a
stage is not "ported" until it matches the reference fixture.

**Independent Test**: For each ported stage, a C++ test loads the fixture
input, runs the stage, and asserts against expected output at tolerance.

**Acceptance Scenarios**:

1. **Given** `tests/fixtures/<stage>/*.npz`, **When** the C++ stage runs on
   the fixture input, **Then** output matches expected within tolerance.
2. **Given** a stage mid-port, **When** the suite runs, **Then** both the C++
   and the legacy Python output are checked against the same fixture.

---

### User Story 4 - Reproducible cross-platform build (Priority: P2)

A CI maintainer builds and tests the C++ library + Python wheels for every
supported platform on each tagged release.

**Why this priority**: Without wheels + a standalone build, neither the Python
nor the native-consumer story ships.

**Independent Test**: CI matrix produces a building C++ library and importable
wheels on linux/macos/windows × supported Python; smoke tests pass on each.

**Acceptance Scenarios**:

1. **Given** a tagged commit, **When** CI runs, **Then** the C++ library
   compiles standalone (CMake) and wheels build + import-and-mesh on every
   target.

---

### Edge Cases

- C++ output diverges from MATLAB only on degenerate input (collinear slivers,
  zero-area triangles) — parity fixtures must cover these, not just nominal.
- Build toolchain absent at install AND no wheel for the platform — sdist
  fallback behavior must be defined (build-from-source vs hard-fail).
- Float reproducibility across compilers/arches (gcc / clang / msvc) under the
  same parity tolerance.
- User-supplied callbacks (custom `size_field` / SDF) from Python crossing into
  the C++ core per evaluation — correctness + performance of the bridge.
- A C++-native consumer needs domain input without Python — the C++ API must
  accept domains from file (fort.14 / JSON) directly.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: ADMESH MUST build as a standalone C++ library (CMake) with a
  C++ public API covering domain construction, `triangulate`, and fort.14 I/O,
  usable with no Python runtime.
- **FR-002**: The existing Python public API MUST remain source-compatible via
  pybind11 bindings — no signature or observable-behavior change for current
  users.
- **FR-003**: Each C++ stage MUST pass the existing MATLAB `.npz` fixture
  parity test. Parity mode is per-stage (Q3): bit-parity (`atol=1e-8`) where
  cheap; relaxed tolerance with documented rationale where costly.
- **FR-004**: The Python/Numba path MUST be retained **permanently** as a
  no-toolchain fallback (Q2). Any stage without a C++ implementation, or any
  install without a wheel/toolchain, falls back to it — pipeline always runs.
- **FR-005**: Where a stage targets bit-parity, the build MUST forbid
  `-ffast-math` (and equivalents) and pin reduction/iteration order.
- **FR-006**: The release pipeline MUST publish prebuilt wheels and a buildable
  sdist + standalone CMake source distribution. [DEFERRED to plan: exact
  platform/Python matrix.]
- **FR-007**: Python callbacks (custom `size_field`, custom SDF) MUST work
  unchanged when the surrounding stage runs in C++.
- **FR-008**: fort.14 round-trip in C++ MUST be byte-faithful, including
  paired-edge / weir records (IBTYPE 3 / 4 / 13 / 24).
- **FR-009**: The benchmark harness MUST gain a C++ column so per-stage and
  end-to-end speedup over the Numba baseline is tracked.
- **FR-010**: A user MUST be able to select the active backend (C++ vs Python)
  for debugging. [DEFERRED to plan: env var / kwarg / build flag.]

### Key Entities

- **C++ stage**: native implementation of one of the 13 pipeline stages;
  parity-tested against the MATLAB fixture.
- **C++ public API**: `Domain`, `Mesh`, `triangulate`, fort.14 reader/writer —
  the native surface, mirrored to Python via bindings.
- **Parity fixture**: captured MATLAB input/expected `.npz` per stage; the
  contract every implementation must satisfy.
- **Build artifact**: standalone C++ library (CMake), platform/Python wheels,
  and an sdist that builds from source.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of existing `tests/` pass against the C++-backed build
  (parity + API + fort.14 round-trip), zero regressions.
- **SC-002**: A standalone C++ test target (no Python) meshes the MVP domains
  and WNAT, asserting quality within parity tolerance.
- **SC-003**: End-to-end `triangulate` on WNAT (~49k nodes) is benchmarked
  against the Numba baseline at the same operating point and seed; per-stage
  and end-to-end speedup is measured and reported. No fixed threshold gates
  acceptance (Q4) — the requirement is the measurement, not a target multiple.
- **SC-004**: Importable wheels + a building standalone C++ library exist for
  every declared target and pass an install/build-and-mesh smoke test in a
  clean environment.
- **SC-005**: No user-observable change in mesh output: identical node/element
  counts and quality distribution within tolerance on the MVP set and WNAT.

## Assumptions

- The `cpp-distmesh` foundation (pybind11 build, raw-buffer access, Triangle
  Delaunay) is the starting point and is mergeable independently.
- MATLAB `.npz` reference fixtures remain the authoritative parity oracle.
- "All in C++" means the numerical core AND the API/IO are reimplemented in
  C++; Python is a thin binding layer over the C++ library, retained for
  backward compatibility.
- The Numba path is retained **permanently** as a no-toolchain fallback (not
  removed post-port), keeping the pipeline always-runnable and the
  "no compile step at install" north star intact.

## Out of Scope

- 3-D, anisotropic, or non-triangular meshing (unchanged project scope).
- GPU acceleration (separate `gpu`-labeled investigation).
- Changing mesh algorithms or output — this is a port, not a redesign.
- tri2quad / CHILmesh smoothing (lives downstream in CHILmesh).
