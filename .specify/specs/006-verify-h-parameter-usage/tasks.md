# Tasks: Verify h_min/h_max Parameter Usage in triangulate() API

**Feature**: Issue #37 Investigation  
**Status**: Planning Complete - Ready for Execution  
**Phase**: Analysis & Diagnosis (No Code Implementation)

## Overview

This investigation task list breaks down the verification of `h_min`/`h_max` parameter usage into atomic, independently executable diagnostic tasks. The investigation is organized around four user stories (US1-US4) from the specification, each representing a developer need or investigation goal.

**Note**: Tests are NOT included in this task list (diagnostic investigation, not TDD). Deliverables are analytical reports and code traces.

---

## Phase 1: Setup (Investigation Infrastructure)

**Purpose**: Prepare environment and documentation structure for investigation

- [ ] T001 Create `docs/issue-37-h-parameter-investigation.md` template with sections for parameter trace, composition logic, diagnostic output, root cause, and recommendations
- [ ] T002 Create `docs/issue-37-code-trace.md` for detailed file:line references and parameter flow diagram
- [ ] T003 Prepare diagnostic script template in `scripts/diagnose_h_parameter.py` for size-field grid sampling on WNAT fixture
- [ ] T004 Set up issue #37 local workspace: Clone WNAT fixture reference, verify reproducibility

---

## Phase 2: Foundational (Code Inspection Preparation)

**Purpose**: Establish baseline understanding before diving into detailed investigation

- [ ] T005 Audit `admesh/api.py::triangulate()` function signature and docstring; document h_min/h_max parameter existence and documented behavior
- [ ] T006 Audit `admesh/routine.py::triangulate()` driver function; document parameter acceptance and forwarding
- [ ] T007 Audit `admesh/mesh_size.py::build_h()` function signature; document expected parameters and documented composition logic
- [ ] T008 List all size-field stages in `admesh/curvature.py`, `medial_axis.py`, `bathymetry.py`, `dominate_tide.py`; extract composition order from code

**Checkpoint**: Code baseline documented; investigation scope clear

---

## Phase 3: User Story 1 - Developer Verifies Parameter Flow (Priority: P1) 🎯

**Goal**: Trace h_min/h_max parameters from `triangulate()` API through to `mesh_size.build_h()` with concrete file:line evidence.

**Independent Test**: Trace can be verified by code inspection alone (no execution needed initially).

### Investigation Tasks for US1

- [ ] T009 [US1] Trace parameter flow: `admesh/api.py::triangulate()` → identify parameter definition, default value, and where it's passed next; document with file:line in `docs/issue-37-code-trace.md`
- [ ] T010 [P] [US1] Trace `admesh/routine.py::triangulate()` → identify where h_min/h_max are received and how they're forwarded to subsequent calls; document file:line references
- [ ] T011 [P] [US1] Trace `admesh/mesh_size.py::build_h()` → identify parameter reception, how it's used in composition logic, and final clipping/binding; document file:line references
- [ ] T012 [US1] Identify the `_build_default_size_field()` function (if it exists); trace how h_min/h_max are passed to it or how defaults are applied when not provided
- [ ] T013 [US1] Generate parameter-flow diagram in `docs/issue-37-code-trace.md` showing full chain from API to final size-field grid with all file:line references
- [ ] T014 [US1] Document in `docs/issue-37-h-parameter-investigation.md` section 1 (Parameter Flow Trace) the complete flow with code snippets and line references

**Checkpoint**: Parameter flow fully traced and documented; developer can see complete pathway from API input to downstream consumption

---

## Phase 4: User Story 2 - Developer Verifies Size-Field Composition (Priority: P1)

**Goal**: Understand and document how h_min/h_max bounds are applied during size-field composition (clipping? driving? ignored?).

**Independent Test**: Composition logic can be verified by code inspection and docstring analysis.

### Investigation Tasks for US2

- [ ] T015 [P] [US2] Inspect `admesh/mesh_size.py::build_h()` implementation; identify composition stage order (curvature → medial → bathymetry → tide → clip); document in `docs/issue-37-h-parameter-investigation.md` section 2
- [ ] T016 [P] [US2] For each size-field stage (`curvature.py`, `medial_axis.py`, `bathymetry.py`, `dominate_tide.py`), determine if h_min/h_max is referenced; document which stages use these bounds
- [ ] T017 [US2] Inspect the clipping/bounding logic in `build_h()` after composition; determine if `h_min <= h(X,Y) <= h_max` is enforced globally or per-stage; document the algorithm
- [ ] T018 [US2] Identify any hardcoded `h_min`, `h_max` defaults in `build_h()` or `triangulate()` when values are not provided; document default values
- [ ] T019 [US2] Write composition-logic explanation for `docs/issue-37-h-parameter-investigation.md` section 2: explain whether h_min/h_max actively drives density at each stage or are post-hoc clipping bounds
- [ ] T020 [US2] Create before/after pseudocode examples showing how the size-field grid would differ if h_min/h_max were applied vs. ignored

**Checkpoint**: Composition logic fully documented; clear explanation of whether parameters have an effect on final size-field grid

---

## Phase 5: User Story 3 - Developer Documents Expected vs Actual Behavior (Priority: P1)

**Goal**: Verify API documentation claims against code reality; identify any discrepancies.

**Independent Test**: Documentation audit is purely comparative (docstring vs. code).

### Investigation Tasks for US3

- [ ] T021 [US3] Read and extract all claims about h_min/h_max from `admesh/api.py::triangulate()` docstring; list each claim in `docs/issue-37-h-parameter-investigation.md` section 5 (API Documentation Status)
- [ ] T022 [P] [US3] Check `docs/api.md`, `docs/user-guide.md`, `README.md` for h_min/h_max documentation; extract all claims and compare to code behavior
- [ ] T023 [P] [US3] Create a claim-vs-reality table in `docs/issue-37-h-parameter-investigation.md` section 5 with columns: [Documented Claim], [Code Reality], [Status: Verified/Incorrect/Ambiguous]
- [ ] T024 [US3] For each "Incorrect" or "Ambiguous" status, flag the docstring/docs file that needs updating with a list of specific required changes
- [ ] T025 [US3] Draft recommendations for documentation updates: should API docs be clarified, or should code be fixed? Document in section 5

**Checkpoint**: API documentation status clear; identified what needs updating to match reality (or what code needs fixing to match docs)

---

## Phase 6: User Story 4 - Developer Identifies Root Cause of Undersampling (Priority: P2)

**Goal**: Determine why WNAT Tier-2 mesh is severely undersampled: are parameters correctly applied but insufficient, or not applied at all?

**Independent Test**: Diagnostic output from size-field sampling can be compared to parameter bounds programmatically.

### Investigation Tasks for US4

- [ ] T026 [P] [US4] Implement diagnostic script `scripts/diagnose_h_parameter.py` that:
  - Loads WNAT fixture (`tests/fixtures/fort14/adcirc_examples/wnat_test.14`)
  - Calls `Domain.from_mesh(wnat)` to create domain
  - Builds size-field grid with explicit h_min=0.1, h_max=2.0
  - Samples the grid at 10×10 regular points across domain bbox
  - Outputs min/max/mean of h(X,Y) values to compare against h_min/h_max bounds
  
- [ ] T027 [US4] Run diagnostic script and generate size-field statistics for WNAT fixture; document output in `docs/issue-37-h-parameter-investigation.md` section 3 (Diagnostic Output)

- [ ] T028 [US4] Analyze diagnostic output: does the size-field grid satisfy `h_min <= h(X,Y) <= h_max` everywhere, or are there violations? Document findings in section 3

- [ ] T029 [US4] If size-field grid respects bounds: trace distmesh solver behavior (is distmesh undersampling despite correct h field?). If not: identify which stage produces out-of-bounds h values

- [ ] T030 [US4] Generate hypothesis in `docs/issue-37-h-parameter-investigation.md` section 4 (Root Cause Hypothesis):
  - **Option A**: Parameters correctly applied, size-field grid is correct → distmesh solver issue (issue #10 focus)
  - **Option B**: Parameters applied but insufficient (e.g., SDF gradient too steep) → composition tuning needed
  - **Option C**: Parameters not applied (bug in plumbing) → quick fix needed
  - Document evidence for the hypothesis

- [ ] T031 [P] [US4] Inspect edge cases: What happens when h_min > h_max, h_min=0, h_max<0, or h_min/h_max not provided? Test these scenarios in diagnostic script and document behavior

**Checkpoint**: Root cause hypothesis identified with supporting diagnostic evidence; findings ready for issue #10 follow-up

---

## Phase 7: Polish & Handoff

**Purpose**: Finalize investigation report and prepare handoff to issue #10 fix

- [ ] T032 Review all investigation findings in `docs/issue-37-h-parameter-investigation.md`; ensure all 6 sections are complete and consistent
- [ ] T033 Generate executive summary in issue #37 GitHub comment: root cause in 1-2 sentences, findings, and recommended next steps for #10
- [ ] T034 [P] Update `docs/PORTING_NOTES.md` (if applicable) with any h_min/h_max behavior deviations discovered between MATLAB and Python
- [ ] T035 Create follow-up issue(s) if documentation updates are needed; link from issue #37
- [ ] T036 Close issue #37 with reference to investigation report location (`docs/issue-37-h-parameter-investigation.md`)

**Checkpoint**: Investigation complete; handoff ready for issue #10 implementation phase

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - blocks all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational completion
  - US1, US2, US3, US4 can proceed in parallel (different aspects of investigation)
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (Parameter Flow Trace)**: Independent - can start after Foundational
- **US2 (Composition Logic)**: Independent - can start after Foundational  
- **US3 (Documentation Audit)**: Independent - can start after Foundational
- **US4 (Root Cause)**: Depends on US1 + US2 being complete (needs parameter flow understanding + composition logic understanding to interpret diagnostic output)

### Within Each User Story

- Read code first (audit tasks)
- Document findings
- Cross-reference with other stories as needed
- No code implementation or modifications

### Parallel Opportunities

- **Setup phase**: All tasks can run in parallel (T001-T004)
- **Foundational phase**: Audit tasks T005-T008 can run in parallel (different files)
- **US1 + US2 + US3**: Can run fully in parallel (different investigation focuses)
- **US4**: Can start immediately after US1 and US2 findings are ready (needs understanding from those stories)
- **Polish phase**: T032-T036 are sequential (build on investigation completion)

---

## Parallel Example: Full Parallel Execution

```
Phase 1 (Setup): Run T001, T002, T003, T004 in parallel
├─ Completes in ~30 min (sequential slowest path)
│
Phase 2 (Foundational): Run T005, T006, T007, T008 in parallel
├─ Completes in ~1-2 hours (depends on code familiarity)
│
Phase 3-6 (User Stories):
├─ US1 (Parameter Flow): Run T009, T010, T011 in parallel → T012, T013, T014 sequential
├─ US2 (Composition): Run T015, T016 in parallel → T017, T018, T019, T020 sequential
├─ US3 (Documentation): Run T021, T022 in parallel → T023, T024, T025 sequential
└─ US4 (Root Cause): T026 → T027, T028, T029, T030, T031 in parallel
│
Phase 7 (Polish): T032 → T033, T034 in parallel → T035, T036 sequential

Total time: ~5-6 hours (if one person doing investigation)
Parallel time: ~2-3 hours (if multiple people on different user stories)
```

---

## Implementation Strategy

### Investigation First (Linear Path - Single Investigator)

1. **Phase 1**: Setup - 30 min
   - Prepare documentation templates and diagnostic infrastructure
2. **Phase 2**: Foundational - 1-2 hours
   - Understand code baseline, audit API and core modules
3. **Phase 3**: US1 Parameter Flow - 1-2 hours
   - Trace parameters end-to-end with file:line documentation
4. **Phase 4**: US2 Composition Logic - 1-2 hours
   - Understand how h_min/h_max are used at each stage
5. **Phase 5**: US3 Documentation Audit - 1 hour
   - Check what API claims vs. what code does
6. **Phase 6**: US4 Root Cause - 2-3 hours
   - Run diagnostics, analyze output, form hypothesis
7. **Phase 7**: Polish & Handoff - 1 hour
   - Finalize report, create GitHub summary, close issue

**Total**: 7-12 hours investigation effort

### Parallel Team Strategy (Multiple Investigators)

1. **Team**: Complete Setup + Foundational together (~2 hours)
2. **Then split**:
   - **Person A**: US1 (Parameter Flow) + US4 (Root Cause Analysis)
   - **Person B**: US2 (Composition Logic) + US3 (Documentation Audit)
3. **Then unite**: Phase 7 (Polish & Handoff) together

**Total**: ~4-5 hours with 2-person team

---

## Task Format & Validation

**All tasks follow strict checklist format**:
```
- [ ] [TaskID] [P?] [Story?] Description with file path
```

**Examples**:
- ✅ `- [ ] T009 [US1] Trace parameter flow: admesh/api.py::triangulate() → identify parameter...`
- ✅ `- [ ] T010 [P] [US1] Trace admesh/routine.py::triangulate()...`
- ✅ `- [ ] T032 Review all investigation findings in docs/issue-37-h-parameter-investigation.md`

---

## Success Criteria for Investigation

| Criterion | Verified By | Task(s) |
|-----------|---|---|
| Parameter flow traced with file:line refs | `docs/issue-37-code-trace.md` | T009-T014 |
| Composition logic documented | `docs/issue-37-h-parameter-investigation.md` §2 | T015-T020 |
| Diagnostic output on WNAT generated | `docs/issue-37-h-parameter-investigation.md` §3 | T026-T031 |
| Root cause identified | `docs/issue-37-h-parameter-investigation.md` §4 | T030 |
| API docs status clarified | `docs/issue-37-h-parameter-investigation.md` §5 | T021-T025 |
| Handoff to issue #10 ready | GitHub issue comment + linked report | T033 |

---

## Notes

- **No code changes expected** in this investigation phase (diagnosis only)
- **Parallel opportunities**: US1, US2, US3 can proceed fully in parallel; US4 benefits from US1+US2 context
- **Minimal instrumentation**: Diagnostic script is the only code artifact (sampling utility, not a core change)
- **Report-driven**: Primary output is `docs/issue-37-h-parameter-investigation.md` (diagnostic findings)
- **Handoff-focused**: Phase 7 ensures findings unblock issue #10 implementation
