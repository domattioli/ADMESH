# Implementation Plan: Octree Background Grid for Multi-Scale Size-Function & Medial-Axis Robustness

**Branch**: `021-octree-size-field` | **Date**: 2026-05-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/021-octree-size-field/spec.md`

## Summary

Replace the uniform cartesian background grid with an **octree** (in 2D, its specialization a **quadtree**) as the substrate on which the size function and medial axis are computed. The uniform grid forces a single global cell spacing; on multi-scale domains a tractable spacing is too coarse to resolve narrow features, so the medial-axis stage finds no interior cells in a pinch and silently falls back to "boundary distance only" (spec US1). The octree refines locally down to the `h_min` floor where features are small and stays coarse in open water, so the medial axis resolves everywhere a feature exists, the size function can target ≥ 4 elements across every feature (US2), and cell count grows sub-quadratically in the feature-size ratio (US3).

Technical approach: add a new leaf-utility module `admesh/_stages/octree_grid.py` (construction, 2:1 balance, point-location, leaf interpolation, leaf-adjacency graph) and route the three locked stages through it — `background_grid.py` (octree-backed grid), `medial_axis.py` (medial axis + MAD on the leaf graph via the existing FMM distance, generalised to variable spacing), and `mesh_size.py` (`build_h` builds the octree substrate, gradient-limits on the leaf graph, and returns an octree-backed query interpolant). The uniform grid is retained as the construction-failure fallback and as the no-refinement degenerate case (US4/FR-018). This modifies locked faithful-port modules under explicit user authorization and is gated on a Constitution amendment (see Constitution Check).

## Technical Context

**Language/Version**: Python 3.10–3.13 (CI matrix: ubuntu/macos/windows × 3.10–3.13)
**Primary Dependencies**: NumPy; SciPy (`ndimage.distance_transform_edt`, `interpolate.RegularGridInterpolator`, `spatial`); Numba (`@njit` gradient-limit solver). **No new third-party dependency planned** — the octree is a lightweight in-repo structure (Principle II). If one becomes necessary it lands in `pyproject.toml` with a one-line rationale.
**Storage**: N/A (library). Test fixtures as `.npz`; new synthetic domain fixture under `tests/fixtures/`.
**Testing**: `pytest tests/ -q`. Current stage tests are analytic/hand-derived (MATLAB `.npz` export for these stages is still blocked on spec 013 / issue #78), plus the Numba-vs-NumPy parity test for `solve_iter`.
**Target Platform**: Cross-platform, `pip install`-able without a C toolchain (Principle II).
**Project Type**: Library (algorithmic meshing backend).
**Performance Goals**: octree cell count sub-quadratic in feature-size ratio (≥ 10× fewer cells than uniform-at-finest at ratio 1000, SC-004); build time within a small documented margin of the uniform path on non-multi-scale domains (SC-008).
**Constraints**: refinement floor = `h_min` with no separate max-depth cap (FR-004); 2:1 neighbour balance (FR-003); gradient limit `|∇h| ≤ g` preserved on the leaf graph (FR-009); octree-affected stages need not reproduce MATLAB bit-for-bit (authorized departure).
**Scale/Scope**: feature-size ratios to ≈ 10³–10⁴; reference domains up to WNAT (~10⁴ nodes). Touches 3 locked stage modules + 1 new module; adds 1 governance amendment.

## Constitution Check

*GATE: evaluated against `.specify/memory/constitution.md` v1.0.2. Re-checked after Phase 1 design (below).*

- **I. Faithful Port Before Optimization** — ❌ **VIOLATION (authorized; amendment required).** The octree intentionally diverges from MATLAB's uniform-grid algorithm inside `background_grid.py`, `medial_axis.py`, and `mesh_size.py`. The user granted explicit permission (2026-05-28) to unlock these modules. This narrows Principle I's scope for the named stages, so it requires a Constitution amendment — a **MAJOR** governance bump (v2.0.0) per the versioning policy ("scope materially narrowed"). Justified in Complexity Tracking. **Mitigation**: the uniform-grid faithful-port algorithm is *retained* as the fallback/degenerate path (FR-017/FR-018), so it is not deleted and stays exercisable.
- **II. Pure-Python First (No C Extensions)** — ✅ **PASS.** The octree is pure Python + Numba in the first cut; no new C/C++ extension. (A C++ acceleration may follow later under Principle II's ">2× slower" clause, consistent with the in-flight `admesh/_cpp` work — out of scope here.) The Numba `solve_iter` parity test (`atol=1e-10`) is preserved for the uniform path; a leaf-graph gradient limiter adds an analogous parity test.
- **III. Reference-Test Discipline (NON-NEGOTIABLE)** — ⚠️ **CONDITIONAL.** Numeric parity to MATLAB is *waived for the octree-affected stages only* (that waiver is the feature). Few MATLAB `.npz` fixtures exist for these stages today, so the practical fixture-regeneration cost is low; new **property/behavioural** tests replace parity asserts for the octree path, and any regenerated fixtures carry provenance documenting the divergence (FR-016). Stages NOT on the octree keep their fixtures and `atol=1e-8/rtol=1e-6` parity. The uniform fallback path remains parity-testable. `pytest tests/ -q` must still pass on `main`.
- **IV. Stage-by-Stage Bottom-Up Porting** — ✅ **PASS.** `octree_grid.py` is a new leaf utility; consumption order is `background_grid → medial_axis → mesh_size` (bottom-up); the integrator (`routine`/`api.triangulate`) is unchanged.
- **V. Report-and-Advance Session Cadence** — ✅ **PASS** (process principle; no code impact).

**Gate result**: PASS *with* one documented, user-authorized Principle I violation tracked in Complexity Tracking and gated on the v2.0.0 amendment (an explicit task in `/speckit-tasks`).

**Post-Phase-1 re-check**: design keeps the violation scoped to the three named stages, adds no new third-party dependency, and preserves the uniform fallback path — no new violations introduced. Gate still PASS.

## Project Structure

### Documentation (this feature)

```text
specs/021-octree-size-field/
├── spec.md              # /speckit-specify + /speckit-clarify output
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (internal interface contracts)
│   └── octree-size-field.md
├── checklists/
│   └── requirements.md  # spec-quality checklist (already present)
└── tasks.md             # /speckit-tasks output (NOT created here)
```

### Source Code (repository root)

```text
admesh/_stages/                 # CANONICAL faithful-port tree (top-level admesh/*.py are auto-reflecting shims)
├── octree_grid.py              # NEW — octree/quadtree: construction, 2:1 balance, point-location,
│                               #       leaf interpolation, leaf-adjacency graph, uniform-fallback detection
├── background_grid.py          # MODIFIED — octree-backed grid alongside the uniform BackgroundGrid
├── medial_axis.py              # MODIFIED — medial axis + MAD/LFS on the leaf graph (reuse medial_distance_fmm,
│                               #            generalised to variable leaf spacing)
└── mesh_size.py                # MODIFIED — build_h(): octree substrate, leaf-graph gradient limiting,
                                #            octree-backed query interpolant; uniform fallback on failure

admesh/api.py                   # UNCHANGED — additive layer; triangulate() keeps its current call path

tests/
├── test_octree_grid.py         # NEW — octree construction, balance, point-location, interpolation, fallback
├── test_background_grid.py     # UPDATED — octree-backed grid behaviour + uniform degenerate case
├── test_medial_axis.py         # UPDATED — multi-scale resolution (basin+inlet), agreement where uniform resolves
├── test_mesh_size.py           # UPDATED — octree build_h, ≥4-elements verification, leaf-graph limiter parity
└── fixtures/
    └── multiscale/             # NEW — synthetic basin+inlet fixture (controllable L/W) + real ADCIRC mesh ref

docs/governance/CONSTITUTION.md          # AMENDED — Principle I carve-out for octree stages (v2.0.0)
.specify/memory/constitution.md          # AMENDED — mirror of the same amendment + Sync Impact Report
docs/PORTING_NOTES.md                    # UPDATED — note the deliberate divergence for the three stages
```

**Structure Decision**: Single-project library layout. The octree is a new leaf utility in the canonical `_stages/` tree; the three locked stages consume it bottom-up. All edits stay in `_stages/` (the top-level `admesh/*.py` shims re-export automatically); `api.py` and the rest of the additive layer are untouched, keeping the public `triangulate()` contract stable.

## Complexity Tracking

> Justifies the Constitution Check violation above.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Modifying locked faithful-port stages (`background_grid`, `medial_axis`, `mesh_size`) — Principle I | The medial-axis failure originates *inside* these stages' uniform-grid assumption; the size function and medial axis are computed there. Fixing it means changing how the grid is built and consumed. | A purely additive wrapper cannot alter how the locked stages build/sample their grid, so it cannot fix the root cause. The user explicitly authorized unlocking these modules (2026-05-28). |
| Waiving MATLAB numeric parity for these stages — Principle III | The octree produces a *different (better)* size function by design; parity to the uniform-grid MATLAB output is exactly what is being improved past. | Keeping parity would forbid the feature. Mitigated: uniform fallback stays parity-testable; new property tests + provenance-tagged fixtures cover the octree path. |
| Constitution amendment, MAJOR bump to v2.0.0 | Principle I scope is materially narrowed for the named stages, which the versioning policy classifies as MAJOR. | Shipping without amending would leave code contradicting governance; Principle I is the default null hypothesis and must be formally carved out (amendment procedure: PR + Amendments-log entry + Sync Impact Report). |

## Phase 0 — Research

See [research.md](./research.md): decisions on octree-vs-quadtree realisation, construction/refinement criteria, the medial-axis-on-octree method (FMM on the leaf graph vs. generalised AOF/skeletonization vs. locally-uniform rasterization), leaf-graph gradient limiting, octree query interpolation, and the fallback trigger. All Technical-Context unknowns are resolved there.

## Phase 1 — Design & Contracts

See [data-model.md](./data-model.md) (entities: `OctreeGrid`, `OctreeLeaf`, leaf-adjacency graph, size-field arrays, exception record), [contracts/octree-size-field.md](./contracts/octree-size-field.md) (internal interface contracts for construction, query callable, and medial-axis-on-octree signatures — preserving the existing `fh(p)` query contract `triangulate()` depends on), and [quickstart.md](./quickstart.md) (developer walkthrough + validation steps). The agent context (`CLAUDE.md` SPECKIT block) is updated to point at this plan.
