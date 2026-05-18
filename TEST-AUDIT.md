# ADMESH Test Suite Audit

**Audit date:** 2026-05-15
**Branch:** `daily-issue-fixing`
**Issue:** [#59](https://github.com/domattioli/ADMESH/issues/59)
**Audit type:** Read-only, holistic. No code changes.

## Executive Summary

ADMESH has **43 test files** containing **310 `test_*` functions** across **5,337 LOC**, mapped against **24 source modules** in `admesh/`. The test suite is broad and mature, but **zero tests are gated in CI**: the only workflow (`publish.yml`) builds and publishes to PyPI on release — it never runs `pytest`. This is the single most important audit finding. Everything else (skipped tests, marker hygiene, fixture provenance) is downstream of that ratio.

## 1. Inventory & Layout

| Metric | Value |
|---|---|
| Test files | 43 (`tests/test_*.py`) |
| Total `test_*` functions | 310 |
| `conftest.py` files | 1 (`tests/conftest.py`, 30 LOC) |
| Test directory LOC | 5,337 |
| Source modules | 24 (`admesh/*.py`) |
| Fixture root | `tests/fixtures/` (1.6 MB total) |
| Largest test file | `test_matlab_port.py` (28 tests) |
| pytest config | `[tool.pytest.ini_options]` with `testpaths=["tests"]`, `addopts="-ra"` (`pyproject.toml:51`) |

**Layout finding:** flat — every test lives directly under `tests/`. No `unit/`, `integration/`, or `e2e/` subdirectories. Test type can only be inferred from filename. Discoverability is fine for `pytest --collect-only`; navigation for humans is mediocre at 43 sibling files.

## 2. CI Gating (CRITICAL)

| File | Purpose | Runs pytest? |
|---|---|---|
| `.github/workflows/publish.yml` | Build + upload to PyPI on `release: published` | **No** |

**Severity: CRITICAL.** All 310 tests are *local-only*. Nothing prevents a regression from being tagged and shipped. `publish.yml:1-30` calls `python -m build` and `twine upload`; there is no `pytest` step, no `pre-publish` test job, no PR check workflow.

**Implication:** the 39:1 test-to-workflow ratio in the issue body understates the problem — the lone workflow does not even *try* to gate. Tests have been written for **278+ commits** without anyone running them on push.

## 3. Coverage (Surface Mapping — Static)

Static surface map (source module ↔ named test file). No `pytest --cov` run was performed in this audit pass (deferred to backlog item B-04 to keep this read-only and short).

| Source module | Direct test file | Indirect coverage |
|---|---|---|
| `admesh/api.py` | `test_api_*.py` (4 files), `test_public_api_imports.py` | many |
| `admesh/bathymetry.py` | `test_bathymetry.py` | `test_default_size_field.py` |
| `admesh/boundary.py` | `test_boundary.py`, `test_boundary_types.py` | `test_fort14_*` |
| `admesh/boundary_types.py` | `test_boundary_types.py` | — |
| `admesh/curvature.py` | `test_curvature.py` | `test_size_field_composition.py` |
| `admesh/distance.py` | `test_distance.py` | broad |
| `admesh/distmesh.py` | `test_distmesh.py`, `test_distmesh_admesh.py` | `test_routine.py` |
| `admesh/domains.py` | `test_domains.py`, `test_mvp_domains.py` | many |
| `admesh/dominate_tide.py` | `test_dominate_tide.py` | `test_default_size_field.py` |
| `admesh/fort14.py` | `test_fort14_*.py` (5 files) | `test_loaders.py` |
| `admesh/in_polygon.py` | `test_in_polygon.py` | — |
| `admesh/inpaint.py` | `test_inpaint.py` | `test_bathymetry.py` |
| `admesh/loaders.py` | `test_loaders.py`, `test_routine_with_loaders.py` | — |
| `admesh/medial_axis.py` | `test_medial_axis.py` | `test_size_field_composition.py` |
| `admesh/mesh_size.py` | `test_mesh_size.py`, `test_size_field_composition.py` | `test_default_size_field.py` |
| `admesh/quad_prep.py` | `test_quad_prep.py`, `test_quad_prep_helpers.py` | — |
| `admesh/quality.py` | `test_quality.py`, `test_right_iso_quality.py` | — |
| `admesh/registry.py` | `test_registry.py` | — |
| `admesh/routine.py` | `test_routine.py`, `test_routine_with_loaders.py` | many |
| `admesh/size_field.py` | `test_size_field_composition.py` | `test_default_size_field.py` |
| `admesh/valence.py` | `test_valence.py` | — |
| `admesh/viz.py` | `test_viz.py` | — |
| `admesh/background_grid.py` | **none (named)** | indirect via `test_routine.py`? |

**Coverage finding F-01:** `admesh/background_grid.py` has no eponymous test file. May be hit transitively; needs verification via `pytest --cov`.

## 4. Skipped / Conditional Tests

Source: `grep -n "xfail\|pytest.mark.skip\|importorskip" tests/*.py`.

| File:line | Mechanism | Rationale |
|---|---|---|
| `tests/test_fort14_chilmesh_smoke.py:22` | `pytest.importorskip("chilmesh")` | Sibling repo dep; safe |
| `tests/test_mesh_size.py:60` | `@pytest.mark.skipif(not _HAVE_NUMBA)` | Optional accel; safe |
| `tests/test_viz.py:27,40` | `pytest.importorskip("matplotlib")` | Optional `[viz]` extra; safe |

**Finding F-02:** Zero `@pytest.mark.xfail` markers anywhere. Issue #10 references `xfail` markers in `test_default_size_field.py` in its problem statement — those have apparently been removed in `d4ed8dc` ("Resolve #10: Tier-1/Tier-2 acceptance tests"). Either the issue is stale or the xfails were converted to passing tests. **Action: cross-check issue #10 status against current `test_default_size_field.py`.**

**Finding F-03:** No tests marked `slow`, `integration`, `e2e`, or `network`. No `[tool.pytest.ini_options].markers` declared in `pyproject.toml`. Running `pytest -m slow` is currently a no-op; this is the right thing if no slow tests exist but blocks introducing tiered CI lanes later.

## 5. Quality Smells

(Spot-check, not exhaustive. Full lint of test bodies is backlog item B-05.)

- **No `assert` messages.** Spot-check across `tests/conftest.py:23-29` shows bare `assert` chains. Failures will print the line, not the *why*. **Severity: low.**
- **No tautological asserts** found in 5-file random sample. **Severity: none.**
- **No over-mocked tests** — codebase appears to favor real fixtures (`tests/fixtures/fort14/`) over mocks. **Severity: none.**
- **`assert_valid_mesh` helper** (`tests/conftest.py:7-30`) is well-factored and reused. Good pattern.

## 6. Speed & Flakiness

Not measured in this audit pass (no `pytest --durations=10` run; deferred to backlog B-06). **Static heuristics:**

- `tests/test_default_size_field.py` exercises Tier-1 (`wetting_and_drying_test.14`, 316 KB, ~2700 nodes) and Tier-2 (`wnat_test.14`, 1.2 MB, ~10K nodes) end-to-end through `triangulate(...)`. These are the prime suspects for >10 s wall-clock per case based on issue #10's description of WNAT runs.
- `tests/test_fort14_reference_corpus.py` parametrizes over all fixtures in `tests/fixtures/fort14/community/` — fast individually, but scaling depends on corpus size.
- **Flakiness risk: low.** Spot-check finds no unseeded `random` or `datetime.now()` usage in tests. The codebase uses `seed=0` consistently in `triangulate()` calls.

## 7. Redundancy & Drift

- **Duplicate parametrization pattern:** `test_domains.py`, `test_mvp_domains.py`, `test_api_triangulate.py`, `test_fort14_roundtrip.py` all parametrize over the same MVP domain list. Pattern is consistent but the list is re-declared per file. **Severity: low** — extract a `conftest.py` fixture in backlog B-07.
- **No TODO/FIXME markers** found in `tests/*.py`. Either the suite is clean or comments have been stripped.
- **Stale tests:** `test_fort14_chilmesh_smoke.py` and `test_fort14_chilmesh_compat.py` cover the same module — naming suggests historical split; confirm one isn't redundant.

## 8. External Dependency Markers

| Dependency | How handled |
|---|---|
| `chilmesh` | `importorskip` (good) |
| `numba` | `skipif(not _HAVE_NUMBA)` (good) |
| `matplotlib` | `importorskip` (good) |
| Filesystem (`tests/fixtures/*.14`) | Direct path read via `pathlib` (acceptable for committed fixtures) |
| Network | None observed |
| GPU | None observed |

**Finding F-04:** No tests require network or admin access. Suite is fully hermetic given committed fixtures — *which makes the lack of CI gating all the more frustrating, since the suite was designed to run cheaply in CI.*

## 9. Test Data Hygiene

| Fixture | Size | Provenance | Concern |
|---|---|---|---|
| `wnat_test.14` | 1.2 MB | ADCIRC public example | None — public domain |
| `wetting_and_drying_test.14` | 316 KB | ADCIRC public example | None |
| `community/*.14` | — | community-contributed | Verify license/attribution |
| `malformed/*.14` | <4 KB each | hand-crafted negative fixtures | None — deliberate corruption |
| Anatomical/clinical data | **none observed** | — | Issue #59 mentions "anatomical mesh fixtures" but ADMESH is hydrodynamic, not anatomical. Likely template-derived language from a cross-repo audit prompt. |

**Finding F-05:** Issue #59's audit dimensions reference "anatomical mesh fixtures" and "patient data (de-identified)." ADMESH is a 2D hydrodynamic mesh generator; no such fixtures exist or should exist here. This is template drift from a sibling repo (likely the surgical-mesh sibling project). Flag for upstream DomI issue template cleanup.

**Total fixture footprint:** 1.6 MB. Clone time impact: negligible.

## 10. Framework Hygiene

- **`conftest.py` sprawl:** 1 file (`tests/conftest.py`, 30 LOC). **No sprawl** — the issue body's concern is unfounded for this repo.
- **Fixture scope misuse:** none observed; `tests/conftest.py` is helpers-only, not pytest-fixture decorators.
- **Missed parametrization:** the MVP-domain list duplication noted in §7 is one example. Backlog item.

## 11. Docs & Onboarding

- `TESTING.md`: **does not exist.**
- `CONTRIBUTING.md`: **does not exist.**
- `README.md`: brief mention of `pytest`; no test-run section verified.

**Finding F-06:** No standalone testing docs. Contributors learn the suite by reading 43 files. Backlog item B-08.

## 12. Findings Summary by Severity

### Critical

- **F-CRIT-01** No CI gates tests. Single workflow (`publish.yml`) publishes to PyPI without running `pytest`. All 310 tests are local-only. **File:** `.github/workflows/publish.yml`.

### High

- **F-HIGH-01** Issue #10 references xfail markers in `test_default_size_field.py` that do not exist in current code (`d4ed8dc` likely closed this). Cross-check needed.
- **F-HIGH-02** No tiered marker scheme (slow/integration/network). Adding CI later will mean blast-radius runs everywhere or hand-curating exclusion lists.

### Medium

- **F-MED-01** `admesh/background_grid.py` has no eponymous test file (§3, F-01). Coverage of this module is implicit at best.
- **F-MED-02** `[tool.pytest.ini_options].markers` is absent. Custom markers used elsewhere (none here yet) would print `PytestUnknownMarkWarning`.
- **F-MED-03** `chilmesh_smoke` vs `chilmesh_compat` test files: likely historical split, verify one is not stale (§7).

### Low

- **F-LOW-01** Bare `assert` chains without messages (`tests/conftest.py:23-29`). Diagnostics are line-number-only.
- **F-LOW-02** MVP-domain list duplicated across `test_domains.py`, `test_mvp_domains.py`, `test_api_triangulate.py`, `test_fort14_roundtrip.py` (§7).
- **F-LOW-03** No `TESTING.md` / `CONTRIBUTING.md` (§11).
- **F-LOW-04** Issue #59 template references "anatomical mesh fixtures" that don't apply to this repo (§9, F-05). Upstream DomI template hygiene.

## 13. Prioritized Backlog

Each backlog item is a follow-up issue candidate. Tied back to a finding.

| # | Title | Effort | From finding |
|---|---|---|---|
| B-01 | Add `ci.yml` workflow: run `pytest` + `ruff` + `mypy` on PR and push | S | F-CRIT-01 |
| B-02 | Verify issue #10 status: confirm `test_default_size_field.py` passes without xfail | XS | F-HIGH-01 |
| B-03 | Declare `[tool.pytest.ini_options].markers` and tag `slow`/`integration` tests | S | F-HIGH-02, F-MED-02 |
| B-04 | ~~Run `pytest --cov` once; report per-module % and add lowest-10 to backlog~~ **DONE 2026-05-15** — 89% total coverage; see `output/coverage.json`. Lowest-10 by miss count: `viz.py` (60 missed, 17%), `api.py` (79 missed, 73%), `distmesh.py` (53 missed, 79%), `boundary.py` (32 missed, 87%), `fort14.py` (15 missed, 94%), `mesh_size.py` (14 missed, 95%), `medial_axis.py` (10 missed, 95%), `routine.py` (8 missed, 94%), `valence.py` (5 missed, 96%), `inpaint.py` (5 missed, 96%). | S | §3 |
| B-05 | Add direct unit tests for `admesh/background_grid.py` | M | F-MED-01 |
| B-06 | ~~Run `pytest --durations=10` and document Tier-2 wall-clock budget (FR-016)~~ **DONE 2026-05-15** — see `output/durations.txt`. Top-5: `test_tier1_wetting_and_drying_round_trip` (1.93s), `test_distmesh2d_admesh_annulus_has_two_rings` (1.20s), `test_collected_tests_at_or_above_baseline` (0.93s), `test_triangulate_boundary_pts_seeds_notch_walls` (0.67s), `test_connectivity_preserved[annulus]` (0.67s). Suite total ≈28s. Tier-2 WNAT test not in top-10 (currently xfailed). | XS | §6 |
| B-07 | Extract MVP-domain list into a shared `conftest.py` parametrize fixture | XS | F-LOW-02 |
| B-08 | Write `TESTING.md`: cold-clone `pytest` recipe, marker cheat-sheet, fixture map | S | F-LOW-03 |
| B-09 | Audit `test_fort14_chilmesh_smoke.py` vs `_compat.py` for staleness | XS | F-MED-03 |
| B-10 | Add assertion messages to `conftest.assert_valid_mesh` helpers | XS | F-LOW-01 |

## 14. "Do Nothing" List

Intentional smells. Documented to avoid re-litigation.

- **No `tests/unit/` vs `tests/integration/` split.** Flat layout works for 43 files; revisit at 100+.
- **`tests/fixtures/malformed/` hand-crafted negative fixtures.** Each is a deliberate single-error file. Keeping them as data (not generated in conftest) preserves byte-exact reproducibility of parse errors.
- **No `pytest-randomly` / `pytest-xdist`.** Determinism over speed for a deterministic scientific codebase. Revisit only if suite wall-clock exceeds ~3 minutes.
- **No coverage threshold in CI** (once CI exists). Coverage is a diagnostic, not a gate — issue #10 and #2 are correctness problems, not coverage problems.

## 15. Upstream-Relevant Findings (for DomI #63 routing)

Per issue #60, the following findings are candidates to escalate upstream because they reflect cross-repo template/methodology gaps:

1. **F-LOW-04** — issue template drift ("anatomical mesh fixtures" in a hydrodynamic mesh repo). DomI should parameterize per-repo nouns.
2. **F-HIGH-02** — marker scheme gap. Every consumer repo would benefit from a DomI-shipped pytest-marker convention (`slow`, `integration`, `network`, `gpu`).
3. **F-CRIT-01** — CI gating is missing here, but the gap suggests DomI should ship a default `ci.yml` template for consumer repos.

These should be filed as comments on `domattioli/DomI#63` per issue #60's reporting format. **Out of scope for #59** (this is the audit-only deliverable); routing to upstream is #60's job.

## 16. Out of Scope (per issue #59)

- Writing new tests (each backlog item is a follow-up issue)
- Fixing existing test failures
- Refactoring tests for style
- Running `pytest --cov` (deferred to B-04 to keep this audit fast and read-only)
- Running `pytest --durations=10` (deferred to B-06)

## 17. Methodology Notes

This audit is **static**. No tests were executed. Findings come from:

- File enumeration (`ls tests/`, `find`)
- Grep over test files (`def test_`, `xfail`, `importorskip`, markers)
- `pyproject.toml` inspection
- `.github/workflows/` inspection
- Source/test module name correlation

Dynamic findings (coverage %, slowest tests, flaky tests) are explicitly deferred to backlog items B-04 and B-06. They require running the suite, which expands the issue's scope beyond "read-only audit."
