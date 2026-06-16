# Spec 002 Constitution — Default Size-Field Stack & 0.1.0 Release Readiness

**Scope**: Wire the 4 existing MATLAB-faithful size-field stages (curvature, medial-axis, bathymetry, tide) as the always-on default for `triangulate()`. Define release-readiness tiers (Tier-0 polygon domains, Tier-1 ADCIRC Example 10, Tier-2 WNAT).  
**Spec Document**: `specs/002-size-field-defaults/spec.md`  
**Related Specs**: ↑ Spec 001 (fort.14 I/O must work) | ↓ Issue #10 (Tier-1/2 unblock), Spec 007 (1D seeding improves Tier-0 quality)

## How This Constitution Relates to the Project Constitution

Extends Article I of `docs/governance/CONSTITUTION.md`:

- **Article I** (Faithful Port) extended: the "faithful port" now includes the default composition of the 4 size-field stages, not just individual stage functions. The composition rule (min-stack) mirrors MATLAB's `mesh_size.build_h()` behavior.
- **Article III** (Reference-Test Discipline) adapted: no MATLAB `.npz` reference exists for the composition's *output*. The substitution (structural testing + stage-level fixtures) is documented as Decision 5 in `research.md`. This is a JUSTIFIED DEVIATION, not a principle violation.
- **Article V** (Session Cadence): The tier framework (Tier-0 / Tier-1 / Tier-2) is this spec's mechanism for the "report-and-advance" pattern — Tier-0 ships, Tier-1/2 are xfail with tracked issues.

The 13 faithful-port stage modules are **immutable** in this spec. All changes live in `admesh/api.py` and new test files. Constitution Principle I is preserved.

## Core Principles

### I. Default Stack as Flagship

`admesh.triangulate(domain)` with no size-field arguments produces a feature-aware mesh by default: curvature and medial-axis are always-on; bathymetry and tide activate when `Domain` carries the corresponding data. Callers who want uniform `h` must opt out explicitly (`enable_curvature=False, enable_medial_axis=False`).

**Why**: The MATLAB ADMESH was designed to produce feature-aware meshes. Shipping a Python port that defaults to uniform `h` would be a misleading downgrade.

### II. Layer-by-Layer Composition (Faithful)

The built-in stages (curvature, medial-axis, bathymetry, tide) are `min`-stacked in the same order as MATLAB's `build_h()` — non-negotiable. User contributions are applied *after* the built-in stack via a user-supplied combiner (default `np.minimum.reduce`). The built-in stack is never partially applied or reordered.

**Why**: Reordering or skipping stages changes the mesh output in ways that cannot be compared to MATLAB, violating the port guarantee.

### III. Tier-Based Release Readiness

- **Tier-0** (5 MVP polygon domains): Must pass. min_q ≥ 0.30, mean_q ≥ 0.60, no vertex outside domain bbox. This is the 0.1.0 release gate.
- **Tier-1** (ADCIRC Example 10, ~2700 nodes): `xfail` pending Issue #10.
- **Tier-2** (WNAT, ~10K nodes): `xfail` pending Issue #10.

Tier-1 and Tier-2 become release blockers for 0.2.0 after Issue #10 resolves.

**Why**: Shipping with known xfail tests and a tracked issue is better than blocking the release on a hard numerical problem.

### IV. Numerical Stability Under Composition

When the size-field composition breaks (NaN, extreme values from medial-axis, bathymetry convex-hull extrapolation artifacts), the pipeline must fail loudly with a diagnostic message — never silently produce a mesh that overshoots the domain or contains degenerate elements.

**Why**: Silent failure (degenerate elements, quality=0.0) is harder to debug than a loud assertion.

## Domain-Specific Constraints

- **Always-on default**: Curvature + medial-axis on by default; disable via explicit kwargs. Bathymetry/tide activate only when `Domain` carries the data.
- **Immutable stage modules**: The 13 stage files may not be changed in this spec. All new logic in `admesh/api.py`.
- **NaN handling**: `inpaint_nans` fills bathymetry NaN zones. Extrapolation outside convex hull must be bounded.
- **Tier-0 quality gate**: Every Tier-0 test must pass without `xfail`. Tier-1/2 tests may remain `xfail(reason="Issue #10")`.

## Quality Gates & Workflow

**Definition of done** (Tier-0; required for 0.1.0):

- [ ] `triangulate(domain)` with no size-field kwargs produces feature-aware mesh on all 5 MVP domains
- [ ] min_q ≥ 0.30, mean_q ≥ 0.60 on all 5 MVP domains with default stack
- [ ] No vertex outside domain bounding box on Tier-0
- [ ] `tests/test_default_size_field.py` Tier-0 tests pass (no xfail)
- [ ] Tier-1/2 tests exist but are `xfail(reason="Issue #10")`
- [ ] User contributions extension point documented with example
- [ ] `pytest tests/ -q` green
- [ ] No regression on spec-001 fort.14 round-trip tests
- [ ] `docs/PORTING_NOTES.md` entry for the composition's deviation from Article III

**Versioning policy**:
- **MAJOR**: Changing the default stack order or removing a stage from the default
- **MINOR**: Adding a new stage to the stack, exposing a new kwarg for stage control
- **PATCH**: Bug fix, NaN handling improvement, tolerance tweak

## Governance

**Amendment procedure**: PR against this file. If the amendment changes the default stack composition, it must also update `docs/governance/CONSTITUTION.md` Amendments log.

**Compliance review**: Every PR touching `admesh/api.py::_build_default_size_field` or `tests/test_default_size_field.py` must verify Tier-0 quality gates before merge.

## Amendments Log

### 2026-05-11 — v1.0.0 — Initial constitution

Synthesized from `spec.md`, `plan.md`, `research.md` (Decision 5). Tier framework and justified deviation from Article III are the key new elements. Constitution Principle I preserved: 13 faithful-port stage modules unchanged.

---
**Version**: 1.0.0 | **Ratified**: 2026-05-11 | **Last Amended**: 2026-05-11
