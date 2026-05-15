# Tasks: 1D Boundary Seeding for Domain Path

**Issue**: #2 | **Branch**: `daily-issue-fixing`

## Phase 1: Setup
- [x] T001 Baseline verification

## Phase 2: Foundational
- [x] T002 Add `boundary_polygon` field to Domain in `admesh/domains.py`
- [x] T003 [P] Set `boundary_polygon` on NOTCHED_RECTANGLE in `admesh/domains.py`
- [x] T004 Implement `_seed_boundary_1d()` in `admesh/routine.py`

## Phase 3: US1 - Uniform Coverage
- [x] T005 [US1] Update `triangulate()` in `admesh/routine.py`
- [x] T006 [US1] Add notch-wall coverage tests in `tests/test_routine.py`
- [x] T007 [US1] Run and confirm tests pass

## Phase 4: US2 - Adaptive Spacing
- [x] T008 [P] [US2] Add non-uniform fh test in `tests/test_routine.py`
- [x] T009 [US2] Verify NaN/<=0 guard in `_seed_boundary_1d`

## Phase 5: US3 - Regression
- [x] T010 [P] [US3] Full suite: 327 passed, 11 skipped, 0 failures
- [x] T011 [US3] Non-notched domain boundary_polygon=None checks added

## Phase 6: Polish
- [x] T012 Updated `docs/PORTING_NOTES.md`
- [x] T013 [P] Committed via MCP push_files
- [x] T014 Diff verified: only intended files changed

**Status**: COMPLETE
