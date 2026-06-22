# Implementation Plan: Verify h_min/h_max Parameter Usage

**Date**: 2026-05-06  
**Status**: Planning Phase  
**Issue Reference**: #37  
**Branch**: `daily-maintenance` (mandate reuse)

## Overview

This investigation verifies whether the `h_min`/`h_max` parameters in `triangulate(domain, h_min=..., h_max=...)` are correctly honored in the default size-field path. The investigation is diagnostic and analytical, not algorithmic — we trace parameter flow, verify composition logic, and document findings without modifying the core algorithm.

## Technical Context

### Code Paths to Investigate

1. **Entry Point**: `admesh/api.py::triangulate(domain, h_min=0.05, h_max=2.0, ...)`
   - Signature inspection: are h_min/h_max parameters accepted?
   - Call trace: where are they passed next?

2. **Driver Layer**: `admesh/routine.py::triangulate(...)`
   - Receives h_min/h_max from the API level?
   - Forwards to `mesh_size.build_h()` or size-field builder?

3. **Size-Field Composition**: `admesh/mesh_size.py::build_h(grid_points, h_min, h_max, ...)`
   - How are h_min/h_max used?
   - Are they clipping bounds, or do they actively drive density?
   - What is the composition order: curvature → medial-axis → bathymetry → tide → clipping?

4. **Default Stack**: `admesh/api.py::_build_default_size_field(...)`
   - Called when size_field=None?
   - How does it incorporate h_min/h_max?

5. **Distmesh Integration**: `admesh/distmesh.py::distmesh2d(..., h0, ...)`
   - Receives the size-field grid?
   - How does h0 parameter relate to h_min/h_max in the grid?

### Real-World Test Case

- **Fixture**: `tests/fixtures/fort14/adcirc_examples/wnat_test.14`
- **Call**: `admesh.triangulate(Domain.from_mesh(wnat), h_min=0.1, h_max=2.0)`
- **Expected**: Mesh with element count ≈ source mesh (similar density)
- **Observed**: Mesh with 25× fewer elements (severe undersampling)

### Dependencies & Assumptions

- Investigation is code-inspection + minimal instrumentation (no new testing framework)
- WNAT fixture is stable and reproducible
- API docstrings and `docs/` are source of truth for expected behavior
- No changes to core algorithm (diagnostic only)

## Constitution Check

**Principles Invoked**:
1. **Principle III (Reference-Test Discipline)**: This investigation validates that the API contract (h_min/h_max control density) is correct; it does not modify tested stages
2. **Principle V (Report-and-Advance)**: Investigation findings will be documented and reported immediately

**Scope Boundaries**:
- ✅ Diagnostic analysis (in scope)
- ✅ Documentation of findings (in scope)
- ✅ API contract verification (in scope)
- ❌ Algorithm modifications (out of scope)
- ❌ Bug fixes (out of scope — belong to issue #10)
- ❌ Performance optimization (out of scope)

**Deviations**: None — pure investigation, no implementation.

## Phase 0: Research & Prerequisites

### Investigation Questions

1. **Q1**: In `admesh/api.py::triangulate()`, are h_min/h_max parameters stored as instance attributes, function locals, or passed through kwargs?
   - **Research task**: Inspect function signature + implementation
   - **Deliverable**: Code trace with line references

2. **Q2**: How is the default size-field composed when h_min/h_max are provided without explicit size_field callable?
   - **Research task**: Trace `_build_default_size_field()` and `mesh_size.build_h()`
   - **Deliverable**: Step-by-step composition logic documentation

3. **Q3**: Are h_min/h_max used to clip/bound the final size-field grid, or do they actively drive density at each stage?
   - **Research task**: Inspect `build_h()` implementation + stage order
   - **Deliverable**: Comparison of expected vs actual usage

4. **Q4**: On the WNAT fixture, does the size-field grid respect h_min/h_max bounds?
   - **Research task**: Generate diagnostic grid sampling
   - **Deliverable**: Size-field statistics on 10×10 grid sample

### Research Subtasks

- **T-P0-01**: Trace parameter flow from triangulate() → routine.triangulate() → mesh_size.build_h() with file:line references
- **T-P0-02**: Document _build_default_size_field() composition order and how h_min/h_max are applied
- **T-P0-03**: Inspect edge-case handling (h_min > h_max, zero/negative values, missing parameters)
- **T-P0-04**: Generate diagnostic: size-field grid sample on WNAT with min/max/mean statistics
- **T-P0-05**: Compare API documentation claims vs code behavior

### Completion Criteria for Phase 0

- All 4 research questions answered with code evidence
- Parameter flow fully traced with file:line references
- Size-field composition logic documented
- Edge cases enumerated
- Diagnostic output generated (WNAT grid sample)

---

## Phase 1: Analysis & Documentation

### Diagnostic Report Structure

**Document**: `docs/issue-37-h-parameter-investigation.md`

```
1. Parameter Flow Trace
   - triangulate() acceptance
   - routine.triangulate() propagation
   - mesh_size.build_h() reception
   - [Each with file:line references]

2. Size-Field Composition Logic
   - Stage order (curvature → medial → bathymetry → tide → clip)
   - How h_min/h_max is used at each stage
   - Clamping/clipping behavior

3. Diagnostic Output: WNAT Fixture
   - Size-field grid sample (10×10)
   - Min/max/mean of h(X,Y)
   - Comparison to requested h_min/h_max

4. Root Cause Hypothesis
   - Option A: Parameters correctly applied, h-field correct
   - Option B: Parameters applied but insufficient (SDF quality issue)
   - Option C: Parameters not applied (bug)
   - Evidence for each option

5. API Documentation Status
   - Current claims in docstrings
   - Verified vs. identified-for-update

6. Recommendations for Issue #10
```

### Analysis Subtasks

- **T-P1-01**: Generate parameter-flow diagram with file:line references
- **T-P1-02**: Write composition-logic explanation (readable by any developer)
- **T-P1-03**: Run diagnostic: sample size-field grid on WNAT, compute statistics
- **T-P1-04**: Compare diagnostic output to h_min/h_max bounds
- **T-P1-05**: Identify root cause (parameters applied / not-applied / insufficient)
- **T-P1-06**: Audit API documentation for consistency
- **T-P1-07**: Draft recommendations for issue #10 fix

### Completion Criteria for Phase 1

- Diagnostic report complete with all 6 sections filled
- Root cause identified with supporting evidence
- API documentation status clear (verified or flagged for update)
- Recommendations for #10 actionable

---

## Success Criteria (Per Spec)

| Criterion | Task(s) | Deliverable |
|-----------|---------|-------------|
| SC-001: Parameter flow traced with code refs | T-P0-01, T-P1-01 | Parameter flow trace diagram |
| SC-002: Composition logic documented | T-P0-02, T-P1-02 | Composition explanation document |
| SC-003: Diagnostic output with statistics | T-P0-04, T-P1-03 | WNAT grid sample + statistics |
| SC-004: Root cause identified | T-P1-04, T-P1-05 | Root cause hypothesis + evidence |
| SC-005: API docs status clarified | T-P0-05, T-P1-06 | Documentation audit result |
| SC-006: Findings unblock issue #10 | T-P1-07 | Recommendations for #10 |

---

## Phase 2: Deliverables & Handoff

### Artifacts Generated

1. **Diagnostic Report**: `docs/issue-37-h-parameter-investigation.md`
   - Parameter flow trace
   - Composition logic explanation
   - Diagnostic output (WNAT grid sample)
   - Root cause identification
   - API documentation audit
   - Recommendations for #10

2. **Code Trace Document**: `docs/issue-37-code-trace.md` (optional, if diagram is complex)
   - File:line references for every parameter handoff

3. **Issue #37 Resolution**: 
   - Comment on GitHub issue with investigation findings
   - Close issue (investigation complete)

4. **Input to Issue #10**:
   - Recommendations based on root cause (parameters applied vs not)
   - Diagnostic evidence for the maintainer

### Handoff to Next Phase (Issue #10 Fix)

- If root cause is "parameters not applied" → Fix the parameter plumbing (quick fix)
- If root cause is "parameters applied but insufficient" → Debug size-field composition (issue #10 deeper investigation)
- If root cause is "parameters correct, SDF pathological" → Issue #10 must focus on SDF quality

---

## Files to Inspect

| File | Purpose |
|------|--------|
| `admesh/api.py` | triangulate() signature, _build_default_size_field() |
| `admesh/routine.py` | triangulate() driver, call to mesh_size.build_h() |
| `admesh/mesh_size.py` | build_h() implementation, stage composition |
| `admesh/distmesh.py` | distmesh2d(), h0 usage, size-field application |
| `admesh/curvature.py`, `medial_axis.py`, `bathymetry.py`, `dominate_tide.py` | Size-field stages |
| `tests/fixtures/fort14/adcirc_examples/wnat_test.14` | WNAT test fixture |
| `docs/api.md`, `admesh/api.py` docstrings | API documentation claims |

## Timeline & Effort Estimate

- **Phase 0 (Research)**: 2-3 hours (code inspection, documentation trace)
- **Phase 1 (Analysis)**: 2-3 hours (diagnostic output generation, report writing)
- **Phase 2 (Handoff)**: 0.5 hours (issue comment, recommendations)

**Total**: ~5-6 hours of analysis work

---

## Notes

- This investigation is a prerequisite for issue #10 (size-field overshooting fix)
- No code changes are expected in this phase
- The diagnostic report becomes the foundation for #10's design
- If parameters are correctly applied, the issue shifts to SDF quality / solver behavior
- If parameters are NOT applied, the fix is trivial (plumbing bug)
