# Implementation Plan: Pythonic API Layer + fort.14 I/O + chilmesh Integration

**Branch**: `001-pythonize-and-fort14-integration` | **Date**: 2026-04-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-pythonize-and-fort14-integration/spec.md`

## Summary

Layer a Pythonic public API on top of the existing faithful MATLAB port without altering the port's numerical behavior. The new surface is composed of: a `Mesh` dataclass and `Domain` builder; a top-level `admesh.triangulate(domain, **opts) -> Mesh` entry point; an ADCIRC fort.14 reader/writer with lossless round-trip; an optional `mesh.plot()` matplotlib helper; and a documented two-phase size-field composition that lets power users add contributions on top of the MATLAB-faithful built-in stack. The faithful-port surface (module-level snake_case functions in `admesh/*.py`) remains callable and numerically unchanged — Constitution Principle I is preserved by making the Pythonic layer strictly additive.

The chilmesh integration is decided per the spec's recommendation (Option A): admesh2D owns fort.14 export; chilmesh consumes fort.14 as it already does. No cross-imports, no new install-graph entanglement.

## Technical Context

**Language/Version**: Python ≥3.10 (already pinned in `pyproject.toml`)
**Primary Dependencies**: NumPy ≥1.24, SciPy ≥1.11, Numba ≥0.58, Shapely ≥2.0 (existing); matplotlib ≥3.7 added as **optional** extra `[viz]`
**Storage**: ADCIRC fort.14 mesh files (text format, ASCII-only). No database.
**Testing**: pytest (existing 142-test suite); new tests for the Pythonic surface, fort.14 I/O, and round-trip
**Target Platform**: Linux, macOS, Windows (pure Python + Numba; no C extensions)
**Project Type**: Python library (single project — no frontend/backend split)
**Performance Goals**: No new perf gates in v1. Existing `min_q ≥ 0.30`, `mean_q ≥ 0.60` quality gates remain. fort.14 reader/writer designed to allow streaming as a non-breaking future extension (FR-061-style "do not foreclose"), but in-memory implementation is acceptable for v1.
**Constraints**:
- Must not change the faithful-port surface output bit-for-bit (FR-008, FR-018)
- matplotlib is optional — `import admesh` MUST succeed without it (FR-020)
- 1-based ↔ 0-based index conversion lives strictly at the I/O boundary (FR-013)
- Bathymetry sign flip (positive-up internal ↔ positive-down ADCIRC) lives strictly at the I/O boundary
**Scale/Scope**: MVP test domains are <100k nodes. Streaming-capable design for >10M is forward-compatible but not implemented in v1.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Principles I–V from `.specify/memory/constitution.md` (v1.0.0, 2026-04-24):

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Faithful Port Before Optimization | ✅ Preserved | The Pythonic layer is *additive*. FR-008/FR-018/FR-019 mandate the snake_case MATLAB-mirror surface remains callable with numerically identical output. The 142-test suite continues to gate `main`. |
| II. Pure-Python First (No C Extensions) | ✅ Preserved | No new C extensions. matplotlib is pure-Python wheel. |
| III. Reference-Test Discipline | ✅ Preserved | Faithful-port tests untouched. New tests for the Pythonic layer use the same fixture pattern (`tests/fixtures/<area>/<case>.npz`) where applicable. fort.14 round-trip tests use a curated reference corpus (per SC-005). |
| IV. Stage-by-Stage Bottom-Up Porting | ✅ N/A for new layer | The faithful port is complete (post-session 6). This feature builds on top — no porting work in scope. |
| V. Report-and-Advance Session Cadence | ✅ Preserved | Standard cadence applies. |

**Deviations from the constitution's "Out-of-scope" list (Development Workflow & Quality Gates, line 254-259):**

The constitution lists two items as "explicitly deferred":
1. **`ADCIRC .fort.14 I/O`** — this feature lifts the deferral. fort.14 export is a *prerequisite* for the chilmesh integration the user is now exploring; FR-009..FR-015 own the lift.
2. **`GUI / visualization beyond test-output PNGs`** — partially lifted: a single `mesh.plot()` matplotlib helper is in scope (FR-020/FR-021); a richer visualization module is **not** in scope and remains deferred.

These are not principle violations — they are scope changes to the deferred-list. Both are tracked in **Complexity Tracking** below. A follow-up PATCH amendment to `.specify/memory/constitution.md` should remove fort.14 from the deferred list and reword the visualization line to "GUI beyond `mesh.plot()` matplotlib helper" once this feature lands.

**Result**: Constitution Check passes with two documented deferred-list scope changes. No principle violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-pythonize-and-fort14-integration/
├── plan.md              # This file
├── spec.md              # Feature specification (clarified 2026-04-24)
├── research.md          # Phase 0 — design decisions
├── data-model.md        # Phase 1 — entity shapes
├── contracts/
│   └── python-api.md    # Phase 1 — public API contract
├── quickstart.md        # Phase 1 — idealized usage
└── checklists/
    └── requirements.md  # Spec-quality checklist (from /speckit-specify)
```

### Source Code (repository root)

```text
admesh/
├── __init__.py             # Re-exports public API: triangulate, Mesh, Domain, read_fort14, BoundaryType
├── api.py                  # NEW — Mesh, Domain, BoundarySegment dataclasses + triangulate() entry point
├── fort14.py               # NEW — ADCIRC fort.14 reader/writer
├── boundary_types.py       # NEW — BoundaryType IntEnum (OPEN, MAINLAND, MAINLAND_FLUX, ISLAND, WALL)
├── size_field.py           # NEW — two-phase size-field composition (Phase 1 built-ins, Phase 2 user contributions)
├── viz.py                  # NEW — Mesh.plot() implementation (lazy matplotlib import)
│
│   # Faithful-port surface — unchanged, untouched, gated by existing tests:
├── routine.py              # 01 — ADmeshRoutine
├── background_grid.py      # 02
├── distance.py             # 03
├── curvature.py            # 04
├── medial_axis.py          # 05
├── bathymetry.py           # 06
├── dominate_tide.py        # 07
├── boundary.py             # 08
├── mesh_size.py            # 09
├── distmesh.py             # 10
├── quality.py              # 11
├── in_polygon.py           # 12
├── inpaint.py              # 13
└── domains.py              # MVP test-domain helpers

tests/
├── test_api.py             # NEW — Mesh / Domain / triangulate() shape and behavior
├── test_fort14_roundtrip.py    # NEW — write→read→assert equality on canonical domains
├── test_fort14_reader_errors.py    # NEW — malformed-input corpus (SC-007)
├── test_fort14_reference_corpus.py # NEW — ADCIRC examples + community meshes (SC-005)
├── test_size_field_composition.py  # NEW — two-phase combiner semantics
├── test_viz.py             # NEW — plot() smoke + ImportError when matplotlib missing
│
│   # Existing faithful-port tests — unchanged:
├── test_matlab_port.py
├── test_mvp_domains.py
├── test_smoke.py
└── test_<stage>.py × 13

tests/fixtures/
├── fort14/
│   ├── adcirc_examples/    # NEW — ADCIRC v55 documentation example meshes
│   ├── community/          # NEW — at least 3 real-world meshes (SC-005)
│   └── malformed/          # NEW — negative-test corpus (SC-007)
└── <stage>/                # Existing reference fixtures, unchanged

scripts/
└── (existing)              # bench, render, MATLAB fixture export — unchanged

docs/
└── PORTING_NOTES.md        # Existing log; no new entries required for this feature
```

**Structure Decision**: Single-project Python library, additive modules under `admesh/`. The 13 stage modules of the faithful port are untouched. Five new modules (`api.py`, `fort14.py`, `boundary_types.py`, `size_field.py`, `viz.py`) own the Pythonic layer. New tests under `tests/test_*.py` and new fixtures under `tests/fixtures/fort14/`. No new top-level directories.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| fort.14 I/O lifted from constitution's deferred list | The dominant downstream consumer of an ADMESH mesh is an ADCIRC simulation; chilmesh and other tooling read fort.14. Without the reader/writer the Pythonic layer has no canonical persistence path, and the user's chilmesh integration question cannot be answered. | Punting fort.14 to a later spec was rejected because every user story (P1, P2, P3) bottoms out in writing or reading a `.14` file — making it the critical-path artifact for v1, not a "nice to have." |
| `mesh.plot()` matplotlib helper added (constitution defers visualization) | Story 1 Acceptance Scenario 3 requires a useful `__repr__`; users in REPL/notebook workflows expect a one-liner that draws the mesh. Without it, the Pythonic layer feels less complete than what users get from any other meshing library. | A pure `__repr__`-only surface (Option A in the clarification) was rejected by the user. A full visualization module (Option C) was rejected as scope creep — it's a known follow-up. The chosen middle (Option B) keeps matplotlib **optional**, so headless installs are unaffected and the install-graph rule is preserved. |

Both deviations are scope changes to the constitution's "explicitly deferred" list, not principle violations. A follow-up PATCH amendment will reword that list.
