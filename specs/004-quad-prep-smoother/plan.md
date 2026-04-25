# Implementation Plan: Pre-Quadrangulation Triangle Smoother

**Branch**: `claude/smooth-quad-preprocessing-FmMxF` | **Date**: 2026-04-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-quad-prep-smoother/spec.md`

## Summary

Add a preprocessing smoother that takes any ADMESH triangulation and
nudges its triangles toward the right-isoceles target shape so they
can be cleanly fused into quads downstream. The smoother is a new
top-level module `admesh/quad_prep.py` exposing
`smooth_for_quadrangulation(p, t, fd, h=None, pair_hint=True, n_outer=2)`
plus a companion quality metric `right_iso_quality(p, t)` in
`admesh/quality.py` (additive, no edits to `mesh_quality`). The 13
faithful-port stage modules are left untouched (Constitution
Principle I).

**Algorithmic formulation**: Per the research note in
[research.md](./research.md), the v1 implementation uses the
**SVD-invariant FEM target-Jacobian** approach (Formulation 1).
Per-element target Jacobians are oriented by closed-form argmin on
the local SVD each outer iteration, which resolves the
right-angle-corner ambiguity deferred from /speckit-clarify without
requiring a global frame-field solve. Frame-field guided smoothing
(Formulation 2) is recorded as a v2 follow-up spec.

The implementation is independent of issue #1 (`admesh/smoother.py`
with `target="right_isoceles"`); the two share design references but
neither imports the other (per spec FR-012).

## Technical Context

**Language/Version**: Python ≥3.10 (existing `pyproject.toml` pin)
**Primary Dependencies**: NumPy ≥1.24, SciPy ≥1.11 (`scipy.sparse`,
`scipy.sparse.linalg.spsolve`), Numba ≥0.58 (existing). No new third-
party deps.
**Storage**: N/A (pure-library numerical routine).
**Testing**: pytest. New `tests/test_quad_prep.py` plus synthetic
fixtures under `tests/fixtures/quad_prep/` (no MATLAB-derived
fixtures — feature is forward-looking, not a port).
**Target Platform**: Linux, macOS, Windows (pure Python; no C
extensions).
**Project Type**: Python library (single project; flat `admesh/`
layout consistent with the rest of the package).
**Performance Goals**: SC-005 — one end-to-end run on a 10K-node
triangulation completes in ≤ 10 s wall-clock on a developer laptop.
**Constraints**:
- No edits to the 13 faithful-port stage modules (spec FR-009,
  Constitution Principle I).
- Pure Python; no C extensions (Constitution Principle II). Numba
  `@njit` is permitted for the inner per-element local-stiffness
  assembly if profiling shows the NumPy path is >2× too slow.
- Triangle connectivity preserved: `t_out` element-for-element
  identical to `t_in` (FR-002).
- Boundary nodes stay on SDF zero level-set within `geps` (FR-003).
- `fd` is required at runtime; the smoother raises rather than
  falling back to topology-detection (FR-013).
**Scale/Scope**: ~200 LOC for `quad_prep.py`, ~30 LOC for the
`right_iso_quality` extension to `quality.py`, ~150 LOC for the
test suite + synthetic fixtures. Targets coastal-grade meshes (≤
~10K nodes). Frame-field formulation deferred to a future spec.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Principles I–V from `.specify/memory/constitution.md` (v1.0.1,
2026-04-25):

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Faithful Port Before Optimization | ⚠️ Justified deviation | This feature is **not a port** — no equivalent function exists in `01_ADMESH_Library/`. The QuADMesh-MATLAB pipeline does its quad fusion via `tri2quad.m` (which is itself out of scope per the constitution's "Out-of-scope" list) and assumes the quad smoother absorbs the equilateral→rhombus mismatch downstream. This spec adds a *forward-looking* preprocessing step that has no MATLAB counterpart. Justified deviation, tracked in Complexity Tracking below. The 13 existing faithful-port modules in `admesh/*.py` remain bit-for-bit unchanged. |
| II. Pure-Python First (No C Extensions) | ✅ Preserved | NumPy + `scipy.sparse` + (optional) Numba `@njit` for inner-loop assembly. No new C code, no MEX shims. |
| III. Reference-Test Discipline | ⚠️ Justified deviation | NON-NEGOTIABLE for ports. This feature has no MATLAB reference, so the constitution's "fixtures derived from MATLAB" rule cannot apply literally. Substituted with: (a) synthetic golden fixtures derived from the implementation itself + a sanity SDF; (b) parity test between a pure-NumPy reference path and any Numba-accelerated path (per Principle II's pattern in `mesh_size.py`); (c) acceptance assertions on the 7 measurable success criteria from spec.md. Documented in `tests/fixtures/quad_prep/README.md` (new). |
| IV. Stage-by-Stage Bottom-Up Porting | ✅ N/A | The 13 faithful-port stages are complete. This feature builds on top — leaf utilities (`distance.grad_sdf`, `mesh_size.solve_iter`, `quality.mesh_quality`) are already validated. |
| V. Report-and-Advance Session Cadence | ✅ Preserved | Standard cadence applies. |

**Out-of-scope-list considerations**:

The constitution's Out-of-scope list (Development Workflow & Quality
Gates, line 254-259) names "Quad conversion (`tri2quad.m`,
`distquadmesh2d.m`). ADMESH is a triangulation library;
quadrangulation is a separate project."

This feature is **preprocessing for** quadrangulation, not
quadrangulation itself. The fusion step (`tri2quad`) remains
downstream — handled by CHILmesh, OceanMesh2D, or any other consumer.
ADMESH's output stays pure-tri (spec FR-010). The constitution's
Out-of-scope intent is preserved: ADMESH does not produce quad
elements; it produces tri elements that are easier to fuse. Not a
constitution scope change, no amendment required.

**Result**: Constitution Check passes with two justified deviations
on Principles I and III, both downstream of "this feature is
forward-looking, not a port" and tracked in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/004-quad-prep-smoother/
├── plan.md                # This file
├── spec.md                # Feature specification (clarified 2026-04-25)
├── research.md            # Phase 0 — formulation survey + decisions log
├── data-model.md          # Phase 1 — entity shapes
├── contracts/
│   └── python-api.md      # Phase 1 — public API contract
├── quickstart.md          # Phase 1 — idealized usage
└── checklists/
    └── requirements.md    # Spec-quality checklist (from /speckit-specify)
```

### Source Code (repository root)

```text
admesh/
├── __init__.py            # MODIFIED — re-export smooth_for_quadrangulation, right_iso_quality
├── quad_prep.py           # NEW (~200 LOC) — SVD-invariant FEM target-Jacobian smoother
├── quality.py             # MODIFIED (additive ~30 LOC) — add right_iso_quality(p, t).
│                          #   The existing mesh_quality is NOT touched (spec FR-006).
├── api.py                 # OPTIONAL MODIFY — add for_quads=True kwarg to triangulate()
│                          #   that runs the smoother as the final stage (spec FR-011).
│                          #   May land later; not required for v1 acceptance.
│
│   # Faithful-port surface — UNCHANGED, gated by existing tests:
├── routine.py             # 01 — top-level driver
├── background_grid.py     # 02 — CreateBackgroundGrid
├── distance.py            # 03 — SignedDistanceFunction
├── curvature.py           # 04 — CurvatureFunction
├── medial_axis.py         # 05 — MedialAxisFunction
├── bathymetry.py          # 06 — BathymetryFunction
├── dominate_tide.py       # 07 — DominateTideFunction
├── boundary.py            # 08 — EnforceBoundaryConditions
├── mesh_size.py           # 09 — MeshSizeFunction + Numba solver
├── distmesh.py            # 10 — distmesh2d + fixmesh
├── in_polygon.py          # 12 — InPolygon
├── inpaint.py             # 13 — inpaint_nans
└── … (rest of the additive layer from spec-001 unchanged)

tests/
├── test_quad_prep.py      # NEW — acceptance tests against the 7 SCs
└── fixtures/
    └── quad_prep/
        ├── README.md      # NEW — fixture provenance: synthetic, not MATLAB-derived
        ├── square.npz     # input + reference (p_in, t, fd_callable_id)
        ├── l_shape.npz
        ├── u_shape.npz
        ├── square_with_hole.npz
        ├── annulus.npz
        └── varying_h.npz  # synthetic varying-h domain for SC-003

scripts/
└── render_quad_prep_demo.py  # NEW — pre/post side-by-side renders for the
                              #   5 MVP domains; output to tests/output/quad_prep_*.png

docs/
└── PORTING_NOTES.md       # MODIFIED (one new entry) — leg-not-hypotenuse h-coupling
                           #   convention. Brief: explain that for right-isoceles, the
                           #   in-radius scale is h_bar/sqrt(2) on the leg, not h_bar
                           #   on the hypotenuse, because the post-pairing quad inherits
                           #   the leg as its edge length.
```

**Structure Decision**: Flat `admesh/` layout, fully additive over
the existing module set. No new sub-packages; no new top-level
directories. The `quad_prep.py` module sits alongside the 13
faithful-port modules at the same level — same convention used by
spec-001's additive layer (`api.py`, `fort14.py`, `viz.py`, etc.).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Principle I — feature has no MATLAB reference | The QuADMesh-MATLAB pipeline does not include a pre-quadrangulation right-isoceles smoother; downstream tools (CHILmesh `tri2quad`, OceanMesh2D's quad converter) absorb the mismatch in their own smoothers, paying for it in worse output quality. The whole point of this issue (#15) is to do that work upstream where the cost is lower. There is nothing to faithfully port. | "Wait until QuADMesh-MATLAB grows the equivalent function and port it" — that may never happen; the MATLAB lineage is in maintenance only. We'd be holding ADMESH's quality story hostage to upstream activity that has no signal. |
| Principle III — fixtures synthetic, not MATLAB-derived | Same reason: no MATLAB reference exists to derive fixtures from. The substitution (synthetic golden fixtures + pure-NumPy↔Numba parity test + acceptance assertions on the 7 SCs) preserves the spirit of Principle III (every assertion is reproducible and gates the test suite) without claiming a MATLAB lineage that doesn't exist. | "Skip reference-discipline entirely" — unacceptable; tests must still gate. "Hold the feature until a MATLAB reference exists" — same blocker as above. The synthetic-fixture approach is the only path that ships a working preprocessor on the timeline. |

Both deviations are scoped to this feature and do not propagate. The
13 faithful-port modules continue to be governed by Principles I and
III in their original form; spec-001's additive layer (`api.py` etc.)
follows the same "additive, not a port" pattern this feature inherits.
