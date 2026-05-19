# Spec 013 — Implement `admesh._stages.background_grid` (port of `CreateBackgroundGrid.m`)

**Status**: Planning
**Tracks**: [#78](https://github.com/domattioli/ADMESH/issues/78)
**Companion**: [#73](https://github.com/domattioli/ADMESH/issues/73) (gap report); spec 012 (test contract)
**Branch**: `daily-issue-fixing` (no new branch — per CORE MANDATE)
**Severity**: medium · **Type**: port · **Scope**: numerics
**Constitution**: Principle I (MATLAB-numerical-identity) binds this port at `atol=1e-10`.

## 1. Problem statement

`admesh/_stages/background_grid.py` is a 7-line stub: docstring only,
no callable surface. The corresponding MATLAB source —
`01_ADMESH_Library/02_Create_Background_Grid/CreateBackgroundGrid.m` in
QuADMesh-MATLAB @ `19b2eb9` — drives stage 02 of the routine: it
synthesizes the regular background grid on which every downstream
size-field stage (curvature, medial-axis, bathymetry, dominate-tide,
inpaint, gradient-limit) interpolates and accumulates.

Today the routine driver works against the *empty* stub because
`admesh/_stages/routine.py` builds its background grid inline rather
than delegating to the stage module. That tactical inlining was an
expedient during spec 002 / spec 009, but it has three downstream
costs:

1. **No MATLAB-parity contract**: spec 012 wrote the parity test
   scaffolds (`tests/test_background_grid.py`, with four
   `xfail(strict=True, reason="blocked on #78")` markers — currently
   the file itself is deferred to the next impl run, but its contract
   is locked by spec 012).
2. **No stage-02 entry in PORTING_NOTES.md** — Constitution
   Principle I demands one for every faithful-port module.
3. **`admesh/background_grid.py` shim**: it `*`-imports the stub. The
   downstream surface contract locked by
   `tests/test_public_api_imports.py:40` would break if any future
   port were named differently from what the shim re-exports.

This spec ports `CreateBackgroundGrid.m` to NumPy and threads the
result through the existing routine driver in a single, audit-safe
swap.

## 2. Goals

1. Implement `admesh._stages.background_grid` with the same call
   signature shape as the MATLAB source: `(Domain, h0, padding) →
   BackgroundGrid` (exact field names ratified in §6.OQ-3 below).
2. Hit `atol=1e-10` parity against MATLAB on at least one fixture
   (unit square at `h0=0.1`, fixed padding).
3. Land a stage-02 entry in `docs/PORTING_NOTES.md` per Principle I.
4. Lift the four `xfail(strict=True, reason="blocked on #78")` markers
   in `tests/test_background_grid.py` (created in the spec 012
   follow-up run).
5. Preserve the `admesh.background_grid` shim contract locked by
   `tests/test_public_api_imports.py`.

## 3. Non-goals

- Touching the other 12 stage modules. Each has its own port and
  audit; this spec is stage-02 only.
- Rewriting `admesh/_stages/routine.py`'s inline grid construction
  beyond the minimum needed to delegate to the new module. A larger
  refactor is out of scope.
- GPU / multi-core acceleration of the grid construction (issue #8).
- Format-bridge changes to `admesh/fort14.py` or `admesh/gmsh.py`.
- Bathymetry / bathymetric interpolant changes (issue #65).

## 4. Functional requirements

### FR-013-1 — Public surface

The canonical module `admesh/_stages/background_grid.py` MUST expose
the following names:

- `create_background_grid(domain, h0, padding) -> BackgroundGrid`
  (function — the snake_case rename of MATLAB `CreateBackgroundGrid`).
- `BackgroundGrid` (frozen dataclass — see §6.OQ-3 for field names).

The shim `admesh/background_grid.py` MUST continue to re-export
`create_background_grid` and `BackgroundGrid` via the existing
`*`-import + `globals().update(...)` fallback. No new export contract
beyond what spec 012's test file would have demanded.

### FR-013-2 — Numerical identity to MATLAB

For the canonical input case (`Domain.from_polygon(UNIT_SQUARE)`,
`h0=0.1`, default padding), the Python output arrays MUST satisfy
`np.allclose(py_array, mat_array, atol=1e-10, rtol=0)` against the
MATLAB-exported fixture written by the new
`scripts/export_matlab_fixtures.m` stage-02 section.

### FR-013-3 — Property invariants

Independent of fixture parity, the returned `BackgroundGrid` MUST
satisfy:

- **Bbox cover**: the grid's spatial extent equals
  `domain.bbox` expanded by `padding` along each axis (open
  question: does MATLAB use absolute padding or `padding * h0`?
  Resolved by §6.OQ-1).
- **Spacing**: `Δx == Δy == h0` to numerical precision.
- **Uniformity**: the per-row spacing variance is exactly `0.0`.

These are the three property tests spec 012 scaffolded.

### FR-013-4 — Fixture export

`scripts/export_matlab_fixtures.m` MUST gain a stage-02 section that
emits `tests/fixtures/matlab/background_grid_unit_square.npz` (after
`mat_to_npz.py` conversion). The section MUST follow the existing
template (one `outdir =` line, one `if ~exist` guard, one
`CreateBackgroundGrid(...)` invocation, one `save(..., '-v7')`).

### FR-013-5 — Routine integration

`admesh/_stages/routine.py` MUST be updated to call
`create_background_grid(...)` rather than building the grid inline.
The output of `triangulate()` on any existing Tier-0 / Tier-1 / Tier-2
fixture MUST not change by more than `atol=1e-12` from the pre-port
baseline. (This is tighter than the MATLAB parity threshold because
it is a Python-to-Python comparison.)

### FR-013-6 — Docs

`docs/PORTING_NOTES.md` MUST gain a stage-02 entry following the
existing template (date, MATLAB source, Python target, substitution,
behavior diff, impact). The entry MUST cite the MATLAB pin
(`19b2eb9`) and reference both spec 012 and spec 013.

### FR-013-7 — xfail cleanup

The four `xfail(strict=True)` markers in
`tests/test_background_grid.py` MUST be removed in the same commit
that lands the port. CI's strict-xfail mode will catch any that are
forgotten.

## 5. Acceptance criteria

- [ ] `admesh._stages.background_grid.create_background_grid` is
      callable; its docstring cites MATLAB `19b2eb9`.
- [ ] `admesh._stages.background_grid.BackgroundGrid` is a frozen
      dataclass with the fields ratified in §6.OQ-3.
- [ ] `tests/fixtures/matlab/background_grid_unit_square.npz` exists
      and was produced by the new stage-02 section in
      `scripts/export_matlab_fixtures.m`.
- [ ] All four parity tests in `tests/test_background_grid.py` pass
      with `xfail` markers removed; `pytest -q tests/test_background_grid.py`
      exits 0.
- [ ] `tests/test_public_api_imports.py` still passes (shim contract
      preserved).
- [ ] `pytest -q` exits 0 over the full suite (no regression).
- [ ] `docs/PORTING_NOTES.md` has a `## 2026-NN-NN — stage 02 —
      Background grid port` entry.
- [ ] `git grep -n "build inline background grid\|TODO.*background"
      admesh/_stages/routine.py` returns nothing.

## 6. Open questions (must resolve before implementation)

### OQ-1 — Padding semantics

Does `CreateBackgroundGrid.m` expand `domain.bbox` by an absolute
`padding` value, or by `padding * h0`? The MATLAB call sites in
`ADMesh_Main.m` should disambiguate; the resolution is recorded in
the implementation issue's checklist.

**Resolution path**: read the first 50 lines of `CreateBackgroundGrid.m`;
trace how the `padding` argument is consumed.

### OQ-2 — Return shape

MATLAB likely returns either `(X, Y, mask)` (three `meshgrid`-shaped
arrays) or a single struct. The Python contract should be one frozen
dataclass — but its field names MUST mirror the MATLAB convention to
preserve audit-trail readability.

**Resolution path**: read the `return` statement / last 20 lines of
`CreateBackgroundGrid.m`.

### OQ-3 — `BackgroundGrid` field names

Pending OQ-2, candidate fields:

- `x: NDArray[np.float64]` (1-D, shape `(nx,)`) — column coordinates
- `y: NDArray[np.float64]` (1-D, shape `(ny,)`) — row coordinates
- `xx: NDArray[np.float64]` (2-D, shape `(ny, nx)`) — `meshgrid` X
- `yy: NDArray[np.float64]` (2-D, shape `(ny, nx)`) — `meshgrid` Y
- `delta: float` — spacing (== `h0`)
- `mask: NDArray[np.bool_]` (2-D, shape `(ny, nx)`) — in-domain SDF

If MATLAB returns fewer fields, drop the unused ones. Prefer minimal
surface to avoid lock-in on incidental fields.

### OQ-4 — Inline construction in `routine.py`

What exactly does the routine driver build today that
`create_background_grid` will replace? Need the line range so the
delete-and-replace is mechanical.

**Resolution path**: `git grep -n "meshgrid\|background.*grid\|bbox.*pad"
admesh/_stages/routine.py`.

## 7. Cross-repo impact

- **QuADMesh-MATLAB @ `19b2eb9`** — read-only reference. No upstream
  changes.
- **MADMESHR** — none (it consumes Python outputs, not stage
  internals).
- **CHILMESH** — none.
- **ADMESH-Domains** — none (this is upstream of the domain registry).

## 8. Risks

| Risk | Mitigation |
|---|---|
| MATLAB padding convention differs from what's intuited; parity test fails by a half-cell offset | OQ-1 resolved before implementation; fixture export is the ground truth |
| `meshgrid` X/Y ordering convention bites (NumPy `indexing='xy'` vs `'ij'`) | OQ-2/OQ-3 resolved before implementation; explicit `indexing='xy'` in code with comment |
| Routine-driver swap shifts numerical output of `triangulate()` by > `atol=1e-12` | FR-013-5 makes this a hard gate; bisect any drift to identify the divergent step |
| Shim contract regresses if naming differs from spec 012's xfail-test imports | Spec 012 tests import from `admesh._stages.background_grid` directly; shim is independent |
| MATLAB fixture export requires a MATLAB install at `19b2eb9` checkout, which CI lacks | Fixture is committed to repo (per existing precedent for curvature, medial_axis, bathymetry, etc.) |

## 9. Token budget

**SMALL/MEDIUM** — the port itself is < 200 lines of NumPy; the
fixture export adds ~20 lines of MATLAB; the test file already
exists in scaffold form (spec 012); the porting-notes entry is ~15
lines of markdown. Implementation fits in a single focused run.

## 10. Phasing

- **Phase A — Pre-flight** (this spec): resolve OQ-1..OQ-4 by reading
  MATLAB; commit the resolutions to this spec.
- **Phase B — Port** (impl run): write `create_background_grid`,
  `BackgroundGrid`, fixture export section, routine-driver swap.
- **Phase C — Parity** (impl run): export fixture (requires MATLAB),
  drop xfail markers, run full suite.
- **Phase D — Docs** (impl run): PORTING_NOTES.md entry; close #78.

This planning-only run lands Phase A artifacts only (spec, plan,
tasks). Phases B–D are an implementation-phase follow-up.
