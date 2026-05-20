# Tasks 013 — Implement `admesh._stages.background_grid`

**Spec**: `specs/013-background-grid-impl/spec.md`
**Plan**: `specs/013-background-grid-impl/plan.md`
**Branch**: `daily-issue-fixing`

Atomic, testable, ordered. Each task ties to a spec acceptance
criterion (AC) and/or a plan pass.

## Phase A — Pre-flight (this planning run)

### T-013-A1 — Land spec / plan / tasks
- **Depends on**: nothing
- **Owner**: current run
- **Inputs**: this run's directives
- **Action**: Write `spec.md`, `plan.md`, `tasks.md` under
  `specs/013-background-grid-impl/`.
- **Outputs**: three markdown files.
- **Acceptance**: files exist; `ls specs/013-background-grid-impl/`
  shows them.

### T-013-A2 — Update PROJECT_PLAN.md
- **Depends on**: T-013-A1
- **Owner**: current run
- **Inputs**: existing `PROJECT_PLAN.md` (if present)
- **Action**: Add spec 013 to the planning index if a planning index
  exists. If `PROJECT_PLAN.md` does not exist or has no
  index, skip and note in run summary.
- **Outputs**: edited `PROJECT_PLAN.md` (or skip note).
- **Acceptance**: `grep -n "013" PROJECT_PLAN.md` matches or the skip
  is documented in the run summary.

### T-013-A3 — Comment on issue #78
- **Depends on**: T-013-A1
- **Owner**: current run
- **Inputs**: spec 013 URL
- **Action**: Post a comment on #78 stating "Planning complete —
  spec 013 landed on `daily-issue-fixing`. Implementation in a
  follow-up run; resolves OQ-1..OQ-4 first." Link to spec / plan /
  tasks.
- **Outputs**: comment posted.
- **Acceptance**: comment appears on GH issue #78.

### T-013-A4 — Comment on issue #73 (cross-link)
- **Depends on**: T-013-A1
- **Owner**: current run
- **Inputs**: spec 013 URL
- **Action**: Post a brief comment on #73 noting that the
  implementation that closes the parity tests of #73 is now planned
  in spec 013. Link to spec 013.
- **Outputs**: comment posted.
- **Acceptance**: comment appears on GH issue #73.

## Phase B — Port implementation (next impl run)

### T-013-B1 — Resolve OQ-1..OQ-4
- **Depends on**: access to QuADMesh-MATLAB @ `19b2eb9`
- **Owner**: next impl run
- **Inputs**: `01_ADMESH_Library/02_Create_Background_Grid/CreateBackgroundGrid.m`
- **Action**: Read MATLAB source; trace `padding` semantics, return
  shape, field names, and inline-construction lines in
  `admesh/_stages/routine.py`. Append a "Resolutions" section to
  spec 013's `spec.md`.
- **Outputs**: spec.md updated with OQ resolutions.
- **Acceptance**: `grep -n "## 11. Resolutions" specs/013-background-grid-impl/spec.md`
  matches.

### T-013-B2 — Ensure `tests/test_background_grid.py` exists with xfail scaffolds
- **Depends on**: T-013-B1
- **Owner**: next impl run
- **Inputs**: spec 012 FR-012-1 .. FR-012-4
- **Action**: If the file doesn't exist (spec 012 task T-012-2 not
  yet shipped), create it now with the four xfail scaffolds
  (`xfail(strict=True, reason="blocked on #78")`). If it exists,
  verify the four scaffolds are present.
- **Outputs**: scaffolded test file.
- **Acceptance**: `pytest -q tests/test_background_grid.py` exits 0
  with the four parity tests reported as `xfail`.

### T-013-B3 — Implement `create_background_grid` + `BackgroundGrid`
- **Depends on**: T-013-B1
- **Owner**: next impl run
- **Inputs**: spec FR-013-1 .. FR-013-3
- **Action**: Replace `admesh/_stages/background_grid.py` stub with
  the port per Plan §Pass 3. Include the `BackgroundGrid` dataclass
  with field names from OQ-3.
- **Outputs**: implemented module.
- **Acceptance**: `python -c "from admesh._stages.background_grid
  import create_background_grid, BackgroundGrid"` succeeds; module
  passes a hand-written property check on the unit square.

### T-013-B4 — Wire into `admesh/_stages/routine.py`
- **Depends on**: T-013-B3
- **Owner**: next impl run
- **Inputs**: spec FR-013-5; OQ-4 line ranges
- **Action**: Replace the inline grid construction with a call to
  `create_background_grid(...)`. Add the adapter alias for X/Y/mask
  so downstream stages remain unchanged.
- **Outputs**: edited routine.py.
- **Acceptance**: `pytest -q tests/test_routine.py
  tests/test_api_triangulate.py tests/test_default_size_field.py`
  exits 0; no Tier-0/1/2 output differs by > `atol=1e-12` from the
  pre-port baseline.

### T-013-B5 — Add stage-02 fixture export
- **Depends on**: T-013-B3
- **Owner**: next impl run (MATLAB-equipped)
- **Inputs**: spec FR-013-4
- **Action**: Append the stage-02 section to
  `scripts/export_matlab_fixtures.m` per Plan §Pass 5a. Run the
  exporter; run `python scripts/mat_to_npz.py`. Commit
  `tests/fixtures/matlab/background_grid_unit_square.npz`.
- **Outputs**: edited `.m` script; new `.npz` file.
- **Acceptance**: fixture file exists; size > 0; loadable via
  `np.load`.

### T-013-B6 — Remove xfail markers
- **Depends on**: T-013-B5
- **Owner**: next impl run
- **Inputs**: `tests/test_background_grid.py`
- **Action**: Delete the four `@pytest.mark.xfail(strict=True,
  reason="blocked on #78")` decorators.
- **Outputs**: edited test file.
- **Acceptance**: `pytest -q tests/test_background_grid.py` exits 0
  with no `xfail` outcomes; `grep -n xfail tests/test_background_grid.py`
  returns nothing.

### T-013-B7 — Update `docs/PORTING_NOTES.md`
- **Depends on**: T-013-B3, T-013-B5
- **Owner**: next impl run
- **Inputs**: spec FR-013-6; plan §Pass 5c template
- **Action**: Append a "stage 02 — Background grid port" entry per
  the template at the top of `docs/PORTING_NOTES.md`. Fill in
  behavior-diff bullet from OQ-1 resolution.
- **Outputs**: edited PORTING_NOTES.md.
- **Acceptance**: `grep -n "stage 02" docs/PORTING_NOTES.md` matches.

### T-013-B8 — Full-suite regression + pre-tag check
- **Depends on**: T-013-B6, T-013-B7
- **Owner**: next impl run
- **Inputs**: working tree at end of Phase B
- **Action**: `pytest -q` over the whole suite; `bash
  scripts/pre_tag_check.sh`.
- **Outputs**: green CI signal.
- **Acceptance**: both commands exit 0.

### T-013-B9 — Close issue #78
- **Depends on**: T-013-B8
- **Owner**: next impl run
- **Inputs**: passing CI from T-013-B8
- **Action**: Comment on #78 with the implementation summary
  (changes, validation, fixture provenance, PORTING_NOTES link).
  Close the issue.
- **Outputs**: closed issue.
- **Acceptance**: issue #78 state = closed; #73 cross-linked via
  comment.

## Dependency graph

```
[Phase A — this run]
T-013-A1 ─► T-013-A2
        └─► T-013-A3
        └─► T-013-A4
                │
                │  (planning-only run ends here ▲)
                ▼
[Phase B — next impl run]
T-013-B1 ─► T-013-B2 ─► T-013-B3 ─► T-013-B4
                              └─► T-013-B5 ─► T-013-B6 ─► T-013-B8 ─► T-013-B9
                                          └─► T-013-B7 ─┘
```

## Constitution / cross-cutting checks

- **Principle I (numerical identity)**: T-013-B5 + T-013-B6
  enforce `atol=1e-10` against MATLAB fixture, matching the
  precedent of spec 002 / 009.
- **Principle II (no branch proliferation)**: all tasks land on
  `daily-issue-fixing`.
- **Principle III (audit gates close)**: T-013-B6 closes the
  Track B half of spec 012's audit ledger; #73 closes
  transitively when #78 closes.

## Current-run deliverables

- [x] `specs/013-background-grid-impl/spec.md`
- [x] `specs/013-background-grid-impl/plan.md`
- [x] `specs/013-background-grid-impl/tasks.md`
- [ ] Comment on issue #78 — planning complete
- [ ] Comment on issue #73 — cross-link
- [ ] PROJECT_PLAN.md updated (if index exists)
- [ ] Commit + push planning artifacts to `daily-issue-fixing`
