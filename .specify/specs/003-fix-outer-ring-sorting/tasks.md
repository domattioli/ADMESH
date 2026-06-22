# Tasks: Fix Domain.from_mesh Ring Sorting

**Input**: Design documents from `/specs/003-fix-outer-ring-sorting/`  
**Specification**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Data Model**: [data-model.md](data-model.md)

**Organization**: This is a targeted bug fix with 3 core implementation tasks + validation.

---

## Phase 1: Setup & Validation Baseline

**Purpose**: Establish baseline and verify the bug exists

- [ ] T001 Reproduce issue #11 with wnat_test.14 fixture: Verify `Domain.from_mesh(wnat)` produces wrong bbox and `triangulate()` fails with ValueError
- [ ] T002 Run existing test suite to establish baseline: `pytest tests/ -xvs` should pass except xfail marks on tier-1/tier-2 tests

---

## Phase 2: Core Implementation

**Purpose**: Fix the ring-sorting logic

### T003: Implement signed-area helper function

- [ ] T003 Add `_ring_area(ring_segment: BoundarySegment, nodes: NDArray) -> float` helper in `admesh/api.py` (lines ~360-375)
  - Use shoelace formula: `0.5 * abs(sum(x[i]*y[i+1] - x[i+1]*y[i]))`
  - Return absolute area as float
  - Handle degenerate rings (area ≈ 0) gracefully

### T004: Replace ring-sorting criterion

- [ ] T004 [P] Modify `_derive_boundary_segments()` ring sort in `admesh/api.py` (line ~408)
  - Change from: `rings.sort(key=len, reverse=True)`
  - Change to: `rings.sort(key=lambda s: _ring_area(s, mesh_nodes), reverse=True)`
  - Verify outer ring = rings[0] after sort

- [ ] T005 [P] Update `Domain.from_mesh()` in `admesh/api.py` (line ~420) if needed
  - Confirm outer_ring = rings_segs[0] and holes = rings_segs[1:] logic is correct after T004

---

## Phase 3: Validation & Testing

**Purpose**: Verify fix works and doesn't break existing functionality

### Test Implementation for Core Fix

- [ ] T006 [P] Create unit test for multiply-connected domain in `tests/test_api.py`
  - **Test name**: `test_domain_from_mesh_multiply_connected_outer_ring_by_area`
  - **Fixture**: A synthetic multiply-connected domain where interior ring has MORE nodes than outer
  - **Assertion**: After `Domain.from_mesh(mesh)`, the outer ring is correctly identified (by area, not node count)
  - **Evidence**: `domain.outer_ring` should span the full extent, not a sub-region

- [ ] T007 Test wnat_test.14 recovery in `tests/test_api.py` (or integrate into `test_default_size_field.py`)
  - **Test name**: `test_domain_from_mesh_wnat_bbox_precision`
  - **Setup**: Load `wnat_test.14` via `admesh.read_fort14()`
  - **Fixture verification**: Source bbox = `[-97.85, 8.00]` to `[-60.04, 45.77]`
  - **Test**: `Domain.from_mesh(src)` produces domain with bbox matching source within `1e-9` tolerance
  - **Assertion**: `max(|bbox_delta| / mesh_diag) < 1e-9`

- [ ] T008 Test triangulate() succeeds on WNAT in `tests/test_default_size_field.py`
  - **Test name**: `test_tier2_wnat_release_gate` (remove `@pytest.mark.xfail` after fix)
  - **Setup**: Load domain via `Domain.from_mesh(wnat)`, call `triangulate(domain, h_min=0.05, h_max=2.0, ...)`
  - **Assertion**: No `ValueError`, mesh has `n_nodes > 100` and `n_elements > 100`
  - **Expected**: Mesh area ≥ 95% of original domain area

- [ ] T009 Verify Tier-1 round-trip still passes in `tests/test_default_size_field.py`
  - **Test name**: `test_tier1_wetting_and_drying_round_trip` (already written, should stay green)
  - **Fixture**: wetting-and-drying-test.14
  - **Setup**: Load source, call `Domain.from_mesh(src)`, triangulate, measure area coverage
  - **Assertion**: No regression; area coverage ≥ 95%

- [ ] T010 [P] Run MVP domain regression suite in `tests/test_api.py`
  - **Test name**: `test_domain_from_mesh_mvp_domains_no_regression`
  - **Fixtures**: Square, L-shape, U-shape, square-with-hole, annulus
  - **Setup**: For each domain, triangulate, recover via `Domain.from_mesh()`, re-triangulate
  - **Assertion**: All domains round-trip without errors; bbox and area reasonable

---

## Phase 4: Integration & Regression Testing

**Purpose**: Ensure no side effects from the fix

- [ ] T011 Run full pytest suite: `pytest tests/ -x` — all tests pass (xfail marks removed for tier-1/tier-2)
- [ ] T012 [P] Check `admesh.Domain` and `admesh.Mesh` API is still compatible (no breaking changes)
  - Verify existing user code calling `Domain.from_mesh()` still works as expected
  - Verify round-trip: `Domain -> triangulate -> Mesh -> Domain.from_mesh() -> triangulate` is stable

---

## Phase 5: Documentation & Closure

**Purpose**: Document the fix and close the issue

- [ ] T013 Update `docs/PORTING_NOTES.md` (if applicable)
  - Note: Ring sorting now uses signed area (matches MATLAB behavior, fixes Python discrepancy if any)
  - Add example of multiply-connected domain handling

- [ ] T014 Add docstring to `_ring_area()` explaining shoelace formula and why area-based sorting is canonical

- [ ] T015 Verify commit message references issue #11 and includes the acceptance criteria summary

- [ ] T016 Run `quickstart.md` validation: Execute the example code blocks in `quickstart.md` to ensure they work correctly

---

## Dependencies & Execution Order

### Strict Order (Sequential)

1. **Phase 1 (Setup)** — T001, T002 (establish baseline)
2. **Phase 2 (Implementation)** — T003 → T004 → T005 (must be in order)
3. **Phase 3 (Validation)** — T006-T010 (can run in parallel once Phase 2 done)
4. **Phase 4 (Regression)** — T011-T012 (depends on Phase 3)
5. **Phase 5 (Closure)** — T013-T016 (final documentation)

### Parallelizable Within Phases

- **Phase 3**: T006, T007, T008, T009, T010 can run in parallel once Phase 2 is complete
  - Different test files, no inter-dependencies
- **Phase 4**: T011 and T012 can run in parallel

### MVP Scope

**Minimal viable fix**: T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008

**Extended for confidence**: Add T009, T010, T011 for regression coverage

---

## Independent Testability

Each phase is independently testable:

- **Phase 1**: Baseline established (issue reproduced)
- **Phase 2**: `_ring_area()` and sort can be tested in isolation in a unit test
- **Phase 3**: Fix validated against all acceptance scenarios
- **Phase 4**: No regressions confirmed
- **Phase 5**: Complete and documented

---

## Success Criteria Mapping

| Criterion | Test Task(s) | Expected Result |
|-----------|-------------|----------|
| **SC-001**: WNAT bbox precision | T007 | bbox matches source to within `1e-9` |
| **SC-002**: WNAT non-empty mesh | T008 | `triangulate()` succeeds, no ValueError |
| **SC-003**: Mesh area coverage | T008, T009 | area ≥ 95% of original |
| **SC-004**: MVP no regression | T010 | all 5 domains round-trip without error |
| **SC-005**: Explicit multiply-connected | T006 | test explicitly covers longest-ring-is-hole case |

---

## Implementation Notes

- **Language**: Python (NumPy operations)
- **Files modified**: `admesh/api.py` (2 changes + 1 new helper)
- **Files added**: None (tests go in existing `tests/` structure)
- **Dependencies added**: None (uses existing NumPy/SciPy)
- **Estimated LOC**: ~15 for helper + ~3 for sort change = ~20 total new/modified lines
