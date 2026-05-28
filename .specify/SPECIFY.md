# SPECIFY Phase: Manim ADMESH Visualization (Issue #97)

## Problem Reframed

**Current state:** Baranja Hill attempt (scripts/gen_baranja_viz_data.py, scripts/manim_admesh_baranja.py) uses synthetic bathymetry over a real geographic boundary. **Critical flaw:** the derived size field is nearly uniform across the domain—no meaningful variation in mesh element sizes. Visualization doesn't teach the viewer how size-field computation *drives* adaptive meshing.

**Root cause:** Baranja boundary is ~1600m × ~1600m (UTM coordinates 6553k–6554k E, 5070k–5072k N), but the synthetic bathymetry was hand-crafted with ad-hoc Gaussian bumps. Small curvature variations on the boundary + mild slope/depth contrasts → miniscule size-field differences → distmesh produces nearly uniform triangles with no visible size gradation.

**Reframed goal:** Choose a *small realistic domain* where bathymetry and boundary geometry conspire to create **rich, obvious size-field variation** that the animation can show step-by-step. Domain must:

1. Have high-curvature boundary features (headland, notch, channel mouth) → size-field clustering near inflection zones
2. Have steep bathymetric slopes (shelf break, ridge flank, channel wall) → size-field refinement in steep regions
3. Be small enough (~2–5 km extent) that Manim renders detail-rich mesh without flattening zoom
4. Have *realistic* bathymetry so variation feels earned, not synthetic

**Narrative arc:** Domain intro → boundary curvature ("fine mesh at headlands") → bathymetric slope ("fine mesh on steep shelf break") → depth ("extra refinement offshore") → combined size field → initial point cloud → iterative meshing → final quality colormap.

---

## Domain Choice Justification

### Candidate 1: Synthetic Coastal Notch (PREFERRED)
**Geometry:** Straight shelf boundary with a triangular notch or embayment. Sharply curved at notch tip → high boundary curvature.  
**Bathymetry:** Linear alongshore slope + exponential cross-shelf deepening, with a topographic high (seamount) in the notch interior → steep gradients concentrated.  
**Why it works:**
- Notch curvature is *extreme* (≫ straight coastline) → size field clusters visibly at tip
- Seamount + cross-shelf slope → multiple depth/gradient "stories" in one small area
- Fully synthetic but geometrically motivated; feels like a teaching example, not contrived
- ~3 km × 2 km domain ⟹ fine mesh detail legible at Manim resolution

### Candidate 2: San Francisco Bay Mouth (Realistic, Data-Driven)
Headland + strait transition. Real NOAA bathymetry. But: full estuary ~20 km wide → Manim struggles to show local mesh refinement; risk of "uniform sludge" again.

### Candidate 3: Underwater Canyon Intersection (Realistic, Steep)
Ridge flank + canyon wall, ~8 km scale. Extremely steep slopes (>10° slopes → order-of-magnitude size variation). Risk: geometry + bathymetry together = visual cacophony; hard to disentangle curvature signal.

---

## Recommended Domain: Synthetic Notch + Seamount

**Geometry:**
- Outer boundary: half-circle on deeper side, straight shelf edge, V-notch indent on shallow side
- Notch: 60° apex angle, 1 km tip-to-opening distance → curvature at tip ~200 m⁻¹ (vs. 0 on straight edge)

**Bathymetry (physical units, meters):**
- Cross-shelf profile: 0 m at coastline, −10 m at shelf edge (2 km offshore), −100 m beyond
- Alongshore slope: flat except in notch region
- Seamount in notch interior: 4 m elevation (topographic high), Gaussian footprint ~400 m radius
- Result: slope |∇z| ranges 0.005 (open shelf) to 0.15 (seamount flank), peak 0.50 (notch corner)

**Size-field implication:**
- Straight shelf: h ≈ 0.30 (coarse, deep water, low slope)
- Shelf edge: h ≈ 0.15 (medium, shelf-break reflex)
- Notch corner: h ≈ 0.08 (fine, high curvature decay + slope)
- Seamount flank: h ≈ 0.10 (fine, steep slope)
- Factor ratio: h_min / h_max ≈ 0.27 → visible 3.7× element-size variation

---

## Narrative Arc (5-Act)

1. **Act I — Domain.** Domain boundary materializes. Labels: "high-curvature notch" (tip), "straight shelf" (edge), "open water" (exterior).

2. **Act II — Size Factors.** Three size-field components appear in sequence, each as a heatmap overlay:
   - **Boundary curvature factor** (magenta = fine): concentrates at notch corner, decays outward
   - **Bathymetric slope factor** (blue = fine): highlights seamount flank + shelf-break edge
   - **Depth factor** (cyan = fine): deepens offshore (weaker signal than curvature/slope here)
   - Viewer sees: "fine cells cluster where the domain *turns sharply* or *slopes steeply*"

3. **Act III — Combined Size Field.** Components fade; minimum is revealed (true size field). Text: "Adaptive mesh target (h): smallest where factors align."

4. **Act IV — Meshing Process.** Distmesh snapshot sequence (every 5–10 iterations) shows nodes + Delaunay edges:
   - Frame 0: random initial lattice (coarse everywhere)
   - Frames 1–N: truss relaxes; nodes compress in fine-mesh zones (notch corner denser), spread on shelf
   - Final: quasi-equilibrium, element sizes track h(x,y)
   - Overlay grid: show h(x,y) contours faintly so viewer traces node motion to size-field valleys

5. **Act V — Final Quality.** Mesh holds. Quality colormap (green = isotropic, red = skewed). Text: "Min quality Q = X, mean Q = Y" (target Q ≥ 0.6 mean). Optional: pan/zoom to notch to show local isotropy.

---

## Key Constraints & Decisions

- **Size-field computation:** Use exact ADMESH factors (boundary distance-weighted curvature, numerical gradient of bathymetry, depth clipping). Do NOT fake it; viewers must learn the real algorithm.
- **Mesh iteration sampling:** Capture every iteration but render only 15–20 key frames (every 5–10 iters, skip plateaus). ~40–60 total distmesh iterations → 5–10 sec animation.
- **Manim rendering:** Edge width inverse-proportional to local h? No—too visual clutter. Constant edge width; let node density speak.
- **Color space:** Terrain colormap (bathymetry: blue→brown) vs. size-field colormap (magenta/hot→teal/cool). Perceptually distinct so crossfade is clear.

---

## Success Criteria

Animation complete when:
1. ✓ Domain bathymetry has |∇z| ≥ 0.30 somewhere (steep enough to matter)
2. ✓ Notch geometry has curvature ≥ 100 m⁻¹ (≫ straight boundary)
3. ✓ Size-field range: h_min / h_max ≤ 0.35 (≥ 2.8× variation visible)
4. ✓ Final mesh: min_quality ≥ 0.40, mean_quality ≥ 0.65 (distmesh quality gate)
5. ✓ Animation runtime 8–12 sec (720p @ 30fps)
6. ✓ Viewer can name three size-field factors after watching
