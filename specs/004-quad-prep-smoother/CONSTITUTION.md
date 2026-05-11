# Spec 004 Constitution — Pre-Quadrangulation Triangle Smoother

**Scope**: Implement an optional post-processing smoother that transforms ADMESH triangular meshes toward right-isosceles triangle shapes, preparing them for downstream quad conversion or quality improvement workflows.  
**Spec Document**: `specs/004-quad-prep-smoother/spec.md`  
**Related Specs**: ↑ Spec 001 (consumes `Mesh` object), Spec 002 (smoother runs on default-stack output) | ↓ Future quad-conversion spec

## How This Constitution Relates to the Project Constitution

This spec introduces a **non-port** feature — there is no MATLAB `smoothquad.m` equivalent. Documented deviations from Articles I and III:

- **Article I** (Faithful Port) adaptation: No MATLAB source to port. The smoother is a new feature extending Python ADMESH beyond the MATLAB baseline. Allowed post-v1 as long as the 13 faithful-port stage modules are unchanged.
- **Article III** (Reference-Test Discipline) adaptation: No MATLAB `.npz` fixture possible. Substituted with: (a) synthetic golden fixtures, (b) NumPy/Numba parity test (mirroring the `mesh_size.py` pattern), (c) 7 acceptance criteria from spec.

Constitution Principle I preserved: the 13 faithful-port stage modules are not modified.

## Core Principles

### I. Optional Enhancement (Non-Port)

The smoother is opt-in only: `admesh.smoother.smooth(mesh)` or `triangulate(..., smooth=True)`. Never applied by default. Does not modify the primary meshing pipeline.

**Why**: The faithful port must be the default experience. Opt-in enhancements are additive.

### II. Triangle-Quality Optimization

The smoother must improve or preserve quality:
- Aspect ratio (primary): output must have lower mean aspect-ratio deviation from target than input.
- Element quality (secondary): min_q and mean_q must not decrease after smoothing.
- Convergence: must terminate in finite iterations, never diverge.

**Why**: A smoother that degrades quality is worse than no smoother.

### III. Right-Isosceles as Canonical Target

The right-isosceles algorithm (iteratively adjusts vertices to minimize deviation from 45-45-90 angles) is the default. An equilateral-target algorithm is a valid alternative sharing the same API (`target="equilateral"` kwarg), but right-isosceles is the primary deliverable.

**Why**: Right-isosceles triangles are the natural precursor for structured quad conversion.

### IV. Numerical Parity Between Reference and Accelerated Paths

A pure-NumPy reference `_smooth_iter_py()` and Numba-accelerated `_smooth_iter_nb()` must produce results within `atol=1e-10` on fixed inputs. Pattern mirrors `admesh/mesh_size.py`.

**Why**: The parity test is the regression guard for silent Numba divergence.

## Domain-Specific Constraints

- **Opt-in only**: No default activation.
- **No modification of stage modules**: `admesh/curvature.py`, `admesh/distmesh.py`, etc. are read-only.
- **Synthetic fixtures**: `tests/fixtures/quad_prep/` with README. No MATLAB side.
- **Convergence guard**: Max iterations kwarg (default 100); early exit on displacement norm.
- **No new mandatory dependency**: Numba already a dependency.

## Quality Gates & Workflow

**Definition of done** (all 7 acceptance criteria from spec.md):

- [ ] `admesh.smoother.smooth(mesh, target="right_isosceles") -> Mesh` exists and exported
- [ ] Right-isosceles target reduces mean angle deviation from 45°/45°/90° vs. input
- [ ] Element quality does not decrease: `smooth(mesh).min_q >= input_mesh.min_q - 1e-3`
- [ ] Convergence in ≤ max_iter iterations on all MVP domains
- [ ] Parity test: `_smooth_iter_py` and `_smooth_iter_nb` agree within `atol=1e-10`
- [ ] Synthetic fixtures in `tests/fixtures/quad_prep/` with README
- [ ] `pytest tests/ -q` green
- [ ] No regression when smoother is NOT applied (default path unchanged)

**Versioning policy**:
- **MAJOR**: Changing the default target algorithm
- **MINOR**: Adding a new target algorithm, exposing new convergence params in public API
- **PATCH**: Bug fix, tolerance tweak, Numba path improvement

## Governance

**Amendment procedure**: PR against this file. If the amendment enables the smoother by default, it requires a main constitution Amendments log entry.

**Compliance review**: Every PR touching `admesh/smoother.py` must run the parity test and verify all 7 acceptance criteria.

## Amendments Log

### 2026-05-11 — v1.0.0 — Initial constitution

Synthesized from `spec.md`, `plan.md`, `data-model.md`. Codifies the non-port deviation from Article I and the reference-test adaptation. Adds Principle IV (NumPy/Numba parity) consistent with `mesh_size.py` pattern already in the project.

---
**Version**: 1.0.0 | **Ratified**: 2026-05-11 | **Last Amended**: 2026-05-11
