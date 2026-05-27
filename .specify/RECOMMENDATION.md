# Recommendation: Next Phase (PLAN)

## Expert Assessment

**SPECIFY & CLARIFY Complete.** Domain choice and acceptance criteria now unambiguous:

- **Domain:** Synthetic coastal notch (60° V-shape, 1 km wide) + seamount (4 m high, 400 m radius in notch interior)
- **Scale:** 3 km × 2 km, final mesh ≈ 150 nodes (legible at Manim 720p)
- **Size-field variation:** Target ≥ 2.8× (h_min / h_max ≤ 0.35)
- **Animation arc:** 5 acts, 12–15 sec, emphasizing curvature → slope → depth → combined → meshing → quality

**Risk level:** Low. Code reuses proven ADMESH `size_components()` + `instrumented_distmesh()` (locked stage 09–10); only data generation + Manim rendering are new. No algorithm changes required.

---

## Recommended PLAN Skeleton

### Phase Phases (4 subtasks, ~2–3 days parallel work)

1. **DOMAIN + BATHYMETRY** (1 day)
   - Parametrize notch as piecewise Bezier + line segments → JSON
   - Synthetic bathymetry: cross-shelf profile + seamount Gaussian
   - Validate SDF via `fast_sdf(rings)` on 50-point test grid
   - Output: `notch_seamount_domain.json` + static plots

2. **SIZE-FIELD COMPUTATION** (4 hours)
   - Copy `gen_baranja_viz_data.py` → `gen_notch_seamount_data.py`
   - Swap domain + bathymetry functions
   - Run distmesh instrumentation; validate final mesh Q ≥ 0.60 mean
   - Tune h_min, h_max if size-field range < 2.8×
   - Output: `notch_seamount_admesh.npz`

3. **MANIM ANIMATION** (1.5 days)
   - Copy `manim_admesh_baranja.py` → `manim_notch_seamount.py`
   - Implement Acts I–V as separate `add_*` methods
   - Build node+edge interpolation via `always_redraw()` + `ValueTracker` frames
   - Low-res test (240p) for timing/flow
   - Output: Full-res render (720p, MP4)

4. **VALIDATION + DOCS** (4 hours)
   - Generate static plots: domain + 4 heatmaps + final mesh with quality colormap
   - Write scene docstring + brief README
   - Smoke-test quality gate; document any deviations from target

---

## Execution Strategy

- **Leverage existing code:** 90% of the heavy lifting (distmesh, size-field, Manim boilerplate) is copy-paste-modify from Baranja attempt. No new algorithms.
- **Early validation gates:**
  1. After domain: SDF renders correctly
  2. After data gen: final mesh Q meets 0.60 target
  3. After Manim skeleton: Acts I–III timing OK at low res
  4. Final: full-res render

- **Potential blockers (unlikely):**
  - Distmesh won't converge on notch shape → increase iterations or adjust h scaling
  - Manim renders too slowly → pre-render heatmaps as PNG; load instead of compute

---

## Conviction Level

**HIGH.** This domain + narrative arc directly addresses issue #97 root cause (uniform mesh from weak size-field variation). Synthetic notch guarantees rich, visible gradients. Animation script reuses proven Manim patterns from Baranja. Only execution risk is tuning constants; no algorithmic risk.

**Estimated delivery:** 2–3 days wall-clock, 1–2 days person-effort if sequential; faster if subtasks parallelized (domain geometry ∥ Manim skeleton).
