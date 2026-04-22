# Session 3 — Phase P2 kickoff OR faithful-port backfill

**Goal (plain English):** either backfill faithful ports of the
session-2 clean-room modules (if the MATLAB clone is provisioned)
or advance to Phase P2 (physical-field sizing) as another
clean-room pass. The WS0 environment check decides the branch.

**Session-start read order** (per `CLAUDE.md` + Article VII):
`CONSTITUTION.md` → `PROJECT_PLAN.md` → `CLAUDE.md` →
`docs/session_2_state.md` → `docs/session_2_report.md` → this plan.

---

## WS0 — Environment provisioning check (mandatory)

**Do this first. It shapes the rest of the session.**

```bash
ls /workspace/QuADMesh-MATLAB/01_ADMESH_Library/ 2>/dev/null
```

- **If present (directory lists):** follow Branch A (faithful-port
  backfill).
- **If absent:** follow Branch B (Phase P2 clean-room). Append a
  `SOURCE_UNAVAILABLE` row to `docs/persistence_journal.md`. If
  this is the 3rd occurrence overall, propose an amendment to
  `CONSTITUTION.md` — either relax Article II.1 for
  no-clone environments or add a workflow-layer provisioning rule.

---

## Branch A — Faithful-port backfill

**Deliverables:** diff `admesh/curvature.py`, `admesh/medial_axis.py`,
`admesh/mesh_size.py::build_h` against `01_ADMESH_Library/{04,05,09,01}`;
resolve any algorithmic divergences; append "resolved" PORTING_NOTES
entries.

### WS1-A — `CurvatureFunction.m` faithful diff

**Steps:**
1. Read `01_ADMESH_Library/04_Curvature_Function/CurvatureFunction.m`
   end-to-end. Catalog stencil choice, boundary handling, masking
   rule, any `inpaint_nans` call.
2. If MATLAB diverges from our clean-room (likely at boundary /
   masking logic), adjust `admesh/curvature.py` to match — **keep
   the analytic-reference tests passing** while matching MATLAB
   output on a reference grid.
3. Capture a MATLAB fixture: run MATLAB on the unit disk + annulus
   and save `κ` to `tests/fixtures/curvature/{disk,annulus}.npz`.
   Add a parity test: `test_curvature_matlab_parity` in
   `tests/test_curvature.py`.

### WS2-A — `medial_distance_FMM.m` faithful diff

**Steps:**
1. Read `05_Medial_Axis/{MedialAxisFunction,TriMedialAxisFunction,
   medial_distance_FMM,heap}.m`.
2. Decide: keep `scipy.ndimage.distance_transform_edt` (EDT ≈ FMM
   with unit speed at fine grids) + document the equivalence, OR
   implement a heap-based FMM in `admesh.medial_axis._fmm_py` if
   MATLAB's heap has side-effects we need (e.g. medial-cell
   ordering affecting ties).
3. Fixture + parity test on annulus.

### WS3-A — `ADmeshRoutine.m` composer diff

**Steps:**
1. Read `01_ADMESH_Routine/ADmeshRoutine.m` to see how the MATLAB
   side composes curvature + medial + bathymetry into an h-field.
2. Adjust `admesh.mesh_size.build_h` to match — likely needs a
   rework of the reduction-term combination formula.
3. End-to-end fixture: MATLAB mesh a single domain with known
   parameters, compare final `(p, t)` cardinalities.

### WS-final-A

1. `pytest tests/ -q` green; MATLAB-parity tests included.
2. Update PORTING_NOTES.md entries from "deferred" to "resolved".
3. Update PROJECT_PLAN.md "Where we are today".
4. Session 3 report + state + session 4 plan (Phase P2 kickoff).

---

## Branch B — Phase P2 clean-room

**Deliverables:** `admesh/bathymetry.py`, `admesh/dominate_tide.py`,
`admesh/inpaint.py`, respective test files.

### WS1-B — `06_Bathymetry_Function` (clean-room)

**Steps:**
1. From context (PROJECT_PLAN, CLAUDE.md, ADCIRC literature),
   implement a bathymetry-driven size field:
   `h_bathy(p) ∝ depth / (wave-speed-scale)`. Takes a depth field
   (sampled or analytic) + a scale factor.
2. Add `BathymetryField` dataclass to pass depth data around.
3. Test on a synthetic linear bathymetry: `depth(x, y) = 10 + x`.

### WS2-B — `07_Dominate_Tide` (clean-room)

**Steps:**
1. Implement tidal-wavelength sizing:
   `h_tide = wavelength(depth) / resolution_factor`.
   Wavelength via shallow-water approx: `c = sqrt(g·depth)`,
   `λ = c · T_tide`. Default `T_tide = 12.42 h` (M2 component).
2. Test: constant-depth case yields uniform h_tide.

### WS3-B — `13_In_Paint_NaNs`

**Steps:**
1. Implement `inpaint_nans` via `scipy.interpolate.griddata`
   nearest-neighbor fallback inside a convex hull of known data.
2. Hook into the composer as a preprocessing step for any sampled
   field (bathymetry, tidal) with gaps.
3. Test on a chessboard-NaN pattern.

### WS-final-B

1. `pytest tests/ -q` green. Target: ≥75 tests.
2. 3 new PORTING_NOTES entries (all "deferred clean-room").
3. Update PROJECT_PLAN.md.
4. Session 3 report + state + session 4 plan.

---

## Session budget (either branch)

- WS0: ≤ 5%.
- WS1/WS2/WS3: ~75% total, roughly evenly split.
- WS-final: ~20%.

Do not mix branches. If WS0 is ambiguous (e.g. MATLAB partial
clone, missing some but not other files), go with Branch B —
consistency of scope beats coverage.
