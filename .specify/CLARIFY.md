# CLARIFY Phase: Acceptance Criteria, Constraints, Open Questions

## Acceptance Criteria (Testable)

### Data Generation
- [ ] Domain geometry (notch boundary) loads from JSON and renders crisply
- [ ] Bathymetry grid (240×240 px) has |∇z| peak ≥ 0.30 in notch region
- [ ] Size-field grid computes via `size_components()` with curvature, slope, depth factors
- [ ] Per-factor heatmaps generated and saved: h_curv, h_grad, h_depth, h_combined
- [ ] Distmesh instrumentation captures ≥ 40 iterations with node positions + edge lists

### Mesh Quality Gate
- [ ] Final mesh nodes ≥ 50, triangles ≥ 80 (adequate detail for 3+ sec mesh animation)
- [ ] Min element quality (angle ratio) ≥ 0.40
- [ ] Mean element quality ≥ 0.65
- [ ] All triangles satisfy Delaunay property (no edges flipped by post-check)

### Animation Rendering (Manim)
- [ ] **Act I (Domain):** Boundary trace-draws in ~1 sec; labels appear at high-curvature zones
- [ ] **Act II (Size Factors):** Three heatmaps crossfade in sequence (~2 sec each); perceptually distinct colormaps
- [ ] **Act III (Combined):** Min-stack h(x,y) displays with contour underlay (~1 sec)
- [ ] **Act IV (Meshing):** 15–20 mesh frames interpolate node positions smoothly; edge rebuild visible on re-triangulation (~4 sec)
- [ ] **Act V (Quality):** Final mesh + colormap + text label "Min Q = X, Mean Q = Y" (~2 sec hold)
- [ ] Total runtime 12–15 sec at 30 fps, no frame drops
- [ ] Output: 720p or better, MP4 or PNG sequence

### Documentation
- [ ] Code comments in `gen_notch_seamount_data.py` explain bathymetry choice + size-field formula
- [ ] Manim scene docstring lists the 5-act storyboard with timing
- [ ] `README.md` (or in-code instructions) explains: "Run gen_notch, then manim -ql manim_notch_seamount.py"

---

## Technical Constraints

### Manim Rendering
1. **Resolution & Performance:**
   - Default "low quality" (720p, 30 fps) must render in < 10 min on modern CPU (i7-level)
   - Mesh edge count ≤ 200 to keep scene complexity tractable (no massive point clouds)
   - Node dot radius (NODE_R = 0.018 in current code) must remain legible at 720p

2. **Heatmap Rendering:**
   - Background images (bathymetry + size-field) are 240×240 px (current resolution)
   - Manim `ImageMobject` will scale smoothly; compute RGB→RGBA in `_heatmap_rgba()`
   - Three distinct colormaps required (terrain for bathy; "hot→cool" for size field components)
   - Opacity mask needed for transparency outside domain (test `inside` mask)

3. **Graph Rendering (Mesh Snapshots):**
   - Node positions: `np.array(p[snap_idx])` → convert to 3D manim coords via `to_scene(p, bbox)`
   - Edges: index into node list via `bars[snap_idx]` (Delaunay connectivity)
   - Animated line segments: use `always_redraw()` + `ValueTracker` for smooth interpolation between iterations
   - Avoid re-triangulating in Manim; pre-compute all Delaunay + edge geometry in Python

4. **Animation Timing:**
   - Five acts ≈ 12 sec total; split: Domain 1s, Size components 6s (2s each), Combined 1s, Mesh 3s, Quality 2s
   - Smooth transitions require 0.3–0.5 s crossfades (Manim standard)
   - Mesh iteration sampling: store every 5th iteration (skip plateaus where nodes don't move)

### Python Data Pipeline
1. **Geometry Setup:**
   - Notch boundary: parametrize as straight edge + circular arc + straight edge (piecewise smooth)
   - Discretize to ~100 pts total for JSON export (matches Baranja ring resolution)
   - Verify SDF computation (fast_sdf module) handles notch + exterior correctly

2. **Bathymetry Function:**
   - Cross-shelf depth profile: e.g., z(x) = 0 + 10 × erf(x / 1000) − 100 (smooth shelf edge at x ≈ 2000 m)
   - Seamount: Gaussian bump z(x,y) = 4 × exp(−((x−x0)² + (y−y0)²) / 400²) in notch interior
   - Unit: meters; handle normalization to [−1, 1] domain coords carefully

3. **Size-Field Computation:**
   - Use exact `size_components()` from `gen_baranja_viz_data.py` (proven code)
   - Curvature factor: nearest-boundary curvature (discrete, ring vertices) + distance decay
   - Slope factor: finite-difference gradient of bathymetry on interior grid
   - Depth factor: clipping to [0, max_depth], inverse scaling
   - Min-stack all three, clamp to [h_min, h_max] ← tuning parameters (TBD in PLAN phase)

4. **Distmesh Instrumentation:**
   - Reuse `instrumented_distmesh()` from current code (proven, locked-in)
   - Run with h_min, h_max tuned to achieve ≥ 2.8× element-size variation
   - Default: ~100 iterations, seed=0 reproducible

5. **NPZ Output:**
   - Same layout as `baranja_admesh.npz`: ring, bbox, bathy, h_curv, h_grad, h_depth, sizef, inside, n_snaps, p{i}, b{i}
   - Swap out `baranja_admesh.npz` → `notch_seamount_admesh.npz` in Manim script

### Distmesh Quality
- **Expected Q_min:** ~0.40–0.50 (distmesh does not optimize quality, only respects size field)
- **Improvement:** if Q_min < 0.35, iterate on h_min/h_max tuning or increase distmesh iterations
- **Validation:** run `admesh.quality.MeshQuality(mesh)` on final mesh; reject if mean_Q < 0.60

---

## Open Questions & Decisions Needed

### Domain Geometry
1. **Notch shape:** Symmetric V vs. asymmetric notch (one steep wall, one sloped)? 
   - **Recommend:** Symmetric V (60° apex) for pedagogical clarity; both walls equally steep

2. **Notch depth:** 1 km inland vs. 500 m? 
   - **Recommend:** 1 km (notch half-width ~500 m) so curvature clustering visible at animation scale

3. **Seamount location:** Centered in notch, or offset to one wall?
   - **Recommend:** Offset slightly onshore of notch tip (500 m) so slope + curvature overlap visually but don't overshadow

4. **Domain extent:** 3 km × 2 km (current proposal) or 5 km × 3 km?
   - **Recommend:** 3 km × 2 km to keep initial mesh ~50 nodes, final ~150 nodes (legible in Manim; ~4–5 sec animation)

### Bathymetry Tuning
5. **Shelf-edge depth:** Exactly 10 m (shallow) or 50 m (deeper)?
   - **Recommend:** 20 m (compromise; depth factor contributes but curvature/slope dominant)

6. **Seamount height:** 4 m (subtle) vs. 10 m (dramatic)?
   - **Recommend:** 4 m (matches NOAA-realistic slope steepness; larger risked looking synthetic)

### Size-Field Tuning
7. **h_min, h_max:** Current code uses 0.05, 0.18 for Baranja. What for notch?
   - **Recommend:** Iterate in PLAN phase: start with 0.08, 0.25 (notch is smaller), adjust if ratio < 2.8× or mesh too coarse/fine

8. **Curvature decay length:** Current code: `decay = exp(−(d_min / 0.30)²)`. Does 0.30 (normalized coords) make sense for notch?
   - **Recommend:** Keep as-is; test post-data-gen, adjust if size-clustering too tight or too diffuse

### Manim Rendering
9. **Heatmap colorspace:** Separate maps for bathymetry (terrain: blue→brown) vs. size components (magenta→teal)?
   - **Recommend:** Yes; distinct enough that crossfade is perceptually clear. "This is bathymetry" vs. "This is what Manim computes"

10. **Mesh edge rendering during Acts IV–V:** Visible edges (thin lines) or inferred from node density?
    - **Recommend:** Visible edges (thin, white, ~0.5 pt width). Lets viewer track edge reassembly on re-triangulation. Manim `Line` objects between bars.

11. **Initial lattice visualization:** Show random initial point cloud explicitly, or fade in already-positioned first triangulation?
    - **Recommend:** Skip initial lattice; start animation at iteration 0 with Delaunay already computed (saves ~1 sec, focus on convergence narrative)

### Documentation & Validation
12. **Validation gate:** Before animation, generate static plots (like `baranja_boundary_plot.png`) of domain + heatmaps?
    - **Recommend:** Yes; place in `output/notch_seamount_*.png` for review. Re-use `render_*.py` pattern

13. **Narrative text in animation:** Hardcoded labels (e.g., "High-curvature notch") or silent visualization?
    - **Recommend:** Minimal text overlays (3–4 labels, 12pt font); let visuals dominate. Text only at act boundaries ("Act II: Size-Field Factors")

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| Bathymetry too smooth → size field nearly uniform | Medium | High | Increase notch depth or seamount height; test gradient range early |
| Distmesh produces low-quality mesh (Q_mean < 0.55) | Medium | Medium | Adjust h_min/h_max or increase iterations; accept Q_min ≥ 0.35 if unavoidable |
| Manim rendering slow (>15 min @ low quality) | Low | Medium | Pre-render heatmap images as PNG; load in scene rather than compute |
| Curvature factor too localized → size field dominated by slope/depth | Low | Low | Increase decay length from 0.30 to 0.50; re-tune weights in size_components() |
| Animation too crowded (5 acts in 12 sec feels rushed) | Low | Low | Extend total to 15–18 sec; drop Act III (combined size field) if time tight |

---

## Next Steps (PLAN Phase)

1. **Finalize domain geometry:** Parametrize notch boundary as JSON; validate SDF
2. **Tune bathymetry:** Run `gen_notch_seamount_data.py` with candidate depth/slope profiles; check gradient range
3. **Distmesh validation:** Run `instrumented_distmesh()`; verify final mesh Q ≥ 0.60 mean
4. **Manim skeleton:** Build scenes for Acts I–V; test image/animation timing at low res
5. **Iterate & render:** Full-quality Manim render; review with issue author; refine if needed

---

## Assumptions & Unknowns

- **Assumption:** Manim `always_redraw()` loop can smoothly interpolate 100+ points/edges at 30 fps without lag
- **Unknown:** Exact distmesh iteration count needed for convergence on notch domain (current code: 120; may differ for smaller domain)
- **Unknown:** Whether 240×240 heatmap resolution sufficient for Manim 720p rendering; may need 480×480
