# ADMESH Constitution

Governs **how we work** on the ADMESH Python port. Companion docs:
- `PROJECT_PLAN.md` — **what** we build (phased roadmap)
- `CLAUDE.md` — **how the code is organized** (operational reference)

Read first at every session. If rule here conflicts with `CLAUDE.md`, this wins.

---

## Article I — Identity & north star

**ADMESH** = Advanced Meshing (Python). Faithful port of MATLAB `01_ADMESH_Library` from QuADMesh-MATLAB.

**North star**: Python package reproducing MATLAB ADMESH pipeline output bit-for-bit (within floating-point tolerance), `pip install`-able without C toolchain, drop-in algorithmic backend for downstream meshing.

**Source of truth**: `github.com/domattioli/QuADMesh-MATLAB`, commit `19b2eb9f078a648daec3fd40d5d4c6e072f467ac`, path `01_ADMESH_Library/`. Locally cloned to `/workspace/QuADMesh-MATLAB`.

---

## Article II — Hard rules

1. **Port faithfully before optimizing.** First pass mirrors MATLAB algorithm 1:1 (variable names may Pythonize; algorithm does not). Optimization, vectorization rewrites, API redesigns come AFTER passing reference test.
2. **No C/C++ extensions in first cut.** Single `.c` file (`MeshSizeIterativeSolver.c`) ported to NumPy + Numba. If profiling shows Numba underperforms by > 2× on realistic domains, Cython/C extension allowed — with PR note explaining why.
3. **MATLAB 1-based indexing is translated, not preserved.** Python is 0-based. Index-arithmetic in MATLAB source is adjusted; port does NOT emulate 1-based indexing.
4. **MATLAB column-major semantics only matter at I/O boundaries.** Internal arrays are row-major NumPy. Loading reference `.mat` files or matching MATLAB's `reshape` order is an explicit boundary concern.
5. **Every stage ships with reference test.** For each `admesh/<stage>.py`, `tests/test_<stage>.py` exercises function on MATLAB-captured input (under `tests/fixtures/<stage>/`) and asserts numerical agreement to documented tolerance.
6. **`pytest tests/ -q` must pass on `main`.** PR that breaks it is not merged.
7. **No third-party meshing dependency added silently.** If module needs `scipy.spatial`, `shapely`, `meshpy`, etc., it goes in `pyproject.toml` with one-line rationale in commit message.
8. **MATLAB mex binaries (`.mexw64`, `.mexmaci64`) are discarded.** Platform-specific builds of `MeshSizeIterativeSolver.c`; Python port replaces them entirely.

---

## Article III — Malleable choices (open for redirect)

- **Module naming** — flat names (`admesh/distance.py`) instead of numeric prefixes (`01_ADMESH_Routine`). Numbered dirs are MATLAB path convention; Python uses imports.
- **Numerical tolerance defaults** — `atol=1e-8, rtol=1e-6` for reference-test agreement. Tighten or loosen per stage as port reveals each function's conditioning.
- **Reference fixture format** — `.npz` with named arrays, one file per stage/test-case. If unwieldy, can switch to HDF5.
- **Public API surface** — TBD until Phase 3. Phase 1/2 expose every stage function; Phase 3 distills user-facing entry points.

---

## Article IV — Porting discipline

1. **One MATLAB function → one Python function, same name in snake_case.** `CreateBackgroundGrid.m` → `create_background_grid()`. Internal helpers keep their structure; don't merge prematurely.
2. **Docstring cites MATLAB source path + commit.** Reader should be able to `cd /workspace/QuADMesh-MATLAB` and diff.
3. **Preserve algorithmic comments from MATLAB source** where they explain *why* (derivation, paper citation, edge-case rationale). Drop purely procedural MATLAB comments.
4. **Ports land stage-by-stage**, bottom-up. Leaf utilities (`in_polygon`, `inpaint`, `quality`) first; integrator modules (`distmesh`, `routine`) last. See `PROJECT_PLAN.md` phase ordering.
5. **If MATLAB uses toolbox function** (e.g. `inpolygon`, `delaunay`, `fmincon`), replace with SciPy/Shapely equivalent and note substitution in `# port:` comment with behavior differences.
6. **Numerical divergence from MATLAB is a bug until proven otherwise.** If port disagrees with reference fixture, fix the port — don't widen tolerance to make test pass.

---

## Article V — Testing & validation

1. **Unit tests** in `tests/test_<stage>.py`, run on every push.
2. **Reference fixtures** generated once from MATLAB (`scripts/export_matlab_fixtures.m`) and committed under `tests/fixtures/`. Load-only in Python; regenerate only when MATLAB source commit pin changes.
3. **End-to-end tests** exercise full `routine.adm_esh_routine()` on small synthetic domains (unit square, L-shape, annulus) and compare final mesh to MATLAB output.
4. **Visual inspection encouraged but not required.** Test producing PNG under `output/` is fine; don't gate CI on it.

---

## Article VI — Commit & workflow

1. **Trunk-based.** Work on `main`. Feature branches only if change crosses > 3 commits or needs review.
2. **Commit messages reference MATLAB source paths** when porting: `port: CreateBackgroundGrid.m → admesh/background_grid.py`.
3. **No auto-PR, no auto-merge.** Claude drafts PRs on request only.
4. **GitHub posting on user's behalf requires explicit instruction.** Creating issues for tracking is pre-approved; commenting / closing / merging is not.
5. **Feature branches are speckit-driven only.** New feature branch created exclusively as part of `/speckit-specify` workflow. Claude does NOT create branches manually, does NOT create from session-system prompts (e.g. `claude/<...>-<random>`), does NOT create per-task branches for one-off edits. Direct work on `main` is default.
6. **Speckit naming is the only branch convention.** All feature branches follow `NNN-<short-name>` (sequential) or `YYYYMMDD-HHMMSS-<short-name>` (timestamp), per `.specify/init-options.json`. `claude/<feature>-<hash>` pattern NOT adopted.
7. **Scan before creating.** Before invoking `/speckit-specify` or any branch-creation, run `git branch -a` and check local + remote for existing branch matching feature's intent. If matching branch exists, REUSE it.
8. **Consolidate redundant branches when discovered.** If multiple branches address same feature, confirm with user once, then delete redundant ones (local + remote) and keep only speckit-named branch.

---

## Article VII — Persistent-session cadence

Operational rules for Claude sessions to prevent pause-for-ack pattern observed in session 0.

1. **Report-and-advance after every milestone.** When milestone ships, report result and immediately start next item. Do not end turn with "ready to continue" or any soft-ask phrasing.
2. **Zero `AskUserQuestion` outside destructive or ambiguous actions.** Permitted: destructive git operations, architecturally significant PR review replies, genuine ambiguity no reading of plan resolves. Banned: default-pick questions, option lists in prose, visibility/config picks, continue-prompts.
3. **Session-start read order is fixed.** `CONSTITUTION.md` → `PROJECT_PLAN.md` → `CLAUDE.md` → latest `docs/sessions/session_<N-1>_state.md` → active `docs/sessions/session_<N>_plan.md`. This is load-bearing; skipping previous-session state file is how context gets lost at session boundaries.

---

## Article VIII — External Upstream (DomI)

Foundational skills and policy governed by [domattioli/DomI](https://github.com/domattioli/DomI).

1. `.domi-pin` ledger MUST be committed and current.
2. Session start auto-checks drift via `scripts/instructions_on_start.sh`. Hard stop on drift; `/sync-from-domi` unblocks.
3. Skills from DomI take precedence over inline implementations. Local repo-specific skills (those NOT shipped by DomI) are exempt.
4. Repo-specific principles in this constitution override DomI universal defaults where they conflict.
5. This section does NOT affect existing repo-specific algorithmic principles.

Note: ADMESH speckit branch policy (Articles VI 5–8) stays as-is. The universal routine session instructions from DomI do NOT override ADMESH-specific branch and speckit rules.

---

## Amendments log

### 2026-05-08 — Article VIII adopted (External Upstream: DomI)

Added Article VIII to wire this repo to the DomI plugin marketplace
contract. Foundational skills sourced from domattioli/DomI via
sync-from-domi plugin. `.domi-pin` ledger required. Routine session
instructions are universal and do NOT override repo-specific branch
or speckit rules (Articles VI 5–8 intact). Session reference: DomI
downstream rollout.

### 2026-04-25 — Article VI rules 5–8 adopted (branch governance)

Tightened Article VI with four new rules (5–8) on branch lifecycle: speckit is ONLY path to feature branch; speckit naming (`NNN-<short-name>`) is ONLY accepted convention; existing branches must be scanned before creation; redundant branches must be consolidated. Adopted after session-system auto-created branches (`claude/<feature>-<hash>`) coexisted with speckit branches for same feature. Session reference: ADMESH session on `005-adcirc-mesh-registry`.

### 2026-04-21 — Article VII adopted

Added Article VII — Persistent-session cadence. Codifies report-and-advance discipline learned from session 0's four `UNCONFIRMED_PAUSE` interrupts (see `docs/persistence_journal.md` and `docs/sessions/session_0_report.md` § "Persistence retro"). Session reference: ADMESH session 1.

### 2026-04-18 — Constitution adopted

Initial ratification. ADMESH is new private repo (`domattioli/ADMESH`) porting QuADMesh-MATLAB `01_ADMESH_Library` @ `19b2eb9` to Python. Structure adapted from MADMESHR constitution down to port-focused rule set. Session reference: ADMESH session 0.
