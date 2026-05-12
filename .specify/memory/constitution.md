<!--
SYNC IMPACT REPORT
==================
Version change: TEMPLATE → 1.0.0
Bump rationale: Initial concrete fill of spec-kit constitution scaffold.
                Distilled from existing repo governance: CONSTITUTION.md
                (7 articles, ratified 2026-04-18, amended 2026-04-21),
                PROJECT_PLAN.md (phase ordering), and CLAUDE.md (operational
                conventions). MAJOR=1 because this is the first non-template
                version of THIS file; underlying governance it codifies
                has been in force since 2026-04-18.

Modified principles (template → concrete):
  [PRINCIPLE_1_NAME]               → I. Faithful Port Before Optimization
  [PRINCIPLE_2_NAME]               → II. Pure-Python First (No C Extensions)
  [PRINCIPLE_3_NAME]               → III. Reference-Test Discipline (NON-NEGOTIABLE)
  [PRINCIPLE_4_NAME]               → IV. Stage-by-Stage Bottom-Up Porting
  [PRINCIPLE_5_NAME]               → V. Report-and-Advance Session Cadence

Added sections:
  - Porting Conventions & Constraints (replaces [SECTION_2_NAME])
  - Development Workflow & Quality Gates (replaces [SECTION_3_NAME])

Templates requiring updates:
  ⚠ .specify/templates/plan-template.md  — Constitution Check gate is a
     placeholder; should reference Principles I–V by name and add a
     "Faithful-port deviation justification" row when clean-room
     implementation precedes faithful-port pass.
  ⚠ .specify/templates/spec-template.md  — should require "MATLAB source
     reference" field for any spec that ports a stage from
     01_ADMESH_Library/.
  ⚠ .specify/templates/tasks-template.md — task categories should include
     "port" (faithful-port pass) and "fixture" (reference-fixture export)
     alongside standard test/impl/docs categories.
  ✅ .specify/memory/constitution.md     — this file, just written.

Follow-up TODOs: none. All placeholders filled with concrete values.
-->

# ADMESH Constitution

Governs **how we work** on the ADMESH Python port. Operational complement to:

- `PROJECT_PLAN.md` — **what** we build (phased roadmap)
- `CLAUDE.md` — **how the code is organized** (operational reference)

Read first at every working session. If rule here conflicts with `CLAUDE.md` or any other in-repo doc, this file wins until amended.

## Core Principles

### I. Faithful Port Before Optimization

Every algorithm originates from `01_ADMESH_Library/` in `github.com/domattioli/QuADMesh-MATLAB` at commit `19b2eb9f078a648daec3fd40d5d4c6e072f467ac`. First Python pass MUST mirror MATLAB algorithm 1:1 — same control flow, same numerical operations, same edge-case handling. Variable names MAY be Pythonized; algorithms MUST NOT be redesigned.

Optimization, vectorization rewrites, API redesigns happen ONLY after passing reference test on faithful port. Clean-room implementation permitted as temporary scaffold to unblock downstream work, but MUST be flagged with `deferred-faithful-port` note in `docs/PORTING_NOTES.md` and retired before stage ships in a release.

**Why**: Numerical divergence from MATLAB is a bug until proven otherwise. Optimizing clean-room reimplementation tends to bake in subtle behavior differences invisible until downstream stage consumes wrong output.

### II. Pure-Python First (No C Extensions)

First cut MUST NOT introduce C or C++ extensions. Single MATLAB `.c` file (`MeshSizeIterativeSolver.c`) ported to NumPy + Numba, with two implementations co-located in `admesh/mesh_size.py`:

1. `_solve_iter_py(...)` — pure NumPy, readable, the reference.
2. `_solve_iter_nb(...)` — `@njit(cache=True)`, the optimized path.

Test MUST assert agreement between two paths to `atol=1e-10` on fixed input. Public dispatcher selects Numba by default and accepts `use_numba=False` kwarg for debugging.

Cython or C extension MAY be introduced later if profiling on realistic domains shows Numba path is more than 2× slower than original C baseline. Such change MUST land in its own PR with profile excerpt in commit message.

MATLAB MEX binaries (`.mexw64`, `.mexmaci64`) MUST be discarded — not committed, not shimmed, not referenced.

**Why**: Package goal is `pip install`-able without C toolchain. Every C dependency multiplies install-failure surface across platforms.

### III. Reference-Test Discipline (NON-NEGOTIABLE)

For each stage `admesh/<stage>.py`, `tests/test_<stage>.py` MUST exercise function on MATLAB-captured input and assert numerical agreement to documented tolerance. Reference fixtures under `tests/fixtures/<stage>/<case>.npz` with named arrays for inputs and expected outputs.

Default tolerances: `atol=1e-8, rtol=1e-6`. Tighter or looser tolerances require one-line justification in test docstring.

Rules:

1. `pytest tests/ -q` MUST pass on `main`. PR that breaks it is not merged.
2. Fixtures generated once from MATLAB via `scripts/export_matlab_fixtures.m` and committed. Load-only in Python; regenerate only when MATLAB source commit pin changes.
3. If port disagrees with reference fixture, fix the port. Do NOT widen tolerance to make test pass.
4. End-to-end tests exercise `routine.triangulate()` on 5 MVP synthetic domains and assert quality gates `min_q ≥ 0.30`, `mean_q ≥ 0.60`.
5. Visual inspection (PNGs under `output/`) encouraged but MUST NOT gate CI.

**Why**: This is a port. Reference is authoritative. Without fixtures-from-MATLAB, "passing tests" only proves self-consistency, not MATLAB agreement.

### IV. Stage-by-Stage Bottom-Up Porting

Ports land bottom-up: leaf utilities first (`in_polygon`, `inpaint`, `quality`), integrator modules last (`distmesh`, `routine`). Each MATLAB function maps to one Python function with same name in snake_case.

Rules:

1. Internal helpers preserve their MATLAB structure. Don't merge or refactor prematurely — obscures diff against MATLAB.
2. Every ported function's docstring MUST cite MATLAB source path AND commit pin. Reader MUST be able to `cd /workspace/QuADMesh-MATLAB` and diff.
3. Preserve algorithmic comments from MATLAB source where they explain *why*. Drop purely procedural MATLAB comments.
4. When MATLAB uses toolbox function, substitute SciPy/Shapely equivalent and note substitution in `docs/PORTING_NOTES.md` with one-line note on behavioral differences.
5. MATLAB 1-based indexing MUST be translated to Python 0-based. `x(i:j)` inclusive becomes `x[i-1:j]`. Port does NOT emulate 1-based indexing.

**Why**: Bottom-up porting means every integrator test exercises only already-validated leaves, so when integrator test fails, bug is in the integrator — not buried two stages down.

### V. Report-and-Advance Session Cadence

Working sessions follow fixed read order at startup: `CONSTITUTION.md` → `PROJECT_PLAN.md` → `CLAUDE.md` → latest `docs/sessions/session_<N-1>_state.md` (if any) → active `docs/sessions/session_<N>_plan.md`. Skipping previous-session state file is how context gets lost at session boundaries; this read order is load-bearing.

During a session:

1. **Report-and-advance after every milestone.** When milestone ships, report result and immediately start next item. Turns MUST NOT end with "ready to continue" or soft-ask phrasing.
2. **Zero `AskUserQuestion` outside destructive or ambiguous actions.** Permitted: destructive git operations, architecturally significant PR review replies, genuine ambiguity no reading of plan resolves. Banned: default-pick questions, option lists in prose, visibility/config picks, continue-prompts.
3. **Trunk-based commits.** Work on `main`. Feature branches only when change crosses more than 3 commits or genuinely needs review.
4. **Commit messages reference MATLAB source paths when porting**: `port: CreateBackgroundGrid.m → admesh/background_grid.py`.
5. **No auto-PR, no auto-merge.** PRs drafted on explicit user request. Creating tracking issues is pre-approved; commenting, closing, or merging is not.

**Why**: Session 0 logged four `UNCONFIRMED_PAUSE` interrupts driven by soft-ask phrasing. Cost of wrong autonomous step is single revert; cost of stalled session is whole session.

## Porting Conventions & Constraints

**MATLAB → Python conventions** (full table in `CLAUDE.md`):

| MATLAB | Python |
|--------|--------|
| `inpolygon(xq, yq, xv, yv)` | `admesh.in_polygon.in_polygon(...)` (our port) |
| `delaunay(x, y)` | `scipy.spatial.Delaunay(...).simplices` |
| `griddata` | `scipy.interpolate.griddata` |
| `bwdist` | `scipy.ndimage.distance_transform_edt` |
| `struct` | `dataclasses.dataclass` or dict (per-module) |
| cell array of varying-length vectors | `list[np.ndarray]` |

**Indexing**: MATLAB column-major semantics matter ONLY at I/O boundaries. Internal arrays are row-major NumPy.

**Dependencies**: New third-party package goes in `pyproject.toml` with one-line rationale in commit message. No silent additions.

**Module naming**: Flat names (`admesh/distance.py`) instead of MATLAB's numeric-prefix convention.

**Substitutions log**: Every non-obvious MATLAB → Python substitution gets one-line entry in `docs/PORTING_NOTES.md` describing behavioral difference.

## Development Workflow & Quality Gates

**Definition of done for a stage port**:

1. Faithful Python port of every MATLAB function in the stage.
2. Docstrings cite MATLAB source paths + commit pin.
3. Reference fixture(s) under `tests/fixtures/<stage>/`.
4. `tests/test_<stage>.py` asserts numerical agreement to documented tolerance.
5. `docs/PORTING_NOTES.md` has entry for any non-trivial substitution.
6. Quality gates met (where stage produces mesh): `min_q ≥ 0.30`, `mean_q ≥ 0.60` on affected MVP domain(s).
7. `pytest tests/ -q` green on `main`.

**Release gates** (for tagged versions on PyPI / GitHub Releases):

- All MVP domains pass quality gates.
- Fresh-venv install of built wheel imports cleanly and runs smoke triangulation case.
- Version bump follows semver:
  - **MAJOR**: backward-incompatible API change in `admesh.*` public surface.
  - **MINOR**: new stage, new public function, new optional dependency.
  - **PATCH**: bug fix, doc update, fixture refresh, internal refactor preserving behavior.

**Out-of-scope (explicitly deferred)**:
- Quad conversion (`tri2quad.m`, `distquadmesh2d.m`). ADMESH is triangulation library.
- GUI / visualization beyond `Mesh.plot()` matplotlib helper and test-output PNGs.

## Governance

Constitution supersedes all other in-repo working-style guidance. `CLAUDE.md`, session plan, or any doc contradicting a principle here loses until amended.

**Amendment procedure**:

1. Proposed amendment drafted as PR editing this file AND appending entry to Amendments log.
2. PR description MUST state version bump and rationale.
3. PR MUST include Sync Impact Report (HTML comment at top) listing every dependent template/doc needing follow-up.
4. Any template marked `⚠ pending` in Sync Impact Report MUST be resolved before next release tag.

**Versioning policy**:
- **MAJOR**: backward-incompatible governance change (principle removed, redefined, or scope materially narrowed).
- **MINOR**: new principle/section added, or guidance materially expanded.
- **PATCH**: clarifications, wording, typo fixes, non-semantic refinements.

**Compliance review**: Every PR porting a stage MUST verify "Definition of done" checklist. Every PR adding non-port feature MUST be justified against principles — Principle I is default null hypothesis.

## Amendments log

### 2026-04-25 — v1.0.2 — default size-field stack as precondition for fort.14-contract release readiness

Spec `002-size-field-defaults` wires existing MATLAB-faithful size-field stages as default Phase-1 source for `admesh.triangulate(domain)` when neither `size_field=` nor `user_contribs=` supplied. v1.0.1 amendment lifted fort.14 I/O off deferred list; v1.0.2 acknowledges fort.14 contract is release-ready only when default mesher produces feature-aware meshes on real ADCIRC fixtures.

Changes (PATCH — clarifications, no governance change):
- Document `admesh.triangulate(domain)` with no size-field arguments is now feature-aware (curvature + medial-axis always-on; bathymetry + tide opt-in via `Domain` fields).
- Document fort.14 reader/writer supports paired-edge BC records (IBTYPE 3 / 4 / 13 / 24 / 25) with column-agnostic `barrier_data`.
- Tier-2 / WNAT structural-validity gate for 0.1.0 tag tracked as issue #10.

### 2026-04-25 — v1.0.1 — fort.14 I/O lifted off deferred list; viz scope narrowed

Spec `001-pythonize-and-fort14-integration` ships ADCIRC v55 fort.14 read/write and lazy-imported matplotlib helper. Both were on "explicitly deferred" list at v1.0.0.

Changes (PATCH — clarifications, no governance change):
- Remove `ADCIRC .fort.14 I/O` from Out-of-scope.
- Reword visualization line to `GUI / visualization beyond the Mesh.plot() matplotlib helper and test-output PNGs`.

### 2026-04-24 — v1.0.0 — Spec-kit constitution scaffold filled

Concrete fill of `.specify/memory/constitution.md` template using content distilled from `CONSTITUTION.md` (ratified 2026-04-18, amended 2026-04-21), `PROJECT_PLAN.md`, and `CLAUDE.md`. No governance change in substance — spec-kit-managed mirror of rules already in force.

**Version**: 1.0.2 | **Ratified**: 2026-04-18 | **Last Amended**: 2026-04-25
