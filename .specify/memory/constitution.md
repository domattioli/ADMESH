<!--
SYNC IMPACT REPORT
==================
Version change: TEMPLATE → 1.0.0
Bump rationale: Initial concrete fill of the spec-kit constitution scaffold.
                Distilled from existing repo governance: CONSTITUTION.md
                (7 articles, ratified 2026-04-18, amended 2026-04-21),
                PROJECT_PLAN.md (phase ordering), and CLAUDE.md (operational
                conventions). MAJOR=1 because this is the first non-template
                version of THIS file; the underlying governance it codifies
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

Removed sections: none (all template slots filled or replaced).

Templates requiring updates:
  ⚠ .specify/templates/plan-template.md  — Constitution Check gate is a
     placeholder; should reference Principles I–V by name and add a
     "Faithful-port deviation justification" row when a clean-room
     implementation precedes a faithful-port pass.
  ⚠ .specify/templates/spec-template.md  — should require a "MATLAB source
     reference" field for any spec that ports a stage from
     01_ADMESH_Library/.
  ⚠ .specify/templates/tasks-template.md — task categories should include
     "port" (faithful-port pass) and "fixture" (reference-fixture export)
     alongside the standard test/impl/docs categories.
  ✅ .specify/memory/constitution.md     — this file, just written.

Follow-up TODOs: none. All placeholders filled with concrete values.
-->

# ADMESH Constitution

This constitution governs **how we work** on the ADMESH Python port. It is
the operational complement to two other documents:

- `PROJECT_PLAN.md` — **what** we build (phased roadmap)
- `CLAUDE.md` — **how the code is organized** (operational reference)

This file is read first at every working session. If a rule here conflicts
with `CLAUDE.md` or any other in-repo doc, this file wins.

## Core Principles

### I. Faithful Port Before Optimization

Every algorithm originates from `01_ADMESH_Library/` in
`github.com/domattioli/QuADMesh-MATLAB` at commit
`19b2eb9f078a648daec3fd40d5d4c6e072f467ac`. The first Python pass MUST
mirror the MATLAB algorithm 1:1 — same control flow, same numerical
operations, same edge-case handling. Variable names MAY be Pythonized
(snake_case, drop type sigils); algorithms MUST NOT be redesigned.

Optimization, vectorization rewrites, and API redesigns happen ONLY after
a passing reference test on the faithful port. A clean-room implementation
is permitted as a temporary scaffold to unblock downstream work, but it
MUST be flagged with a `deferred-faithful-port` note in
`docs/PORTING_NOTES.md` and retired before the stage ships in a release.

**Why**: Numerical divergence from MATLAB is a bug until proven otherwise.
Optimizing a clean-room reimplementation tends to bake in subtle behavior
differences (boundary inclusion, tie-breaking, ordering) that are
invisible until a downstream stage consumes the wrong output.

### II. Pure-Python First (No C Extensions)

The first cut of the port MUST NOT introduce C or C++ extensions. The
single MATLAB `.c` file (`MeshSizeIterativeSolver.c`) is ported to NumPy +
Numba, with two implementations co-located in `admesh/mesh_size.py`:

1. `_solve_iter_py(...)` — pure NumPy, readable, the reference.
2. `_solve_iter_nb(...)` — `@njit(cache=True)`, the optimized path.

A test MUST assert agreement between the two paths to `atol=1e-10` on a
fixed input. The public dispatcher selects Numba by default and accepts a
`use_numba=False` kwarg for debugging.

A Cython or C extension MAY be introduced later if profiling on realistic
domains shows the Numba path is more than 2× slower than the original C
baseline. Such a change MUST land in its own PR with a profile excerpt in
the commit message.

MATLAB MEX binaries (`.mexw64`, `.mexmaci64`) are platform-specific builds
of the same C source and MUST be discarded — not committed, not shimmed,
not referenced.

**Why**: The package goal is `pip install`-able without a C toolchain.
Every C dependency multiplies the install-failure surface across
platforms.

### III. Reference-Test Discipline (NON-NEGOTIABLE)

For each stage `admesh/<stage>.py`, `tests/test_<stage>.py` MUST exercise
the function on an input captured from MATLAB and assert numerical
agreement to a documented tolerance. Reference fixtures live under
`tests/fixtures/<stage>/<case>.npz` with named arrays for inputs and
expected outputs.

Default tolerances: `atol=1e-8, rtol=1e-6`. Tighter or looser tolerances
require a one-line justification in the test docstring (typically: the
function's conditioning, or a known MATLAB-side numerical quirk).

Rules:

1. `pytest tests/ -q` MUST pass on `main`. A PR that breaks it is not
   merged.
2. Fixtures are generated once from MATLAB via
   `scripts/export_matlab_fixtures.m` and committed under
   `tests/fixtures/`. They are load-only in Python; regenerate only when
   the MATLAB source commit pin changes.
3. If the port disagrees with the reference fixture, fix the port. Do
   NOT widen the tolerance to make the test pass.
4. End-to-end tests exercise `routine.triangulate()` on the 5 MVP
   synthetic domains (unit square, L-shape, unit disk, annulus, notched
   rectangle) and assert quality gates `min_q ≥ 0.30`, `mean_q ≥ 0.60`.
5. Visual inspection (PNGs under `tests/output/`) is encouraged but
   MUST NOT gate CI.

**Why**: This is a port. The reference is authoritative. Without
fixtures-from-MATLAB, "passing tests" only proves the port is
self-consistent — not that it matches MATLAB.

### IV. Stage-by-Stage Bottom-Up Porting

Ports land bottom-up: leaf utilities first (`in_polygon`, `inpaint`,
`quality`), integrator modules last (`distmesh`, `routine`). Each MATLAB
function maps to one Python function with the same name in snake_case
(`CreateBackgroundGrid.m` → `create_background_grid()`).

Rules:

1. Internal helpers preserve their MATLAB structure. Don't merge or
   refactor them prematurely — that obscures the diff against MATLAB.
2. Every ported function's docstring MUST cite the MATLAB source path
   AND the commit pin (e.g., `01_ADMESH_Library/02_.../File.m @ 19b2eb9`).
   The reader MUST be able to `cd /workspace/QuADMesh-MATLAB` and diff.
3. Preserve algorithmic comments from the MATLAB source where they
   explain *why* (derivation, paper citation, edge-case rationale).
   Drop purely procedural MATLAB comments — well-named Python already
   says WHAT.
4. When the MATLAB uses a toolbox function (`inpolygon`, `delaunay`,
   `fmincon`), substitute the SciPy/Shapely equivalent and note the
   substitution in `docs/PORTING_NOTES.md` with a one-line note on
   behavioral differences (boundary inclusion semantics, tie-breaking,
   ordering).
5. MATLAB 1-based indexing MUST be translated to Python 0-based.
   `x(i:j)` inclusive becomes `x[i-1:j]` (half-open). The port does NOT
   emulate 1-based indexing.

**Why**: Bottom-up porting means every integrator test exercises only
already-validated leaves, so when an integrator test fails, the bug is
in the integrator — not buried two stages down.

### V. Report-and-Advance Session Cadence

Working sessions follow a fixed read order at startup:
`CONSTITUTION.md` → `PROJECT_PLAN.md` → `CLAUDE.md` → the latest
`docs/session_<N-1>_state.md` (if any) → the active
`docs/session_<N>_plan.md`. Skipping the previous-session state file is
how context gets lost at session boundaries; this read order is
load-bearing.

During a session:

1. **Report-and-advance after every milestone.** When a milestone ships,
   report the result and immediately start the next item on the session
   plan. Turns MUST NOT end with "ready to continue" or any soft-ask
   phrasing that reads as a request for confirmation.
2. **Zero `AskUserQuestion` outside destructive or ambiguous actions.**
   Permitted uses: destructive git operations (force push, hard reset on
   dirty trees), architecturally significant PR review replies, or
   genuine ambiguity that no reading of the plan resolves. Banned uses:
   default-pick questions, option lists in prose, visibility/config
   picks, continue-prompts.
3. **Trunk-based commits.** Work on `main`. Feature branches only when a
   change crosses more than 3 commits or genuinely needs review.
4. **Commit messages reference MATLAB source paths when porting**:
   `port: CreateBackgroundGrid.m → admesh/background_grid.py`.
5. **No auto-PR, no auto-merge.** PRs are drafted on explicit user
   request. Creating tracking issues is pre-approved; commenting,
   closing, or merging is not.

**Why**: Session 0 logged four `UNCONFIRMED_PAUSE` interrupts driven by
soft-ask phrasing. The cost of a wrong autonomous step is a single
revert; the cost of a stalled session is the whole session.

## Porting Conventions & Constraints

These are non-negotiable conventions that complement the principles above.

**MATLAB → Python conventions** (full table in `CLAUDE.md`):

| MATLAB                                  | Python                                           |
|-----------------------------------------|--------------------------------------------------|
| `inpolygon(xq, yq, xv, yv)`             | `admesh.in_polygon.in_polygon(...)` (our port)   |
| `delaunay(x, y)`                        | `scipy.spatial.Delaunay(...).simplices`          |
| `griddata`                              | `scipy.interpolate.griddata`                     |
| `bwdist`                                | `scipy.ndimage.distance_transform_edt`           |
| `struct`                                | `dataclasses.dataclass` or dict (per-module)     |
| cell array of varying-length vectors    | `list[np.ndarray]`                               |

**Indexing**: MATLAB column-major semantics matter ONLY at I/O boundaries
(loading `.mat` files, matching MATLAB `reshape` order). Internal arrays
are row-major NumPy.

**Dependencies**: A new third-party package (scipy submodule, shapely,
meshpy, etc.) goes in `pyproject.toml` with a one-line rationale in the
commit message. No silent additions.

**Module naming**: Flat names (`admesh/distance.py`) instead of MATLAB's
numeric-prefix convention (`01_ADMESH_Routine`). Numbered directories are
a MATLAB-path artifact; Python uses imports.

**Substitutions log**: Every non-obvious MATLAB → Python substitution gets
a one-line entry in `docs/PORTING_NOTES.md` describing the behavioral
difference. This is load-bearing for downstream stages.

## Development Workflow & Quality Gates

**Definition of done for a stage port**:

1. Faithful Python port of every MATLAB function in the stage.
2. Docstrings cite MATLAB source paths + commit pin.
3. Reference fixture(s) under `tests/fixtures/<stage>/`.
4. `tests/test_<stage>.py` asserts numerical agreement to documented
   tolerance.
5. `docs/PORTING_NOTES.md` has an entry for any non-trivial substitution.
6. Quality gates met (where the stage produces a mesh): `min_q ≥ 0.30`,
   `mean_q ≥ 0.60` on the affected MVP domain(s).
7. `pytest tests/ -q` green on `main`.

**Release gates** (for tagged versions on PyPI / GitHub Releases):

- All MVP domains pass quality gates.
- A fresh-venv install of the built wheel imports cleanly and runs the
  smoke triangulation case (UNIT_DISK or equivalent) without error.
- The version bump follows the project's semver:
  - **MAJOR**: backward-incompatible API change in `admesh.*` public
    surface.
  - **MINOR**: new stage, new public function, new optional dependency.
  - **PATCH**: bug fix, doc update, fixture refresh, internal refactor
    that preserves behavior.

**Out-of-scope (explicitly deferred)**:

- Quad conversion (`tri2quad.m`, `distquadmesh2d.m`). ADMESH is a
  triangulation library; quadrangulation is a separate project.
- GUI / visualization beyond the `Mesh.plot()` matplotlib helper
  and test-output PNGs.

## Governance

This constitution supersedes all other in-repo working-style guidance. If
`CLAUDE.md`, a session plan, or any doc contradicts a principle here,
this file wins until amended.

**Amendment procedure**:

1. A proposed amendment is drafted as a PR that edits this file AND
   appends an entry to the Amendments log below.
2. The PR description MUST state the version bump and its rationale per
   the policy below.
3. The PR MUST include a Sync Impact Report (HTML comment at the top of
   this file) listing every dependent template/doc that needs follow-up
   updates.
4. Any template marked `⚠ pending` in the Sync Impact Report MUST be
   resolved (updated or explicitly deferred with a TODO) before the next
   release tag.

**Versioning policy** for this constitution:

- **MAJOR**: backward-incompatible governance change (principle removed,
  redefined, or its scope materially narrowed).
- **MINOR**: new principle/section added, or guidance materially
  expanded.
- **PATCH**: clarifications, wording, typo fixes, non-semantic
  refinements.

When the version bump type is ambiguous, the proposer MUST state their
reasoning in the PR description before finalizing.

**Compliance review**: Every PR that ports a stage MUST verify the
"Definition of done for a stage port" checklist above. Every PR that
adds a non-port feature MUST be justified against the principles —
Principle I (faithful port first) is the default null hypothesis, and
deviations need an explicit rationale.

**Runtime guidance**: For day-to-day operational details (commands,
file layout, MATLAB→Python substitution table) see `CLAUDE.md`. For the
phased roadmap and current state, see `PROJECT_PLAN.md`.

## Amendments log

### 2026-04-25 — v1.0.1 — fort.14 I/O lifted off the deferred list; viz scope narrowed

Spec `001-pythonize-and-fort14-integration` ships ADCIRC v55 fort.14
read/write (`admesh/fort14.py`) and a lazy-imported matplotlib helper
(`admesh.viz.plot_mesh` via `Mesh.plot()`). Both were on the
"explicitly deferred" list at v1.0.0.

Changes (PATCH — clarifications, no governance change):

- Remove the `ADCIRC .fort.14 I/O` bullet from Out-of-scope. The I/O
  surface is implemented as `admesh.fort14.{read_fort14,write_fort14,
  Fort14ParseError}` plus the `Mesh.to_fort14(path)` method, with all
  1-based↔0-based and elevation↔depth conversion confined to that
  module.
- Reword the visualization line from `GUI / visualization beyond
  test-output PNGs` to `GUI / visualization beyond the Mesh.plot()
  matplotlib helper and test-output PNGs`. The helper is opt-in via
  the `[viz]` extra and lazy-imports matplotlib so headless
  environments are unaffected.

Constitution Principle I unchanged — the new modules are strictly
additive over the 13 faithful-port stage modules; the 142-test
faithful-port baseline still passes verbatim.

### 2026-04-24 — v1.0.0 — Spec-kit constitution scaffold filled

Concrete fill of the `.specify/memory/constitution.md` template using
content distilled from `CONSTITUTION.md` (the existing top-level governance
doc, ratified 2026-04-18 and amended 2026-04-21 to add Article VII),
`PROJECT_PLAN.md`, and `CLAUDE.md`. No governance change in substance — this
is the spec-kit-managed mirror of the rules already in force.

**Version**: 1.0.1 | **Ratified**: 2026-04-18 | **Last Amended**: 2026-04-25
