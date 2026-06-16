# Plan 013 — Implementation plan for background-grid port

**Spec**: `specs/013-background-grid-impl/spec.md`
**Branch**: `daily-maintenance`

## Approach

The MATLAB stage-02 source is small (a single `meshgrid` plus a
domain-SDF mask, by inspection of analogous stage-03 / stage-04
modules). The port is mechanically straightforward; the
non-mechanical work is OQ-1..OQ-4 resolution and the routine-driver
swap.

We execute in five passes, each landable as its own commit:

### Pass 1 — OQ resolution (read MATLAB, write into spec)

Inputs: `01_ADMESH_Library/02_Create_Background_Grid/CreateBackgroundGrid.m`
at QuADMesh-MATLAB `19b2eb9`.

Resolve in order:

1. **OQ-1 (padding semantics)**. Trace `padding` from call-site
   downward.
2. **OQ-2 (return shape)**. Identify the `return` statement / last
   assignment.
3. **OQ-3 (BackgroundGrid field names)**. Synthesize the dataclass
   shape from OQ-2.
4. **OQ-4 (routine inline ranges)**. `git grep` in
   `admesh/_stages/routine.py`; record line ranges.

Output: append a "Resolutions" section to `spec.md`. No code yet.

### Pass 2 — Test scaffold materialization (if spec 012 follow-up hasn't shipped)

Spec 012 has tasks T-012-2 (test file) and T-012-3 (TEST-AUDIT
update) parked. They may or may not have landed by the time spec
013 implementation begins. If they haven't, materialize them
*first* — spec 013 should never be the run that creates the test
file, because the xfail markers are spec 012's contract surface.

Skip if `tests/test_background_grid.py` already exists with the
four `xfail(strict=True, reason="blocked on #78")` markers.

### Pass 3 — Pure NumPy port

File: `admesh/_stages/background_grid.py`. Replace the stub with:

```python
"""background_grid — port of CreateBackgroundGrid.m.

MATLAB source: github.com/domattioli/QuADMesh-MATLAB @ 19b2eb9,
path 01_ADMESH_Library/02_Create_Background_Grid/CreateBackgroundGrid.m.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from numpy.typing import NDArray
from admesh.api import Domain


@dataclass(frozen=True, slots=True)
class BackgroundGrid:
    # field names ratified by OQ-3; placeholders here
    x: NDArray[np.float64]
    y: NDArray[np.float64]
    xx: NDArray[np.float64]
    yy: NDArray[np.float64]
    delta: float
    mask: NDArray[np.bool_]


def create_background_grid(
    domain: Domain, h0: float, padding: float
) -> BackgroundGrid:
    """Port of CreateBackgroundGrid.m. See module docstring for MATLAB pin."""
    # implementation TBD; see spec 013 OQ-2/OQ-3
    ...
```

Key MATLAB → NumPy substitutions to expect:

| MATLAB | NumPy |
|---|---|
| `[X, Y] = meshgrid(xs, ys)` | `xx, yy = np.meshgrid(xs, ys, indexing='xy')` |
| `xs = xmin:h0:xmax` | `xs = np.arange(xmin, xmax + h0/2, h0)` (half-step guard against floating-point fencepost) |
| `mask = Domain.SDF(X, Y) < 0` | `mask = domain.sdf(np.column_stack([xx.ravel(), yy.ravel()])).reshape(xx.shape) < 0` |
| `padding * h0` | resolved by OQ-1 |

### Pass 4 — Routine-driver swap

File: `admesh/_stages/routine.py`. Replace the inline grid
construction (line range from OQ-4) with a single call:

```python
bg = create_background_grid(domain, h0=h0, padding=padding)
X, Y, mask = bg.xx, bg.yy, bg.mask  # adapter for downstream stages
```

Adapter alias keeps downstream stages untouched. A future spec can
push the `BackgroundGrid` object all the way through; that is
explicitly out of scope here.

Run `pytest -q tests/test_routine.py tests/test_api_triangulate.py
tests/test_default_size_field.py` — these are the three suites that
exercise `triangulate()` end-to-end. Any drift > `atol=1e-12` is a
defect in the port; bisect before proceeding.

### Pass 5 — Fixture export + xfail cleanup

#### Pass 5a — MATLAB fixture export

Add to `scripts/export_matlab_fixtures.m` (following the existing
template, after the curvature / medial-axis blocks):

```matlab
%% 02_Create_Background_Grid: CreateBackgroundGrid on the unit square =====
outdir = fullfile(FIXTURE_ROOT, 'background_grid');
if ~exist(outdir, 'dir'); mkdir(outdir); end

% Unit-square Domain, h0=0.1, default padding.
PTS = struct('Points', {{[0 0; 1 0; 1 1; 0 1]}});
h0 = 0.1;
padding = 0.05;   % TODO: confirm via OQ-1
[X, Y, mask, delta] = CreateBackgroundGrid(PTS, h0, padding);
save(fullfile(outdir, 'unit_square.mat'), ...
     'X', 'Y', 'mask', 'delta', 'h0', 'padding', '-v7');
```

Run the exporter via MATLAB; run `python scripts/mat_to_npz.py` to
emit `tests/fixtures/matlab/background_grid_unit_square.npz`.

#### Pass 5b — xfail cleanup

In `tests/test_background_grid.py` remove the four
`@pytest.mark.xfail(strict=True, reason="blocked on #78")` decorators.
CI's strict-xfail mode will catch any forgotten ones.

#### Pass 5c — Porting note

Append to `docs/PORTING_NOTES.md`:

```
## YYYY-MM-DD — stage 02 — Background grid port (spec 013, issue #78)

**MATLAB**: `CreateBackgroundGrid(PTS, h0, padding)` in
`01_ADMESH_Library/02_Create_Background_Grid/CreateBackgroundGrid.m`
@ `19b2eb9`.
**Python**: `admesh._stages.background_grid.create_background_grid(domain, h0, padding)`.
**Substitution**: `meshgrid(xs, ys)` → `np.meshgrid(xs, ys, indexing='xy')`;
`xs = a:h:b` → `np.arange(a, b + h/2, h)` (half-step floating-point guard);
return tuple → frozen `BackgroundGrid` dataclass.
**Behavior diff**: <fill from OQ-1>.
**Impact**: `admesh._stages.routine.triangulate()` now delegates
stage-02 to this module; output unchanged within `atol=1e-12`
(verified against Tier-0 / Tier-1 / Tier-2 fixtures).
```

## Files affected

- `admesh/_stages/background_grid.py` (replace stub)
- `admesh/_stages/routine.py` (delegate to new module)
- `scripts/export_matlab_fixtures.m` (add stage-02 section)
- `tests/test_background_grid.py` (remove xfail markers)
- `tests/fixtures/matlab/background_grid_unit_square.npz` (new fixture)
- `docs/PORTING_NOTES.md` (new entry)
- `specs/013-background-grid-impl/spec.md` (resolutions appended)

## Validation gates

1. **OQ resolution**: `spec.md` "Resolutions" section non-empty before
   any code lands.
2. **Module-level smoke**: `python -c "from admesh._stages.background_grid
   import create_background_grid, BackgroundGrid"` succeeds.
3. **Parity**: `pytest -q tests/test_background_grid.py` exits 0 with
   `xfail` markers removed.
4. **No regression**: `pytest -q` over the full suite exits 0.
5. **Shim contract**: `pytest -q tests/test_public_api_imports.py` exits 0.
6. **Pre-tag check**: `bash scripts/pre_tag_check.sh` exits 0.

## Rollback

If Pass 3 / Pass 4 introduces a regression and bisecting is not
tractable in the impl run, revert the routine-driver swap (Pass 4
only) and leave the port module in place but unwired. The four
`xfail` markers stay in place; the spec stays open with the
regression cause recorded.

## Cross-cutting

- **Constitution Principle I**: enforced by FR-013-2 / FR-013-6.
- **Principle II (no branch proliferation)**: all passes on
  `daily-maintenance`.
- **Principle III (audit gates close)**: F-MED-01 / B-05 close once
  Pass 5b finishes.

## Out of scope (explicit reminders)

- Other stages (stage 01, 03, 04, ...) — separate ports.
- Quality gates beyond bbox-cover / spacing / uniformity — spec 002 / spec 009 own those.
- Multi-core / GPU acceleration — issue #8.
- Bathymetry-aware grid refinement — issue #65.
