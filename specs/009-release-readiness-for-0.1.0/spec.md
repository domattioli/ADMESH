# Feature Specification: Release Readiness for ADMESH 0.1.0

**Feature Branch**: `009-release-readiness-for-0.1.0`
**Created**: 2026-05-15
**Status**: Draft
**Input**: User description: "speckit specify release-readiness for 0.1.0, with phases roughly: R1 version-string reconciliation + plan refresh + TEST-AUDIT.md B-04/B-06 follow-ups + pre_tag_check.sh gating; R2 CI test workflow (closes F-CRIT-01) + TESTING.md + CONTRIBUTING.md + admesh-domains contract doc + pin; R3 light package reorg (if Constitution amendment passes) + API reference (mkdocs-material is cheap); R4 resolve #10 (the only numerics blocker the plan flags) + un-xfail Tier-1/Tier-2 + tag"

## Context

ADMESH has shipped MVP, P1, P2, and P3 phases per `docs/governance/PROJECT_PLAN.md`. The "Path to 0.1.0" stated in that plan is "resolve #11 + #10, un-xfail the Tier-1/Tier-2 tests, run `bash scripts/pre_tag_check.sh`, tag." Issue #11 closed 2026-05-06. Issue #10 remains open. In the three weeks since the plan was last updated, six new specs (003-008) landed, the `admesh-domains` sibling became a hard dependency, and `TEST-AUDIT.md` (issue #59) surfaced an F-CRIT-01 finding that no CI workflow runs the test suite. The package version is also inconsistent: `pyproject.toml` declares `0.1.0` while `admesh/__init__.py` declares `__version__ = "0.2.0"`.

This spec bundles the release-readiness work into a single feature so the 0.1.0 tag ships from a coherent, hygienic, and externally-documented base.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tag-gate hygiene passes for a maintainer (Priority: P1)

A maintainer preparing the 0.1.0 PyPI tag needs assurance that the repo's release-state invariants hold: package version strings agree, the project plan reflects current state, the test-audit backlog items that gate a tag are resolved, and `scripts/pre_tag_check.sh` actually fails the build when those invariants drift. Today the plan is three weeks stale, `pyproject.toml` says `0.1.0` while `admesh/__init__.py` says `0.2.0`, and the pre-tag script does not check for either drift.

**Why this priority**: Without this slice, all downstream release work (R2/R3/R4) is shipped on a contradictory base. Tagging from a state where `__version__ != pyproject.version` produces a broken wheel and burns the tag.

**Independent Test**: Run `bash scripts/pre_tag_check.sh` cold on the repo. It must (a) detect the current `0.1.0` ↔ `0.2.0` mismatch and exit non-zero, (b) detect a stale `PROJECT_PLAN.md` (no "Where we are today" entry within 30 days of HEAD) and exit non-zero, (c) re-pass once both are reconciled. `git grep "Where we are today (2026-05-"` shows a 2026-05-15 (or later) entry.

**Acceptance Scenarios**:

1. **Given** `pyproject.toml` declares `version = "0.1.0"` and `admesh/__init__.py` declares `__version__ = "0.2.0"`, **When** the maintainer runs `bash scripts/pre_tag_check.sh`, **Then** the script exits non-zero with a message identifying both files and their conflicting version strings.
2. **Given** `docs/governance/PROJECT_PLAN.md`'s most recent "Where we are today" entry is older than 30 days from `git log -1 --format=%cI`, **When** the maintainer runs `bash scripts/pre_tag_check.sh`, **Then** the script exits non-zero with a `PLAN_STALE` message.
3. **Given** `TEST-AUDIT.md` backlog items B-04 (lowest-10 coverage report) and B-06 (slowest-10 timings) have no committed evidence under `output/`, **When** the maintainer runs `bash scripts/pre_tag_check.sh`, **Then** the script reports them as outstanding pre-tag items.
4. **Given** all the above are reconciled (versions agree, plan entry is fresh, B-04/B-06 outputs are committed under `output/`), **When** the maintainer re-runs the script, **Then** it exits zero.

---

### User Story 2 - End user can pip-install and triangulate a coastal fixture (Priority: P1)

A coastal-modeling researcher visits the ADMESH GitHub page, runs `pip install admesh2D`, and follows the README quickstart on the WNAT or wetting-and-drying fixture (both Tier-1 / Tier-2 real-world meshes). Today they cannot — `admesh2D` is not on PyPI yet, and the Tier-1 and Tier-2 tests that exercise those fixtures are marked `xfail` against issue #10 (default size-field overshoots domain on real-world coastal data).

**Why this priority**: This is the headline use case the project pitches in its README ("ADvanced, automatic unstructured MESH generator for 2D shallow-water models"). The 0.1.0 tag exists to deliver this. Tagging without resolving #10 ships a release whose own `xfail`ed tests prove the headline feature is broken.

**Independent Test**: In a fresh virtualenv on a laptop-class machine: `pip install admesh2D==0.1.0`. Then run the 3-line quickstart from README on `wnat_test.14` and `wetting_and_drying_test.14`. Both produce a `Mesh` whose nodes satisfy `domain.sdf(p) <= bbox_diag * 1e-2` and whose area covers ≥95% of the source-domain area. `pytest tests/test_default_size_field.py::test_tier1_wetting_and_drying_round_trip tests/test_default_size_field.py::test_tier2_wnat_release_gate` exits zero (no `xfail` markers, no `xpassed`).

**Acceptance Scenarios**:

1. **Given** a fresh Python 3.10+ virtualenv, **When** the user runs `pip install admesh2D`, **Then** the install succeeds and `python -c "import admesh; print(admesh.__version__)"` prints `0.1.0` (matching `pyproject.toml`).
2. **Given** `admesh==0.1.0` is installed and `tests/fixtures/fort14/adcirc_examples/wetting_and_drying_test.14` is available, **When** the user runs `admesh.triangulate(admesh.Domain.from_mesh(admesh.read_fort14(path)))`, **Then** the result is a non-empty `Mesh` with all nodes inside the domain SDF (`max node sdf ≤ bbox_diag * 1e-2`) and total area ≥ 95% of the source.
3. **Given** the spec-002 Tier-1 and Tier-2 tests were `xfail` before this work, **When** `pytest tests/test_default_size_field.py` runs after the fix, **Then** zero tests are `xfailed` and zero are `xpassed`.
4. **Given** the maintainer has executed Phase R4 successfully, **When** they push the `v0.1.0` git tag, **Then** the GitHub Actions `publish.yml` workflow uploads a wheel + sdist to PyPI and the wheel's `__version__` matches the tag.

---

### User Story 3 - External contributor onboards from a cold clone (Priority: P2)

A new contributor (academic collaborator or open-source drive-by) clones the repo and wants to make a small contribution. They need to know: how to install dev deps, how to run the tests, what CI checks they must pass, what the contract is for changes that cross the `admesh-domains` boundary. Today there is no `CONTRIBUTING.md`, no `TESTING.md`, no CI workflow that runs tests (only `publish.yml`), and the `admesh-domains>=0.1.0` dep pin is undocumented.

**Why this priority**: Onboarding friction is the dominant barrier to outside contribution on scientific Python repos. P2 because the project can ship 0.1.0 without it (maintainer-only flow); but contributor flow only gets harder to fix the more the user base grows.

**Independent Test**: A contributor who has never seen this repo clones it on a fresh machine. Following `CONTRIBUTING.md` + `TESTING.md` only (no external help), they get all 310 test functions passing locally, open a trivial PR, and see CI exercise the same suite they ran locally. CI fails the PR if they break a test.

**Acceptance Scenarios**:

1. **Given** a cold clone on a machine with Python 3.10+ pre-installed, **When** the contributor follows `CONTRIBUTING.md`, **Then** they reach a state where `pytest` runs the full standard suite green within 15 minutes wall-clock from `git clone`.
2. **Given** a contributor opens a PR that breaks a test in `tests/`, **When** the GitHub Actions test workflow runs, **Then** the PR is marked failed and the failing test is named in the check output.
3. **Given** the `admesh-domains` package contract is documented in `docs/ADMESH_DOMAINS_CONTRACT.md`, **When** the contributor reads it, **Then** they learn the exact public surface ADMESH consumes from `admesh-domains` and the supported version range.
4. **Given** `pyproject.toml` pins `admesh-domains>=0.1.0,<0.2`, **When** a future `admesh-domains` 0.2.0 ships, **Then** ADMESH 0.1.x installs do not silently accept it.

---

### User Story 4 - API consumer browses the public surface (Priority: P3)

A downstream library author wants to depend on `admesh2D` and needs to know: which symbols are public vs. internal? where do the 13 faithful-port stage modules live vs. the v1 additive layer? where is the API reference for `Mesh`, `Domain`, `triangulate`, the registry loaders, the quad-prep smoother? Today the package is 23 flat modules with `__all__` mixing public surface and stage modules, and there is no rendered API reference site.

**Why this priority**: Discoverability and a clear public/internal split matter most when the library has external consumers. P3 because pre-0.1.0 there are essentially zero external consumers; the project can ship without this and add it pre-1.0. But once 0.1.0 is on PyPI, every reorg becomes a breaking change, so doing it as part of the same spec is the cheapest moment.

**Independent Test**: Visit the rendered docs site (mkdocs-material, GitHub Pages). Land on a public API page that lists exactly the 0.1.0 supported surface: `Mesh`, `Domain`, `triangulate`, `read_fort14`, `write_fort14`, `BoundaryType`, `BoundarySegment`, `Fort14ParseError`, `compose_size_field`, `SizeFieldFn`, `load_domain_from_*`, `mesh_quality`, `right_iso_quality`, `smooth_for_quadrangulation`, `balance_valence_triangles`, `compute_valence`, `get_valence_report`. Internal/stage modules (`distmesh`, `curvature`, `medial_axis`, etc.) are reachable but clearly marked as faithful-port internals subject to numerical-port revision.

**Acceptance Scenarios**:

1. **Given** the reorg-or-not Constitution amendment passes, **When** the package is reorganized into `admesh/` (public) + `admesh/_stages/` (internals) — or kept flat with explicit `__all__` separation if the amendment fails — **Then** `from admesh import triangulate, Mesh, Domain, read_fort14, write_fort14` continues to work without deprecation warnings.
2. **Given** the mkdocs site is built and deployed, **When** the user navigates to the docs URL listed in `pyproject.toml` `[project.urls]`, **Then** they see an index of every public symbol with its docstring, type hints, and at least one runnable example per top-level function.
3. **Given** a faithful-port stage module is imported directly (e.g. `from admesh.curvature import apply_curvature`), **When** the import resolves, **Then** the module's docstring warns that it is an internal stage subject to numerical-port revision per Constitution Article II.1.

### Edge Cases

- **Version mismatch direction**: If `pyproject.toml` and `__init__.py` disagree, which wins? Resolved: `pyproject.toml` is the build-time authority; `__init__.py` MUST mirror it; `pre_tag_check.sh` enforces.
- **Plan staleness threshold**: Spec sets 30 days. The gate is advisory pre-tag, not blocking on every push.
- **CI runs local vs. cloud parity**: Some `tests/test_*.py` files use real coastal fixtures (~10 MB each). Spec puts these behind a `slow` marker; the standard CI lane skips `slow`; a separate lane runs the full suite on a weekly cadence and on `v*` tags.
- **`admesh-domains` version pin update flow**: If the upstream sibling ships a breaking 0.2.0, the ADMESH maintainer bumps the pin after re-running the parity test introduced in FR-016.
- **mkdocs vs. sphinx**: Choice is intentionally mkdocs-material for cost; documented as a non-breaking choice that can be revisited at 1.0.
- **Reorg blast radius**: If the Constitution amendment for reorg fails, US4 reduces to "rendered docs over the existing flat layout" — still shippable, no `_stages/` subdir.
- **#10 escalation**: If #10 proves to require >2 weeks of focused work, this spec permits parking US2 to spec 010 and shipping `0.1.0a1` as a pre-release tag covering US1+US3+US4 only.
- **Windows / macOS CI**: Standard lane runs on `ubuntu-latest` only for cost; macOS and Windows are validated on a weekly cron lane.

## Requirements *(mandatory)*

### Functional Requirements

#### Phase R1 — Tag-gate hygiene

- **FR-001**: `scripts/pre_tag_check.sh` MUST verify that `pyproject.toml` `[project].version` equals `admesh/__init__.py::__version__`, exiting non-zero with both file paths and conflicting values when they differ.
- **FR-002**: `scripts/pre_tag_check.sh` MUST verify that `docs/governance/PROJECT_PLAN.md` contains a `## Where we are today (YYYY-MM-DD` entry whose date is within 30 days of `git log -1 --format=%cI` on HEAD, exiting non-zero with a `PLAN_STALE` message when stale.
- **FR-003**: `docs/governance/PROJECT_PLAN.md` MUST gain a 2026-05-15 (or later) "Where we are today" entry capturing: closure of #11, addition of specs 003–008, daily-issue-fixing workflow adoption, DomI v1.9 sync state, audit issues #59/#60/#61, and an explicit pointer to this spec as the active sub-plan for 0.1.0.
- **FR-004**: A `pytest --cov=admesh --cov-report=json --cov-report=term-missing` run output and a `pytest --durations=10` run output MUST be committed under `output/` and referenced from `TEST-AUDIT.md` (closes backlog items B-04 and B-06).
- **FR-005**: `scripts/pre_tag_check.sh` MUST verify that `output/coverage.json` and `output/durations.txt` exist and were generated within 30 days of HEAD.
- **FR-006**: Reconcile the version strings: `pyproject.toml` and `admesh/__init__.py::__version__` MUST both declare `0.1.0` (or whatever the agreed initial tag) at the moment R4 fires.

#### Phase R2 — CI + onboarding + contract

- **FR-010**: A new `.github/workflows/tests.yml` MUST run the full pytest suite on every push and PR to any branch, on Python 3.10 / 3.11 / 3.12, on `ubuntu-latest`. This closes TEST-AUDIT finding F-CRIT-01.
- **FR-011**: Tests requiring real coastal fixtures or external binaries MUST be marked with a `slow` pytest marker; the standard CI lane skips `slow`; a separate weekly lane (`.github/workflows/tests-slow.yml`) runs the full suite including `slow`.
- **FR-012**: `CONTRIBUTING.md` MUST exist at repo root and cover: dev setup (`pip install -e ".[dev]"`), running tests (`pytest`), the `daily-issue-fixing` branch contract, the DomI sync expectation (`.domi-pin` ledger), and how to file an issue.
- **FR-013**: `TESTING.md` MUST exist (repo root or `docs/`) and cover: pytest invocation patterns, markers (`slow`, `requires_matlab`, `requires_chilmesh`), fixture-data locations, and the parity-tests pattern (port-correctness vs. MATLAB fixtures).
- **FR-014**: `docs/ADMESH_DOMAINS_CONTRACT.md` MUST exist and document: the exact symbols ADMESH imports from `admesh-domains`, the supported version range, the parity-test mechanism, and the upgrade policy when `admesh-domains` ships a minor or major bump.
- **FR-015**: `pyproject.toml` `[project].dependencies` MUST pin `admesh-domains>=0.1.0,<0.2` (or whatever upper bound the contract doc justifies).
- **FR-016**: A new `tests/test_admesh_domains_contract.py` MUST assert that every symbol listed in `docs/ADMESH_DOMAINS_CONTRACT.md` is importable from the pinned `admesh-domains` version and has the documented signature.

#### Phase R3 — Reorg (gated by amendment) + API reference

- **FR-020**: A Constitution amendment proposal MUST be drafted as `specs/009-release-readiness-for-0.1.0/CONSTITUTION-AMENDMENT.md` covering whether to physically reorganize `admesh/` into `admesh/` (public surface) + `admesh/_stages/` (faithful-port internals). The amendment passes only with explicit maintainer sign-off recorded in that file.
- **FR-021**: If the amendment passes, the package MUST be reorganized such that all faithful-port stage modules (`background_grid`, `bathymetry`, `boundary`, `curvature`, `distance`, `distmesh`, `dominate_tide`, `in_polygon`, `inpaint`, `medial_axis`, `mesh_size`, `quality`, `routine`) live under `admesh/_stages/`, with stub re-exports preserving backward compatibility on the old import paths until 1.0.
- **FR-022**: If the amendment fails, `admesh/__init__.py::__all__` MUST be split into clearly commented "public surface" and "faithful-port stage modules (internal)" groups.
- **FR-023**: A `docs/` subdirectory MUST house a mkdocs-material configuration (`mkdocs.yml`) covering: index page, quickstart, public API reference (auto-generated from docstrings via `mkdocstrings`), the porting-notes journal, and the constitution.
- **FR-024**: GitHub Pages MUST serve the rendered docs from the `gh-pages` branch on every push to `daily-issue-fixing` and `main`, via a new `.github/workflows/docs.yml`.
- **FR-025**: Every public-surface symbol (`Mesh`, `Domain`, `triangulate`, `read_fort14`, `write_fort14`, `BoundaryType`, `BoundarySegment`, `Fort14ParseError`, `compose_size_field`, `SizeFieldFn`, `load_domain_from_fort14`, `load_domain_from_json`, `load_domain_from_toml`, `load_domain_from_registry`, `load_domain_with_metadata`, `list_available_domains`, `mesh_quality`, `right_iso_quality`, `smooth_for_quadrangulation`, `balance_valence_triangles`, `compute_valence`, `get_valence_report`, `BalanceConfig`, `BalanceResult`, `ValenceStats`) MUST have a complete docstring with `Parameters`, `Returns`, and at least one runnable example.

#### Phase R4 — Issue #10 resolution + tag

- **FR-030**: Issue #10 (default size-field overshoot on real-world coastal fixtures) MUST close. The fix lives under this spec OR a sibling spec (010) referenced from here.
- **FR-031**: `tests/test_default_size_field.py::test_tier1_wetting_and_drying_round_trip` MUST pass without `xfail` decoration.
- **FR-032**: `tests/test_default_size_field.py::test_tier2_wnat_release_gate` MUST pass without `xfail` decoration and complete within 60 seconds wall-clock on a laptop-class CI runner.
- **FR-033**: The fresh meshes produced for Tier-1 and Tier-2 fixtures MUST satisfy structural validity: every node and centroid has `domain.sdf(point) <= bbox_diag * 1e-2`, and total mesh area covers ≥95% of the source domain area.
- **FR-034**: No regression: every existing Tier-0 polygon-domain test (square, L-shape, U-shape, square-with-hole, doughnut) MUST continue to pass.
- **FR-035**: After R1–R3 complete and FR-031/032/033 are green, the maintainer MUST push the `v0.1.0` git tag, which triggers `.github/workflows/publish.yml` to publish `admesh2D==0.1.0` to PyPI.
- **FR-036**: Post-tag, `pip install admesh2D==0.1.0` in a fresh virtualenv on Python 3.10 / 3.11 / 3.12 MUST install cleanly and `python -c "import admesh; print(admesh.__version__)"` MUST print `0.1.0`.

### Key Entities

- **`pre_tag_check.sh`**: Existing shell script under `scripts/`. Gains version-string, plan-staleness, and audit-artifact checks. The pre-tag invariant gate; non-zero exit blocks the tag workflow.
- **`PROJECT_PLAN.md`**: Existing document under `docs/governance/`. Gains the 2026-05-15 entry plus an explicit "0.1.0 Release-Readiness Sub-Plan" section pointing to this spec.
- **`ADMESH_DOMAINS_CONTRACT.md`**: New document. Defines the import surface, version range, and upgrade policy for the `admesh-domains` sibling.
- **`CONSTITUTION-AMENDMENT.md`** (under this spec): Proposes Article-level guidance on the public/internal split. Pass/fail by maintainer sign-off.
- **`.github/workflows/tests.yml`**: New CI workflow. The standard test gate. Closes F-CRIT-01.
- **`.github/workflows/tests-slow.yml`**: New CI workflow. Weekly + on-tag full-suite lane.
- **`.github/workflows/docs.yml`**: New CI workflow. Builds and publishes mkdocs to GitHub Pages.
- **mkdocs site**: Rendered API reference at `https://domattioli.github.io/ADMESH/` (or equivalent).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `bash scripts/pre_tag_check.sh` exits zero on the `daily-issue-fixing` branch HEAD before the tag is pushed, and a deliberately-introduced version mismatch (test) causes it to exit non-zero.
- **SC-002**: `pip install admesh2D==0.1.0` in a fresh Python 3.10 / 3.11 / 3.12 virtualenv installs cleanly on Linux (and on macOS + Windows when validated by the weekly slow lane).
- **SC-003**: 100% of public-surface symbols (per FR-025) have a docstring containing `Parameters`, `Returns`, and ≥1 runnable example; verified by a `tests/test_docstring_completeness.py`.
- **SC-004**: CI test workflow runs all 310 test functions on every PR; a contributor opening a PR that fails any test sees the failure inline on the GitHub PR check, with median CI wall-clock under 8 minutes on the standard lane.
- **SC-005**: Spec-002 Tier-1 and Tier-2 acceptance tests both pass without `xfail` decoration on the `v0.1.0` tagged commit.
- **SC-006**: A cold contributor (zero prior context) clones the repo and, following only `CONTRIBUTING.md` + `TESTING.md`, gets `pytest` green within 15 minutes wall-clock. Verified by one walkthrough captured under `docs/sessions/`.
- **SC-007**: Issue #10 closes with `state_reason: completed` and references the commit that resolves it.
- **SC-008**: Zero post-release issues filed in the first 30 days that report `pip install admesh2D` failure or quickstart-on-coastal-fixture failure. (Track via a `0.1.0-regression` GitHub issue label.)

## Assumptions

- The ADMESH maintainer (`@domattioli`) retains sole sign-off authority on the Constitution amendment in FR-020.
- `admesh-domains` is currently at 0.1.0 and the project assumes no breaking API change from the sibling during this spec's execution.
- Issue #10's fix fits within this spec's scope; if not, it spins out to spec 010 and US2 (P1) downgrades to a pre-release tag (`0.1.0a1`).
- mkdocs-material is acceptable as the docs framework; sphinx is not a hard requirement and revisiting is allowed at 1.0.
- GitHub Pages / Actions are the deployment substrate; no alternative hosting (ReadTheDocs) is required for 0.1.0.
- The existing single-CI-workflow constraint is acceptable to expand: this spec adds 3 new workflows (`tests.yml`, `tests-slow.yml`, `docs.yml`) on top of the existing `publish.yml`.
- The `daily-issue-fixing` branch remains the integration branch; this spec lives on `009-release-readiness-for-0.1.0` and merges back to `daily-issue-fixing` only after all four phases complete or are explicitly deferred.
- Real coastal fixtures (`wnat_test.14`, `wetting_and_drying_test.14`) remain committed under `tests/fixtures/` and are acceptable as Tier-1/Tier-2 release-gate test data.
- chilmesh integration remains a gated compat smoke test; no runtime dependency on `chilmesh` is introduced by this spec.

## Out of Scope

- Implementing the actual `admesh-segmenter` sibling project (issue #9). Compatibility with `admesh-domains` is in scope; segmenter is post-1.0.
- GPU / multi-core acceleration of the size-field stack (issue #8). Post-1.0.
- The PyPI name claim on `admesh` (issue #13). The project ships as `admesh2D` on PyPI; the bare `admesh` claim can proceed independently on its own timeline.
- Transformer / LSTM research directions (issue #25). Post-1.0.
- Right-isosceles smoothing via dimensional remapping (issue #41). Post-1.0.
- Any quad-conversion or `tri2quad` work. Out of scope per the existing project plan ("ADMESH is a triangulation library; any quadrangulation work happens in a separate project").

## Dependencies and Ordering

Phases must execute approximately in order — R1 unlocks R4 (the gate machinery must exist before the tag is pushed); R2 is independent and can land in parallel with R1 or R4; R3 is independent and can land in parallel with any other phase, but the reorg sub-task (FR-021) must complete before the docs build (FR-023) to avoid stale import paths in the rendered API reference.

A reasonable execution order is: R1 → R2 → R3 → R4. A maintainer-pressed alternative is R1 → R4 (ship as `0.1.0a1` pre-release) → R2 → R3 → `0.1.0` tag.

## Related Issues and Specs

- Closes (or supersedes): TEST-AUDIT finding F-CRIT-01 (no CI test gate).
- Depends on: issue #10 (size-field overshoot) — explicit blocker for FR-031 / FR-032.
- References: spec 002 (default size-field stack, source of the Tier-1 / Tier-2 xfailed tests).
- References: spec 005 (ADCIRC mesh registry, source of the `admesh-domains` coupling).
- Companions: issues #59 (TEST-AUDIT.md, kept open for B-04 / B-06 follow-ups consumed here), #60 / #61 (sibling audits routing to DomI).
- Sub-plan of: `docs/governance/PROJECT_PLAN.md` "0.1.0 Release-Readiness" section.
