# Spec 003 Constitution — Fix Domain.from_mesh Ring Sorting

**Scope**: One targeted bug fix: `Domain.from_mesh()` extracts boundary rings in the wrong order when the source mesh has holes. Fix ring sorting to produce outer-ring-first ordering.  
**Spec Document**: `specs/003-fix-outer-ring-sorting/spec.md`  
**Related Specs**: ↑ Spec 001 (fixes a bug in the `Domain` path) | ↓ Spec 002 (Tier-0 domains depend on correct ring ordering)

## How This Constitution Relates to the Project Constitution

Directly reinforces Articles I and III of `docs/governance/CONSTITUTION.md`:

- **Article I** (Faithful Port): The bug is a deviation from MATLAB's ordering; fixing it restores fidelity.
- **Article III** (Reference-Test Discipline): A new test must confirm the fix on the annulus domain.

No deviations. This is the simplest kind of spec — a single function fix with a new test.

## Core Principles

### I. One Bug, One Fix

This spec has exactly one deliverable: fix the ring-ordering bug in `Domain.from_mesh()`. No other changes to `admesh/api.py`, no new features, no refactoring of unrelated code.

**Why**: Bug-fix specs with unbounded scope create merge conflicts and test debt. A contained fix is reviewable, revertable, and attributable.

### II. Correctness Preservation (No Regression)

The fix must not degrade quality on any existing MVP domain. All existing passing tests must remain passing. The ring-ordering fix improves the annulus and hole-domain cases; it does not change single-ring cases.

**Why**: A bug fix that breaks a neighboring code path is a net negative.

## Domain-Specific Constraints

- **Target function**: `admesh/api.py::Domain.from_mesh()` ring extraction logic only.
- **Test case**: Annulus domain must pass; hole ring must be second in the boundary list.
- **No new dependencies**: Uses only existing NumPy/Shapely utilities.
- **No API change**: `Domain.from_mesh()` signature unchanged; behavior corrected.

## Quality Gates & Workflow

**Definition of done**:

- [ ] `Domain.from_mesh(annulus_mesh)` returns boundaries with outer ring first, hole ring(s) second
- [ ] New test in `tests/test_api.py` or `tests/test_domains.py` covers ring ordering on annulus
- [ ] All existing tests pass (no regression)
- [ ] `pytest tests/ -q` green
- [ ] No change to `Domain.from_mesh()` signature or return type

**Versioning policy**: PATCH fix only — behavior correction, no API change.

## Governance

**Amendment procedure**: Only if the fix scope expands. Scope expansion triggers a MINOR bump.

**Compliance review**: PR must run the full test suite. Ring-ordering test is mandatory (not optional/xfail).

## Amendments Log

### 2026-05-11 — v1.0.0 — Initial constitution

Synthesized from `spec.md`. Simple bug-fix spec; two principles suffice.

---
**Version**: 1.0.0 | **Ratified**: 2026-05-11 | **Last Amended**: 2026-05-11
