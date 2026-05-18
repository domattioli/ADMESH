# Tasks: Release Readiness for ADMESH 0.1.0

**Input**: Design documents from `specs/009-release-readiness-for-0.1.0/`
**Prerequisites**: spec.md ✅, plan.md ✅

**Organization**: Tasks grouped by phase (R1→R4) and user story (US1/US2/US3/US4). R1 blocks R4; R2 and R3 are independent of each other and can proceed in parallel once R1 is complete.

---

## Phase 1: Foundational — Version Reconciliation (blocks all phases)

**Purpose**: Resolve the `pyproject.toml` (`0.1.0`) ↔ `admesh/__init__.py` (`0.2.0`) mismatch before any other change lands. `pyproject.toml` is the build-time authority; `__init__.py` must mirror it.

- [ ] T001 [US1] Set `__version__ = "0.1.0"` in `admesh/__init__.py` (currently `"0.2.0"`). Verify with `python -c "import admesh; print(admesh.__version__)"`.

**Checkpoint**: `python -c "import admesh; print(admesh.__version__)"` prints `0.1.0`.

---

## Phase 2: R1 — Tag-Gate Hygiene (User Story 1, P1)

**Goal**: `bash scripts/pre_tag_check.sh` catches version drift, stale plan, and missing audit artifacts, then exits zero when all three are clean.

**Independent Test**: Run `bash scripts/pre_tag_check.sh`. With current repo state it must fail ≥3 gates; after all R1 tasks it must exit zero.

### R1 — pre_tag_check.sh extensions

- [ ] T002 [US1] Extend `scripts/pre_tag_check.sh`: add gate 6 — parse `version = "..."` from `pyproject.toml` (first match, strip quotes) and compare to `__version__` string in `admesh/__init__.py`; fail with `VERSION_MISMATCH: pyproject=X __init__=Y` when they differ.
- [ ] T003 [US1] Extend `scripts/pre_tag_check.sh`: add gate 7 — grep `docs/governance/PROJECT_PLAN.md` for `## Where we are today (YYYY-MM-DD`; extract the most recent date; compare to `git log -1 --format=%cs` (ISO date of HEAD); fail with `PLAN_STALE: last_entry=DATE head=DATE delta=N_days` when delta > 30.
- [ ] T004 [US1] Extend `scripts/pre_tag_check.sh`: add gate 8 — verify `output/coverage.json` exists; compare its mtime (via `stat` fallback to `find -newer`) to HEAD commit timestamp; fail with `COVERAGE_STALE` or `COVERAGE_MISSING` accordingly.
- [ ] T005 [US1] Extend `scripts/pre_tag_check.sh`: add gate 9 — same mtime check for `output/durations.txt`; fail with `DURATIONS_STALE` or `DURATIONS_MISSING`.

### R1 — audit artifacts

- [ ] T006 [US1] Run `pytest --cov=admesh --cov-report=json --cov-report=term-missing -q 2>&1 | tee output/coverage_report.txt` from repo root; move / copy the generated `coverage.json` to `output/coverage.json`.
- [ ] T007 [US1] Run `pytest --durations=10 -q 2>&1 | tee output/durations.txt` from repo root.
- [ ] T008 [US1] Update `TEST-AUDIT.md`: mark backlog items B-04 and B-06 complete; add cross-references to `output/coverage.json` and `output/durations.txt`.

### R1 — final gate

- [ ] T009 [US1] Run `bash scripts/pre_tag_check.sh` — all 9 gates must pass. Fix any residual failures.

**Checkpoint**: `bash scripts/pre_tag_check.sh` exits 0.

---

## Phase 3: R2 — CI + Onboarding + Contract (User Story 3, P2)

**Goal**: Every PR triggers a test run on Python 3.10/3.11/3.12; a cold contributor can follow `CONTRIBUTING.md` + `TESTING.md` to get green locally in ≤ 15 min; `admesh-domains` coupling is documented and pinned.

**Independent Test**: Open a trivial PR that breaks one test — CI marks the PR red and names the failing test.

> R2 tasks T010–T017 are all parallel to each other and to R3 tasks T020+. They can start once T001 is done.

### R2 — CI workflows

- [ ] T010 [P] [US3] Write `.github/workflows/tests.yml`: matrix Python 3.10/3.11/3.12 on `ubuntu-latest`; steps: checkout, setup-python, `pip install -e ".[dev]"`, `pytest -m "not slow" -q`; triggers on push and pull_request to any branch.
- [ ] T011 [P] [US3] Write `.github/workflows/tests-slow.yml`: same matrix; steps: checkout, setup-python, `pip install -e ".[dev]"`, `pytest -q` (full suite including slow); triggers on `workflow_dispatch`, weekly cron (`0 4 * * 1`), and push of `v*` tags.

### R2 — slow marker setup

- [ ] T012 [P] [US3] Add to `[tool.pytest.ini_options]` in `pyproject.toml`: `markers = ["slow: tests requiring real coastal fixtures or external binaries (deselect with -m 'not slow')"]`. Scan `tests/` for slow candidates and mark with `@pytest.mark.slow`: at minimum `test_fort14_chilmesh_smoke.py` (requires chilmesh), `test_default_size_field.py::test_tier1*` and `::test_tier2*` (large fixture + long runtime), any test that reads `wnat_test.14`.

### R2 — onboarding docs

- [ ] T013 [P] [US3] Write `CONTRIBUTING.md` at repo root covering: (1) dev setup `git clone` + `pip install -e ".[dev]"`; (2) running tests `pytest -m "not slow" -q`; (3) branch contract — all work on `daily-issue-fixing`, no direct push to `main`; (4) DomI sync expectation — `.domi-pin` must match DomI HEAD before starting a write session; (5) how to file an issue (ADMESH or DomI).
- [ ] T014 [P] [US3] Write `TESTING.md` at repo root covering: (1) pytest invocation patterns (standard, full, single file, single test, cov); (2) markers: `slow` (deselect by default), `requires_matlab` (MATLAB fixture skip), `requires_chilmesh` (chilmesh skip); (3) fixture-data locations under `tests/fixtures/`; (4) parity-test pattern (port-correctness tests vs. MATLAB golden fixtures); (5) the `assert_structurally_valid` helper in `tests/_structural_validity.py`.

### R2 — admesh-domains contract

- [ ] T015 [P] [US3] Write `docs/ADMESH_DOMAINS_CONTRACT.md` documenting: (1) symbols ADMESH imports from `admesh_domains` — `load_default_registry()` (returns an object with `.load_domain(id)` and `.list_available()` methods); (2) duck-typed attributes consumed from a registry domain object — `.rings` or `.boundaries` (list of node arrays), `.bbox` (4-tuple or None), `.fixed_points` (array or None); (3) supported version range `>=0.1.0,<0.2`; (4) upgrade policy — bump pin after running `tests/test_admesh_domains_contract.py` against the new version.
- [ ] T016 [US3] Update `pyproject.toml`: change `admesh-domains>=0.1.0` to `admesh-domains>=0.1.0,<0.2` in `[project].dependencies`. (Depends on T015 for the rationale.)
- [ ] T017 [US3] Write `tests/test_admesh_domains_contract.py`: (1) import `admesh_domains`; (2) assert `admesh_domains.__version__` satisfies `>=0.1.0,<0.2` via `packaging.version`; (3) call `admesh_domains.load_default_registry()` and assert the returned object has `.load_domain` and `.list_available` callables; (4) call `.list_available()` and assert it returns an iterable without raising.

**Checkpoint**: `.github/workflows/tests.yml` passes on a fresh branch, `CONTRIBUTING.md` + `TESTING.md` exist, contract parity test runs green.

---

## Phase 4: R3 — Reorg (Conditional) + API Reference (User Story 4, P3)

**Goal**: `admesh` public surface is clearly delimited in `__all__`; mkdocs-material API reference is live on GitHub Pages; every public symbol has a complete docstring.

**Independent Test**: Navigate to `https://domattioli.github.io/ADMESH/` and find the `triangulate` function with `Parameters`, `Returns`, and a runnable example.

> R3 tasks start after R1 is complete. T020 (amendment draft) gates T021 (conditional reorg); T022 (split __all__) runs regardless. Docstring work (T027) is independent of both.

### R3 — Constitution amendment

- [ ] T020 [US4] Draft `specs/009-release-readiness-for-0.1.0/CONSTITUTION-AMENDMENT.md`: proposal to add an Article governing the public-surface / faithful-port-internals split; state the specific change (move 13 stage modules to `admesh/_stages/`, keep backward-compat re-exports until 1.0, or adopt explicit `__all__` annotation instead); obtain maintainer sign-off (comment in the file or GitHub review approval).

### R3 — package layout (one of the two following tasks runs, not both)

- [ ] T021 [US4] [CONDITIONAL — amendment passes] Create `admesh/_stages/`; move the 13 faithful-port stage modules (`background_grid`, `bathymetry`, `boundary`, `curvature`, `distance`, `distmesh`, `dominate_tide`, `in_polygon`, `inpaint`, `medial_axis`, `mesh_size`, `quality`, `routine`) there; add stub re-export modules at the old paths (e.g. `admesh/curvature.py` becomes a one-liner `from admesh._stages.curvature import *`); update `admesh/__init__.py::__all__` to reference `_stages` clearly.
- [ ] T022 [US4] [ALWAYS — regardless of amendment outcome] In `admesh/__init__.py`, split `__all__` into two clearly-commented groups: `# --- Public API surface (stable, semver-guarded) ---` and `# --- Faithful-port stage modules (internal, numerically frozen per Article II.1) ---`.

### R3 — docstrings

- [ ] T023 [P] [US4] Complete docstrings (Parameters / Returns / Example) on all public symbols in `admesh/api.py`: `Domain`, `Mesh`, `BoundarySegment`, `triangulate`. Currently missing structured docstrings on most methods.
- [ ] T024 [P] [US4] Complete docstrings on all public symbols in `admesh/fort14.py`: `read_fort14`, `write_fort14`, `Fort14ParseError`.
- [ ] T025 [P] [US4] Complete docstrings on all public symbols in `admesh/loaders.py`: `load_domain_from_fort14`, `load_domain_from_json`, `load_domain_from_toml`.
- [ ] T026 [P] [US4] Complete docstrings on all public symbols in `admesh/registry.py`: `list_available_domains`, `load_domain_from_registry`, `load_domain_with_metadata`.
- [ ] T027 [P] [US4] Complete docstrings on all public symbols in `admesh/quad_prep.py`: `smooth_for_quadrangulation`; `admesh/quality.py`: `mesh_quality`, `right_iso_quality`; `admesh/size_field.py`: `SizeFieldFn`, `compose_size_field`; `admesh/boundary_types.py`: `BoundaryType`.
- [ ] T028 [P] [US4] Complete docstrings on all public symbols in `admesh/valence.py`: `BalanceConfig`, `BalanceResult`, `ValenceStats`, `balance_valence_triangles`, `compute_valence`, `get_valence_report`.
- [ ] T029 [US4] Write `tests/test_docstring_completeness.py`: iterate over every symbol in `admesh.__all__`; for each that resolves to a class or function, assert its `__doc__` contains `Parameters`, `Returns`, and `Example`. (After T023–T028 are complete.)

### R3 — mkdocs site

- [ ] T030 [US4] Add `mkdocs-material>=9` and `mkdocstrings[python]>=0.24` to `[project.optional-dependencies]` `dev` extras in `pyproject.toml`.
- [ ] T031 [US4] Write `mkdocs.yml` at repo root: `site_name: ADMESH`, nav covering index / quickstart / api-reference / porting-notes / constitution; `theme: material`; `plugins: [search, mkdocstrings]`.
- [ ] T032 [P] [US4] Write `docs/index.md` (project overview, install, 3-line quickstart, links to API ref and porting notes).
- [ ] T033 [P] [US4] Write `docs/quickstart.md` (end-to-end worked example: polygon → `triangulate` → `mesh.to_fort14`; plus round-trip with a real ADCIRC fixture; plus custom size-field contribution pattern).
- [ ] T034 [US4] Write `.github/workflows/docs.yml`: steps checkout, setup-python, `pip install -e ".[dev]"`, `mkdocs gh-deploy --force`; triggers on push to `daily-issue-fixing` and `main`.

**Checkpoint**: `mkdocs build` succeeds locally; `mkdocs serve` shows the API reference page with all public symbols documented.

---

## Phase 5: R4 — Issue #10 Resolution + Tag (User Story 2, P1)

**Goal**: Tier-1 and Tier-2 acceptance tests pass without `xfail`; `v0.1.0` is on PyPI.

**Independent Test**: `pytest tests/test_default_size_field.py -v` exits zero with zero xfails and zero xpassed.

> R4 starts after R1 is complete (pre_tag_check.sh gate exists). Investigation tasks T035–T037 run first and inform which fix tasks T038–T041 are needed. Fix tasks may be re-planned based on findings.

### R4 — investigation

- [ ] T035 [US2] Add a diagnostic mode to `admesh/api.py::_build_default_size_field` (env-var-gated, e.g. `ADMESH_DEBUG_SIZEFIELD=1`): after each of curvature, medial-axis, bathymetry, and tide stages, write the full h-grid as a `.npy` file to `output/debug_h_{stage}.npy`. Run on Tier-1 and Tier-2 fixtures. Examine for: NaN proportion per stage, h-values exceeding `h_max`, and spatial discontinuities at the bathymetry convex-hull boundary.
- [ ] T036 [US2] Examine `admesh/api.py::Domain.from_mesh` and `admesh/bathymetry.py::create_elevation_grid`: characterize the `LinearNDInterpolator` NaN coverage on Tier-1 fixture (log fraction outside convex hull); test whether `NearestNDInterpolator` + explicit convex-hull mask would eliminate the NaN boundary artifacts.
- [ ] T037 [US2] Examine `admesh/distmesh.py`: identify nodes that end up outside the SDF=0 contour in a failed Tier-1 run; map them to the size-field h-values at their pre-drift positions; determine whether boundary-projection is skipping them or a force imbalance is driving them out.

### R4 — fixes (adjust scope to investigation findings)

- [ ] T038 [US2] Fix `admesh/api.py::Domain.from_mesh` bathymetry interpolant: replace `LinearNDInterpolator` with `NearestNDInterpolator` (or add convex-hull mask that clips values to `[h_min, h_max]` before the inpaint step), per T036 findings.
- [ ] T039 [US2] Fix `admesh/bathymetry.py::create_elevation_grid` or `admesh/api.py::_build_default_size_field`: add an explicit `h_max` clip after the bathymetry stage; guard against NaN propagation into the medial-axis or tide stages, per T035 findings.
- [ ] T040 [US2] Fix `admesh/distmesh.py` boundary projection (if T037 shows nodes escaping the SDF=0 contour): tighten the `geps` tolerance on the projection guard or add a hard post-iteration clamp that re-projects any node with `sdf(p) > 0`.
- [ ] T041 [US2] If T035 reveals stage-ordering or gradient-clipping issues in `admesh/mesh_size.py::build_h`, fix the ordering / clipping logic. Add a `PORTING_NOTES.md` entry if the fix diverges from the MATLAB behavior.

### R4 — un-xfail + regression check

- [ ] T042 [US2] Remove `@pytest.mark.xfail` from `tests/test_default_size_field.py::test_tier1_wetting_and_drying_round_trip`. Run the test standalone — it must pass.
- [ ] T043 [US2] Remove `@pytest.mark.xfail` from `tests/test_default_size_field.py::test_tier2_wnat_release_gate`. Run the test standalone — it must pass within 60 s wall-clock.
- [ ] T044 [US2] Run the full test suite: `pytest -q`. Verify zero failures, zero xfails, no new skips.

### R4 — final gate + tag

- [ ] T045 [US2] Run `bash scripts/pre_tag_check.sh` — all 9 gates must pass. Fix any residual failures.
- [ ] T046 [US2] Update `README.md`: remove the `🚧 0.1.0 in progress` callout; update the "Install" section to show `pip install admesh2D` without a source-only caveat; update the "Advanced kwargs" note to say "documented in `docs/quickstart.md`".
- [ ] T047 (Maintainer action) Push `v0.1.0` git tag: `git tag -a v0.1.0 -m "Release 0.1.0"` and `git push origin v0.1.0`. Confirm `publish.yml` workflow uploads wheel + sdist to PyPI. Confirm `pip install admesh2D==0.1.0` installs cleanly in a fresh virtualenv.

**Checkpoint**: `pip install admesh2D==0.1.0` in a fresh venv; `python -c "import admesh; print(admesh.__version__)"` prints `0.1.0`.

---

## Dependencies & Execution Order

```
T001 (version fix)
  ↓
T002–T009 (R1)  ←→  T010–T017 (R2) [parallel once T001 done]
                ←→  T020–T034 (R3) [parallel once T001 done]
  ↓
T035–T047 (R4)
```

### Within R4

- T035 + T036 + T037 (investigation) run in parallel — all read-only
- T038–T041 (fixes) follow investigation; scope adjusts to findings
- T042 + T043 depend on T038–T041 being complete
- T044 depends on T042 + T043
- T045–T047 depend on T044

### Parallel Opportunities

- All R2 tasks (T010–T017) are independent of each other — run simultaneously
- All R3 docstring tasks (T023–T028) are independent of each other — run simultaneously
- R3 mkdocs tasks (T030–T034) can run in parallel after T022
- R4 investigation tasks (T035–T037) are independent of each other

---

## Notes

- `[P]` = safe to run in parallel (different files, no shared state)
- `[CONDITIONAL]` tasks run only if the stated condition is met
- R4 fix tasks T038–T041 are written against the most likely candidates from the spec; the actual tasks executed depend on investigation findings from T035–T037
- After T001, all phases (R1/R2/R3) can advance in parallel; R4 waits for R1 only (not R2/R3)
- The 0.1.0 tag (T047) is a maintainer action — Claude cannot push tags; prepare the pre-tag artifacts and hand off
