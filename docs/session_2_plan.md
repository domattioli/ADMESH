# Session 2 — Phase P1 kickoff: sizing enrichments

**Goal (plain English):** unlock richer mesh-size fields by porting
`04_Curvature_Function` and `05_Medial_Axis`, and wire them as
**optional ingredients** (not defaults) of the `admesh.mesh_size`
h-field composition. When this session ships, the Python port can
build curvature- and medial-axis-aware size fields at parity with
MATLAB on the five MVP domains (analytic curvature reference), and
`triangulate(..., fh=...)` accepts a composed `fh`.

**Session-start read order** (per `CLAUDE.md` + Article VII):
`CONSTITUTION.md` → `PROJECT_PLAN.md` → `CLAUDE.md` →
`docs/session_1_state.md` → `docs/session_1_report.md` → this plan.

---

## Binding gate

All four of:

1. `admesh.curvature.curvature_function(...)` returns a grid
   curvature field matching the analytic reference (`κ = 1/r` on
   the unit disk) to `atol=1e-6, rtol=1e-4` on a 200×200 grid.
2. `admesh.medial_axis.medial_distance_fmm(...)` returns a
   fast-marching distance-to-medial-axis field on the annulus that
   agrees with the analytic reference (`r_inner + (outer-inner)/2 -
   r`) to `atol=1e-3` on a 200×200 grid.
3. `admesh.mesh_size` exposes a composer `build_h(...)` that takes
   a baseline + optional (curvature, medial) ingredients and
   returns an `fh(points)` callable. MVP `triangulate(domain)`
   default behavior is unchanged (uniform size).
4. `pytest tests/ -q` green; at least `tests/test_curvature.py` and
   `tests/test_medial_axis.py` added; full count ≥ 60.

---

## Workstreams

### WS1 — `04_Curvature_Function` port

**Deliverables:** `admesh/curvature.py`, `tests/test_curvature.py`.

**Steps:**
1. Read `CurvatureFunction.m` + helpers in
   `/workspace/QuADMesh-MATLAB/01_ADMESH_Library/04_Curvature_Function/`.
   Catalog every MATLAB-toolbox call; note the substitution in
   `docs/PORTING_NOTES.md`.
2. Implement `curvature_function(fd, bbox, h)` returning a grid
   curvature field. Internally: evaluate `fd` on the grid, compute
   `κ = div(grad fd / |grad fd|)` via 4th-order finite differences
   (same stencil pattern as `admesh.distance.grad_sdf`).
3. Test on `unit_disk` (analytic `κ = 1/r`) and `annulus` (analytic
   on both rings). Mask corners for `unit_square` / `l_shape` /
   `notched_rectangle` where κ is undefined (|grad fd| → 0).
4. Populate `docs/PORTING_NOTES.md` with any MATLAB-toolbox
   substitutions made during the port.

**Risk:** the MATLAB source may use `inpaint_nans` (stage 13) to
heal undefined-κ regions. If so, a stub `admesh.inpaint` that wraps
`scipy.ndimage`-based interpolation is acceptable for session 2;
full port lands in Phase P2.

### WS2 — `05_Medial_Axis` port + FMM

**Deliverables:** `admesh/medial_axis.py`, `tests/test_medial_axis.py`.

**Steps:**
1. Read `MedialAxisFunction.m`, `TriMedialAxisFunction.m`,
   `medial_distance_FMM.m` + heap helper in
   `/workspace/QuADMesh-MATLAB/01_ADMESH_Library/05_Medial_Axis/`.
2. Implement `medial_distance_fmm(D, ...)` using
   `skfmm.distance` if available, else a pure-Python heap-based
   fast-marching (preferred for zero-extra-deps). Document the
   choice in a `# port:` comment.
3. Implement `medial_axis_function(fd, bbox, h)` returning the
   distance-to-medial-axis field used by the size-field composer.
4. Test on `annulus` (analytic medial ring at `r = (inner+outer)/2`)
   and `unit_disk` (medial point at origin).

**Risk:** MATLAB's `medial_distance_FMM.m` may hand-roll the
min-heap. If we use `skfmm`, parity is approximate (skfmm uses a
second-order scheme by default); document the divergence.

### WS3 — size-field composer

**Deliverables:** `admesh.mesh_size.build_h`, updated
`tests/test_mesh_size.py`.

**Steps:**
1. Add `build_h(domain, *, base=0.1, curvature_scale=None,
   medial_scale=None, g=0.2) -> SizeFn`. When both scales are
   `None`, returns a uniform-size callable (existing MVP default).
2. When either scale is set, construct the combined size field via
   the gradient-limited PDE solver (`solve_iter`) seeded with the
   composed initial field; return an interpolant-backed callable.
3. Add an end-to-end test: `triangulate(annulus, fh=build_h(annulus,
   curvature_scale=0.3))` produces a mesh with smaller elements
   near both circular boundaries than in the MVP uniform-size
   version.

### WS-final — wrap-up

1. `pytest tests/ -q` green.
2. Update `PROJECT_PLAN.md` "Where we are today" for
   post-P1 / session-2 state.
3. Write `docs/session_2_report.md` + `docs/session_2_state.md`.
4. Draft `docs/session_3_plan.md` targeting Phase P2 kickoff
   (`06_Bathymetry_Function` + `07_Dominate_Tide` + `13_In_Paint_NaNs`).
5. Commit + push to the session's designated branch. Do NOT auto-open
   a PR.

---

## Out of scope for session 2

- Phase P2+ (bathymetry, tide, boundary, inpaint, full routine) —
  session 3+.
- Quad conversion — permanently out of ADMESH scope (see
  `PROJECT_PLAN.md` 2026-04-18 revision).
- Changing the MVP `triangulate(domain)` default — the uniform-size
  path must remain the zero-config default.

---

## Session budget

- WS1 (mandatory): ~35% of budget.
- WS2 (mandatory): ~35%.
- WS3 (mandatory): ~20%.
- WS-final: ~10%.

Curvature + medial-axis are paired; if WS1 overflows, the composer
in WS3 can skip the curvature branch (medial-only composer is still
a useful milestone). Re-plan if both WS1 and WS2 overflow.
