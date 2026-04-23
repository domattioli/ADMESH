# Session 6 — Boundary backfill + notched polish; bathymetry/tide last

**Goal (plain English):** retire the last clean-room module
(`admesh/boundary.py`) by faithful-porting
`08_Enforce_Boundary_Conditions/`, polish the notched_rect demo,
port `13_In_Paint_NaNs` (a utility bathymetry + tide will need),
then land the physical-field modules (`06_Bathymetry_Function`,
`07_Dominate_Tide`) on top of that foundation. After this session
all 13 ADMESH library stages have faithful Python ports; the
port's north star (bit-for-bit MATLAB parity within FP tolerance)
becomes directly testable.

**Session-start read order** (per `CLAUDE.md` + Article VII):
`CONSTITUTION.md` → `PROJECT_PLAN.md` → `CLAUDE.md` →
`docs/session_5_state.md` → `docs/session_5_report.md` → this plan.

---

## WS0 — Env check

```bash
ls /workspace/QuADMesh-MATLAB/01_ADMESH_Library/
```

Must exist. Article II.1 is binding — no clean-room fallback.

---

## Binding gate

All of:

1. `admesh/boundary.py` rewritten as faithful port of
   `08_Enforce_Boundary_Conditions/{EnforceBoundaryConditions,
   create_polygon_structure}.m` (retires last session-3 clean-room).
2. `admesh/inpaint.py` faithful port of
   `13_In_Paint_NaNs/inpaint_nans.m`.
3. `admesh/bathymetry.py` faithful port of
   `06_Bathymetry_Function/BathymetryFunction.m` (+ helpers).
4. `admesh/dominate_tide.py` faithful port of
   `07_Dominate_Tide/Dominate_tide.m` (+ helpers).
5. `build_h` extended to take `bathymetry` + `tide_scale` kwargs
   that route to the new ports.
6. `tests/test_matlab_port.py` extended — port-correctness tests
   for each new module.
7. `scripts/export_matlab_fixtures.m` populated for each new
   module.
8. MVP M.4 gate regression-clean; demo suite regenerates; `pytest
   tests/ -q` green with ≥ 110 tests.
9. **All 13 ADMESH library stages on faithful ports.** PROJECT_PLAN
   "Faithful-port backfill remaining" line is gone.
10. notched_rect medial demo crosses the 0.30 min_q gate.

---

## Workstreams (reordered: bathymetry + tide LAST)

### WS1 — `08_Enforce_Boundary_Conditions` faithful backfill

**Priority #1** — retires the last clean-room module; unblocks
honest Article II.1 compliance across all ported stages.

Rewrite `admesh/boundary.py` against
`EnforceBoundaryConditions.m` + `create_polygon_structure.m`.
PTS struct should grow any fields the MATLAB version has that the
session-3 port skipped. `enforce_boundary_conditions` maps
per-ring BC tags into h-field adjustments (MATLAB line 37:
`h_ic(D > hmin) = hmax`; line 47: `h_ic(IB) = hmax` for open-ocean
boundaries).

### WS2 — notched_rect demo polish

**Priority #2 — cheap, high-visibility win.** Route
`demo_notched_rect_medial` through the PTS path, same way the
annulus demo works — `distmesh2d_admesh`'s density control +
best-q tracking will clean up the transition-zone slivers.
Target: min_q ≥ 0.30.

### WS3 — `13_In_Paint_NaNs` port

**Priority #3 — utility prerequisite for WS4/WS5.**
NaN-fill on a grid for sparse physical-field inputs. Small module.
Used by bathymetry + tide when depth data has gaps.

### WS4 — `06_Bathymetry_Function` port

**Priority #4.** Depth-driven size field. Wire into `build_h`.

### WS5 — `07_Dominate_Tide` port

**Priority #5.** Long-wave `λ = sqrt(g·depth)·period`; tide-size
contribution to the composed h.

### WS-final — wrap-up

Standard: pytest green, PORTING_NOTES updated, PROJECT_PLAN
rolled forward, session 6 report/state, session 7 plan targeting
Phase P3 (full `ADmeshRoutine.m` orchestration — the final port).

---

## Out of scope for session 6

- Full `ADmeshRoutine.m` orchestration — session 7.
- PyPI publish / public repo flip — Phase P4.

---

## Session budget

- WS0: ≤ 1%.
- WS1 (boundary backfill): ~30%.
- WS2 (notched polish): ~5%.
- WS3 (inpaint): ~10%.
- WS4 (bathymetry): ~20%.
- WS5 (tide): ~15%.
- WS-final: ~20%.

If WS1 overruns, drop WS5 to session 7 — bathymetry alone is still
a meaningful P2 ship. If WS1+WS2 run clean and WS3/4/5 all land,
session 6 completes the full 13-stage port.

Reordering rationale (user call, post-S5): finishing the
clean-room backfill and getting a visible demo win first gives
session 6 a strong spine even if P2 physical-field work slips;
bathymetry and tide are more speculative (caller hasn't driven
them in any demo yet) and build on inpaint, so they belong last.
