# Phase 0 Research: Full C++ Rewrite of ADMESH

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-05-25

Resolves the unknowns flagged in Technical Context and the spec's
DEFERRED-to-plan items (FR-006 matrix, FR-010 backend select, Art II.2 framing).

## R1 — Build system: one CMake source, two delivery paths

**Decision**: Adopt **scikit-build-core** as the Python build backend; keep a
top-level standalone `admesh-cpp/CMakeLists.txt` as the native source of truth.

**Rationale**: scikit-build-core drives CMake from `pyproject.toml`, so the same
CMake tree produces (a) a `find_package(admesh)` / `add_subdirectory`-able
native library for US1 and (b) an importable wheel for US2/US4. The current
`setuptools.build_meta` backend can't emit a consumable native lib; a raw CMake
build can't publish wheels ergonomically.

**Alternatives rejected**: `setuptools` + custom `CMakeExtension` (works for
wheels but leaves the standalone lib as a second, drift-prone build); Meson
(less common in the scientific-Python wheel ecosystem, weaker cibuildwheel
integration).

**Migration note**: `pyproject.toml` `build-backend` flips from
`setuptools.build_meta` to `scikit_build_core.build`. Pure-Python install
(no compiler) must still succeed → wheels carry the compiled module; sdist
falls back to the Numba path if CMake/compiler absent (see R4).

## R2 — Wheel platform / Python matrix (resolves FR-006)

**Decision**: **cibuildwheel** matrix —
- OS: `linux` (manylinux2014 x86_64 + aarch64), `macos` (x86_64 + arm64), `windows` (AMD64)
- Python: CPython **3.10, 3.11, 3.12, 3.13**
- sdist published alongside; PyPI gets wheels + sdist.

**Rationale**: Mirrors the scientific-Python baseline (NumPy/SciPy support
window). aarch64 + macOS arm64 included because Apple Silicon is a known install
pain point (README "Install hiccups"). PyPy excluded (Numba/pybind11 friction,
no user demand).

**Alternatives rejected**: x86_64-only (drops Apple Silicon — primary user
platform); adding 3.9 (EOL trajectory, NumPy 2.x dropped it).

## R3 — Float reproducibility across compilers (gcc/clang/msvc)

**Decision**: For bit-parity stages: compile **without `-ffast-math`** (and
without `/fp:fast` on MSVC), use `-fno-fast-math` explicitly, pin reduction
order in source (no parallel/SIMD-reordered accumulation in parity-critical
loops), and **drop `-march=native`** from parity builds (replace with a fixed
baseline ISA, e.g. `-mavx2` or generic) so the same binary semantics hold across
arches.

**Rationale**: `-march=native` (currently in `admesh/_cpp/CMakeLists.txt`) makes
FMA-contraction and codegen host-dependent — incompatible with cross-arch
parity at `atol=1e-8`. IEEE-754 basic ops are deterministic across compliant
compilers once contraction and reassociation are disabled; FMA contraction is
the main cross-compiler divergence, gated by `-ffp-contract=off` on the
bit-parity translation units.

**Alternatives rejected**: keeping `-march=native` (fails SC-005 cross-platform
parity); global `-ffp-contract=off` everywhere (needless slowdown on relaxed
stages — apply per translation unit).

## R4 — sdist / no-toolchain fallback behavior (resolves edge case)

**Decision**: sdist install with no wheel **does not hard-fail**. Build attempts
the C++ module; on any compiler/CMake-absent or build-error condition, install
**still succeeds** and the package imports with the C++ module absent. At
runtime, `_backend.py` detects the missing module and routes to the permanent
Numba fallback (FR-004). "No compile step at install" north star holds.

**Rationale**: Hard-failing the sdist would break the pure-Python guarantee.
Soft-degrade keeps the pipeline always-runnable.

## R5 — Backend selection mechanism (resolves FR-010)

**Decision**: Three-tier, precedence high→low —
1. **kwarg** `triangulate(..., backend="cpp"|"python"|"auto")` — per-call, for debugging.
2. **env var** `ADMESH_BACKEND=cpp|python|auto` — session-wide override.
3. **auto** (default) — C++ if the compiled module imported, else Python.

A build flag is **not** used for selection (build produces both; selection is
runtime). Mismatch (e.g. `backend="cpp"` with no module) raises a clear error
rather than silently falling back, so debugging is unambiguous.

**Rationale**: kwarg gives per-call A/B for parity debugging (US3); env var
gives CI/bisect control without code edits; auto preserves zero-config UX.

**Alternatives rejected**: build-flag-only (can't A/B at runtime); silent
fallback on explicit `backend="cpp"` (hides the very bug you're chasing).

## R6 — Python callback bridge (resolves FR-007 + edge case)

**Decision**: Custom `size_field` / SDF callbacks supplied from Python are
invoked across the binding per evaluation via pybind11. **Vectorize the bridge**:
the C++ core hands the callback an array of query points and receives an array
back (one crossing per batch), not one GIL round-trip per point.

**Rationale**: Per-point GIL acquisition would dominate runtime on ~49k-node
domains. Batched evaluation amortizes the crossing. Correctness is unchanged
(same callable, same inputs); only call granularity changes.

**Open risk**: a user callback with per-point side effects could observe
batching. Documented as a contract: callbacks must be pure array→array.

## R7 — Triangle (Shewchuk) license

**Decision**: Triangle is already vendored/used in PR #103 for Delaunay.
**Flag for operator**: Triangle's license restricts commercial redistribution.
For an Apache-2.0 PyPI package this is a **distribution concern** — confirm
license compatibility or gate Triangle behind an optional build (fall back to
the vendored `delaunator.hpp`, MIT, for the default wheel).

**Rationale**: Surfaced now so it doesn't block the wheel-publish phase (US4).
Not resolved here — needs operator/legal call. Tracked as a plan-phase risk.

## R8 — Per-stage parity mode (resolves FR-003 application)

Initial classification (refined per stage during execution; each stage records
its mode in its parity test docstring):

| Stage | Module | Parity mode | Rationale |
|---|---|---|---|
| routine (01) | `routine` | bit-parity | orchestration, cheap |
| background_grid (02) | `background_grid` | bit-parity | grid construction, deterministic |
| distance (03) | `distance` | **relaxed** | SDF grid eval — transcendental/order-sensitive; document atol |
| curvature (04) | `curvature` | bit-parity | cheap, local |
| medial_axis (05) | `medial_axis` | **relaxed** | Voronoi/geometry libs differ; document atol |
| bathymetry (06) | `bathymetry` | bit-parity | interpolation, pin order |
| dominate_tide (07) | `dominate_tide` | bit-parity | algebraic |
| boundary (08) | `boundary` | bit-parity | indexing/assembly |
| mesh_size (09) | `mesh_size` | bit-parity | already Numba↔NumPy parity at 1e-10 |
| distmesh (10) | `distmesh` | **relaxed** | iterative relaxation + Triangle Delaunay; count/quality within tol, not bitwise |
| quality (11) | `quality` | bit-parity | closed-form |
| in_polygon (12) | `in_polygon` | bit-parity | predicate |
| inpaint (13) | `inpaint` | bit-parity | diffusion, pin iteration order |

**Note**: distmesh already diverges in node/element counts (README: 49377→49192)
because Triangle replaces scipy Delaunay — parity here is count+quality-within-
tolerance, per spec edge case, NOT bitwise. This is the canonical "costly →
documented relaxed" case (FR-003).

## Outstanding (carried to plan/operator, not blocking research)

- **Article II.2 amendment** — operator-deferred for this iteration (plan §Constitution Check).
- **R7 Triangle license** — operator/legal decision before wheel publish.
