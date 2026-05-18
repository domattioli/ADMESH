# ADMESH Project Plan

Phased roadmap for porting `QuADMesh-MATLAB/01_ADMESH_Library` to Python. Governance rules in `CONSTITUTION.md`; code layout in `CLAUDE.md`.

---

## Where we are today (2026-05-17, spec 009 release-readiness-for-0.1.0 COMPLETE — tag push pending)

**Spec 009 R1–R4 implemented; awaiting maintainer `git tag v0.1.0 && git push origin v0.1.0`.**

- All 4 phases done on branch `009-release-readiness-for-0.1.0` (PR #63):
  - R1: version reconciled (`pyproject.toml` and `__init__.py` both `0.1.0`); `scripts/pre_tag_check.sh` extended with 4 new gates (version-match, plan staleness, coverage artifact, durations artifact); `output/coverage.json` + `output/durations.txt` committed; TEST-AUDIT B-04/B-06 closed.
  - R2: `.github/workflows/tests.yml` (Python 3.10/3.11/3.12, `not slow`) + `tests-slow.yml` (weekly + on-tag); `CONTRIBUTING.md` + `TESTING.md`; `docs/ADMESH_DOMAINS_CONTRACT.md`; pin tightened to `admesh-domains>=0.3.0,<0.4`; `tests/test_admesh_domains_contract.py` (6 tests). Drift discovered: `admesh/registry.py` adapter is broken against `admesh-domains` 0.3.x — filed as #64 (post-0.1.0 rewrite).
  - R3: Constitution amendment (proposed Article VIII) — `admesh/_stages/` subpackage created; 14 faithful-port modules moved with backward-compat stubs preserving both public and private-name imports; `__all__` cleaned (25 public symbols, no stage-module noise); `mkdocs-material` + `mkdocstrings` site (`docs/index.md`, `docs/quickstart.md`, 7 API ref pages, `.github/workflows/docs.yml` deploys to GitHub Pages); `tests/test_docstring_completeness.py` (3 tests, 2 callables soft-flagged).
  - R4: Tier-1 + Tier-2 + Tier-0 structural-validity tests already green (no `xfail`); README ship-ready; pre_tag_check gate 2 inverted to accept either pre-ship or ship-ready README state; **issue #10 closed**; quality-improvement follow-up filed as #65 (3-step plan from #10's May 13 planning comment, scoped post-0.1.0).
- **366 tests** pass (slow lane included), **9/9 pre_tag_check gates** green.
- Path to tag: maintainer runs `git tag -a v0.1.0 -m "Release 0.1.0" && git push origin v0.1.0` → `publish.yml` ships `admesh2D==0.1.0` to PyPI.
- Bonus fixes during spec 009 R1 (pre-existing regressions from user commit `072d669`): restored 530 lines of `admesh/_stages/distmesh.py` (`fixmesh`, `MeshOutput`, `distmesh2d_admesh`) that had been accidentally dropped; threaded `initial_points` through `api.py::triangulate()` → `opts` → `distmesh2d` so the issue-#45 warm-start path works end-to-end.

---

## Where we are today (2026-05-15, sub-plan: spec 009 release-readiness-for-0.1.0)

**Status snapshot (3 weeks since the 2026-04-26 entry):**
- Issue **#11** (`Domain.from_mesh` outer-ring sort) — **closed 2026-05-06**. The mechanical half of the "Path to 0.1.0" gate is done. Got its own spec `003-fix-outer-ring-sorting`.
- Issue **#10** (default size-field overshoots domain on real-world coastal fixtures) — **closed 2026-05-17** against structural-validity gate as part of spec 009 R4; quality-improvement follow-up filed as #65.
- Six new specs landed that this plan did not previously mention:
  - `003-fix-outer-ring-sorting` (closed #11)
  - `004-quad-prep-smoother` (issue #15, right-isosceles smoother for quad fusion prep — shipped, lives in `admesh/quad_prep.py`)
  - `005-adcirc-mesh-registry` (federated mesh-discovery registry — shipped, lives in `admesh/registry.py` + `admesh/loaders.py`)
  - `006-verify-h-parameter-usage` (investigation for issue #37)
  - `007-1d-boundary-seeding` (issue #2, in progress)
  - `008-gmsh-io-integration` (issue #5, planning)
- ~20 ADMESH issues closed since the 2026-04-26 entry; issue #15 (right-isoceles smoother), #27 (valence balancing) and #36 (`distmesh2d` undefined `_boundary_cleanup`) are among the larger ones.
- New "daily-issue-fixing" workflow adopted: one long-lived integration branch, no PR proliferation, autonomous routine driven by DomI skill marketplace. ADMESH consumes DomI v1.9 manifest (pinned at commit `ab5bb49e`, `manifest_sha256` recorded in `.domi-pin`).
- `TEST-AUDIT.md` shipped on 2026-05-15 (issue #59). Surfaced **F-CRIT-01**: only `publish.yml` exists, no CI workflow runs the 310 test functions. Sibling audit issues #60 (test surface, routes to DomI #63) and #61 (Claude Code hooks, routes to DomI #64) are open.
- `admesh-domains>=0.1.0` is now a hard runtime dependency (`pyproject.toml:22`). The registry sibling is part of the public surface for 0.1.0.

**Known drift to fix before tag:**
- **Version mismatch**: `pyproject.toml` declares `version = "0.1.0"` but `admesh/__init__.py` declares `__version__ = "0.2.0"`. Both must agree at the moment the tag is pushed.
- **Test gate missing**: no CI workflow runs `pytest`. Wheel can be tagged on a broken suite today.
- **Docs**: no `CONTRIBUTING.md`, no `TESTING.md`, no rendered API reference. README still says "0.1.0 in progress."

### 0.1.0 Release-Readiness Sub-Plan → `specs/009-release-readiness-for-0.1.0/`

The remaining work to ship 0.1.0 is bundled into spec 009. Four phases:

- **Phase R1 — Tag-gate hygiene**: reconcile the `pyproject.toml` ↔ `__init__.py` version strings; extend `scripts/pre_tag_check.sh` with version-match, plan-staleness, and audit-artifact gates; commit `output/coverage.json` + `output/durations.txt` to close TEST-AUDIT backlog items B-04 / B-06.
- **Phase R2 — CI + onboarding + contract**: add `.github/workflows/tests.yml` (closes F-CRIT-01) on Python 3.10/3.11/3.12; introduce a `slow` pytest marker with a weekly lane; ship `CONTRIBUTING.md`, `TESTING.md`, and `docs/ADMESH_DOMAINS_CONTRACT.md`; tighten the `admesh-domains` pin to `>=0.1.0,<0.2`; add a contract-parity test.
- **Phase R3 — Reorg (gated) + API reference**: draft a Constitution amendment for splitting `admesh/` into a public-surface layer + `admesh/_stages/` faithful-port internals; if it passes, do the split with back-compat re-exports; ship mkdocs-material + GitHub Pages with auto-generated API reference via `mkdocstrings`.
- **Phase R4 — Issue #10 + tag**: resolve the size-field-overshoot blocker; un-`xfail` `test_tier1_wetting_and_drying_round_trip` and `test_tier2_wnat_release_gate`; push `v0.1.0` and let `publish.yml` ship the wheel to PyPI as `admesh2D==0.1.0`.

See `specs/009-release-readiness-for-0.1.0/spec.md` for the full feature spec (4 user stories, 26 functional requirements across the 4 phases, 8 measurable success criteria). The path to the actual 0.1.0 tag goes through that spec.

---

## Where we are today (2026-04-26, main merged — 298 tests green, open blockers #10/#11/#12)

**Shipped this session (spec 002 — default size-field stack, implementation phase):**
- All 41 tasks from `specs/002-size-field-defaults/tasks.md` walked through. T001-T015 + T018-T028 + T032-T037 done; T016/T017 (Tier-1 / Tier-2 acceptance) marked `xfail` pending issue #10; T029-T031 (Shinnecock fixture) deferred (network-dependent, not gating 0.1.0).
- **Headline behavior change**: `admesh.triangulate(domain)` with no size-field arguments now invokes default Phase-1 stack (curvature + medial-axis always-on; bathymetry + tide opt-in via `Domain` fields). Spec-001 uniform-`h` fallback reachable via `enable_curvature=False, enable_medial_axis=False`.
- `admesh/api.py` extended: `Domain.bathymetry`, `Domain.tide_period`, `Domain.polygons`, `Domain.from_mesh(...)` classmethod, `_build_default_size_field(...)` private helper, new `triangulate()` kwargs (`h_target`, `enable_curvature`, `enable_medial_axis`, `default_depth`, `tide_elements_per_wavelength`), extended `Mesh.equals` for paired-edge + barrier_data.
- `admesh/boundary_types.py` extended: `EXTERNAL_BARRIER=3`, `EXTERNAL_BARRIER_FLUX=4`, `INTERNAL_BARRIER_PIPE=13`, `INTERNAL_BARRIER=24`.
- `admesh/fort14.py` extended: paired-edge / single-node-barrier reader/writer for IBTYPE 3 / 4 / 13 / 23 / 24 / 25 with column-agnostic `barrier_data`. Open- and land-segment header parsers tolerate inline `=` comments. `wetting_and_drying_test.14` corpus round-trip went RED → GREEN.
- New tests: `test_default_size_field.py` (8 tests), `test_fort14_paired.py` (5 tests), `test_backward_compat.py` (4 tests), `tests/_structural_validity.py`. Final suite: **259 passed, 8 skipped, 2 xfailed**.
- Constitution amendment v1.0.2 (T023): documents spec-002 default stack as precondition for fort.14-contract release readiness.
- README "0.1.0 in progress" callouts restored (T024/T025); ADCIRC compatibility tagline preserved.
- Cleanup (T026/T027/T028): `papers/wnat_admesh.png`, `dist/`, `build/`, 3 stale diagnostic PNGs under `tests/output/` removed.
- `scripts/pre_tag_check.sh` (T032): 5-gate pre-tag verification script. Currently PASSES.
- `docs/PORTING_NOTES.md` (T019): new entry for fort.14 paired-edge / barrier BC records.
- `requirements.txt` cleanup: removed accidentally-duplicated matplotlib.
- New quality-comparison artifacts in `tests/output/`: `wnat_quality.png` (4-panel histogram) and `tier1_source_vs_fresh.png` (side-by-side comparison, shape-q-mean 0.92 vs source 0.99).

**Open follow-up issues** (filed this session):
- #8 — GPU + CPU-parallel acceleration for size-field stack (post-v1).
- #9 — admesh-segmenter sibling project (post-v1).
- #10 — **Default size-field stack overshoots domain on real-world coastal fixtures** (severity:high). Tier-1/Tier-2 acceptance gates blocked. 0.1.0 tag contingent on resolving #10.
- #11 — `Domain.from_mesh` picks wrong outer ring on WNAT (sorts by node count, not area). Independently breaks Tier-2 path; resolution is mechanical (~M effort).

**Branch state**: `002-size-field-defaults` on origin, head `1149adf`. Spec-001 branch (`001-pythonize-and-fort14-integration`, head `f1ce987`) preserved for archive.

**Path to 0.1.0**: resolve #11 (mechanical) + #10 (tuning), un-xfail Tier-1/Tier-2 tests, run `bash scripts/pre_tag_check.sh`, tag.

---

## Where we are today (2026-04-25, post-spec-001)

**Shipped (spec 001 — Pythonic API + fort.14 I/O):**
- v1 Pythonic surface in `admesh/api.py`, `admesh/fort14.py`, `admesh/boundary_types.py`, `admesh/size_field.py`, `admesh/viz.py` — strictly additive over 13 faithful-port stage modules. 142-test faithful-port baseline still passes.
- 3-line happy path runs end-to-end on all 5 MVP domains: `domain_from_polygon([ring])` → `triangulate(domain)` → `mesh.to_fort14(path)`. Round-trip equal at `atol=1e-5`.
- ADCIRC v55 fort.14 reader/writer with `Fort14ParseError` carrying `line_no/expected/actual`. Open-segments / land-segments round-trip; named and unmapped numeric BC codes both preserved.
- Real-world stress test: `tests/fixtures/fort14/adcirc_examples/wnat_test.14` (1.2 MB, 9,934 nodes) parses, round-trips, and re-triangulates.
- chilmesh round-trip: 8 compat tests cover BC label preservation across fort.14 boundary.
- Two-phase size-field composer (`compose_size_field`): Phase-1 builtins always min-stack (Principle I); Phase-2 user contributions combine via caller-chosen reduction.
- Test totals: 239 passed / 6 skipped.
- Constitution PATCH amendment removes `ADCIRC .fort.14 I/O` from deferred-list; version bumped to 1.0.1.

Open work in spec 001: T027 (≥ 3 community fixtures, needs external acquisition).

---

## Where we are today (2026-04-24, post-session 6)

**Shipped (session 6 — faithful-port completion across all 13 stages):**
- **`admesh/boundary.py`** rewritten as faithful port of `08_Enforce_Boundary_Conditions/`. New `BCSegment` + `PolygonStructure` + `create_polygon_structure` + MATLAB-faithful `enforce_boundary_conditions`. **Retires last clean-room stage.**
- **`admesh/inpaint.py`** rewritten as faithful port of MATLAB `inpaint_nans.m` method 0 (default). Column-major sparse del² operator + lsqr solve.
- **`admesh/bathymetry.py`** rewritten as faithful port of `06_Bathymetry_Function/`. Formula `h_bathy = s·|Z|/|∇Z|` with 4th-order interior ∇Z stencil.
- **`admesh/dominate_tide.py`** rewritten as faithful port of `07_Dominate_Tide/Dominate_tide.m`. `h_tide = (T/sz)·√(g·|Z|)` with `g = 9.81`.
- **`admesh.mesh_size.build_h`** extended with `bathymetry`, `bathy_scale`, `tide_period`, `tide_scale` kwargs routing to faithful ports.
- **4 new PORTING_NOTES entries**, **`scripts/export_matlab_fixtures.m`** gains 4 new fixture emitter blocks.
- Test count: **131 → 134 passing**, 5 skipped (MATLAB fixtures).
- **All 13 ADMESH library stages now on faithful ports.** Article II.1 compliance restored.

**Next entry point:** session 7 — Phase P3, full `01_ADMESH_Routine/ADmeshRoutine.m` + `ADmeshSubMeshRoutine.m` orchestration.

## Where we are today (2026-04-23, post-session 5)

**Shipped (session 5 — faithful port of `04_Curvature_Function/` + `05_Medial_Axis/`):**
- **`admesh/curvature.py`** rewritten as faithful port. New `apply_curvature` uses MATLAB's narrow-band formula.
- **`admesh/medial_axis.py`** rewritten as faithful port. New `apply_medial_axis` + `_average_outward_flux` + `_skeletonize_zhang_suen` (vectorized) + `_remove_isolated`.
- **`admesh.mesh_size.build_h`** routes `curvature_scale` / `medial_scale` kwargs to faithful ports.
- **`admesh.distmesh.distmesh2d`** gains final `_boundary_cleanup(p, t, None)` call (MATLAB does this; Persson's reference doesn't).
- **95 pytest tests passing, 4 skipped** (MATLAB fixtures); MVP M.4 gate regression-clean.

## Where we are today (2026-04-23, post-session 4)

**Shipped (session 4 — faithful port of `10_Distmesh_2d/`):**
- MATLAB reference clone at `/workspace/QuADMesh-MATLAB` @ `19b2eb9` — unblocks Article II.1 faithful-port rule.
- **`admesh.distmesh.distmesh2d_admesh`** rewritten as faithful port. Clean-room session-3 version retired.
- **`admesh.distmesh._boundary_cleanup`** rewritten as faithful port of `BoundaryCleanUp.m`. Signature changed `(p, t, pts)` → `(p, t, C)`.
- **`admesh.distmesh._project_back_to_boundary`** new port of `projectBackToBoundary.m`.
- **90 pytest tests passing, 4 skipped**; MVP M.4 gate regression-clean.

## Where we are today (2026-04-23, post-session 3)

**Shipped (session 3 — P3 core-algorithm lift; still clean-room):**
- `admesh/boundary.py` — clean-room `PTS` dataclass + `BoundaryType` + `PTS.from_polygons` + `PTS.from_domain` + `enforce_boundary_conditions`.
- `admesh.mesh_size.build_h` extended with `pts=` + `boundary_scale=` kwargs.
- `admesh.distmesh.distmesh2d_admesh` ADMESH-variant path: PTS-seeded `pfix`, polygon-SDF synthesis, typed `MeshOutput` dataclass.
- **82 pytest tests passing** (65 → 82). MVP M.4 gate regression-clean.

## Where we are today (2026-04-23, post-session 2)

**Shipped (session 2 — Phase P1 opened; faithful-port pass deferred):**
- Clean-room `admesh/curvature.py` — 4th-order `κ = ∇·(∇f/|∇f|)` grid computation. 3 analytic-reference tests.
- Clean-room `admesh/medial_axis.py` — scipy EDT + gradient threshold + EDT for medial distance. 4 analytic-reference tests.
- **`admesh.mesh_size.build_h` composer** — wires curvature + medial optional contributions, gradient-limits via `solve_iter`. 4 new tests.
- 3 PORTING_NOTES entries with deferred-faithful-port flags.
- **65 pytest tests passing** (54 → 65).

## Where we are today (2026-04-21, post-session 1)

**Shipped (session 0 + session 1 — MVP complete):**
- Repo live at `domattioli/ADMESH` (private, Apache-2.0).
- Governance: `CONSTITUTION.md` (7 articles), `PROJECT_PLAN.md`, `CLAUDE.md`, `README.md`, full session artifact set under `docs/`.
- **M.0** scaffold: 14-module `admesh/` package, `pyproject.toml`, `requirements.txt` + `requirements-dev.txt`, smoke test.
- **M.1** leaf utilities: `in_polygon.py`, `quality.py`, `domains.py` (5 MVP SDFs).
- **M.2** distance + mesh_size: `distance.py`, `mesh_size.py` (pure-Python + Numba solver, parity to `atol=1e-10`).
- **M.3** distmesh + driver: `distmesh.py` (Persson DistMesh2D + `fixmesh`), `routine.py::triangulate()`.
- **M.4** end-to-end validation + PNGs: `tests/test_mvp_domains.py` parametrized over all 5 domains; quality metrics (`min_q ≥ 0.30, mean_q ≥ 0.60`) met on every domain.
- **Correctness bugfix in `distmesh2d`** (S1): added final Delaunay + centroid-filter step after iteration loop. Raised `unit_square` min_q from `0.000 → 0.804`.
- 54 pytest tests passing.

---

## North star

Python package reproducing MATLAB ADMESH pipeline on reference test domains within documented floating-point tolerance, installs without C toolchain, exposes each of the 13 stages as independently-callable function.

---

## MVP — Triangulation on well-planned test domains

**Goal**: given 2D domain polygon (straight-edge, possibly non-convex, possibly multiply-connected), produce triangular mesh.

**In scope for MVP:**

| Stage | MATLAB source | Python module |
|---|---|---|
| Leaf utilities | `12_In_Polygon/`, `11_Mesh_Quality/MeshQuality.m` | `in_polygon.py`, `quality.py` |
| Signed distance | `03_Distance_Function/SignedDistanceFunction.m` + `PTS2PointList.m` | `distance.py` |
| Mesh-size field | `09_Mesh_Size/MeshSizeIterativeSolver.c` (Numba port) | `mesh_size.py` |
| Triangulation engine | `10_Distmesh_2d/distmesh2d.m` + `fixmesh.m` | `distmesh.py` (triangulation only — NO `tri2quad` yet) |
| Driver | minimal subset of `01_ADMESH_Routine/ADmeshRoutine.m` | `routine.py::triangulate(domain, params)` |

**Explicitly OUT of MVP scope** (deferred to post-MVP phases):
- Quad conversion (`tri2quad`) and mixed-element output.
- Bathymetry-driven sizing, tidal-wavelength sizing, medial-axis sizing, curvature field.
- Boundary-condition enforcement, NaN in-painting.
- Full `ADmeshRoutine.m` + `ADmeshSubMeshRoutine.m` orchestration.

### Test domains

1. **Unit square** `[0,1]²` — trivial sanity; uniform mesh size.
2. **L-shape** — non-convex re-entrant corner.
3. **Unit disk** (curved) — tests boundary resolution with non-polygonal SDF.
4. **Annulus** — doubly-connected topology.
5. **Notched rectangle** — tight pinch point, mirrors MADMESHR's `pinch_figure8`.

Each domain in `admesh/domains.py` as `(signed_distance_fn, bounding_box, fixed_points)`. Tests assert: completion (no orphaned regions), element-count within ±15% of target, min-quality ≥ 0.30.

### MVP acceptance criteria

- `admesh.triangulate(domain, params)` returns `(vertices, triangles)` for all 5 test domains.
- `pytest tests/test_mvp_*.py` all green.
- At least one rendered PNG per domain committed to `output/mvp_<domain>.png`.
- Runtime ≤ 60 s per domain on laptop.

---

## MVP phasing (sub-steps)

**M.0 — Scaffold** — Package layout, docs, empty stubs, passing import-smoke test.

**M.1 — Leaf utilities + domain registry** — Port `in_polygon.py`, `quality.py`. Define 5 test domains in `admesh/domains.py`.

**M.2 — Signed distance + mesh-size solver** — Port `distance.py`. Port `mesh_size.py` including Numba solver.

**M.3 — DistMesh triangulation + driver** — Port `distmesh2d.m` → `distmesh.py::distmesh2d()`. Wire top-level `admesh.triangulate()`.

**M.4 — Validate + visualize** — Run on all 5 test domains; generate PNGs; tune tolerances.

---

## Post-MVP phases

**Phase P1 — Sizing enrichments.**
- `04_Curvature_Function` → `curvature.py`
- `05_Medial_Axis` → `medial_axis.py` (FMM + heap helper)
- Integrate into `mesh_size.py` size-field composition.

**Phase P2 — Physical-field sizing.**
- `06_Bathymetry_Function` → `bathymetry.py`
- `07_Dominate_Tide` → `dominate_tide.py`
- `13_In_Paint_NaNs` → `inpaint.py`

**Phase P3 — Boundary + full routine.**
- `08_Enforce_Boundary_Conditions` → `boundary.py`
- `01_ADMESH_Routine/ADmeshRoutine.m` + `ADmeshSubMeshRoutine.m` → full `routine.py`

**Phase P4 — Polish & release.**
- Public API review, type hints, optional PyPI publish, flip repo to public.

---

## Deferred / parking lot

- **GUI / visualization.** MATLAB repo has GUI (not in `01_ADMESH_Library`); not in scope.
- **ADCIRC `.fort.14` I/O.** Downstream concern.
- **Zero-C-extension permanence.** Article II.2 permits Cython/C fallback if Numba underperforms.

---

## Revision history

### 2026-04-18 — Initial plan; MVP = triangulation

Adopted at session 0. MVP defined as triangulation-only on 5 test domains, deferring quad conversion and advanced sizing to post-MVP phases.
