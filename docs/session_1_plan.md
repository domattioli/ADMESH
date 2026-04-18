# Session 1 — ADMESH MVP M.4 + governance tightening

**Goal (plain English):** close out the MVP by triangulating all 5
test domains end-to-end, committing a rendered PNG for each as
reviewable evidence, and tightening the governance docs with the
persistence-cadence lesson from session 0. When this session ships,
the MVP acceptance gate in `PROJECT_PLAN.md` is met and the port
pivots to Phase P1 (quad conversion).

**Session-start read order** (per `CLAUDE.md`):
`CONSTITUTION.md` → `PROJECT_PLAN.md` → `CLAUDE.md` →
`docs/session_0_state.md` → `docs/session_0_report.md` → this plan.

---

## Binding gate

All five of:

1. `admesh.triangulate(domain, h0=<per-domain>)` returns a valid mesh
   (`_assert_valid_mesh` helper, same contract as `tests/test_distmesh.py`)
   for each of: `unit_square`, `l_shape`, `unit_disk`, `annulus`,
   `notched_rectangle`.
2. `mean_q ≥ 0.60` and `min_q ≥ 0.30` on every domain.
3. One PNG per domain committed to `tests/output/mvp_<name>.png`
   (force-add — the dir is gitignored per
   `CONSTITUTION.md` Article II.6 style).
4. `pytest tests/ -q` green (target: 55+ tests).
5. `docs/PORTING_NOTES.md` populated with the four MATLAB→Python
   divergences noted in `docs/session_0_report.md` (InPolygon
   mex-only; SignedDistanceFunction MVP subset; distmesh2d canonical
   vs. ADMESH variant; `.mex*` binaries discarded).

---

## Workstreams

### WS1 — MVP triangulation tests + PNG rendering

**Deliverables:** `tests/test_mvp_domains.py`,
`scripts/render_mvp_meshes.py`, 5 PNGs under `tests/output/`.

**Steps:**
1. Write `scripts/render_mvp_meshes.py`: for each `Domain` in
   `admesh.domains.ALL`, call `triangulate(...)` with the per-domain
   `h0` defaults (see below), and save a `matplotlib.tri.triplot`
   PNG to `tests/output/mvp_<name>.png`. No CLI flags needed; one
   entry point: `python scripts/render_mvp_meshes.py`.
2. Write `tests/test_mvp_domains.py` with one parametrized test
   asserting the M.4 gate per domain. Use
   `_assert_valid_mesh(p, t, fd, geps)` from
   `tests/test_distmesh.py` (promote it to a shared helper in
   `tests/conftest.py` if that's cleaner).
3. Per-domain `h0` defaults (first cut; tune if a domain misses the
   quality gate): `unit_square=0.12`, `unit_disk=0.15`,
   `l_shape=0.15`, `annulus=0.12`, `notched_rectangle=0.08`. Adjust
   `niter` upward from default 500 only if a domain doesn't
   converge — document in the test why.
4. Commit PNGs. `git add -f tests/output/mvp_*.png`.

**Falsifier:** If a domain fails completion (e.g. `annulus` loses a
ring of triangles because the inner boundary has no pinned
fixed-points), do NOT widen the quality gate. The correct fix is
usually adding explicit `fixed_points` to the `Domain` definition in
`admesh/domains.py` (inner ring sample for annulus; top-rim points
for notched_rectangle).

**Risk + mitigation:** Persson's DistMesh on multiply-connected
domains can strand boundary nodes. If the `annulus` mesh looks
degenerate, sample `N = 2π·r_inner / h0` points uniformly around the
inner circle and add them as `fixed_points` in `_sdf_annulus`'s
registry entry. Document in a PNG comparison (`mvp_annulus_nofix.png`
vs. `mvp_annulus.png`) the first time this comes up.

### WS2 — Governance tightening

**Deliverables:** Article VII added to `CONSTITUTION.md`; amendments
log updated. `docs/PORTING_NOTES.md` populated.

**Steps:**
1. Append `Article VII — Persistent-session cadence` to
   `CONSTITUTION.md` with three rules: (a) report-and-advance after
   every milestone, (b) zero AskUserQuestion outside destructive
   actions, (c) session-start reads must include the latest
   `session_<N-1>_state.md`. Log the amendment with today's date
   and cite session 0's persistence retro.
2. Populate `docs/PORTING_NOTES.md` with four entries (one per
   divergence named in the session 0 report). Use the template at
   the top of that file.
3. Update `PROJECT_PLAN.md` "Where we are today" to mark M.4 shipped
   and name Phase P1 as the next entry point.

### WS3 — Numba benchmark (stretch)

**Deliverable:** `scripts/bench_mesh_size.py`, run result committed
to session 1 report.

**Steps:**
1. Generate a realistic `h0`, `D` pair (e.g. annulus at `delta=0.02`
   — `~5000×5000` would be extreme; `200×200` is plenty).
2. Time `solve_iter(..., use_numba=True)` vs `use_numba=False`; also
   record total iterations.
3. Commit `scripts/bench_mesh_size.py` plus the numeric result in
   the session 1 report. Gate: Numba path is ≤ 2× a "reasonable"
   C baseline if one is reachable (sidecar build; otherwise just
   record Numba/Python ratio).

If session budget is tight, WS3 skips and ports over to session 2.

### WS-final — Wrap-up (per `.claude/skills/session-handoff/SKILL.md`)

1. Run `pytest tests/ -q`; ensure green.
2. Update `PROJECT_PLAN.md` "Where we are today" for post-M.4 state.
3. Write `docs/session_1_report.md` (template: session 0's report).
4. Write `docs/session_1_state.md` (overwrites if any).
5. Draft `docs/session_2_plan.md` targeting Phase P1 kickoff
   (`04_Curvature_Function` + `05_Medial_Axis` → richer size fields).
6. Roll up the persistence journal: any trigger class ≥ 3 this
   session → propose plan/constitution edit.
7. Commit + push. Do NOT auto-open a PR.

---

## Out of scope for session 1

- Phase P1+ (curvature, medial-axis, bathymetry, tide, boundary,
  inpaint) — session 2+.
- Reference fixture round-trip from MATLAB (post-MVP P4).
- PyPI publish / public repo flip — Phase P5.

---

## Session budget

Session 0 burned the user's usage budget by end-of-evening. Session 1
should budget conservatively:

- WS1 (mandatory): ~60% of budget.
- WS2 (mandatory): ~25%.
- WS3 (stretch): ~15%; drops if WS1+WS2 take longer.
- WS-final: fixed ~10% overhead on top.

If WS1 blows past the 60% mark because a domain needs `pfix` tuning,
drop WS3, finish WS1+WS2, and call it a session.
