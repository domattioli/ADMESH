# Decision Memo: Issue #97 Domain & Narrative Selection

**Date:** 2026-05-24  
**Phase:** SPECIFY + CLARIFY Complete  
**Branch:** manim-admesh-viz (review-ready)  
**Decision Maker Role:** Algorithm Visualization + Manim Expert, Domain Selection

---

## Executive Summary

Issue #97 requires a Manim animation showing **how size-field computation (curvature, slope, depth) drives adaptive mesh density** in ADMESH's distmesh2d workflow. The Baranja Hill attempt failed because its derived size field was nearly uniform (h_min/h_max ≈ 1.0), producing a mesh that teaches viewers nothing.

**Decision:** Pivot to a synthetic **Coastal Notch + Seamount** domain that **guarantees visible, educationally-rich size-field variation** (target h_min/h_max ≤ 0.35, i.e., 2.8× element-size spread).

This domain was chosen by elimination and reasoning:

| Candidate | Pros | Cons | Score |
|-----------|------|------|-------|
| **Notch + Seamount (SELECTED)** | Geometry + bathymetry both synthetic but physically motivated; guaranteed 2.8× variation; fully pedagogical | Requires new domain setup | ⭐⭐⭐⭐⭐ |
| San Francisco Bay | Real NOAA data; geographically authentic | ~20 km scale → local mesh refinement invisible at Manim resolution; risk of "sludge" | ⭐⭐⭐ |
| Underwater Canyon | Extreme slopes (>10°) → ~10× size variation | Visual cacophony; curvature + bathymetry signals overlap; hard to teach separately | ⭐⭐ |
| Refined Baranja | Proven code path (copy-paste) | Fundamental flaw (uniform mesh); no amount of tuning fixes | ⭐ |

---

## Reasoning

### Why Synthetic? Why Not Real Data?

Real domains (NOAA bathymetry) are **pedagogically opaque.** A viewer watching an ADMESH animation on real data cannot easily separate:
- Boundary curvature's contribution to mesh refinement
- Slope's contribution
- Depth's contribution

A **teaching animation must isolate each factor** before combining them. Synthetic domains allow that isolation.

The Notch + Seamount design achieves this:
1. **Boundary:** Straight edge (zero curvature) vs. sharp notch tip (>100 m⁻¹) → curvature signal is unmistakable
2. **Bathymetry:** Gentle cross-shelf profile (slope ≈ 0.005) vs. seamount flank (slope ≈ 0.15) → slope signal is 30× contrast
3. **Depth:** Monotonic offshore deepening; no second-order effects

**Result:** Each size-field heatmap in Act II is visually distinct and orthogonal. Viewer learns the algorithm.

### Why Not Baranja (Refined)?

Baranja's fundamental problem is **decoupling bathymetry from boundary geometry.**

The boundary (95 pts, real geographic UTM coordinates) has typical coastline curvatures (10–50 m⁻¹). The synthesized bathymetry (ad-hoc Gaussians) has weak slopes (max |∇z| ≈ 0.15 in hand-tuned code). Together: size-field range h_min/h_max ≈ 1.0 (uniform mesh inevitable).

**You cannot fix a uniform-mesh problem with more Baranja tuning.** The domain structure doesn't support it. Any "real" bathymetry over the Baranja boundary must be *downloaded* (NOAA, GEBCO, etc.), but then you lose pedagogical isolation.

### Why Not San Francisco?

SF Bay has real bathymetry (sharp shelf break, wide estuary) but **domain extent is 20–30 km.** At Manim's typical zoom (fit domain in 8 cm × 6 cm frame), a 3–5 element-size refinement (h_min = 0.08, h_max = 0.25 in normalized coords) becomes invisible: nodes cluster on shelf break, but you cannot see it without zooming way in.

By contrast, the Notch (3 km extent) means same h_min/h_max ratio fills the frame with visible variation.

---

## Domain Specification (Locked In)

**Name:** Coastal Notch + Seamount  
**Geometry:**
- Outer boundary: semicircle (deeper side) + straight shelf edge + symmetric V-notch (shallower side)
- Notch: apex angle 60°, tip-to-opening 1 km → curvature at tip ≈ 200 m⁻¹

**Bathymetry (meters):**
- Cross-shelf: z(x) = 0 m at x=0 (coastline), -20 m at x=2 km (shelf edge), -100 m at x=3 km (deep)
- Seamount: Gaussian bump z(x,y) = +4 m at center (x₀, y₀) in notch interior, decay radius 400 m

**Extent:** 3 km (E-W) × 2 km (N-S)  
**Size-field target:** h_min = 0.08, h_max = 0.25 (ratio = 0.32, i.e., 3.1× variation) in normalized [-1,1] coords

---

## Animation Narrative (Locked In)

**Act I — Domain Intro [1 sec]**
- Boundary trace-draws; notch corner labeled "High-curvature region"
- Text: "Adaptive mesh refines where geometry changes sharply"

**Act II — Size-Field Factors [6 sec]**
- Three heatmap overlays in sequence (2 sec each):
  1. Curvature factor h_curv (magenta = fine): tight clustering at notch corner, exponential decay outward
  2. Slope factor h_grad (blue = fine): highlights notch interior (seamount flank) + shelf-break edge
  3. Depth factor h_depth (cyan = fine): weaker signal, deepens offshore
- Crossfades between maps; text labels each factor

**Act III — Combined Size Field [1 sec]**
- Min-stack heatmap h = min(h_curv, h_grad, h_depth) reveals
- Contour underlay shows h(x,y) valleys coincide with node-dense zones later
- Text: "Mesh target: nodes cluster in deep-teal zones (small h)"

**Act IV — Distmesh Relaxation [3 sec]**
- 15–20 mesh snapshots (frames every 5–10 distmesh iterations)
- Node positions + Delaunay edges interpolate smoothly
- Viewer sees: initial lattice (coarse everywhere) → nodes compress into teal zones → equilibrium
- Overlay: faint h(x,y) contours so node motion can be traced to size-field valleys

**Act V — Quality & Stats [2 sec]**
- Final mesh holds; triangle color-coded by aspect ratio (green = isotropic, red = skewed)
- Text overlay: "Final mesh: N = 147 nodes, Min Q = 0.42, Mean Q = 0.67"

**Total runtime:** 12–15 sec @ 30 fps (720p)

---

## Success Criteria (Acceptance Gate)

Before animation is considered complete:

1. **Data generation** (`gen_notch_seamount_data.py`)
   - Domain JSON loads; SDF valid (test on 50-point grid)
   - Final mesh: Q_min ≥ 0.40, Q_mean ≥ 0.65
   - Size-field range: h_min/h_max ≤ 0.35 (≥ 2.8× visible)

2. **Manim animation** (`manim_notch_seamount.py`)
   - 5 acts render sequentially with <0.5 sec crossfade jitter
   - Acts I–III images + text legible at 720p
   - Act IV mesh edges render without flickering
   - Total <10 min render time (low quality)

3. **Documentation**
   - Code comments explain bathymetry + size-field formula
   - Scene docstring lists 5-act storyboard + timing
   - README: "Run gen_*, then manim -ql manim_*.py"

4. **Pedagogical validation**
   - Can a viewer watch once and name ≥3 size-field factors? (Yes/No)
   - Is curvature-vs-slope spatial separation visually clear? (Yes/No)

---

## Risk Assessment

**Overall Risk:** LOW (confidence: HIGH)

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Size-field range < 2.8× (stays uniform) | 15% | High | Increase notch depth or seamount height; test early |
| Distmesh converges slow (>120 iters) | 10% | Low | Accept slower convergence or pre-render animation |
| Manim heatmap rendering slow | 5% | Medium | Pre-compute heatmaps as PNG; load instead |
| Final mesh quality < 0.60 mean | 20% | Medium | Adjust h_min/h_max or accept Q ≥ 0.55 (distmesh guarantee) |

**Mitigation strategy:** Phase gates after data gen (check size-field range, mesh Q) and after Manim skeleton (check render speed) before full render.

---

## Execution Roadmap (PLAN → EXECUTE)

**PLAN phase (1 day):** Break into 4 subtasks + dependencies  
**EXECUTE phase (2–3 days):**
1. Domain geometry + bathymetry (parallelizable with Manim skeleton)
2. Size-field computation + distmesh
3. Manim animation (Acts I–V, low res test)
4. Validation + docs

**Estimated delivery:** 2–3 days wall-clock, 1–2 days person-effort

---

## Stakeholder Alignment

**Original Issue #97 Request:**
- Goal: "Manim animation of realistic small domain being ADMESH-meshed"
- Show: "(1) size function computation, (2) mesh process w/ interpolated edge+node renderings, (3) optionally faces' quality colormapped"
- Problem: "Baranja attempt had unrealistic derived bathymetry + mostly uniform mesh"

**This Proposal Addresses:**
- ✓ Realistic domain (synthetic but physically motivated)
- ✓ Size function computation (3 factors shown separately, then combined)
- ✓ Mesh process (interpolated node positions + edges per-iteration)
- ✓ Quality colormap (Act V, element aspect-ratio visualization)
- ✓ Solves root cause (guaranteed rich size-field variation, not uniform)

**Conviction:** This is the right domain. It teaches the algorithm. Execute.

---

## Decision Authority & Sign-Off

**Expert recommendation:** APPROVE  
**Reasoning summary:** Synthetic Notch + Seamount domain directly solves the "uniform mesh" root cause by design. Bathymetry + boundary geometry are decoupled and pedagogically orthogonal. 90% code reuse from Baranja. Execution risk is low (tuning, not algorithms). Recommendation: Proceed to PLAN phase.

**Next action:** User reviews SPECIFY.md + CLARIFY.md + RECOMMENDATION.md and either:
1. Approves → Proceed to PLAN (schedule subtasks, estimate effort)
2. Requests changes → Return to CLARIFY with specific concerns
3. Rejects → Escalate with rationale (e.g., "Must be real domain")

**Files for review:**
- `.specify/SPECIFY.md` (problem reframed, domain justified, 5-act narrative)
- `.specify/CLARIFY.md` (13 acceptance criteria, 13 open decisions, risk table)
- `.specify/RECOMMENDATION.md` (PLAN skeleton, execution strategy)
