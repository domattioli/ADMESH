# Issue #97 Speckit Phase: SPECIFY + CLARIFY (Complete)

**Status:** Ready for Review  
**Branch:** manim-admesh-viz  
**Created:** 2026-05-24  

---

## Documents (Read in Order)

### 1. DECISION_MEMO.md (Start Here)
**Audience:** Decision maker, issue author  
**Length:** 2 pages  
**What it answers:**
- Why Baranja failed (uniform mesh from weak size-field variation)
- Why Notch + Seamount is the right domain choice
- Locked-in narrative arc (5 acts, 12-15 sec)
- Success criteria, risk assessment, stakeholder alignment
- **Bottom line:** "Approve → proceed to PLAN" or "Request changes"

### 2. SPECIFY.md (Detailed Specification)
**Audience:** Technical leads, anyone implementing PLAN  
**Length:** 2 pages  
**What it contains:**
- Problem statement reframed (root cause analysis)
- Four domain candidates evaluated and scored
- Recommended domain: Coastal Notch + Seamount (geometry + bathymetry specified)
- 5-act narrative arc with timing
- Key constraints & pedagog goals
- Success criteria (6 testable items)

### 3. CLARIFY.md (Acceptance Criteria & Open Questions)
**Audience:** Implementation team, QA  
**Length:** 4 pages  
**What it contains:**
- 4 groups of acceptance criteria (13 items, all testable)
- Technical constraints (Manim rendering, Python pipeline, distmesh quality)
- 13 open decisions needing PLAN-phase resolution (with recommendations)
- Risk mitigation table (5 risks, probability/impact/mitigation)
- Assumptions & unknowns

### 4. RECOMMENDATION.md (Next Steps)
**Audience:** Project manager, sprint planner  
**Length:** 1 page  
**What it contains:**
- Expert assessment ("Risk: LOW, Conviction: HIGH")
- PLAN phase skeleton (4 subtasks)
- Execution strategy (dependencies, parallelization)
- Estimated delivery (2-3 days)

---

## Key Decisions Made (Locked In)

| Item | Decision | Rationale |
|------|----------|-----------|
| **Domain type** | Synthetic Notch + Seamount | Guarantees rich size-field variation; pedagogically isolates curvature vs. slope vs. depth |
| **Domain extent** | 3 km × 2 km | Matches Manim frame; element-size variation visible without zoom |
| **Notch geometry** | 60° V-shape, 1 km wide/deep | High curvature (200 m⁻¹) unmistakable; symmetric for clarity |
| **Bathymetry** | Cross-shelf (0→-100 m) + seamount (+4 m) | Slope + depth factors balanced; seamount adds localized peak |
| **Size-field range** | h_min/h_max ≤ 0.35 (≥2.8× variation) | Minimum required for visible mesh refinement at animation scale |
| **Mesh quality gate** | Q_min ≥ 0.40, Q_mean ≥ 0.65 | ADMESH distmesh2d standard; deviation flagged but acceptable |
| **Animation length** | 12-15 sec @ 30 fps | 5 acts fit naturally; <10 min render time achievable |
| **Narrative structure** | 5-act: domain → factors (3) → combined → mesh → quality | Teaches algorithm step-by-step; each act builds on previous |

---

## Open Questions Requiring PLAN-Phase Decision

Questions marked with 📍 recommend one option; all others are tie-breakers or tuning parameters.

1. **Notch depth:** 1 km 📍 vs. 500 m
2. **Seamount height:** 4 m 📍 vs. 10 m
3. **h_min, h_max:** Start 0.08, 0.25 📍 (adjust if size-field < 2.8×)
4. **Initial lattice:** Skip to iteration 0 📍 vs. show random cloud
5. **Mesh edge rendering:** Visible white lines 📍 vs. infer from node density
6. **Animation text:** Minimal labels (3-4) 📍 vs. narrated voice-over
7. **Heatmap resolution:** 240×240 px or 480×480 px (test after skeleton)
8. **Curvature decay length:** Keep as-is (0.30 in norm coords) or tune
9. **Distmesh iterations:** Default 120 or increase if convergence slow
10. **Static validation plots:** Generate + review before final render 📍
11. **Quality colormap:** Aspect ratio (green→red) 📍 vs. angle-skewness ratio
12. **Frame interpolation:** Smooth between mesh snapshots via `always_redraw()` + `ValueTracker` 📍
13. **Manim quality setting:** Default ql (720p) 📍 vs. qh (1080p) for final

---

## What Gets Built (EXECUTE Phase)

### New Scripts
- `scripts/gen_notch_seamount_data.py` — Domain + bathymetry setup, distmesh instrumentation
- `scripts/manim_notch_seamount.py` — 5-act Manim scene

### New Data Files
- `benchmarks/data/notch_seamount_domain.json` — Domain geometry (piecewise curves, ~100 pts)
- `scripts/viz_data/notch_seamount_admesh.npz` — Size grids + distmesh snapshots

### Generated Artifacts (For Validation)
- `output/notch_seamount_domain_plot.png` — Domain boundary
- `output/notch_seamount_heatmaps.png` — 2×2 grid: bathy, h_curv, h_grad, h_depth, h_combined
- `output/notch_seamount_final_mesh.png` — Final mesh with quality colormap
- `media/videos/manim_notch_seamount/` — Rendered animation (MP4 or PNG sequence)

---

## Criteria for Phase Completion

**SPECIFY + CLARIFY are complete when:**
- ✓ Domain choice unambiguous (Coastal Notch + Seamount selected)
- ✓ Narrative arc specified (5 acts with timing)
- ✓ Acceptance criteria testable (13 + 13 criteria across SPECIFY & CLARIFY)
- ✓ Open decisions documented (13 items with recommendations)
- ✓ Risk assessment done (5 risks, mitigation for each)
- ✓ PLAN skeleton outlined (4 subtasks, dependencies, effort estimate)
- ✓ Decision authority signoff (Expert recommendation: APPROVE)

**Status:** ✓ COMPLETE

---

## How to Use These Documents

**For Issue Author (User):**
1. Read DECISION_MEMO.md (2 min)
2. Skim SPECIFY.md + CLARIFY.md (5 min)
3. Decide: Approve → PLAN, or Request changes → re-CLARIFY

**For Implementation Team:**
1. Read all 4 documents in order (20 min)
2. PLAN phase: resolve 13 open questions; create detailed project plan
3. EXECUTE phase: build scripts/data/animation following PLAN

**For QA / Validation:**
1. Read CLARIFY.md acceptance criteria (5 min)
2. After each subtask, validate against acceptance gate
3. Final sign-off: all 13 criteria met

---

## Next Action

→ **PLAN Phase** (If approved)
  - Resolve 13 open decisions
  - Create detailed task breakdown + effort estimates
  - Define checkpoints + validation gates
  - Schedule subtasks (parallelizable: domain ∥ Manim skeleton)

OR

→ **Re-CLARIFY** (If requested)
  - User provides specific concerns
  - Expert revisits affected sections
  - Updates decision memo + documents
  - Re-submit for approval

---

**Documents created:** 2026-05-24  
**Branch:** manim-admesh-viz  
**Status:** Review-Ready  
**Confidence:** HIGH (Expert conviction on domain choice: 95%)
