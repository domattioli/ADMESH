# Architecture overview

One-screen tour of the ADMESH module layout. Authoritative
architecture reference is
[`CLAUDE.md`](https://github.com/domattioli/ADMESH/blob/main/CLAUDE.md);
the spec-level contracts live under
[`specs/`](https://github.com/domattioli/ADMESH/tree/main/specs).

For the *flow* through these modules, see [Pipeline](Pipeline.md).
For *what each concept means*, see [Concepts](Concepts.md).

---

## Two layers

```
┌──────────────────────────────────────────────────────────────────────┐
│  Pythonic API + I/O                          ◀── spec-001 + spec-002 │
│  api.py · domains.py · loaders.py · fort14.py · boundary_types.py    │       additive surface
│  size_field.py · registry.py · viz.py · quad_prep.py · valence.py    │       (post-v1 specs land here)
├──────────────────────────────────────────────────────────────────────┤
│  13 faithful-port stage modules (admesh/*.py)        ◀── locked      │
│  routine · background_grid · distance · curvature · medial_axis ·    │       numerically identical to
│  bathymetry · dominate_tide · boundary · mesh_size · distmesh ·      │       MATLAB reference
│  quality · in_polygon · inpaint                                      │
└──────────────────────────────────────────────────────────────────────┘
```

Per
[Constitution Article II](https://github.com/domattioli/ADMESH/blob/main/docs/governance/CONSTITUTION.md):
the bottom layer is locked — its job is to match MATLAB to numerical
tolerance. New features extend via the top layer. The top layer has
grown since spec-001 / spec-002 shipped, and any of the open specs
(004 quad_prep smoother, 007 1D boundary seeding, 008 Gmsh I/O) will
add to it without touching the locked layer.

---

## The 13 stages (locked layer)

One-to-one mapped to MATLAB `01_ADMESH_Library/`:

| # | Module | MATLAB origin | Role |
|---|---|---|---|
| 01 | [`routine.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/routine.py) | `ADmeshRoutine.m` | top-level driver |
| 02 | [`background_grid.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/background_grid.py) | `CreateBackgroundGrid.m` | structured grid over the domain |
| 03 | [`distance.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/distance.py) | `SignedDistanceFunction.m` | SDF + point-list utilities |
| 04 | [`curvature.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/curvature.py) | `CurvatureFunction.m` | boundary-curvature size contribution |
| 05 | [`medial_axis.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/medial_axis.py) | `MedialAxisFunction.m` + FMM | medial-axis distance + tri-distance |
| 06 | [`bathymetry.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/bathymetry.py) | `BathymetryFunction.m` | depth-driven size contribution |
| 07 | [`dominate_tide.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/dominate_tide.py) | `DominateTideFunction.m` | tide-period size contribution |
| 08 | [`boundary.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/boundary.py) | `EnforceBoundaryConditions.m` | BC enforcement, polygon structure |
| 09 | [`mesh_size.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/mesh_size.py) | `MeshSizeFunction.m` + iterative solver | size-field assembly + Numba PDE |
| 10 | [`distmesh.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/distmesh.py) | `distmesh2d.m` + `fixmesh.m` | Persson distmesh triangulation |
| 11 | [`quality.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/quality.py) | `MeshQuality.m` | per-element quality metrics |
| 12 | [`in_polygon.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/in_polygon.py) | `InPolygon.m` | point-in-polygon |
| 13 | [`inpaint.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/inpaint.py) | `inpaint_nans.m` | NaN inpainting helper |

---

## Additive surface (above the locked layer)

This is the layer spec-001 and spec-002 grew, and where future specs
land. Strictly *over* the 13 stages — never replaces them.

| Module | Role | Origin |
|---|---|---|
| [`api.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/api.py) | `Domain`, `Mesh`, `triangulate()`, `domain_from_polygon()`, default-stack kwargs | spec-001 + spec-002 |
| [`domains.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/domains.py) | analytical example domains (unit-disk, unit-square, annulus, L-shape, notched-rectangle) | spec-001 |
| [`loaders.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/loaders.py) | external file → `Domain` adapters | spec-001 |
| [`fort14.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/fort14.py) | ADCIRC `fort.14` reader + writer (incl. paired-edge BC records) | spec-001 + spec-002 |
| [`boundary_types.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/boundary_types.py) | `BoundaryType` enum (IBTYPE codes) | spec-002 |
| [`size_field.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/size_field.py) | two-phase composer (Phase 1 built-ins `min`-only; Phase 2 user contribs configurable reduction) | spec-001 + spec-002 |
| [`registry.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/registry.py) | bridge into [ADMESH-Domains](https://github.com/domattioli/ADMESH-Domains) registry | spec-005 (now migrated to sibling repo) |
| [`viz.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/viz.py) | matplotlib plotting helpers (opt-in via `pip install admesh2D[viz]`) | spec-001 |
| [`quad_prep.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/quad_prep.py) | pre-quadrangulation triangle smoother (scaffold) | spec-004 (scoped, not on v1 path) |
| [`valence.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/valence.py) | per-vertex valence utilities for smoothing / quad work | spec-004 |
| [`_structural_validity.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/_structural_validity.py) | test helper: positive area / SDF / coverage gates | spec-002 |

---

## Test ladder

Defined in
[`specs/002-size-field-defaults/quickstart.md`](https://github.com/domattioli/ADMESH/blob/main/specs/002-size-field-defaults/quickstart.md):

| Tier | Fixture | Gate |
|---|---|---|
| **0** — synthetic | `tests/fixtures/<stage>/*.npz` + small `fort.14` cases | every PR; numerical-equivalence to MATLAB |
| **1** — small ADCIRC | `wetting_and_drying_test.14` | every PR; round-trip + structural validity |
| **2** — Western North Atlantic | `wnat_test.14` (1.2 MB, 9,934 nodes) | every PR; ≤ 60 s wall-clock; structural-validity gate green (FR-016) |

Tier-2 is the **0.1.0 release gate**. Currently xfailed pending
[#10](https://github.com/domattioli/ADMESH/issues/10) and
[#11](https://github.com/domattioli/ADMESH/issues/11) per
[Roadmap](Roadmap.md).

A 4-panel WNAT shape-q histogram (source MATLAB vs. fresh Python
mesh) is regenerated by `pytest` runs into `tests/output/` —
inspect locally after a Tier-2 run.

---

## How a session adds a feature

The repo uses [spec-kit](https://github.com/github/spec-kit) for
non-trivial features. Each numbered spec under `specs/NNN-…` is a
self-contained design package:

```
specs/NNN-feature-slug/
├── spec.md             — feature specification
├── plan.md             — implementation plan
├── research.md         — background investigation (optional)
├── data-model.md       — types, dataclasses, file formats
├── contracts/*.md      — public-API + file-format contracts
├── quickstart.md       — minimum-viable usage walkthrough
├── tasks.md            — ordered task list (one commit per task)
└── CONSTITUTION.md     — feature-scoped governance amendment
```

Tasks are worked one at a time, with one commit per task and tests
landing alongside the implementation. See
[`specs/002-size-field-defaults/`](https://github.com/domattioli/ADMESH/tree/main/specs/002-size-field-defaults)
for a worked example and [Contributing](Contributing.md) for the
contributor protocol.
