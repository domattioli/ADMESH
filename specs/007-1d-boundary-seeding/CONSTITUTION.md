# Spec 007 Constitution — 1D Distmesh Boundary Seeding

**Scope**: Before the 2D interior seeding pass, run a 1D distmesh equilibrium along each boundary segment to produce evenly-spaced seed points adapted to the local size function `fh`. Improves node clustering on short boundary features (e.g., notch walls in `NOTCHED_RECTANGLE`). Optional (kwarg-controlled).  
**Spec Document**: `specs/007-1d-boundary-seeding/spec.md`  
**Related Specs**: ↑ Spec 001 (`Domain` dataclass extended), Spec 002 (1D seeding runs before the default size-field 2D pass) | ↓ None

## How This Constitution Relates to the Project Constitution

Extends Article I of `docs/governance/CONSTITUTION.md`:

- **Article I** (Faithful Port): There is a MATLAB precedent — `createInitialPointList.m` in `01_ADMESH_Library/10_Distmesh_2d/` at commit `19b2eb9`. Article I's Rule 1 applies: port as `_seed_boundary_1d()` or `create_initial_point_list()`.
- **Article III** (Reference-Test Discipline): MATLAB-side fixture derivable from `createInitialPointList.m`. If fixture capturable, use it; otherwise use synthetic golden fixture with visual verification.
- **Article IV** (Bottom-Up): The 1D seeder is a leaf utility. Port it first, then integrate into `routine.triangulate()`.

No deviations from the main constitution.

## Core Principles

### I. Faithful Port of createInitialPointList.m

The 1D boundary seeder is a faithful Python port of `01_ADMESH_Library/10_Distmesh_2d/createInitialPointList.m`. The algorithm — 1D truss-force equilibrium on each boundary segment — must match MATLAB behavior within floating-point tolerance on the reference test case.

**Why**: Deviating from the MATLAB 1D seeder introduces discrepancies in initial-point distribution that cascade into 2D mesh quality.

### II. Boundary-Aware Seeding Without Hardcoded Thresholds

The 1D distmesh equilibrium naturally adapts spacing to the local `fh` value. No hardcoded "short segment" threshold. Every boundary segment gets 1D seeding; short segments get more seeds because `fh` is smaller there relative to segment length.

**Why**: The threshold-based `short_factor * h0` seeder was rejected because it degraded long edges when incorrectly flagged. The 1D distmesh avoids this by using physics, not a threshold.

### III. Preservation of 2D Quality Gates

The 1D seeding must not degrade 2D triangle quality on any existing MVP domain. Quality gates from Spec 002 (min_q ≥ 0.30, mean_q ≥ 0.60) must still be met. The primary test case (NOTCHED_RECTANGLE) must show improved notch-wall node density vs. the no-1D-seeding baseline.

**Why**: An enhancement that improves one test case while degrading the other four is net-negative.

## Domain-Specific Constraints

- **Target MATLAB function**: `createInitialPointList.m @ 19b2eb9` in `01_ADMESH_Library/10_Distmesh_2d/`.
- **`Domain.boundary_polygon`**: Add optional `boundary_polygon: NDArray[np.float64] | None` field to `Domain` dataclass.
- **Implementation location**: `_seed_boundary_1d(polygon, fh, h0) -> NDArray` in `admesh/routine.py` (or `admesh/boundary_seed.py`).
- **`pfix` integration**: 1D-seeded boundary nodes become `pfix` (fixed points) in the 2D distmesh call.
- **No change to 2D distmesh internals**: `admesh/distmesh.py` is not modified for 1D seeding.

## Quality Gates & Workflow

**Definition of done**:

- [ ] `_seed_boundary_1d(polygon, fh, h0)` or equivalent implemented and tested
- [ ] `Domain.boundary_polygon` field added to `Domain` dataclass
- [ ] `NOTCHED_RECTANGLE` predefined domain has `boundary_polygon` set
- [ ] `Domain.from_mesh()` populates `boundary_polygon` from outer ring
- [ ] `NOTCHED_RECTANGLE` test: notch-wall node count ≥ expected
- [ ] Quality gates preserved: min_q ≥ 0.30, mean_q ≥ 0.60 on all 5 MVP domains with 1D seeding on
- [ ] `pytest tests/ -q` green
- [ ] `docs/PORTING_NOTES.md` entry for `createInitialPointList.m → _seed_boundary_1d()`
- [ ] If MATLAB fixture capturable: reference test using `.npz` fixture, `atol=1e-6`

**Versioning policy**:
- **MAJOR**: Changing the 1D distmesh algorithm
- **MINOR**: Exposing 1D seeding parameters in public `triangulate()` API
- **PATCH**: Bug fix, tolerance tweak, `pfix` integration improvement

## Governance

**Amendment procedure**: PR against this file. If amendment changes whether 1D seeding is on by default, it requires Spec 002 CONSTITUTION.md review.

**Compliance review**: Every PR touching `_seed_boundary_1d`, `Domain.boundary_polygon`, or `routine.triangulate()` must verify the NOTCHED_RECTANGLE node-count test and 5-domain quality gates.

## Amendments Log

### 2026-05-11 — v1.0.0 — Initial constitution

Synthesized from `spec.md`, `plan.md`, `data-model.md`. Principle I links this spec to the MATLAB source, making it a proper faithful port. Principle II addresses historical rejection of threshold-based approaches.

---
**Version**: 1.0.0 | **Ratified**: 2026-05-11 | **Last Amended**: 2026-05-11
