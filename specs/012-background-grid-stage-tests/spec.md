# Spec 012 — Direct stage tests for `admesh._stages.background_grid`

**Status**: Planning
**Tracks**: [#73](https://github.com/domattioli/ADMESH/issues/73)
**Branch**: `daily-maintenance` (no new branch — per CORE MANDATE)
**Severity**: low · **Type**: enhancement · **Scope**: tests
**Companion**: `TEST-AUDIT.md` backlog item B-05 (finding F-MED-01)

## 1. Problem statement

`admesh/background_grid.py` is a re-export shim. The canonical module
`admesh/_stages/background_grid.py` is the MATLAB-faithful port target
for stage 02 (`02_Create_Background_Grid/CreateBackgroundGrid.m`).
Constitution Principle I (MATLAB-numerical-identity) binds this stage
to bit-stable parity with its MATLAB ancestor, but there is no eponymous
`tests/test_background_grid.py` to lock that contract. Coverage today is
implicit through `tests/test_routine.py` driving `triangulate()`, which
exercises the stage transitively but does not assert its outputs in
isolation.

A complication surfaced during planning: the canonical module is
currently a 7-line stub (docstring only). It contains no callable
surface, so a numerical-parity test would be vacuously red and a
behavior test would have nothing to call. The audit finding F-MED-01
nonetheless remains valid — the *gap* it identifies is real even if
filling it requires the port itself.

## 2. Goals

1. Close finding F-MED-01 by producing a stable, named test module
   `tests/test_background_grid.py` that exercises the public surface
   of `admesh._stages.background_grid` directly (not via the routine
   driver).
2. Lock the MATLAB-parity contract for stage 02 at `atol=1e-10` once
   the underlying port lands.
3. Establish an unambiguous dependency edge so the audit gate
   (B-05) is closeable now via Track A (scaffold + smoke), with
   Track B (numerical parity) parked behind a clearly-tracked
   implementation follow-up.
4. Avoid permanently red tests: any test that calls into the not-yet-
   ported surface MUST be marked `pytest.mark.xfail(strict=True, reason=...)`
   pointing at the follow-up issue, so when the port lands and the
   test starts passing CI flags the xfail for removal.

## 3. Non-goals

- Porting `CreateBackgroundGrid.m` itself. That is the follow-up
  implementation issue this spec opens, not this spec.
- Touching `admesh/background_grid.py` (the shim). It already re-exports
  the canonical module via `*`-import and the `globals().update(...)`
  fallback, which is the surface contract `test_public_api_imports.py`
  already locks.
- Adding new MATLAB fixture-export plumbing if `scripts/export_matlab_fixtures.m`
  already has a target for stage 02. (Verification task in `tasks.md`.)
- Adjusting the audit `TEST-AUDIT.md` Tier-1 / Tier-2 budgets. New
  tests inherit the `slow` marker policy from B-03 / F-HIGH-02.

## 4. Functional requirements

### FR-012-1 — `tests/test_background_grid.py` exists

The test file MUST be created at `tests/test_background_grid.py`. It
MUST import from the canonical module path `admesh._stages.background_grid`
(not from the shim `admesh.background_grid`) so the contract test
locks the canonical surface and is immune to shim deletion at 1.0.0.

### FR-012-2 — Smoke test (Track A, lands now)

The file MUST contain at least one always-passing smoke test that:

- Imports `admesh._stages.background_grid as bg_stage`.
- Asserts the module has a non-empty `__doc__`.
- Asserts the module's MATLAB-source reference (`02_Create_Background_Grid/CreateBackgroundGrid.m`)
  is mentioned in the docstring (regex match), pinning the
  provenance contract documented in Constitution Principle I.

This test is the lowest stable contract the module can hold *today*,
before any callable surface lands. It closes B-05's "no eponymous file"
gap immediately.

### FR-012-3 — Parity test scaffold (Track B, xfail until impl lands)

The file MUST also contain the parity-test scaffolds with the SAME
inputs the issue body proposed:

- Inputs: `Domain.from_polygon(UNIT_SQUARE)` (or equivalent unit
  square), `h0=0.1`, fixed seed.
- Assertions (all currently `xfail(strict=True)`):
  - Returned grid bounding box equals `domain.bbox` ± padding tolerance.
  - Grid spacing equals `h0` along both axes.
  - Grid is uniform in both axes (constant Δx, constant Δy).
- Each test MUST be marked
  `@pytest.mark.xfail(strict=True, reason="blocked on #78")`
  (the implementation-tracking issue opened by this spec).

### FR-012-4 — MATLAB-fixture parity test (Track B, xfail until impl lands)

A second parity test MUST be scaffolded that loads a MATLAB-exported
fixture (e.g. `tests/fixtures/matlab/background_grid_unit_square.npz`)
and asserts `np.allclose(py_grid, mat_grid, atol=1e-10)`. This test
MUST also be `xfail(strict=True)` until both:
1. The port lands.
2. `scripts/export_matlab_fixtures.m` is extended to export a stage-02
   fixture and the resulting `.npz` is committed under
   `tests/fixtures/matlab/`.

### FR-012-5 — Audit gate

Once Track A lands, `TEST-AUDIT.md` MUST be updated to reflect:

- F-MED-01 status: superseded — direct test file now exists.
- B-05 status: partially resolved by Track A; full closure depends
  on the follow-up implementation issue completing Track B.

### FR-012-6 — Follow-up implementation issue

A new GitHub issue MUST be opened with the title
`Implement admesh._stages.background_grid (port of CreateBackgroundGrid.m)`,
linked from this spec, and referenced by the `xfail` reasons in the
test file. The follow-up issue closes when Track B's tests start
passing without `xfail`.

## 5. Acceptance criteria

- [ ] `tests/test_background_grid.py` exists and imports from
      `admesh._stages.background_grid`.
- [ ] At least one smoke test passes under `pytest tests/test_background_grid.py`.
- [ ] At least three parity-test scaffolds are present, each marked
      `xfail(strict=True)` with a reason pointing at the follow-up
      implementation issue.
- [ ] `pytest -q` exits 0 on the suite (no new red tests, only
      pre-existing greens plus the new xfails).
- [ ] `TEST-AUDIT.md` updated: F-MED-01 marked superseded, B-05
      marked "Track A done; Track B pending #78".
- [x] Follow-up implementation issue opened, linked from spec 012
      (issue #78, opened 2026-05-19).
- [ ] No code under `admesh/` is modified.
- [ ] All work lands on `daily-maintenance`.

## 6. Risks and mitigations

| Risk | Mitigation |
|---|---|
| `xfail(strict=True)` tests pass unexpectedly (e.g. because the port slipped in on a parallel branch) and break CI before the contract is reviewed | The strict-xfail failure mode is itself the desired signal — it forces review when the impl lands. |
| Smoke test couples too tightly to docstring text and breaks on minor edits | Pin the regex to the MATLAB source path (`02_Create_Background_Grid/CreateBackgroundGrid.m`), which is the provenance contract, not a prose summary that can be reworded. |
| Implementation port (follow-up issue) is much larger than the test spec | That is the correct framing: this spec scoped only the tests. The port lives in its own spec when it lands. |
| MATLAB fixture file does not yet exist and the parity test can't even import | `xfail` covers import-time `FileNotFoundError`; fixture creation is a Track B prerequisite, listed in tasks.md. |

## 7. Open questions

- **OQ-1**: Does `scripts/export_matlab_fixtures.m` already export stage 02?
  Resolution: **NO** (verified 2026-05-19 during T-012-1 — `grep -n
  "background_grid\|CreateBackgroundGrid\|02_Create" scripts/export_matlab_fixtures.m`
  returns nothing). The fixture exporter must gain a stage-02 target
  as part of issue #78 (Track B / T-012-6).
- **OQ-2**: Should the smoke test live in `tests/test_background_grid.py`
  or in `tests/test_public_api_imports.py` (which already imports the
  shim)? Resolution: keep it in `tests/test_background_grid.py` to
  match the issue's "eponymous file" requirement.
- **OQ-3**: Should `tests/test_background_grid.py` also import the
  shim `admesh.background_grid` to lock the re-export surface?
  Resolution: NO. `test_public_api_imports.py:40` already does that.
  Splitting the responsibility keeps each file's failure mode crisp.
