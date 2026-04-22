# Session 4 — Phase P2: physical-field sizing

**Goal (plain English):** add depth-driven (`bathymetry`) and
tidal-wavelength-driven (`dominate_tide`) size fields, plus a
utility (`inpaint`) that heals sparse gridded data before it's
used. With PTS now available (session 3), these modules can pin
per-segment physical context when relevant.

**Session-start read order** (per `CLAUDE.md` + Article VII):
`CONSTITUTION.md` → `PROJECT_PLAN.md` → `CLAUDE.md` →
`docs/session_3_state.md` → `docs/session_3_report.md` → this plan.

---

## WS0 — Environment check

```bash
ls /workspace/QuADMesh-MATLAB/01_ADMESH_Library/ 2>/dev/null
```

- **Absent** → 3rd `SOURCE_UNAVAILABLE`. Propose a Constitution
  amendment (Article II.1 codicil: when the clone is unreachable,
  clean-room + deferred-faithful-port is the default, and the
  codicil auto-lifts when the clone becomes available).
- **Present** → Article II.1 applies normally; capture MATLAB
  fixtures this session.

---

## Binding gate

All of:

1. `admesh/bathymetry.py` — `BathymetryField` dataclass (xy grid +
   depth samples), `BathymetryField.from_callable(depth_fn, bbox,
   delta)`, `bathymetry_size(field, *, base, depth_ref, hmin, hmax)`.
2. `admesh/dominate_tide.py` — `tidal_wavelength(depth, *, period)`,
   `tide_size(field, *, n_per_wavelength, period, hmin, hmax)`.
3. `admesh/inpaint.py` — `inpaint_nans(arr)` nearest-neighbor fill
   inside the convex hull of known data; preserves outside-NaN.
4. `admesh.mesh_size.build_h` extended to take an optional
   `bathymetry: BathymetryField | None` and/or `tide_scale` kwarg
   wiring through the same reduction pipeline as curvature /
   medial / boundary.
5. `pytest tests/ -q` green; target ≥ 95 tests (82 + 13 new:
   ~6 bathymetry, ~4 tide, ~3 inpaint).
6. MVP M.4 gate still passes.

---

## Workstreams

### WS1 — `bathymetry`

**Deliverables:** `admesh/bathymetry.py`, `tests/test_bathymetry.py`.

**Steps:**
1. `BathymetryField` dataclass: `xs, ys: (1D,)`, `depth: (LY, LX)`
   with shape validation + `.sample(p)` via
   `RegularGridInterpolator`. Classmethod
   `from_callable(depth_fn, bbox, delta)`.
2. `bathymetry_size(field, *, base, depth_ref, hmin, hmax)`:
   `h = clip(base * depth / depth_ref, hmin, hmax)`; NaN where
   depth ≤ 0 or NaN.
3. Tests: linear-depth analytic + sampling accuracy +
   out-of-bbox NaN + hmin/hmax clamps + invalid-arg rejection.

### WS2 — `dominate_tide`

**Deliverables:** `admesh/dominate_tide.py`,
`tests/test_dominate_tide.py`.

**Steps:**
1. `tidal_wavelength(depth, *, period=T_M2)` — long-wave
   `λ = sqrt(g·depth) * period`; NaN for depth ≤ 0.
2. `tide_size(field, *, n_per_wavelength=100, period=T_M2, hmin,
   hmax)`.
3. Constants: `_G = 9.80665`, `T_M2 ≈ 44714 s`.
4. Tests: constant-depth uniform h; scaling with depth; NaN path;
   n_per_wavelength validation.

### WS3 — `inpaint_nans`

**Deliverables:** `admesh/inpaint.py`, `tests/test_inpaint.py`.

**Steps:**
1. Implement nearest-neighbor fill using
   `scipy.interpolate.griddata` or `scipy.ndimage.distance_transform_edt`.
2. Document the boundary semantic: values outside the convex hull
   of known data remain NaN (caller handles via clip/assign).
3. Tests: chessboard-NaN, random holes, full-grid (no-op), all-NaN
   rejection.

### WS4 — integration into `build_h`

**Deliverables:** updated `admesh.mesh_size.build_h`, extensions to
`tests/test_mesh_size.py`.

**Steps:**
1. Add `bathymetry: BathymetryField | None = None`,
   `depth_ref: float | None = None`, `tide_n_per_wavelength:
   float | None = None` kwargs. When set, compose into `h` after
   curvature/medial/PTS.
2. End-to-end test: a synthetic shallow-coastal domain (linear
   depth from 0.5 m at shore to 20 m offshore) produces a mesh
   with finer resolution near the shore.

### WS-final

1. `pytest tests/ -q` green; ≥ 95 tests.
2. 3 new PORTING_NOTES entries (all deferred-faithful-port flagged).
3. Update `PROJECT_PLAN.md` "Where we are today".
4. Session 4 report + state + draft session 5 plan (Phase P3
   completion — full `ADmeshRoutine.m` port OR faithful-port
   backfill of all clean-room modules, depending on MATLAB-clone
   availability).

---

## Out of scope for session 4

- Faithful-port backfill (blocked on MATLAB clone).
- Full `ADmeshRoutine.m` orchestration (session 5+).
- PyPI publish / public repo flip (Phase P4 wrap).

---

## Session budget

- WS0: ≤ 3%.
- WS1 (bathymetry): ~25%.
- WS2 (dominate_tide): ~15%.
- WS3 (inpaint): ~15%.
- WS4 (build_h integration + end-to-end test): ~30%.
- WS-final: ~12%.
