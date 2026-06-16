# Implementation Plan: Release Readiness for ADMESH 0.1.0

**Branch**: `009-release-readiness-for-0.1.0` | **Date**: 2026-05-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/009-release-readiness-for-0.1.0/spec.md`

## Summary

Four sequential phases gate the 0.1.0 PyPI tag:

- **R1 — Tag-gate hygiene**: extend `scripts/pre_tag_check.sh` with version-string, plan-staleness, and audit-artifact checks; reconcile the `pyproject.toml` / `__init__.py` version mismatch (0.1.0 vs 0.2.0, pyproject wins); run `pytest --cov` and `--durations=10` and commit outputs to `output/` (closes TEST-AUDIT B-04 / B-06).
- **R2 — CI + onboarding + contract**: add `.github/workflows/tests.yml` on Python 3.10/3.11/3.12 (closes TEST-AUDIT F-CRIT-01); introduce a `slow` pytest marker with a weekly lane; ship `CONTRIBUTING.md`, `TESTING.md`, `docs/ADMESH_DOMAINS_CONTRACT.md`; tighten the `admesh-domains` pin to `>=0.1.0,<0.2`.
- **R3 — Reorg (gated by Constitution amendment) + API reference**: draft amendment, execute restructure if it passes, then ship mkdocs-material + GitHub Pages + `mkdocstrings` API ref and complete docstrings on every public-surface symbol.
- **R4 — Issue #10 + tag**: diagnose size-field overshoot on Tier-1/Tier-2 real-world fixtures via per-stage profiling; fix `Domain.from_mesh` interpolant, `bathymetry.py` NaN extrapolation, and/or `distmesh.py` boundary projection per findings; remove `xfail` from both Tier-1 and Tier-2 tests; push `v0.1.0` tag.

Phases R2 and R3 are independent and can proceed in parallel with each other once R1 is complete. R4 is the last gate and requires R1 to have passed `pre_tag_check.sh`.

## Technical Context

**Language/Version**: Python ≥3.10 (existing `pyproject.toml` pin)
**Primary Dependencies**: NumPy, SciPy, Numba, Shapely (existing); `pytest-cov` (dev); `mkdocs-material`, `mkdocstrings[python]` (dev, new for R3)
**Storage**: N/A — pure library + documentation
**Testing**: pytest; existing `tests/` tree; new `tests/test_admesh_domains_contract.py` (R2) and `tests/test_docstring_completeness.py` (R3)
**Target Platform**: Linux / macOS / Windows (pure Python; CI on `ubuntu-latest`)
**Project Type**: Python library (flat `admesh/` layout); GitHub Actions CI; GitHub Pages docs
**Performance Goals**: Standard CI lane ≤ 8 min wall-clock; Tier-2 WNAT release gate ≤ 60 s (spec FR-032)
**Constraints**:
- R4 fixes must not regress any Tier-0 polygon-domain test (spec FR-034, Constitution Principle I)
- R4 fixes touching the 13 faithful-port stage modules require PORTING_NOTES.md entries documenting any MATLAB divergence (Constitution Article II.1)
- No new C extensions; Numba `@njit` permitted if profiling justifies it (Constitution Principle II)
- `admesh-domains` imports in `admesh/registry.py` are currently lazy (inside functions, not at module level) — R2 must preserve that pattern to keep the import lightweight

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Faithful Port Before Optimization | ✅ Preserved (R1/R2/R3) / ⚠️ Justified (R4) | R4 will modify files from the faithful-port layer (`api.py`, possibly `bathymetry.py`, `distmesh.py`, `mesh_size.py`). Any divergence from MATLAB behavior must be documented in `docs/PORTING_NOTES.md`. The fix is to correct the Python port's overshoot, not to add new functionality. |
| II. Pure-Python First (No C Extensions) | ✅ Preserved | No new C code introduced by any phase. |
| III. Reference-Test Discipline | ✅ Preserved | R4 acceptance gate is the un-xfailed Tier-1/Tier-2 tests, which assert structural validity (node SDF ≤ bbox_diag * 1e-2, area ≥ 95% source). |
| IV. Stage-by-Stage Bottom-Up | ✅ N/A | All 13 stages already ported. R4 works on the v1 additive orchestration layer, not the stage modules directly. |
| V. Report-and-Advance Session Cadence | ✅ Preserved | Standard cadence applies. |

## Project Structure

### Documentation (this feature)

```text
specs/009-release-readiness-for-0.1.0/
├── spec.md                     ✅ done
├── plan.md                     ✅ this file
├── tasks.md                    ← next (/speckit-tasks)
└── CONSTITUTION-AMENDMENT.md   ← R3 task T020
```

### New / Modified Source Files

```text
# R1 — tag-gate hygiene
scripts/pre_tag_check.sh        (modify — add version, staleness, artifact gates)
admesh/__init__.py              (modify — fix __version__ 0.2.0 → 0.1.0)
output/coverage.json            (new — pytest --cov artifact)
output/durations.txt            (new — pytest --durations=10 artifact)
TEST-AUDIT.md                   (modify — mark B-04/B-06 complete)

# R2 — CI + onboarding + contract
.github/workflows/tests.yml     (new — standard test lane, skip slow)
.github/workflows/tests-slow.yml (new — weekly + v* tag lane, full suite)
pyproject.toml                  (modify — slow marker + admesh-domains pin)
CONTRIBUTING.md                 (new — root)
TESTING.md                      (new — root or docs/)
docs/ADMESH_DOMAINS_CONTRACT.md (new)
tests/test_admesh_domains_contract.py (new)

# R3 — reorg (conditional) + API reference
specs/009-.../CONSTITUTION-AMENDMENT.md (new — maintainer sign-off required)
admesh/_stages/                 (new IF amendment passes — contains stage module symlinks/moves)
admesh/__init__.py              (modify — split __all__ regardless of amendment outcome)
pyproject.toml                  (modify — add mkdocs-material, mkdocstrings to [dev])
mkdocs.yml                      (new — root)
docs/index.md                   (new)
docs/quickstart.md              (new)
.github/workflows/docs.yml      (new)
tests/test_docstring_completeness.py (new)

# R4 — issue #10 fix + tag
admesh/api.py                   (modify — Domain.from_mesh interpolant)
admesh/bathymetry.py            (likely modify — NaN extrapolation guard)
admesh/distmesh.py              (likely modify — boundary projection guard)
admesh/mesh_size.py             (likely modify — stage ordering/clipping)
docs/PORTING_NOTES.md           (modify — document any MATLAB divergence)
tests/test_default_size_field.py (modify — remove xfail from Tier-1/Tier-2)
```

## Notes on R4 Investigation

The root cause of the #10 overshoot is not fully confirmed. Spec section "Proposed approach" names four candidates:

1. **Bathymetry NaN extrapolation**: `LinearNDInterpolator` returns NaN outside the convex hull of the source mesh nodes; `inpaint_nans` method 0 may extrapolate extreme values near the hull boundary that feed pathological h-values into downstream stages.
2. **Domain.from_mesh interpolant**: the same `LinearNDInterpolator` issue means the bathymetry grid has 31% NaN at Tier-1 fixture scale; switching to `NearestNDInterpolator` + hull mask is the lowest-risk fix.
3. **Size-field h-min cliff**: curvature/medial-axis stages min-clip at `h_min` near narrow features, creating a spatial discontinuity that distmesh's force-balance solver can amplify.
4. **distmesh boundary projection**: the SDF projection step may fail to keep vertices inside the domain when the size field has extreme h-min spots adjacent to low-gradient regions.

The investigation tasks (T030–T032) must run first to identify which candidates are active before the fix tasks (T033–T036) are executed. Fix scope adjusts to findings; if a different root cause emerges, tasks T033–T036 are re-planned at the start of R4.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| R4 modifies faithful-port stage modules | The overshoot bug lives in the Python translation of MATLAB behavior; fixing it necessarily touches the ported code | A workaround layer above the port would mask the bug rather than fix it; Constitution Principle I requires the port to be correct |
| R3 reorg (conditional) creates a new `admesh/_stages/` subpackage | Provides the public/internal boundary that makes the API ref navigable without ambiguity | Doing it after 0.1.0 requires a version bump and deprecation cycle; now is the cheapest moment |
