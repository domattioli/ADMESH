# Session 7 — Phase P3: full `ADmeshRoutine.m` orchestration

**Goal (plain English):** with all 13 individual stages now on
faithful ports (session 6 close), compose them into the top-level
MATLAB pipeline. Port
`01_ADMESH_Library/01_ADMESH_Routine/{ADmeshRoutine,
ADmeshSubMeshRoutine}.m` faithfully against the MATLAB source at
`@ 19b2eb9`. After this session the Python port reproduces the
end-to-end MATLAB pipeline — north-star milestone for the project.

**Session-start read order** (per `CLAUDE.md` + Article VII):
`CONSTITUTION.md` → `PROJECT_PLAN.md` → `CLAUDE.md` →
`docs/session_6_state.md` → `docs/session_6_report.md` → this
plan.

---

## WS0 — Env check

```bash
ls /workspace/QuADMesh-MATLAB/01_ADMESH_Library/01_ADMESH_Routine/
```

Must exist (or `/tmp/QuADMesh-MATLAB/` fallback). Article II.1 is
binding.

---

## Binding gate

All of:

1. `admesh/routine.py` extended with a faithful port of
   `ADmeshRoutine.m`. Entry point accepts a MATLAB-shaped config
   struct (`Settings` dict) so the existing `triangulate(...)`
   MVP shim + PTS shim remain valid.
2. `ADmeshSubMeshRoutine.m` ported (sub-domain decomposition /
   recursion).
3. End-to-end demo: unit_disk + annulus + notched_rect all run
   through the full routine and satisfy `min_q ≥ 0.30`,
   `mean_q ≥ 0.60`. **notched_rect gate is the session-5 carry-
   over** — full-routine composition is expected to clear it.
4. `tests/test_routine.py` extended with `ADmeshRoutine` port-
   correctness cases (h-field composition across all stages;
   mesh-quality gates; output dataclass shape).
5. `tests/test_matlab_port.py` extended with an end-to-end fixture
   parity test (unit_disk full-routine output vs. MATLAB).
6. `scripts/export_matlab_fixtures.m` gains an `ADmeshRoutine`
   fixture block.
7. PORTING_NOTES entry for the orchestration port.
8. Demo suite regenerates; `pytest tests/ -q` green with ≥ 140
   tests.
9. **North-star reached**: Python port reproduces the MATLAB
   pipeline end-to-end on the reference domains within documented
   FP tolerance. PROJECT_PLAN milestone flag set.

---

## Workstreams

### WS1 — `ADmeshRoutine.m` skeleton

Rewrite the outer loop: parse `Settings`, call
`CreateBackgroundGrid`, `SignedDistanceFunction`, optional
`CurvatureFunction`, optional `MedialAxisFunction`, optional
`BathymetryFunction`, optional `Dominate_tide`,
`EnforceBoundaryConditions`, `MeshSizeIterativeSolver`,
`distmesh2d` (ADMESH variant), `MeshQuality` for reporting,
optional `BoundaryCleanUp` (already in `distmesh2d_admesh` final
step).

### WS2 — `ADmeshSubMeshRoutine.m`

Sub-domain decomposition path. If the MATLAB version is a thin
wrapper around `ADmeshRoutine` per sub-domain, keep the Python
port thin too.

### WS3 — `Settings` dataclass

Port MATLAB `Settings` struct layout: `K.Status`, `R.Status`,
`B.Status`, `T.Status` (per-stage on/off flags), plus per-stage
params. Make it a frozen dataclass with sensible defaults and a
`from_dict` classmethod for user ergonomics.

### WS4 — notched_rect demo polish

Route the demo through the full routine; expect `min_q ≥ 0.30`
lift. If it doesn't land, diagnose against MATLAB trace output.

### WS5 — End-to-end fixture

`scripts/export_matlab_fixtures.m` emitter block: run MATLAB
ADmeshRoutine on `unit_disk` with a representative config; emit
final `(p, t, h_field, min_q, mean_q)`. Python test loads the
fixture, runs our port, compares within tolerance.

### WS-final — wrap-up

PORTING_NOTES entry; PROJECT_PLAN rolled forward (**north-star
milestone achieved**); session 7 report/state; session 8 plan
targeting **Phase P4** — polish, type hints, public API review,
PyPI publish, flip repo to public.

---

## Out of scope for session 7

- GUI plumbing from MATLAB `ADmeshRoutine.m` (status bar, viewer
  callbacks). Constitution Article I north-star is a library, not
  a GUI.
- `.fort.14` ADCIRC I/O. Downstream concern.
- PyPI publish. Phase P4 / session 8.

---

## Session budget

- WS0: ≤ 1%.
- WS1 (ADmeshRoutine skeleton): ~35%.
- WS2 (SubMeshRoutine): ~10%.
- WS3 (Settings): ~10%.
- WS4 (notched polish): ~10%.
- WS5 (end-to-end fixture): ~15%.
- WS-final: ~20%.

If WS1 overruns (the orchestration is complex), split into WS1a
(h-composition pipeline) + WS1b (full routine including
`distmesh2d` loop + final reporting). WS2 can slip to session 8
since the non-submesh path is the primary deliverable.
