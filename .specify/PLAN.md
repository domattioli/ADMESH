# PLAN: Manim ADMESH Notch-Seamount Visualization

**Phase:** SPECIFY (locked spec) → EXECUTE  
**Deliverables:** Two Python modules + visualization outputs  
**Total duration:** 2–3 days (developer time) + 1–2 hours compute (distmesh + Manim render)  
**Risk level:** LOW (90% code reuse from Baranja attempt)

---

## Executive Summary

Produce a pedagogical animation (12–15 sec, 720p) showing how ADMESH's size-field computation drives adaptive meshing. Domain: synthetic 3 km × 2 km coastal notch with seamount, chosen to exhibit **obvious 3–4× element-size variation** driven by boundary curvature + bathymetric slope + depth. Narrative: five acts spanning domain introduction → three size-field factors → combined field → iterative meshing → final quality assessment.

**Code reuse strategy:** 90% copy-paste from existing Baranja scripts (`gen_baranja_viz_data.py`, `manim_admesh_baranja.py`). Swap out domain geometry (Baranja boundary JSON → notch JSON), bathymetry function (Gaussian bumps → cross-shelf + seamount), and tuning parameters (h_min, h_max). No new algorithms.

---

## Dependency Graph & Parallelization

```
Phase 1: Setup (sequential, ~0.5 day)
  ├─ Task 1.1: Parametrize notch boundary (Bezier/arc-line hybrid)
  ├─ Task 1.2: Generate domain JSON + validate SDF
  └─ Task 1.3: Create bathymetry function (shelf profile + seamount)

Phase 2: Data Generation (sequential, ~4–6 hours compute)
  ├─ Task 2.1: Run gen_notch_seamount_data.py
  │  ├─ Inputs: domain JSON, h_min=0.08, h_max=0.25 (initial tuning)
  │  └─ Outputs: notch_seamount_admesh.npz (2–5 MB)
  ├─ Task 2.2: Validate size-field range (h_min/h_max ratio ≥ 2.8×)
  └─ Task 2.3: Validate mesh quality (Q_mean ≥ 0.65, Q_min ≥ 0.40)

Phase 3: Animation (sequential, ~2–3 hours)
  ├─ Task 3.1: Build Manim skeleton (5 scenes)
  ├─ Task 3.2: Integrate heatmap rendering (bathymetry + 3 size-field components)
  ├─ Task 3.3: Wire mesh animation (node + edge interpolation via ValueTracker)
  ├─ Task 3.4: Render @ low quality (test timing + visuals)
  └─ Task 3.5: Render @ full quality (720p, 30 fps)

Phase 4: Validation & Handoff (sequential, ~0.5 day)
  ├─ Task 4.1: Verify animation meets 5 success criteria
  ├─ Task 4.2: Generate validation plots (domain + heatmaps → PNG)
  └─ Task 4.3: Document & commit
```

**Parallelization opportunities:**
- Tasks 1.1–1.3 can overlap (domain geometry ∥ bathymetry tuning)
- Task 3.4 (low-res render test) can overlap with Task 2.3 validation

---

## Data Flow Diagram

```
DOMAIN SETUP
  ├─ Domain JSON (notch boundary)
  │  └─ → fast_sdf (signed distance function)
  │     └─ → distmesh (node generation)
  │
  ├─ Bathymetry function z(x,y)
  │  ├─ Shelf cross-profile: z(x) = cross_shelf_depth(x)
  │  ├─ Seamount: z(x,y) += seamount_bump(x,y)
  │  └─ → Gradient computation (FD 3pt stencil)
  │
  └─ Size-field factors h_i(x,y)
     ├─ h_curv(x,y) from boundary curvature + distance decay
     ├─ h_grad(x,y) from |∇z|
     ├─ h_depth(x,y) from z value clipping
     └─ h(x,y) = min(h_curv, h_grad, h_depth)
        └─ → distmesh iteration loop
           ├─ Per iteration: record p, bars
           └─ → Snapshots array

DATA OUTPUT (NPZ)
  ├─ ring: boundary polygon (N × 2)
  ├─ bbox: extent [xmin, ymin, xmax, ymax]
  ├─ bathy: grid (240 × 240) bathymetry for heatmap
  ├─ h_curv, h_grad, h_depth, h: per-factor size fields (grids)
  ├─ inside: boolean mask (domain interior)
  ├─ n_snaps: iteration count
  └─ p{i}, b{i}: per-iteration node coords + edge lists

ANIMATION INPUT
  └─ notch_seamount_admesh.npz
     ├─ Acts I–II: Boundary + heatmap renders via ImageMobject
     ├─ Acts III–IV: Mesh interpolation via ValueTracker + always_redraw
     └─ Act V: Quality colormap overlay
        └─ → MP4 file (720p, 30 fps, 12–15 sec)
```

---

## Milestones & Checkpoints

| Milestone | Owner | Checks | Gate |
|-----------|-------|--------|------|
| **M1: Domain geometry finalized** | Impl | SDF renders cleanly; curvature ≥ 100 m⁻¹ at notch tip | h_min/h_max ratio ≥ 2.5× predicted |
| **M2: Data generation passes quality** | Impl | `notch_seamount_admesh.npz` created; Q_mean ≥ 0.65, h_min/h_max ≥ 2.8× | Proceed to animation |
| **M3: Manim low-res render** | Impl | 360p test render ≤10 min; 5 acts present, timing sensible | Proceed to full quality |
| **M4: Final animation** | Impl | 720p MP4 file, 12–15 sec, no frame drops, meets success criteria | Ready for issue closure |

---

## Resource Estimates

### Compute
- **Data generation (gen_notch_seamount_data.py):** ~4–6 hours wall time (distmesh convergence)
  - ~2 hours for SDF evaluation + bathymetry grid
  - ~2–4 hours for instrumented distmesh (120 iterations, ~2000 pts/iteration)
  - Machine: modern CPU (i5+); uses NumPy + Delaunay (via SciPy), no GPU needed
  
- **Manim render (low quality, 360p @ 15fps):** ~10 min
- **Manim render (full quality, 720p @ 30fps):** ~20–40 min

### Developer Time
- **Phase 1 (Setup):** 2–4 hours (parametrize geometry, validate SDF)
- **Phase 2 (Data generation):** 2–3 hours (run script, tune h_min/h_max iteratively)
- **Phase 3 (Animation):** 4–6 hours (skeleton → full implementation → rendering)
- **Phase 4 (Validation):** 2–3 hours (quality checks, documentation)

**Total developer time:** ~10–16 hours over 2–3 days

### Storage
- Input: domain JSON (~5 KB)
- Intermediate: `notch_seamount_admesh.npz` (2–5 MB, compressed)
- Output: MP4 (12–15 sec @ 720p ≈ 30–50 MB)

---

## Testing & Validation Strategy

### Data Generation Validation
1. **SDF correctness:** Spot-check fd(x,y) at 5 points (inside, outside, boundary)
2. **Bathymetry realism:** Plot z(x,y) cross-section; verify slope range |∇z| ≥ 0.30
3. **Size-field factors:** Verify h_curv peaks at notch corner, h_grad at shelf edge, h_depth offshore
4. **Distmesh convergence:** Plot node motion vs. iteration (should plateau by iter 80–100)
5. **Mesh quality gate:** Assert Q_min ≥ 0.40, Q_mean ≥ 0.65

### Animation Validation
1. **Act I (Domain):** Boundary renders; labels at notch + shelf zones
2. **Act II (Heatmaps):** Three components crossfade; colors distinct; no flicker
3. **Act III (Combined):** Min-stack visible; contour underlay legible
4. **Act IV (Mesh):** Nodes denser in fine zones; edges rebuild smoothly
5. **Act V (Quality):** Final mesh + colormap; text label displays correctly

### Success Criteria (from SPECIFY)
- ✓ Domain |∇z| ≥ 0.30 somewhere
- ✓ Notch curvature ≥ 100 m⁻¹
- ✓ h_min / h_max ≤ 0.35 (≥ 2.8× variation)
- ✓ Q_min ≥ 0.40, Q_mean ≥ 0.65
- ✓ Animation 8–12 sec @ 720p
- ✓ Viewer learns three size-field factors

---

## Known Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Bathymetry too smooth → h_min/h_max < 2.5× | Medium | High | Increase seamount height or notch depth; profile gradient early (M1 gate) |
| Distmesh slow convergence (>150 iterations) | Low | Medium | Increase h_max slightly; accept longer compute; use cached distmesh from exploratory run |
| Manim rendering slow (>1 hour @ 720p) | Low | Medium | Pre-render heatmap images to PNG; load via ImageMobject; reduce node count if needed |
| Low mesh quality (Q_mean < 0.55) | Medium | Low | Acceptable if Q_min ≥ 0.35; distmesh optimizes size field, not quality |
| Animation timing feels rushed (5 acts in <10 sec) | Low | Low | Extend to 15–18 sec or drop one heatmap component (keep curvature + slope) |

---

## File Checklist

**To create:**
- `.specify/PLAN.md` (this file)
- `.specify/TASKS.md` (detailed task list)
- `.specify/ANALYZE.md` (technical deep-dive + resource analysis)
- `.specify/IMPLEMENT.md` (pseudocode + execution guide)

**To generate (during EXECUTE):**
- `scripts/gen_notch_seamount_data.py` (domain JSON loader + bathymetry + size-field + distmesh)
- `scripts/viz_data/notch_seamount_domain.json` (domain geometry)
- `scripts/viz_data/notch_seamount_admesh.npz` (data export)
- `scripts/manim_notch_seamount.py` (5-act animation)
- `output/notch_seamount_*.png` (validation plots)
- `output/notch_seamount_admesh.mp4` (final animation)

---

## Next Steps for EXECUTE Phase

1. **Execute Phase 1 (Setup):**
   - Review & finalize domain boundary parametrization (Task 1.1)
   - Generate domain JSON + SDF validation (Task 1.2)
   - Implement bathymetry function (Task 1.3)

2. **Execute Phase 2 (Data):**
   - Run data generation script; measure compute time (Task 2.1)
   - Check M2 gate: h_min/h_max ratio, Q_min/Q_mean (Tasks 2.2–2.3)
   - If gate fails, iterate h_min/h_max tuning

3. **Execute Phase 3 (Animation):**
   - Build Manim skeleton + test low-res render (Tasks 3.1–3.4)
   - Integrate mesh animation via ValueTracker (Task 3.3)
   - Full-quality render (Task 3.5)

4. **Validate & Commit:**
   - Run success criteria checks (Task 4.1)
   - Generate static validation plots (Task 4.2)
   - Commit all files with clear messages
   - Close issue #97

---

## Assumptions

1. Distmesh convergence on notch domain ≤ 150 iterations (based on Baranja experience ~120)
2. Final mesh node count 100–200 nodes (legible in Manim, ~4–5 sec animation)
3. Manim 0.18+ installed with Python 3.10+; standard renderer (not OpenGL)
4. `fast_sdf` module stable; no modifications needed
5. h_min/h_max tuning parameters found via binary search within ~3 iterations

---

## References

- SPECIFY.md — locked domain + narrative arc
- CLARIFY.md — acceptance criteria + open questions
- gen_baranja_viz_data.py — proven code (copy 90%)
- manim_admesh_baranja.py — proven Manim patterns (copy 95%)
- ADMESH `size_components()` — faithful-port algorithm (no changes)
