# Tasks 012 — Direct stage tests for `admesh._stages.background_grid`

**Spec**: `specs/012-background-grid-stage-tests/spec.md`
**Plan**: `specs/012-background-grid-stage-tests/plan.md`
**Branch**: `daily-maintenance`

Atomic, testable, ordered. Each task is tied to a spec acceptance
criterion (AC) and/or a plan section.

## Track A — Land scaffold + close audit gate

### T-012-1 — Verify MATLAB fixture exporter state
- **Depends on**: nothing
- **Owner**: implementation run
- **Inputs**: `scripts/export_matlab_fixtures.m`
- **Action**: Read the file; determine whether stage 02
  (`02_Create_Background_Grid/CreateBackgroundGrid.m`) is currently
  a target. Output a one-line note to the spec's OQ-1.
- **Outputs**: OQ-1 resolution recorded in the follow-up impl issue.
- **Acceptance**: OQ-1 resolved (either "already exported" or
  "needs adding under task T-012-6").

### T-012-2 — Create `tests/test_background_grid.py`
- **Depends on**: T-012-1 (only for OQ-1 wording in xfail reason; not
  blocking).
- **Owner**: implementation run
- **Inputs**: spec FR-012-1 .. FR-012-4
- **Action**: Create the new test file with:
  1. One smoke test (`test_module_has_matlab_provenance_docstring`)
     that imports `admesh._stages.background_grid` and asserts the
     MATLAB source path appears in `__doc__`.
  2. Three parity scaffolds (bbox / spacing / uniformity) each
     `xfail(strict=True, reason="blocked on #78")`.
  3. One MATLAB-fixture parity scaffold,
     `xfail(strict=True, reason="blocked on #78 + fixture export")`.
- **Outputs**: New file, ≤ ~90 lines.
- **Acceptance**: AC `tests/test_background_grid.py exists`;
  AC `at least one smoke test passes`; AC `at least three parity
  scaffolds present as xfail(strict)`.
- **Cross-link**: closes the file-existence side of B-05.

### T-012-3 — Update `TEST-AUDIT.md`
- **Depends on**: T-012-2 (file must exist before the audit is updated)
- **Owner**: implementation run
- **Inputs**: lines 91, 93, 186, 207 of `TEST-AUDIT.md` (per Step 2
  grep results).
- **Action**: Mark F-MED-01 as "superseded by spec 012 / Track A";
  mark B-05 as "Track A done 2026-NN-NN; Track B pending
  #78". Add a footnote or row pointing at spec 012.
- **Outputs**: Updated `TEST-AUDIT.md`.
- **Acceptance**: AC `TEST-AUDIT.md updated`; `grep -n "F-MED-01" TEST-AUDIT.md`
  shows the supersession.

### T-012-4 — Open follow-up implementation issue
- **Depends on**: nothing (can run first to get the issue number for
  xfail reasons in T-012-2, but the order is reversible since the
  reason string can be updated post-hoc).
- **Owner**: implementation run (this run can do it too — see below)
- **Inputs**: spec FR-012-6
- **Action**: Open a GitHub issue
  `Implement admesh._stages.background_grid (port of CreateBackgroundGrid.m)`
  on `domattioli/ADMESH`. Body cites Constitution Principle I,
  links spec 012, lists Track B tasks T-012-5..T-012-7.
- **Outputs**: New issue.
- **Acceptance**: AC `follow-up implementation issue opened, linked
  from spec 012`.

> **Note for current run**: This run is in planning-only mode per
> CORE MANDATE. T-012-4 is the only task that can be performed here
> *without* shipping code, because opening an issue is documentation
> work. The follow-up issue is opened in this run; the test file
> (T-012-2) and the audit update (T-012-3) are deferred to the next
> implementation-phase run.

## Track B — Numerical parity (blocked on impl)

### T-012-5 — Port `CreateBackgroundGrid.m`
- **Depends on**: separate spec; opened as the follow-up impl issue
  by T-012-4.
- **Owner**: future run.
- **Inputs**: MATLAB source at MADMESHR /
  `01_ADMESH_Library/02_Create_Background_Grid/CreateBackgroundGrid.m`.
- **Action**: Replace the stub `admesh/_stages/background_grid.py`
  with a port that obeys Constitution Principle I (numerical identity
  at `atol=1e-10`).
- **Outputs**: Implemented module.
- **Acceptance**: Track B parity scaffolds start passing without
  `xfail`.

### T-012-6 — Export MATLAB fixture
- **Depends on**: T-012-1 outcome (may already exist).
- **Owner**: future run.
- **Inputs**: `scripts/export_matlab_fixtures.m`, a MATLAB
  environment with QuADMesh-MATLAB checked out at `19b2eb9`.
- **Action**: Add stage-02 export target if missing; run; commit
  `tests/fixtures/matlab/background_grid_unit_square.npz`.
- **Outputs**: Fixture file checked in.
- **Acceptance**: MATLAB-fixture parity scaffold loads the file
  without `FileNotFoundError`.

### T-012-7 — Remove xfail markers
- **Depends on**: T-012-5 AND T-012-6.
- **Owner**: future run.
- **Inputs**: `tests/test_background_grid.py`.
- **Action**: Once the parity tests pass under the strict-xfail
  regime, CI will fail (because `strict=True` flags
  unexpected-pass). The fix is to delete the four `xfail` decorators
  and re-run.
- **Outputs**: All four parity tests promoted to plain green tests.
- **Acceptance**: `pytest -q` exits 0; `grep -n xfail
  tests/test_background_grid.py` returns nothing; B-05 closes; the
  follow-up impl issue closes.

## Dependency graph

```
T-012-1 ─┐
         ├─► T-012-2 ─► T-012-3
T-012-4 ─┘                  │
                            │     (planning-only run ends here ▲)
                            │
T-012-5 ─┐                  │
T-012-6 ─┴─► T-012-7        │
```

## Constitution / cross-cutting checks

- **Principle I (numerical identity)**: AC for T-012-5 enforces
  `atol=1e-10` against MATLAB-exported fixtures, matching the
  precedent set in spec 002 / spec 009.
- **Principle II (no branch proliferation)**: all tasks land on
  `daily-maintenance`.
- **Principle III (audit gates close)**: T-012-3 explicitly closes
  the F-MED-01 / B-05 entries in `TEST-AUDIT.md`.

## Current-run deliverables

- [x] `specs/012-background-grid-stage-tests/spec.md` (this run)
- [x] `specs/012-background-grid-stage-tests/plan.md` (this run)
- [x] `specs/012-background-grid-stage-tests/tasks.md` (this run)
- [x] T-012-4 follow-up impl issue (this run, opened as #78)
- [ ] Issue #73 comment summarising the planning outcome (this run)
- [ ] PROJECT_PLAN.md updated to list spec 012 (this run)
