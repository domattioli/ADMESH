# ADMESH Constitution

Governs **how we work** on the ADMESH Python port. Companion docs:
- `PROJECT_PLAN.md` — **what** we build (phased roadmap)
- `CLAUDE.md` — **how the code is organized** (operational reference)

This document is read first at every session. If a rule here conflicts
with `CLAUDE.md`, this wins.

---

## Article I — Identity & north star

**ADMESH** = Advanced Meshing (Python). A faithful port of the MATLAB
`01_ADMESH_Library` module from QuADMesh-MATLAB.

**North star**: a Python package that reproduces the MATLAB ADMESH
pipeline output bit-for-bit (within floating-point tolerance) on the
reference test cases, is `pip install`-able without a C toolchain, and
serves as a drop-in algorithmic backend for downstream meshing work.

**Source of truth**: `github.com/domattioli/QuADMesh-MATLAB`,
commit `19b2eb9f078a648daec3fd40d5d4c6e072f467ac`, path
`01_ADMESH_Library/`. Locally cloned to `/workspace/QuADMesh-MATLAB`.

---

## Article II — Hard rules

1. **Port faithfully before optimizing.** First pass mirrors the MATLAB
   algorithm 1:1 (variable names may Pythonize; algorithm does not).
   Optimization, vectorization rewrites, and API redesigns come AFTER
   a passing reference test.
2. **No C/C++ extensions in the first cut.** The single `.c` file
   (`MeshSizeIterativeSolver.c`) is ported to NumPy + Numba. If profiling
   later shows Numba underperforms by > 2× on realistic domains, a
   Cython/C extension is allowed — with a PR note explaining why.
3. **MATLAB 1-based indexing is translated, not preserved.** Python is
   0-based. Any index-arithmetic in the MATLAB source is adjusted; the
   port does NOT emulate 1-based indexing.
4. **MATLAB column-major semantics only matter at I/O boundaries.**
   Internal arrays are row-major NumPy. Loading reference `.mat` files
   or matching MATLAB's `reshape` order is an explicit boundary concern.
5. **Every stage ships with a reference test.** For each `admesh/<stage>.py`,
   `tests/test_<stage>.py` exercises the function on an input captured
   from the MATLAB side (stored under `tests/fixtures/<stage>/`) and
   asserts numerical agreement to a documented tolerance.
6. **`pytest tests/ -q` must pass on `main`.** A PR that breaks it is
   not merged.
7. **No third-party meshing dependency is added silently.** If a module
   needs `scipy.spatial`, `shapely`, `meshpy`, etc., it goes in
   `pyproject.toml` with a one-line rationale in the commit message.
8. **MATLAB mex binaries (`.mexw64`, `.mexmaci64`) are discarded.** They
   are platform-specific builds of `MeshSizeIterativeSolver.c`; the Python
   port replaces them entirely.

---

## Article III — Malleable choices (open for redirect)

- **Module naming** — flat names (`admesh/distance.py`) instead of
  numeric prefixes (`01_ADMESH_Routine`). Numbered dirs are a MATLAB
  path convention; Python uses imports.
- **Numerical tolerance defaults** — `atol=1e-8, rtol=1e-6` for
  reference-test agreement. Tighten or loosen per stage as the port
  reveals each function's conditioning.
- **Reference fixture format** — `.npz` with named arrays, one file per
  stage/test-case. If this gets unwieldy we can switch to HDF5.
- **Public API surface** — TBD until Phase 3. Phase 1/2 expose every
  stage function; Phase 3 distills the user-facing entry points.

---

## Article IV — Porting discipline

1. **One MATLAB function → one Python function, same name in
   snake_case.** `CreateBackgroundGrid.m` → `create_background_grid()`.
   Internal helpers keep their structure; don't merge them prematurely.
2. **Docstring cites the MATLAB source path + commit.** The reader
   should be able to `cd /workspace/QuADMesh-MATLAB` and diff.
3. **Preserve algorithmic comments from the MATLAB source** where they
   explain *why* (derivation, paper citation, edge-case rationale).
   Drop purely procedural MATLAB comments (those describe WHAT; the
   Python already does).
4. **Ports land stage-by-stage**, bottom-up. Leaf utilities
   (`in_polygon`, `inpaint`, `quality`) first; integrator modules
   (`distmesh`, `routine`) last. See `PROJECT_PLAN.md` phase ordering.
5. **If the MATLAB uses a toolbox function** (e.g. `inpolygon`,
   `delaunay`, `fmincon`), replace with the SciPy / Shapely equivalent
   and note the substitution in a `# port:` comment with the behavior
   differences (e.g. boundary inclusion semantics).
6. **Numerical divergence from MATLAB is a bug until proven otherwise.**
   If the port disagrees with the reference fixture, fix the port —
   don't widen the tolerance to make the test pass.

---

## Article V — Testing & validation

1. **Unit tests** live in `tests/test_<stage>.py` and run on every push.
2. **Reference fixtures** are generated once from MATLAB (see
   `scripts/export_matlab_fixtures.m` — TBD Phase 1) and committed
   under `tests/fixtures/`. They are load-only in Python; regenerate
   only when the MATLAB source commit pin changes.
3. **End-to-end tests** exercise the full `routine.adm_esh_routine()`
   entry point on small synthetic domains (unit square, L-shape,
   annulus) and compare the final mesh (vertices + connectivity) to
   MATLAB output.
4. **Visual inspection is encouraged but not required.** A test
   producing a PNG under `output/` is fine; don't gate CI on it.

---

## Article VI — Commit & workflow

1. **Trunk-based.** Work on `main`. Feature branches only if a change
   crosses > 3 commits or needs review.
2. **Commit messages reference MATLAB source paths** when porting:
   `port: CreateBackgroundGrid.m → admesh/background_grid.py`.
3. **No auto-PR, no auto-merge.** Claude drafts PRs on request only.
4. **GitHub posting on the user's behalf requires explicit instruction.**
   Creating issues for tracking is pre-approved; commenting / closing /
   merging is not.
5. **Feature branches are speckit-driven only.** A new feature branch
   is created exclusively as part of the `/speckit-specify` workflow
   (which delegates to the `before_specify` git hook). Claude does NOT
   create branches manually, does NOT create branches from session-system
   prompts (e.g. `claude/<...>-<random>`), and does NOT create
   per-task branches for one-off edits. Direct work on `main` is the
   default; if a change merits isolation, it goes through speckit.
6. **Speckit naming is the only branch convention.** All feature
   branches follow the speckit pattern: `NNN-<short-name>` (sequential)
   or `YYYYMMDD-HHMMSS-<short-name>` (timestamp), per
   `.specify/init-options.json`. The `claude/<feature>-<hash>` pattern
   that some session-init systems suggest is NOT adopted. If the
   session-system creates such a branch automatically, treat it as
   redundant scaffolding to be ignored or consolidated under the
   speckit branch.
7. **Scan before creating.** Before invoking `/speckit-specify` or
   any branch-creation operation, run `git branch -a` and check both
   local and remote branches for an existing branch matching the
   feature's intent (by short-name, topic keywords, or related issue
   number). If a matching branch exists, REUSE it rather than create
   a redundant one — switch to it and continue work, or, if it has
   diverged, ask the user whether to merge/rebase rather than
   silently creating a parallel branch.
8. **Consolidate redundant branches when discovered.** If multiple
   branches address the same feature (e.g. session-system branch +
   speckit branch), confirm with the user once, then delete the
   redundant ones (local + remote) and keep only the speckit-named
   branch. Update any open PRs to point at the canonical branch.

---

## Article VII — Persistent-session cadence

Operational rules for Claude sessions to prevent the pause-for-ack
pattern observed in session 0 (four `UNCONFIRMED_PAUSE` interrupts).

1. **Report-and-advance after every milestone.** When a milestone
   ships, report the result and immediately start the next item on
   the session plan. Do not end a turn with "ready to continue" or
   any soft-ask phrasing that reads as a request for confirmation.
2. **Zero `AskUserQuestion` outside destructive or ambiguous
   actions.** Permitted uses: destructive git operations (force
   push, hard reset on dirty trees), architecturally significant PR
   review replies, or genuine ambiguity that no reading of the plan
   resolves. Banned uses: default-pick questions, option lists in
   prose, visibility / config picks, continue-prompts.
3. **Session-start read order is fixed.** At every session start
   read in order: `CONSTITUTION.md` → `PROJECT_PLAN.md` →
   `CLAUDE.md` → the latest `docs/sessions/session_<N-1>_state.md`
   (if any) → the active `docs/sessions/session_<N>_plan.md`. This
   is load-bearing; skipping the previous-session state file is how
   context gets lost at session boundaries.

---

## Article VIII — External upstream (DomI)

[`domattioli/DomI`](https://github.com/domattioli/DomI) is the upstream
skill and policy provider for this repo.

1. **`.domi-pin` must be committed and current.** It records the upstream
   commit SHA and MANIFEST.md sha256 the repo is synced against.
2. **Session start auto-checks drift.** `scripts/instructions_on_start.sh`
   invokes the `sync-from-domi` drift check; the session HARD STOPs if
   the pin is behind `domattioli/DomI@main` or the manifest hash forks.
3. **DomI-provided skills take precedence over inline implementations.**
   When DomI ships a skill (e.g. `github-release`, `pypi-publish`), this
   repo consumes it via `sync-from-domi` rather than maintaining a local
   copy. Local re-implementations of upstream-owned skills are forbidden.
4. **Orthogonal to Article II Principle I.** This article governs the
   skill / policy layer only. The faithful-port hard rule on the 13
   locked stage modules under `admesh/` is unaffected — DomI sync never
   licenses a stage-module change, and faithful-port work never excuses
   skipping a DomI sync.

---

## Amendments log

### 2026-05-08 — Article VIII adopted (DomI external upstream)

Adopted the DomI sync contract: `.domi-pin` ledger, session-start drift
check via `sync-from-domi`, and upstream precedence for shared skills
(`github-release`, `pypi-publish`). Explicitly orthogonal to Principle I
(faithful port) so the two governance layers cannot be confused. Session
reference: PR #52 (`claude/setup-domi-plugins-tGWnU`).

### 2026-04-25 — Article VI rules 5–8 adopted (branch governance)

Tightened Article VI with four new rules (5–8) on branch lifecycle:
speckit is the ONLY path to a feature branch; speckit naming
(`NNN-<short-name>`) is the ONLY accepted convention; existing
branches must be scanned before creation; redundant branches must
be consolidated. Adopted after observing that session-system
auto-created branches (`claude/<feature>-<hash>`) coexisted with
speckit branches for the same feature, creating ambiguity about
the canonical development line. Session reference: ADMESH session
on `005-adcirc-mesh-registry`.

### 2026-04-21 — Article VII adopted

Added Article VII — Persistent-session cadence. Codifies the
report-and-advance discipline learned from session 0's four
`UNCONFIRMED_PAUSE` interrupts (see `docs/persistence_journal.md`
and `docs/sessions/session_0_report.md` § "Persistence retro"). Session
reference: ADMESH session 1.

### 2026-04-18 — Constitution adopted

Initial ratification. ADMESH is a new private repo (`domattioli/ADMESH`)
porting QuADMesh-MATLAB `01_ADMESH_Library` @ `19b2eb9` to Python.
Structure adapted from the MADMESHR constitution (RL-research-heavy)
down to a port-focused rule set. Session reference: ADMESH session 0.
