# Implementation Plan: Default Size-Field Stack & 0.1.0 Release Readiness

**Branch**: `002-size-field-defaults` | **Date**: 2026-04-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/002-size-field-defaults/spec.md`

## Summary

`admesh.triangulate(domain)` with no size-field arguments today falls through to a uniform `h(p) = base` callable — the visible failure mode being the bad WNAT mesh from the prior session. This feature wires the existing MATLAB-faithful `admesh.mesh_size.build_h(...)` composer (curvature + medial-axis always-on; bathymetry + tide opt-in) as the default Phase-1 size source, attaching `bathymetry` / `tide_period` to the `Domain` dataclass so the call site stays one argument. A graduated test ladder (Tier 0 MVP polygons → Tier 1 ADCIRC Example 10 → Tier 1.5 Shinnecock → Tier 2 WNAT) gates the 0.1.0 release on **structural validity** — positive signed area, boundary-edge preservation, full domain coverage — not on numeric quality. The spec also bundles repository cleanup (constitution walkback, README "in progress" callouts, build-artefact removal) so the 0.1.0 tag has a coherent shippable state.

## Technical Context

**Language/Version**: Python ≥ 3.10 (matches spec 001)
**Primary Dependencies**: NumPy, SciPy (`spatial.Delaunay`, `interpolate.LinearNDInterpolator`, `ndimage.distance_transform_edt`), Numba (existing JIT path for `solve_iter`), Shapely (existing SDF construction in `domain_from_polygon`). No new third-party dependencies.
**Storage**: N/A — pure in-memory library; the only persistent surface is fort.14 file I/O (already specced in 001, extended here for IBTYPE 3 / 4 / 24 paired-edge records).
**Testing**: pytest (existing). New module `tests/test_default_size_field.py` exercises the size-field default path; new module `tests/test_fort14_paired.py` covers the paired-edge BC extensions. The 142-test faithful-port baseline MUST stay green.
**Target Platform**: Linux / macOS / Windows; pure-Python wheel installable in any Python ≥ 3.10 venv. CI matrix unchanged from spec 001.
**Project Type**: Single-package Python library — `admesh/` flat module layout per `CLAUDE.md`.
**Performance Goals**: WNAT regression test (Tier 2) MUST run in < 60 s wall-clock on a developer laptop (no special hardware). Tier 1 (`example10n`, 2716 nodes) MUST run in < 20 s wall-clock. Numba JIT path stays the default for `solve_iter`.
**Constraints**: Constitution Principle I (Faithful Port Before Optimization) is binding — the 13 faithful-port stage modules MUST stay numerically identical. New code is strictly additive over those modules; we wrap `build_h(...)`, we do not reimplement composition. Constitution Principle II (Pure-Python First, No C Extensions) is also binding — no new C/C++/Cython.
**Scale/Scope**: Tier 0 = 5 polygons × < 50 nodes. Tier 1 = 2716 nodes / 4978 elements. Tier 1.5 = ~3K nodes (Shinnecock target). Tier 2 = 9934 nodes / 18578 elements. No fixture beyond 10K nodes for the 0.1.0 release gate.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| **I. Faithful Port Before Optimization** | **PASS** (additive only) | The default-stack wiring wraps the existing `admesh/mesh_size.py::build_h(...)` composer — itself a faithful-port composition. None of the 13 faithful-port stage modules (`distance.py`, `curvature.py`, `medial_axis.py`, `bathymetry.py`, `dominate_tide.py`, `mesh_size.py` solver, `boundary.py`, etc.) are modified. New code lives in `admesh/api.py`, `admesh/fort14.py` (already an additive spec-001 module), and a new `admesh/domains.py` helper (or extension of existing `api.py`). Faithful-port baseline of 142 tests must stay green. |
| **II. Pure-Python First (No C Extensions)** | **PASS** | No C, C++, or Cython introduced. New code uses NumPy + SciPy + existing Numba dispatch. |
| **III. Reference-Test Discipline (NON-NEGOTIABLE)** | **PASS** with documented variance | The default-stack output has no MATLAB-side `.npz` reference fixture for byte-equal comparison because the composition's *outputs* are tested via the existing `build_h` reference fixtures, not via the wrapper. The new acceptance test is structural (topology), not numerical-equality. Documented in `research.md` Decision 5. The faithful-port `.npz` fixtures for individual stages still gate every individual port. |
| **IV. Stage-by-Stage Bottom-Up Porting** | **PASS (no new stages)** | All 5 size-field stages already ported in spec-001 era. Spec 002 is integration, not porting. |
| **V. Report-and-Advance Session Cadence** | **PASS** | Operational concern; this plan ends with `/speckit-tasks` as the next single command. |

**Sub-gate — meta-amendment**: This spec performs FR-017, which walks back the v1.0.1 PATCH amendment to the constitution itself. This is permitted under the Amendment Procedure (Article — Governance). The walkback lands as a v1.0.2 PATCH that explicitly notes the size-field default as a precondition for the fort.14 contract being "release-ready"; the v1.0.1 framing remains in the Amendments log for transparency, but is superseded.

**No violations to track in Complexity Tracking.** All deviations from default principles are minor and documented in `research.md`.

## Project Structure

### Documentation (this feature)

```text
specs/002-size-field-defaults/
├── plan.md                    # This file (Phase 2 entry point)
├── research.md                # Phase 0 output — design decisions
├── data-model.md              # Phase 1 output — entity shapes
├── quickstart.md              # Phase 1 output — user idioms
├── contracts/
│   ├── python-api-default-stack.md   # Public API surface for the default stack
│   └── fort14-paired-edge.md          # Reader/writer contract for IBTYPE 3/4/24
├── checklists/
│   └── requirements.md        # Spec quality checklist (already populated)
├── spec.md                    # Feature spec (already populated, /speckit-clarify-resolved)
└── tasks.md                   # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
admesh/                                    # existing package; flat layout per CLAUDE.md
├── __init__.py                            # extend public API re-exports
├── api.py                                 # extend: Domain new fields, triangulate() new kwargs, wiring to build_h
├── boundary_types.py                      # extend: new IBTYPE members (3, 4, 13, 24) OR keep as int
├── fort14.py                              # extend: paired-edge IBTYPE 3/24 reader+writer
├── viz.py                                 # unchanged
├── size_field.py                          # unchanged (Phase-2 user-contribs composer)
├── boundary.py                            # unchanged (faithful-port stage 8)
├── bathymetry.py                          # unchanged (faithful-port stage 6)
├── curvature.py                           # unchanged (faithful-port stage 4)
├── medial_axis.py                         # unchanged (faithful-port stage 5)
├── dominate_tide.py                       # unchanged (faithful-port stage 7)
├── mesh_size.py                           # unchanged — build_h(...) is the wrapped composer
├── distmesh.py                            # unchanged (faithful-port stage 10)
├── (...other faithful-port stage modules unchanged)

tests/
├── test_default_size_field.py             # NEW — Tier 0/1/2 ladder, structural-validity gate
├── test_fort14_paired.py                  # NEW — IBTYPE 3/24 round-trip; example10n round-trip
├── fixtures/fort14/adcirc_examples/
│   ├── wetting_and_drying_test.14         # added in this commit; ADCIRC Example 10
│   ├── wnat_test.14                       # already in repo (Tier 2)
│   ├── shinnecock.14                      # NEW — pulled during /speckit-implement (Tier 1.5)
│   └── PROVENANCE.md                      # NEW — provenance + license per fixture

scripts/
└── (unchanged — existing benchmark + fixture export scripts)

docs/
├── PORTING_NOTES.md                       # extend: paired-edge BC reader notes
└── (other docs unchanged)

.specify/memory/constitution.md            # FR-017 walkback (v1.0.1 → v1.0.2)
README.md                                  # FR-018 walkback ("0.1.0 in progress" callouts)
```

**Structure Decision**: Single-package library, flat module layout under `admesh/`. New code extends existing modules; only two new files (the two new test modules + the PROVENANCE manifest, plus a new contracts/ directory under the spec). The faithful-port stage modules are not touched.

## Complexity Tracking

*No Constitution violations to justify — this section is intentionally blank.*

The plan introduces no new third-party dependencies, no new C/C++ code, and no new top-level package directories. The `Domain` dataclass and `BoundarySegment` dataclass each gain ≤ 3 optional fields, defaulting to `None` for backward compat. The `BoundaryType` enum gains 4 new members (IBTYPE 3, 4, 13, 24) as named codes; unmapped IBTYPE codes continue to round-trip as plain `int` per spec-001's existing convention.
