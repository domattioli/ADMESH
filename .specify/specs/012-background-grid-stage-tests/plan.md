# Plan 012 — Direct stage tests for `admesh._stages.background_grid`

**Spec**: `specs/012-background-grid-stage-tests/spec.md`
**Branch**: `daily-maintenance`
**Phase**: Planning (no code commits this run)

## 1. Architecture decisions

### AD-012-1 — Two-track delivery

The spec splits work into Track A (smoke + scaffolds, lands now) and
Track B (numerical parity, blocked on impl). Rationale:

- The audit gate B-05 is real and closeable today via Track A.
- Track B has a genuine prerequisite (the port) and parking the
  parity contract behind `xfail(strict=True)` is preferable to either
  (a) leaving it unspecified or (b) writing it inline in the impl
  spec where it would be invisible from the audit.
- `strict=True` on the xfail means "the day this starts passing, CI
  forces us to delete the marker." That is the desired audit signal.

### AD-012-2 — Canonical module path, not the shim

Tests import from `admesh._stages.background_grid` rather than
`admesh.background_grid`. The shim is documented as scheduled for
removal at ADMESH 1.0.0; locking the parity contract on the shim would
either (a) force keeping the shim past 1.0.0 or (b) require rewriting
the parity tests at the deprecation. The shim's surface contract is
already locked by `tests/test_public_api_imports.py:40`.

### AD-012-3 — Fixture format

MATLAB-exported reference grids land as `.npz` files under
`tests/fixtures/matlab/`. This is the format Spec 002 / Spec 009 use
for the size-field stages, so the test conventions stay uniform.

### AD-012-4 — No changes under `admesh/`

This spec adds tests only. It explicitly does not touch the stub
`admesh/_stages/background_grid.py`. The port is a separate
implementation issue.

### AD-012-5 — Two specs, two issues

This spec (012) tracks the test scaffolding only. A new GitHub issue
will be opened to track the port itself. Reasoning: the original
audit finding (F-MED-01) is about *test coverage*, not about
*implementation completeness*. Conflating them would let the test gap
hide indefinitely behind the larger port effort.

## 2. Critical files

| Path | Purpose | Change type |
|---|---|---|
| `specs/012-background-grid-stage-tests/spec.md` | Functional spec | NEW (this run) |
| `specs/012-background-grid-stage-tests/plan.md` | This file | NEW (this run) |
| `specs/012-background-grid-stage-tests/tasks.md` | Task decomposition | NEW (this run) |
| `tests/test_background_grid.py` | New stage test | NEW (Track A — next run) |
| `tests/fixtures/matlab/background_grid_unit_square.npz` | MATLAB parity fixture | NEW (Track B — blocked) |
| `scripts/export_matlab_fixtures.m` | Fixture exporter | MODIFY (Track B — blocked) |
| `TEST-AUDIT.md` | Audit status | MODIFY (Track A — next run) |
| `admesh/_stages/background_grid.py` | The stub being tested | UNCHANGED |
| `admesh/background_grid.py` | Re-export shim | UNCHANGED |

## 3. Sequencing

```
Spec 012 (this run)
    │
    ├── Track A (next implementation run on daily-maintenance)
    │     ├── T-012-1  Verify fixture exporter state
    │     ├── T-012-2  Create test scaffold (smoke + xfail parity)
    │     ├── T-012-3  Update TEST-AUDIT.md (F-MED-01, B-05)
    │     └── T-012-4  Open follow-up impl issue, fill xfail reasons
    │
    └── Track B (blocked on follow-up impl issue)
          ├── T-012-5  Port CreateBackgroundGrid.m (NEW SPEC, NEW ISSUE)
          ├── T-012-6  Export MATLAB fixture
          └── T-012-7  Remove xfail markers when tests start passing
```

Track A is one implementation run. Track B is gated on a separate spec.

## 4. Cross-repo integration points

- **MADMESHR**: MATLAB source of truth lives at
  `github.com/domattioli/QuADMesh-MATLAB @ 19b2eb9 / 01_ADMESH_Library/02_Create_Background_Grid/CreateBackgroundGrid.m`.
  Track B requires re-running the MATLAB script to generate the
  `.npz` fixture. No new MADMESHR changes; this consumes the existing
  reference.
- **ADMESH-Domains**: not involved. Stage 02 operates on a `Domain`
  produced from a polygon or fort.14 input; the registry sibling has
  no role here.
- **CHILMESH**: not involved.
- **DomI**: spec uses the daily-maintenance workflow conventions
  established by spec 009 / 010 / 011 (linked branch, audit gates,
  Constitution Principle I citation).

## 5. Validation strategy (Track A, when implemented)

1. `pytest -q tests/test_background_grid.py` exits 0 (smoke passes,
   xfails marked).
2. `pytest -q` on the full suite exits 0 (no regression).
3. `grep -n "F-MED-01\|B-05" TEST-AUDIT.md` shows the updated status
   lines.
4. The new follow-up impl issue exists and is linked from the spec.

## 6. Token budget recap

SMALL — three markdown files for this run, plus a follow-up issue.
Track A implementation will be a separate SMALL run (single test file,
~80 lines, plus a 2-line audit update). Track B is XL and out of
scope here.
