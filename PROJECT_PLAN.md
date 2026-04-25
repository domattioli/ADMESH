# ADMESH Project Plan

Phased roadmap for porting `QuADMesh-MATLAB/01_ADMESH_Library` to
Python. Governance rules in `CONSTITUTION.md`; code layout in
`CLAUDE.md`.

---

## Where we are today (2026-04-25, post-spec-001)

**Shipped (spec 001 — Pythonic API + fort.14 I/O):**
- v1 Pythonic surface in `admesh/api.py`, `admesh/fort14.py`,
  `admesh/boundary_types.py`, `admesh/size_field.py`, `admesh/viz.py`
  — strictly additive over the 13 faithful-port stage modules
  (Constitution Principle I unbroken). The 142-test faithful-port
  baseline still passes, with `tests/test_smoke.py` the only
  test-tree edit (taught to skip class re-exports).
- 3-line happy path runs end-to-end on all 5 MVP domains:
  `domain_from_polygon([ring])` → `triangulate(domain)` →
  `mesh.to_fort14(path)`. Round-trip equal at `atol=1e-5` on
  `unit_square`, `l_shape`, `unit_disk`, `annulus`,
  `notched_rectangle`. Evidence in
  `tests/output/quickstart_validation.txt`.
- ADCIRC v55 fort.14 reader/writer with ``Fort14ParseError``
  carrying ``line_no/expected/actual``. Open-segments / land-
  segments round-trip; named (`OPEN/MAINLAND/ISLAND/MAINLAND_FLUX`)
  and unmapped numeric BC codes both preserved.
- Real-world stress test: `tests/fixtures/fort14/adcirc_examples/
  wnat_test.14` (1.2 MB, 9,934 nodes, US East Coast + Gulf of
  Mexico + Caribbean) parses, round-trips, and re-triangulates via
  `scripts/wnat_demo.py`.
- chilmesh round-trip: 8 compat tests cover BC label preservation
  across the fort.14 boundary; a separate gated smoke test exercises
  `chilmesh.ChilMesh.from_fort14` when chilmesh is installed.
- Two-phase size-field composer (`compose_size_field`): Phase-1
  builtins always min-stack (Constitution Principle I); Phase-2
  user contributions combine via caller-chosen reduction. Demo
  shrinks mean edge length 44 % near a wave-breaker line
  (`scripts/size_field_extension_demo.py`).
- Test totals: 239 passed / 6 skipped (matplotlib path tested with
  `Agg` backend; chilmesh + 5 MATLAB fixtures absent locally).
- Constitution PATCH amendment removes `ADCIRC .fort.14 I/O` from
  the deferred-list (T050 below); version bumped to 1.0.1.
- Sibling-feature follow-ups parked: GH issue
  [#5](https://github.com/domattioli/ADMESH/issues/5) for Gmsh
  `.msh` I/O as feature 003; reserved feature 002 for performance
  optimization.

Open work in spec 001: T027 (≥ 3 community fixtures, needs external
acquisition). All other tasks in
`specs/001-pythonize-and-fort14-integration/tasks.md` complete.

---

## Where we are today (2026-04-24, post-session 6)

**Shipped (session 6 — faithful-port completion across all 13 stages):**
- **`admesh/boundary.py`** rewritten as faithful port of
  `08_Enforce_Boundary_Conditions/{EnforceBoundaryConditions,
  create_polygon_structure}.m`. New ``BCSegment`` dataclass +
  ``PolygonStructure`` + ``create_polygon_structure`` + MATLAB-
  faithful ``enforce_boundary_conditions(h_ic, X, Y, D, IB, pts,
  hmax, hmin)``. Session-3 node-labelling function preserved as
  ``classify_nodes_against_pts``; ``admesh/distmesh.py`` call sites
  updated. **Retires the last clean-room stage.**
- **`admesh/inpaint.py`** rewritten as faithful port of MATLAB
  ``inpaint_nans.m`` method 0 (default). Column-major sparse del²
  operator + lsqr solve. Methods 1-5 raise ``NotImplementedError``
  (deferred polish).
- **`admesh/bathymetry.py`** rewritten as faithful port of
  ``06_Bathymetry_Function/{BathymetryFunction,CreateElevationGrid}.m``.
  Formula ``h_bathy = s·|Z|/|∇Z|`` with 4th-order interior ∇Z
  stencil; ``D ≥ -4·hmin`` band masked to ``hmax`` when curvature
  stage active (MATLAB line 121).
- **`admesh/dominate_tide.py`** rewritten as faithful port of
  ``07_Dominate_Tide/Dominate_tide.m``. ``h_tide = (T/sz)·√(g·|Z|)``
  with ``g = 9.81``; land cells (Z==0) pinned to hmax before clip.
- **`admesh.mesh_size.build_h`** extended with ``bathymetry``,
  ``bathy_scale``, ``tide_period``, ``tide_scale`` kwargs routing
  to the faithful ports (additive — existing callers unaffected).
- **4 new PORTING_NOTES entries** (boundary, inpaint, bathymetry,
  tide).
- **`scripts/export_matlab_fixtures.m`** gains emitter blocks for
  inpaint, bathymetry, dominate_tide, boundary (4 new fixtures;
  existing 5 unchanged).
- **`tests/test_matlab_port.py`** extended — 8 new port-correctness
  tests for boundary + 1 MATLAB-fixture parity skip;
  ``tests/test_inpaint.py`` (7), ``tests/test_bathymetry.py`` (7),
  ``tests/test_dominate_tide.py`` (6), ``tests/test_boundary.py``
  gains 9 new cases — total test count **131 → 134 passing**
  (adds bathymetry + tide routing via ``build_h``), 5 skipped
  (MATLAB fixtures).
- **All 13 ADMESH library stages now on faithful ports.**
  Article II.1 compliance restored; the PROJECT_PLAN line
  "Faithful-port backfill remaining" is retired.

**Slipped to session 7:** WS2 notched_rect demo polish
(``min_q`` still 0.162 on Domain-path — PTS-path reroute deferred
to session 7 since P3 orchestration work will exercise the PTS
path end-to-end anyway).

**Next entry point:** session 7 — Phase P3, full
``01_ADMESH_Routine/ADmeshRoutine.m`` + ``ADmeshSubMeshRoutine.m``
orchestration. All individual stages are now directly callable on
faithful ports; session 7 composes them into the top-level
pipeline.

## Where we are today (2026-04-23, post-session 5)

**Shipped (session 5 — faithful port of `04_Curvature_Function/` +
`05_Medial_Axis/`):**
- **`admesh/curvature.py`** rewritten as faithful port of
  `CurvatureFunction.m`. New ``apply_curvature`` uses MATLAB's
  narrow-band formula ``h_curve = (1+κ|D|)/((K/π)κ) − g·D`` with
  ``|D| ≤ 2·hmin`` band-gating.
- **`admesh/medial_axis.py`** rewritten as faithful port of
  `MedialAxisFunction.m`. New ``apply_medial_axis`` +
  ``_average_outward_flux`` + ``_skeletonize_zhang_suen``
  (vectorized) + ``_remove_isolated`` replace the session-2
  scipy-EDT-only clean-room.
- **`admesh.mesh_size.build_h`** routes ``curvature_scale`` /
  ``medial_scale`` kwargs to the faithful ports; preserved
  backward-compat for the zero-enrichment MVP path.
- **`admesh.distmesh.distmesh2d`** (canonical MVP path) gains a
  final ``_boundary_cleanup(p, t, None)`` call — MATLAB ADMESH's
  ``distmesh2d.m`` does this; Persson's reference doesn't.
  Pragmatic hybrid; MVP M.4 gate regression-clean.
- **`scripts/export_matlab_fixtures.m`** gains curvature + medial
  emitter blocks (previously ``[defer]`` stubs).
- **`tests/test_matlab_port.py`** extended — 5 new port-correctness
  tests (apply_curvature band-only + on-boundary formula; AOF
  positivity; medial_axis_mask on annulus; LFS constancy).
- **Quality payoff on Domain-path medial demo:**
  unit_disk min_q 0.378 → **0.695**; notched_rect 0.020 → 0.162
  (still below 0.30 gate — session 6 target: PTS-path retarget
  + curvature composition).
- **95 pytest tests passing, 4 skipped** (MATLAB fixtures); MVP
  M.4 gate regression-clean.

**Faithful-port backfill remaining (as of S5):**
`08_Enforce_Boundary_Conditions/` (session-3 clean-room in
``admesh/boundary.py``). **Retired in session 6.**

**Next entry point (as of S5):** session 6 — Phase P2 (bathymetry
+ tide + inpaint) + boundary backfill.

## Where we are today (2026-04-23, post-session 4)

**Shipped (session 4 — faithful port of `10_Distmesh_2d/`):**
- MATLAB reference clone at `/workspace/QuADMesh-MATLAB` @ `19b2eb9`
  (Constitution Article I pin); unblocks Article II.1 faithful-port
  rule for all subsequent work.
- **`admesh.distmesh.distmesh2d_admesh`** rewritten as a faithful
  port of MATLAB `distmesh2d.m` (params + density control + best-q
  tracking). Clean-room session-3 version retired.
- **`admesh.distmesh._boundary_cleanup`** rewritten as faithful port
  of `BoundaryCleanUp.m` (free-boundary edge detection + q<0.15 +
  constraint preservation). Signature changed `(p, t, pts)` →
  `(p, t, C)` to match MATLAB.
- **`admesh.distmesh._project_back_to_boundary`** new port of
  `projectBackToBoundary.m` — projects all points with
  `d > -geps*100`, not just outside points.
- **`scripts/export_matlab_fixtures.m`** populated with emitter
  blocks for the three ported functions + stubbed sections for
  upcoming curvature/medial ports. `scripts/mat_to_npz.py` handles
  `.mat → .npz` with 1-based → 0-based index fixup.
- **`tests/test_matlab_port.py`** (11 tests): 7 hand-derived port-
  correctness + 4 MATLAB-fixture parity tests (skip until the user
  runs the MATLAB export).
- **Quality payoff**: annulus PTS demo `min_q` 0.120 → 0.343
  (crosses the ≥0.30 gate); mean_q 0.842 → 0.880.
- **90 pytest tests passing, 4 skipped** (waiting on MATLAB
  fixtures); MVP M.4 gate regression-clean.

**Next entry point:** session 5 — port `04_Curvature_Function/` +
`05_Medial_Axis/` faithfully, replacing the session-2 clean-room
implementations.

## Where we are today (2026-04-23, post-session 3)

**Shipped (session 3 — P3 core-algorithm lift; still clean-room):**
- **`admesh/boundary.py`** — clean-room `PTS` dataclass +
  `BoundaryType` (OPEN/WALL) + `PTS.from_polygons` +
  `PTS.from_domain` (marching-squares contour extractor with
  fencepost-safe sampling) + `enforce_boundary_conditions`. 8
  tests.
- **`admesh.mesh_size.build_h` extended** with `pts=` +
  `boundary_scale=` kwargs; composes elementwise with existing
  `curvature_scale` / `medial_scale`. `boundary_scale` accepts
  float or per-BC-type dict. 3 new tests (6 total + 7 solver).
- **`admesh.distmesh.distmesh2d_admesh`** ADMESH-variant path:
  PTS-seeded `pfix`, polygon-SDF synthesis from PTS,
  `_boundary_cleanup` sliver pass, typed `MeshOutput` dataclass
  with `node_bc` + `ring_id` labels.
- **`admesh.routine.triangulate` dispatcher**: `Domain` → MVP
  tuple path (unchanged); `PTS` → `MeshOutput` path. 6 new
  tests in `tests/test_distmesh_admesh.py`.
- **3 PORTING_NOTES entries** (boundary / build_h-PTS /
  distmesh-admesh) with deferred-faithful-port flags.
- **82 pytest tests passing** (65 → 82 = +8 boundary + 3 build_h
  PTS + 6 distmesh-admesh). MVP M.4 gate regression-clean.
- **2nd `SOURCE_UNAVAILABLE`** logged; one more recurrence
  triggers a Constitution-amendment proposal.

**Next entry point:** `docs/session_4_plan.md` — Phase P2
(bathymetry + tide + inpaint) now that the PTS structure can
carry per-segment physical data.

## Where we are today (2026-04-23, post-session 2)

**Shipped (session 2 — Phase P1 opened; faithful-port pass deferred):**
- **Clean-room `admesh/curvature.py`** — 4th-order ``κ = ∇·(∇f/|∇f|)``
  grid computation. 3 analytic-reference tests.
- **Clean-room `admesh/medial_axis.py`** — scipy EDT + gradient
  threshold + EDT for medial distance. 4 analytic-reference tests.
- **`admesh.mesh_size.build_h` composer** — wires curvature +
  medial optional contributions, gradient-limits via `solve_iter`,
  returns `RegularGridInterpolator`-backed `fh`. Zero-enrichment
  path preserves MVP uniform-size default. 4 new tests incl.
  end-to-end `triangulate(..., fh=build_h(...))`.
- **3 PORTING_NOTES entries** with explicit deferred-faithful-port
  flags — MATLAB clone was not available in session-2 environment
  (`SOURCE_UNAVAILABLE` trigger class added to persistence journal).
- **65 pytest tests passing** (54 → 65 = +3 curvature + 4 medial
  + 4 composer).

**Next entry point:** `docs/session_3_plan.md` WS0 — if MATLAB
clone is present, backfill faithful-port passes of session-2
modules (Branch A); else continue clean-room with Phase P2
(bathymetry + tide + inpaint, Branch B).

## Where we are today (2026-04-21, post-session 1)

**Shipped (session 0 + session 1 — MVP complete):**
- Repo live at `domattioli/ADMESH` (private, Apache-2.0).
- Governance: `CONSTITUTION.md` (now 7 articles — added Article VII,
  persistent-session cadence), `PROJECT_PLAN.md`, `CLAUDE.md`,
  `README.md`, full session 0 + session 1 artifact set under `docs/`.
- Persistence skills: `.claude/skills/{log-issue,log-interrupt,
  list-issues,session-handoff}/SKILL.md` + `docs/persistence_journal.md`.
- **M.0** scaffold (S0): 14-module `admesh/` package, `pyproject.toml`,
  `requirements.txt` + `requirements-dev.txt`, smoke test.
- **M.1** leaf utilities (S0): `in_polygon.py`, `quality.py`,
  `domains.py` (5 MVP SDFs).
- **M.2** distance + mesh_size (S0): `distance.py` (grid-eval +
  4th-order `grad_sdf`), `mesh_size.py` (pure-Python + Numba
  solver, parity to `atol=1e-10`).
- **M.3** distmesh + driver (S0): `distmesh.py` (canonical Persson
  DistMesh2D + `fixmesh`), `routine.py::triangulate()`.
- **M.4** end-to-end validation + PNGs (S1): `tests/test_mvp_domains.py`
  parametrized over all 5 domains; `tests/conftest.py` with shared
  `assert_valid_mesh` helper; PNGs committed at
  `tests/output/mvp_<name>.png`; quality metrics
  (`min_q ≥ 0.30, mean_q ≥ 0.60`) met on every domain.
- **Correctness bugfix in `distmesh2d`** (S1): added a final Delaunay
  + centroid-filter step after the iteration loop to eliminate
  stale triangles from post-trigger node motion. Raised
  `unit_square` min_q from `0.000 → 0.804`; see
  `docs/PORTING_NOTES.md` 2026-04-21 entry.
- **`docs/PORTING_NOTES.md` populated** (S1) with five retroactive
  MATLAB→Python divergence entries.
- 54 pytest tests passing (49 from S0 + 5 new MVP-domain cases).
- Local MATLAB reference clone at `/workspace/QuADMesh-MATLAB`.

**Next entry point:** Phase P1 — sizing enrichments
(`04_Curvature_Function` + `05_Medial_Axis`), per session 2 plan.

**Not shipped (post-MVP):** any of Phases P1–P4.

---

## North star

A Python package that reproduces the MATLAB ADMESH pipeline on the
reference test domains within documented floating-point tolerance,
installs without a C toolchain, and exposes each of the 13 stages as
an independently-callable function.

---

## MVP — Triangulation on well-planned test domains

**Goal**: given a 2D domain polygon (straight-edge, possibly non-convex,
possibly multiply-connected), produce a triangular mesh. This is the
first deliverable of several.

**In scope for MVP** — the minimum subset of the 13 stages needed to
triangulate:

| Stage | MATLAB source | Python module |
|---|---|---|
| Leaf utilities | `12_In_Polygon/`, `11_Mesh_Quality/MeshQuality.m` | `in_polygon.py`, `quality.py` |
| Signed distance | `03_Distance_Function/SignedDistanceFunction.m` + `PTS2PointList.m` | `distance.py` |
| Mesh-size field | `09_Mesh_Size/MeshSizeIterativeSolver.c` (Numba port) | `mesh_size.py` |
| Triangulation engine | `10_Distmesh_2d/distmesh2d.m` + `fixmesh.m` | `distmesh.py` (triangulation only — NO `tri2quad` yet) |
| Driver | minimal subset of `01_ADMESH_Routine/ADmeshRoutine.m` | `routine.py::triangulate(domain, params)` |

**Explicitly OUT of MVP scope** (deferred to post-MVP phases):
- Quad conversion (`tri2quad`) and mixed-element output.
- Bathymetry-driven sizing (`06_Bathymetry_Function`).
- Tidal-wavelength sizing (`07_Dominate_Tide`).
- Medial-axis sizing (`05_Medial_Axis`) — MVP uses uniform or
  curvature-based mesh-size by default.
- Curvature field (`04_Curvature_Function`) — defer; MVP starts with
  uniform size, adds curvature later if needed for quality gates.
- Boundary-condition enforcement (`08_Enforce_Boundary_Conditions`).
- NaN in-painting (`13_In_Paint_NaNs`) — only needed for grid fields
  that MVP doesn't yet construct.
- Full `ADmeshRoutine.m` + `ADmeshSubMeshRoutine.m` orchestration.

### Test domains (the "well-planned" part)

Design these before porting code; they are the acceptance gate for MVP.

1. **Unit square** `[0,1]²` — trivial sanity; uniform mesh size.
2. **L-shape** — non-convex re-entrant corner.
3. **Unit disk** (curved) — tests boundary resolution with a
   non-polygonal signed-distance function.
4. **Annulus** — doubly-connected topology.
5. **Notched rectangle** (figure-8 or keyhole) — tight pinch point,
   mirrors MADMESHR's `pinch_figure8` as a stress test.

Each domain is defined in `admesh/domains.py` as a `(signed_distance_fn,
bounding_box, fixed_points)` tuple. Tests in `tests/test_mvp_*.py`
generate a mesh on each and assert: completion (no orphaned regions),
element-count within ±15% of a target, and min-quality ≥ 0.30 (loose
gate — we tighten once the port is validated against MATLAB).

### MVP acceptance criteria

- `admesh.triangulate(domain, params)` returns `(vertices, triangles)`
  for all 5 test domains.
- `pytest tests/test_mvp_*.py` all green.
- At least one rendered PNG per domain committed to
  `tests/output/mvp_<domain>.png` as visual evidence.
- Runtime ≤ 60 s per domain on a laptop (the Numba size-field solver
  must not be a wall-clock blocker).

---

## MVP phasing (sub-steps)

**M.0 — Scaffold** (this session).
- Package layout, docs, empty stubs, passing import-smoke test.

**M.1 — Leaf utilities + domain registry**.
- Port `in_polygon.py`, `quality.py`.
- Define the 5 test domains as signed-distance functions in
  `admesh/domains.py`.

**M.2 — Signed distance + mesh-size solver**.
- Port `distance.py` (grid evaluation of a domain sdf).
- Port `mesh_size.py` including the Numba solver (with pure-Python
  parity reference).

**M.3 — DistMesh triangulation + driver**.
- Port `distmesh2d.m` → `distmesh.py::distmesh2d()`, plus `fixmesh`.
- Wire the top-level `admesh.triangulate()` that composes M.1–M.3.

**M.4 — Validate + visualize**.
- Run on all 5 test domains; generate PNGs; tune tolerances.
- If Numba solver is slow, profile; consider Cython fallback per
  constitution Article II.2.

---

## Post-MVP phases

Once triangulation works, the remaining stages port in this order.
**Quad conversion (`tri2quad.m`, `distquadmesh2d.m`) is out of scope
for ADMESH** (user decision, 2026-04-18). ADMESH is a triangulation
library; any quadrangulation work happens in a separate project.

**Phase P1 — Sizing enrichments.**
- `04_Curvature_Function` → `curvature.py`.
- `05_Medial_Axis` → `medial_axis.py` (FMM + heap helper).
- Integrate into `mesh_size.py` size-field composition.

**Phase P2 — Physical-field sizing.**
- `06_Bathymetry_Function` → `bathymetry.py`.
- `07_Dominate_Tide` → `dominate_tide.py`.
- `13_In_Paint_NaNs` → `inpaint.py` (prerequisite for sparse field
  interpolation).

**Phase P3 — Boundary + full routine.**
- `08_Enforce_Boundary_Conditions` → `boundary.py`.
- `01_ADMESH_Routine/ADmeshRoutine.m` + `ADmeshSubMeshRoutine.m`
  → full `routine.py`.

**Phase P4 — Polish & release.**
- Public API review, type hints, optional PyPI publish, flip repo to
  public.

---

## Deferred / parking lot

- **GUI / visualization.** The MATLAB repo has a GUI (not in
  `01_ADMESH_Library`); not in scope here.
- **ADCIRC `.fort.14` I/O.** Downstream concern.
- **Zero-C-extension permanence.** Article II.2 permits a fallback to
  Cython/C if Numba underperforms.

---

## Revision history

### 2026-04-18 — Initial plan; MVP = triangulation

Adopted at session 0. MVP defined as triangulation-only on 5 test
domains, deferring quad conversion and advanced sizing to post-MVP
phases. Rationale: get an end-to-end "polygon → mesh" pipeline
working before broadening stage coverage.
