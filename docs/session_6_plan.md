# Session 6 — Phase P2 (bathymetry + tide + inpaint) + boundary backfill

**Goal (plain English):** add the physical-field sizing modules
(`06_Bathymetry_Function`, `07_Dominate_Tide`, `13_In_Paint_NaNs`)
and retire the last clean-room module (`admesh/boundary.py`) by
faithful-porting `08_Enforce_Boundary_Conditions/`. After this
session all 13 ADMESH library stages have faithful Python ports;
the port's north star (bit-for-bit MATLAB parity within FP
tolerance) becomes directly testable.

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

1. `admesh/bathymetry.py` faithful port of
   `06_Bathymetry_Function/BathymetryFunction.m` (+ helpers).
2. `admesh/dominate_tide.py` faithful port of
   `07_Dominate_Tide/Dominate_tide.m` (+ helpers).
3. `admesh/inpaint.py` faithful port of
   `13_In_Paint_NaNs/inpaint_nans.m`.
4. `admesh/boundary.py` rewritten as faithful port of
   `08_Enforce_Boundary_Conditions/{EnforceBoundaryConditions,
   create_polygon_structure}.m` (retires last session-3 clean-room).
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

---

## Workstreams

### WS1 — `06_Bathymetry_Function` port

**Deliverables:** `admesh/bathymetry.py`, fixture emitter block,
hand-derived + fixture tests.

**Steps:**
1. Read `BathymetryFunction.m` + helpers.
2. Port faithfully — depth-driven size field.
3. Wire into `build_h`.
4. Fixture emitter + tests.

### WS2 — `07_Dominate_Tide` port

Similar scope. Long-wave `λ = sqrt(g·depth)·period`; tide-size
contribution to the composed h.

### WS3 — `13_In_Paint_NaNs` port

Smaller. NaN-fill on a grid for sparse physical-field inputs. Used
by bathymetry + tide when depth data has gaps.

### WS4 — `08_Enforce_Boundary_Conditions` faithful backfill

Rewrite `admesh/boundary.py` against
`EnforceBoundaryConditions.m` + `create_polygon_structure.m`.
PTS struct should grow any fields the MATLAB version has that the
session-3 port skipped. `enforce_boundary_conditions` maps
per-ring BC tags into h-field adjustments (MATLAB line 47:
`h_ic(IB) = hmax` for open-ocean boundaries).

### WS5 — notched_rect demo polish (carry-over from S5)

Cheap: reroute `demo_notched_rect_medial` through the PTS path,
same way annulus demo works. Should get min_q ≥ 0.30.

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

- WS1 (bathymetry): ~20%.
- WS2 (tide): ~15%.
- WS3 (inpaint): ~10%.
- WS4 (boundary backfill): ~30%.
- WS5 (notched polish): ~5%.
- WS-final: ~20%.

If WS4 overruns, drop WS5 to session 7.
