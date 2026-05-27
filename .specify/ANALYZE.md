# ANALYZE: Technical Deep-Dive & Risk Assessment (Issue #97)

**Document purpose:** Pre-execute analysis of technical constraints, resource bottlenecks, known risks, and fallback options.  
**Audience:** Developer executing TASKS.md; stakeholders reviewing feasibility.

---

## Part I: Data Generation Pipeline (Tasks 2.1–2.3)

### A. Distmesh Instrumentation & Iteration Count

**Problem:** How many iterations needed for convergence on notch domain?

**Reference baseline (Baranja):**
- Domain extent: ~1.6 km × 1.6 km (real UTM coords)
- Initial mesh: ~50 nodes (h0-seeded random)
- Convergence: ~120 iterations (documented in gen_baranja_viz_data.py)
- Node count growth: 50 → ~150 nodes over 120 iterations
- Edge count: ~250 → ~400 edges

**Notch domain (proposed):**
- Domain extent: ~3 km × 2 km (slightly larger than Baranja)
- Initial mesh: ~50 nodes (same seeding strategy)
- Expected iterations: 100–150 (similar to Baranja; notch may converge slightly faster due to smaller interior depth)
- Node count projection: 50 → ~150–200 nodes

**Cost analysis (compute time per iteration):**
1. **SDF evaluation:** O(n log n) where n = grid points (240×240 = 57,600)
   - Per iteration: negligible; computed once at startup
2. **Force calculation & repulsion:** O(n · m) where n = nodes, m = edges
   - Per iteration: ~O(150 · 300) = ~45,000 operations
   - CPU time: ~10–20 ms per iteration (on modern i5+)
3. **Delaunay re-triangulation:** O(n log n) via scipy.spatial.Delaunay
   - Per iteration: ~10–30 ms (n = 50–200 points)
4. **Snapshot recording:** O(m) to copy node positions and edge list
   - Per iteration: negligible

**Total per-iteration cost:** ~30–50 ms on modern CPU  
**Total for 120 iterations:** ~1–2 hours wall-clock

**Memory cost:**
- Per snapshot: nodes (50–200 × 2 floats) + edges (250–400 × 2 ints)
- ~2 KB per snapshot
- 120 snapshots × 2 KB = 240 KB (negligible; NPZ compression brings to <100 KB)

**Contingency:** If iterations > 150, either:
1. Domain is too "stiff" (high edge length variations) → increase H_MAX slightly, re-run
2. Distmesh algorithm is not converging → acceptable (may have plateau; store every 5th iteration to reduce IO)

### B. Bathymetry Gradient Computation

**Challenge:** Achieve |∇z| ≥ 0.30 somewhere; avoid artificial spikes.

**Approach:**
- Cross-shelf profile: smooth exponential transition (e.g., erf-based)
- Seamount: Gaussian bump (smooth everywhere, gentle slopes on flanks)
- Gradient: finite-difference 3-point stencil (centered difference for smoothness)

**Risk: Gradient too weak**
- If shelf profile is too gentle: |∇z|_max < 0.20
- Mitigation: Increase shelf-break steepness (slope angle from 5° to 10°) or decrease shelf-edge distance (move break from 2 km to 1.5 km)
- Check: Task 1.3 gate validates max(|∇z|) ≥ 0.30 before proceeding

**Risk: Gradient too noisy**
- Cause: Undersmoothed bathymetry function (e.g., piecewise linear instead of smooth)
- Effect: Size-field becomes jagged; distmesh harder to converge
- Mitigation: Use smooth function (erf, sigmoid, or Gaussian for seamount); avoid sharp corners

**Risk: Seamount elevation insufficient**
- If seamount height < 2 m: gradient contribution negligible
- Current: 4 m elevation → ~0.10 slope on 400 m radius flank (acceptable)
- If slope still weak: increase to 6–8 m (trade-off: must stay realistic)

### C. Size-Field Computation & Factor Weighting

**ADMESH size-field algorithm (from code reference):**
```
h_curv(x,y) = h_max / (1 + 1.2 * κ_near * exp(-(d_min / 0.30)^2))
h_grad(x,y) = h_max / (1 + 2.5 * |∇z|)
h_depth(x,y) = h_max / (1 + 0.5 * z / z_deep) if z < 0 else h_max
h(x,y) = min(h_curv, h_grad, h_depth), clipped to [h_min, h_max]
```

**Factor dominance (expected for notch domain):**
1. **Boundary curvature (h_curv):** Most significant
   - Notch apex: curvature ~200 m⁻¹ → h_curv ≈ 0.08–0.10 (fine)
   - Straight shelf: curvature ~0 → h_curv ≈ 0.25 (coarse)
   - Decay length (0.30 normalized coords) = ~1 km physical → size field concentrated at notch, decays over 1–2 km radius
2. **Bathymetric slope (h_grad):** Secondary signal
   - Shelf edge: |∇z| ≈ 0.10–0.15 → h_grad ≈ 0.15–0.20
   - Seamount flank: |∇z| ≈ 0.08–0.12 → h_grad ≈ 0.17–0.22
   - Open shelf: |∇z| ≈ 0.01 → h_grad ≈ 0.24
3. **Depth (h_depth):** Weakest signal
   - Offshore: z ≈ −100 m → h_depth ≈ 0.12
   - Shelf: z ≈ −20 m → h_depth ≈ 0.22
   - Coastline: z ≈ 0 → h_depth ≈ 0.25

**Expected min/max ratio:**
- h_min ≈ 0.08 (notch apex, all factors aligned)
- h_max ≈ 0.25 (open shelf, no constraints)
- Ratio ≈ 0.32 → **2.8× variation** ✓ (meets criterion)

**Tuning knobs (for Tasks 2.1 & 2.3):**
- `H_MIN`, `H_MAX`: directly set size-field clipping range
- `DECAY_LENGTH`: 0.30 default; increase to 0.50 if clustering too tight, decrease to 0.15 if too diffuse
- Curvature weight (1.2) & slope weight (2.5): hardcoded in Baranja code; do not change without re-validation

**Risk: Size-field nearly uniform**
- Root cause: all factors weak (low curvature, shallow shelf, little variation)
- Symptom: h_min / h_max > 0.40 (< 2.5× variation)
- Mitigation (Task 2.3 gate failure):
  1. Increase notch apex angle (60° → 90° sharper)
  2. Deepen shelf-break transition (0.10 → 0.20 slope)
  3. Increase seamount height (4 m → 8 m)
  4. Decrease h_max (0.25 → 0.20) or increase h_min target slightly

---

## Part II: Manim Rendering Pipeline (Tasks 3.1–3.5)

### A. Heatmap Image Generation & Performance

**Challenge:** Render 240×240 grids as color images; interpolate to Manim scene size (~600 px width @ 720p).

**Current approach (from Baranja):**
```python
def _heatmap_rgba(field, inside, cmap):
    # 1. Normalize field to [0, 1]
    f = field[inside]
    lo, hi = np.percentile(f, [2, 98])
    n = np.clip((f - lo) / (hi - lo), 0, 1)
    # 2. Apply colormap
    rgb = cmap(n)
    # 3. Build RGBA: solid inside, transparent outside
    rgba = np.zeros(field.shape + (4,), dtype=np.uint8)
    rgba[..., :3] = (rgb * 255).astype(np.uint8)
    rgba[..., 3] = np.where(inside, 235, 0)
    return np.flipud(rgba)
```

**Performance analysis:**
- Per-image time: ~100 ms (field normalize, colormap interpolation, RGBA packing)
- Total for 5 images (bathy + h_curv + h_grad + h_depth + h_combined): ~500 ms
- Negligible vs. Manim rendering time

**Colormap choice (perceptual distinctness):**
1. **Bathymetry:** Terrain (blue → brown → white)
   - Blue (0, 0.05, 0.35) → Green (0.30, 0.70, 0.55) → Brown (0.55, 0.35, 0.20) → White (0.95, 0.95, 0.92)
   - Familiar to geoscientists; depth = blue tone
2. **Size-field components:** Hot → Cool (magenta → teal)
   - Fine cells (low h, hot): (0.95, 0.15, 0.55) magenta
   - Coarse cells (high h, cool): (0.10, 0.25, 0.35) teal
   - Distinct from terrain colormap; crossfade obvious

**Risk: Image scaling artifacts at 720p**
- Current: 240×240 source scaled to ~600 px width in Manim
- Scaling factor: 2.5× (mild upsampling)
- Effect: bilinear interpolation; no heavy artifacts expected
- Mitigation: if pixelation visible, increase source grid res to 360×360 (Task 2.1 parameter)

### B. Mesh Animation Complexity

**Challenge:** Animate node positions + edge topology over 15–20 snapshots smoothly at 30 fps.

**Node animation via ValueTracker:**
```python
tracker = ValueTracker(0.0)
def nodes_redraw():
    t = tracker.get_value()
    i = int(np.floor(t))
    j = min(i + 1, n_frames - 1)
    frac = t - i
    P = scene_pts[i] * (1 - frac) + scene_pts[j] * frac  # linear interpolation
    return VGroup(*[Dot(pt, radius=NODE_R, color=YELLOW) for pt in P])
live_nodes = always_redraw(nodes_redraw)
self.play(tracker.animate.set_value(n_frames - 1), run_time=4.0, rate_func=lambda x: x)
```

**Performance analysis:**
1. **Node re-drawing per frame:**
   - 200 nodes × Dot creation = ~200 mobject operations per frame
   - Manim overhead: ~30–50 ms per frame
2. **Edge re-triangulation per frame:**
   - Delaunay already computed; just index into bars arrays
   - 300 edges × Line creation = ~300 mobject operations per frame
   - Total per-frame overhead: ~50–100 ms
3. **Total for 4 sec mesh animation @ 30 fps:**
   - 120 frames × 100 ms = 12 seconds overhead + Manim rendering
   - Expected total Manim render time: 30–60 minutes @ 720p (baseline ~20 min for static scenes)

**Risk: Frame rate drops during mesh animation**
- Symptom: ~always_redraw()~ makes rendering slow (exponential path creation)
- Root cause: Dot/Line creation per frame is expensive in Manim
- Mitigation:
  1. Pre-compute all mobjects once (trade memory for speed)
  2. Use lower node count (downsample mesh to 100 nodes max)
  3. Reduce frame rate to 15 fps for mesh act only
  4. Pre-render mesh animation to PNG sequence, load as video in main scene
- **Recommendation:** Monitor low-res render (Task 3.4); if >10 min, migrate to PNG pre-render

### C. Crossfade Timing & Perceptual Flow

**Act II (Size Components) timing challenge:**
- 3 heatmaps × (fade-in 1s + hold 2s + fade-out 0.5s) = 10.5 sec
- Specification requires 5–6 sec total for Acts II–III
- **Resolution:** Use crossfades instead of sequential (reduce 0.5 sec per transition):
  - Act II heatmap 1: fade in 1s, hold 2s
  - Crossfade 1→2: fade out 0.5s simultaneous with fade in 0.5s = net 0.5s
  - Hold 2s
  - Repeat for 2→3
  - Total: 1 + 2 + 0.5 + 2 + 0.5 + 2 = **8 sec** (acceptable)

**Crossfade implementation:**
```python
self.play(FadeOut(cur_img), FadeIn(new_img), run_time=0.5)
cur_img = new_img
self.wait(2.0)
```

### D. Memory & Disk I/O

**Manim scene construction memory:**
- Initial load: NPZ (~3 MB), load all arrays into RAM
- Heatmap images: 5 × (240×240 × 4 bytes RGB + 4 bytes A) = ~1.15 MB
- Node snapshots: 15–20 × (150 nodes × 3 floats) = ~27 KB
- Total in-memory: ~10 MB (negligible on modern systems)

**Disk I/O:**
- Read NPZ once at scene init
- Write MP4 incrementally (Manim pipes to ffmpeg)
- Total output: 30–50 MB for 12–15 sec @ 720p (standard for Manim)

---

## Part III: Known Risks & Fallback Options

### Risk 1: h_min / h_max < 2.5× (Size-field too uniform)

**Probability:** Medium (depends on bathymetry smoothness)  
**Impact:** Animation doesn't teach size-field variation; success criterion fails  

**Fallback A (increase domain heterogeneity):**
1. Deepen notch apex (currently 1 km → 1.5 km)
2. Increase seamount elevation (4 m → 8 m)
3. Steepen shelf edge (shelf-break angle 5° → 15°)
- **Cost:** 1–2 hours re-tuning geometry + 4–6 hours re-running data gen
- **Likelihood of success:** High (multiple knobs to turn)

**Fallback B (adjust h_min/h_max directly):**
1. Decrease h_min (0.08 → 0.06) OR increase h_max (0.25 → 0.30)
2. Compensate to maintain distmesh convergence
- **Cost:** 30 min parameter tuning + 4–6 hours re-running
- **Likelihood of success:** Medium (may cause mesh quality issues if ratio too extreme)

**Fallback C (accept marginal ratio):**
1. If 2.0×–2.5× ratio achievable: "Acceptable variant, demonstrates concept even if not ideal"
2. Adjust success criterion to h_min/h_max ≤ 0.40 (≥ 2.5× variation)
- **Cost:** None (re-frame expectation)
- **Likelihood of stakeholder acceptance:** Low (defeats pedagogical purpose)

**Recommendation:** Implement Fallback A if initial ratio < 2.5×.

---

### Risk 2: Distmesh Slow Convergence (>150 iterations)

**Probability:** Low (based on Baranja precedent)  
**Impact:** Data generation takes 8+ hours; delays animation work  

**Fallback A (accelerate convergence):**
1. Increase h_max slightly (0.25 → 0.30) to relax force constraints
2. Reduce distmesh iteration cap (120 → 100) if node motion < 1% threshold
3. Use warm-start: initialize from Baranja mesh + warp to notch domain
- **Cost:** 2–3 hours coding warm-start + 4–6 hours re-running
- **Likelihood of success:** High

**Fallback B (accept longer compute):**
1. Run overnight (8+ hours is acceptable if started Friday evening)
2. Checkpoint every 10 iterations (allow resume if interrupted)
- **Cost:** Waiting time (no developer time)
- **Likelihood of success:** High (no risk of failure)

**Fallback C (downsample mesh):**
1. Reduce initial grid resolution (240×240 → 180×180) to speed SDF computation
2. Reduce distmesh target node count (150 → 100 nodes)
- **Cost:** 30 min re-tuning, 4–6 hours re-running
- **Likelihood of success:** High; trade-off: heatmap resolution lower, may affect Act II clarity

**Recommendation:** Monitor Task 2.2 runtime; if > 8 hours by iteration 80, implement Fallback A or B.

---

### Risk 3: Mesh Quality Low (Q_mean < 0.55)

**Probability:** Medium (distmesh optimizes size-field adherence, not quality)  
**Impact:** Visual artifact (many sliver triangles); doesn't block animation, but pedagogically weak  

**Fallback A (smooth size-field):**
1. Increase h_min (0.08 → 0.10) OR decrease h_max (0.25 → 0.20) to reduce ratio extremity
2. Increase decay-length (0.30 → 0.50) to smooth transitions
- **Cost:** 30 min tuning + 4–6 hours re-running
- **Likelihood of success:** High (smoother h → better distmesh quality)

**Fallback B (post-process mesh):**
1. Apply admesh.quad_prep.smooth_for_quadrangulation() to final mesh (gentle smoothing)
2. Re-evaluate quality after smoothing
- **Cost:** 1–2 hours coding + <1 hour re-running
- **Likelihood of success:** Medium (smoothing may degrade size-field adherence)

**Fallback C (accept threshold):**
1. If Q_mean ≥ 0.60, pass (meets success criterion)
2. If Q_mean 0.55–0.60, marginal pass (note in validation, accept risk)
3. If Q_mean < 0.55 AND Q_min ≥ 0.35, acceptable (distmesh trade-off is OK)
- **Cost:** None
- **Likelihood of stakeholder acceptance:** Depends (pedagogical impact low; visuals matter more than metrics)

**Recommendation:** Monitor Task 2.3 quality metrics; if Q_mean < 0.55, implement Fallback A or C.

---

### Risk 4: Manim Rendering Slow (>1 hour @ 720p)

**Probability:** Low (Baranja rendered in ~30–40 min; notch slightly larger but similar structure)  
**Impact:** Animation blocking; delays final deliverable  

**Fallback A (optimize heatmap rendering):**
1. Pre-compute heatmaps as PNG files (outside Manim)
2. Load via ImageMobject(path) instead of on-the-fly computation
3. Expected speedup: ~5–10 minutes (remove colormap interpolation cost)
- **Cost:** 1 hour Python script writing + 30 min per test render
- **Likelihood of success:** High

**Fallback B (reduce mesh detail):**
1. Downsample mesh snapshot sampling (every 5th → every 10th iteration)
2. Reduce node count to 100 max (down-resample distmesh output)
3. Expected speedup: ~5–10 minutes (fewer mobjects to create per frame)
- **Cost:** 30 min tuning + 4–6 hours re-running data gen
- **Likelihood of success:** High; trade-off: mesh animation less smooth

**Fallback C (lower resolution):**
1. Render at 720p but 15 fps (instead of 30 fps)
2. Expected speedup: ~50% (half the frames)
3. Visual impact: acceptable for pedagogical animation (slight choppiness unnoticeable)
- **Cost:** 5 min config change
- **Likelihood of success:** High

**Fallback D (render overnight):**
1. Submit Manim render as background job (weekend)
2. Check result Monday
- **Cost:** Waiting time
- **Likelihood of success:** High (no risk)

**Recommendation:** Plan for 45–60 min render as baseline; implement Fallback A if > 60 min observed in Task 3.4.

---

### Risk 5: Animation Feels Rushed (5 Acts in <10 sec)

**Probability:** Low (12–15 sec spec allows room)  
**Impact:** Viewer can't follow narrative; learning outcome reduced  

**Fallback A (extend duration):**
1. Increase total to 15–18 sec
2. Hold size-component heatmaps longer (2 → 2.5 sec each)
3. Hold mesh animation longer (4 → 5 sec)
4. Add intermediate transitions (0.3 → 1.0 sec crossfades)
- **Cost:** ~30 min Manim script edits
- **Likelihood of success:** High

**Fallback B (drop one act):**
1. Merge Acts II + III: show 2 key factors (curvature + slope) + combined, drop depth factor
2. Save 2 sec
3. Visual impact: still teaches size-field variation (curvature & slope are dominant)
- **Cost:** ~15 min Manim script edits
- **Likelihood of success:** Medium (pedagogical compromise)

**Fallback C (speed up non-critical acts):**
1. Act I (domain): 1.5 → 1.0 sec
2. Act V (quality hold): 2.0 → 1.0 sec
3. Save 1.5 sec without affecting learning
- **Cost:** ~10 min Manim script edits
- **Likelihood of success:** High

**Recommendation:** Monitor Task 3.4 low-res render for pacing; if rushed, implement Fallback A (extend) or C (trim fat).

---

## Part IV: Resource Estimation Summary

### Compute Resources

| Phase | Task | Component | Duration | Notes |
|-------|------|-----------|----------|-------|
| Data Gen | 2.1–2.2 | SDF + bathymetry grids | 2 hours | One-time, parallelizable per grid cell |
| Data Gen | 2.1–2.2 | Distmesh loop (120 iters) | 2–4 hours | ~30 ms/iteration; bottle neck likely here |
| Animation | 3.4 | Low-res render (360p, 15 fps) | 5 min | Quick feedback loop |
| Animation | 3.5 | Full-res render (720p, 30 fps) | 30–60 min | Main rendering job; may be optimization target |
| **Total** | — | — | **4–6 hours compute** | Can run overnight |

### Developer Time

| Phase | Tasks | Activity | Duration | Notes |
|-------|-------|----------|----------|-------|
| Setup | 1.1–1.3 | Parametrize domain, bathymetry | 2–4 hours | Mostly parameter tuning; some SDF validation |
| Data Gen | 2.1–2.3 | Script writing, validation | 2–3 hours | 90% copy-paste; gate-check logic |
| Animation | 3.1–3.3 | Manim skeleton + mesh animation | 2–3 hours | 95% copy-paste; ValueTracker wiring |
| Animation | 3.4–3.5 | Low-res test + full render | 2–3 hours | Monitoring, timing adjustments, re-renders |
| Validation | 4.1–4.3 | Documentation, validation checks, commit | 1–2 hours | Checklist, plots, PR creation |
| **Total** | — | — | **10–16 hours** | ~2–3 days @ 6 hours/day |

### Storage

| Item | Size | Notes |
|------|------|-------|
| Domain JSON | 5 KB | Text; negligible |
| NPZ (compressed) | 2–5 MB | Binary; gzipped snapshots |
| PNG validation plots | <2 MB | 20 images @ 100 KB avg |
| MP4 (720p, 12–15 sec) | 30–50 MB | H.264 codec; standard bitrate |
| **Total** | **~40–60 MB** | Fits in single repo commit |

---

## Part V: Technical Dependencies & Assumptions

### External Dependencies (must verify)

1. **ADMESH library:**
   - `admesh._fast_sdf` module (SDF computation)
   - `admesh.quality.MeshQuality` class (mesh quality analysis)
   - `admesh.in_polygon` (point-in-polygon, used for inside mask)
   - Status: Verified present in repo

2. **Manim library:**
   - Version: 0.18+ (required for stable `always_redraw`)
   - Resolution: tested at 720p, 30 fps
   - Status: Assumed installed; verify in Task 3.1

3. **SciPy:**
   - `scipy.spatial.Delaunay` (mesh generation)
   - `scipy.interpolate.griddata` (optional, not used in current design)
   - Status: Standard dependency; verified

4. **NumPy + Python 3.10+:**
   - Status: Standard environment

### Assumptions (must monitor)

1. **Distmesh convergence:** ≤ 150 iterations (based on Baranja 120 iter precedent)
   - Risk: If > 150, may need algorithmic tuning or warm-start
2. **Size-field reachability:** h_min/h_max ≤ 0.35 achievable with 1 km notch depth
   - Risk: If < 2.5× observed, domain may need redesign
3. **Manim rendering speed:** <1 hour @ 720p (based on Baranja 30–40 min)
   - Risk: If > 1 hour, may need optimization (pre-render PNGs, reduce mesh detail)
4. **Mesh quality acceptable:** Q_mean ≥ 0.60 with h_min/h_max ≤ 0.35
   - Risk: Distmesh may struggle with extreme size variations; may accept Q_mean ≥ 0.55
5. **Fast SDF / `always_redraw` stable:** No bugs in Manim 0.18+
   - Risk: Low (both battle-tested in Baranja)

---

## Part VI: Quality Gates & Go/No-Go Criteria

### M2: Data Generation Complete (Task 2.3)

**Go criteria (proceed to animation):**
- ✓ h_min/h_max ≤ 0.35 (≥ 2.8× variation)
- ✓ Q_mean ≥ 0.60, Q_min ≥ 0.40
- ✓ ≥ 40 distmesh iterations recorded
- ✓ Final mesh ≥ 50 nodes, ≥ 80 triangles

**Marginal (proceed with caution):**
- Q_mean 0.55–0.60 (acceptable trade-off)
- h_min/h_max 0.35–0.40 (slightly weaker variation)

**No-go (iterate or fallback):**
- h_min/h_max > 0.40 → Fallback A or B (redesign bathymetry or tuning)
- Q_mean < 0.55 → Fallback A (smooth size-field)
- Iteration count > 150 → Fallback B (accept slower compute or warm-start)

---

### M3: Manim Low-Res Render (Task 3.4)

**Go criteria:**
- ✓ Render completes in < 10 min @ 360p, 15 fps
- ✓ All 5 acts present and timed sensibly (no rushing)
- ✓ Heatmaps render crisply; colors perceptually distinct
- ✓ Mesh animation fluent (no popping, smooth interpolation)

**Marginal (proceed with minor adjustments):**
- Render 10–12 min (slightly slow; Fallback A pre-render PNGs)
- Animation feels slightly rushed (Fallback A extend, Fallback C trim)

**No-go (blocked animation):**
- Render > 15 min (too slow; implement Fallback A or B)
- Mesh animation choppy (Fallback B downsample mesh)
- Heatmap colors indistinct (re-tune colormaps)

---

### M4: Final MP4 (Task 3.5)

**Acceptance criteria (from SPECIFY):**
1. ✓ Duration 12–15 sec @ 30 fps (no frame drops)
2. ✓ Resolution 720p or better
3. ✓ All 5 acts play seamlessly
4. ✓ Heatmaps and mesh animation visible and clear
5. ✓ No artifacts (black borders, glitches, green cast)

**Fallback:** If any criterion fails:
1. Adjust Manim scene (Act timing, color tweak)
2. Re-render (full quality, 30–60 min)
3. Validate again

---

## Part VII: Comparison to Baranja Baseline

| Aspect | Baranja | Notch-Seamount | Risk |
|--------|---------|-----------------|------|
| Domain size | 1.6 × 1.6 km | 3 × 2 km (25% larger) | Slightly longer compute; Manim scales OK |
| Boundary complexity | Real UTM coords; large | Synthetic V-notch; small | Simpler; easier to parametrize; lower SDF cost |
| Bathymetry | 3 Gaussians + quadratic | Smooth shelf + Gaussian seamount | Smoother; better for distmesh |
| Size-field variation | Weak (~1.5×) | Strong (~2.8×) | **Key improvement; higher distmesh iteration count** |
| Distmesh iterations | 120 | 100–150 (projected) | Comparable to Baranja |
| Final mesh nodes | ~150 | ~150–200 | Slightly larger; Manim handles OK |
| Manim render time | 30–40 min | 30–60 min | Acceptable; may need optimization if > 60 min |
| Success criteria met | Pedagogical gap | ✓ All 6 criteria | **Lower execution risk** |

---

## Part VIII: Recommendations

### Priority 1 (Essential)
1. **Task 1.2 domain JSON validation:** Must pass SDF spot-check before proceeding (prevents cascading failures)
2. **Task 2.3 quality gate:** Mandatory check; reject if h_min/h_max > 0.40 (replan bathymetry)
3. **Task 3.4 low-res test:** Mandatory; catch timing/pacing issues before expensive full render

### Priority 2 (Strongly Recommended)
1. **Pre-generate heatmap PNGs (Fallback A):** If Task 3.4 render > 10 min, implement to save 10–15 min per re-render
2. **Monitor distmesh iteration count (Task 2.2):** If > 120 by iter 80, implement warm-start or h_max tuning
3. **Checkpoint NPZ data:** Save partial snapshots every 20 iterations (allow resume if interrupted)

### Priority 3 (Nice-to-Have)
1. **Mesh downsampling option:** Prepare code to reduce node count 150 → 100 if rendering stays slow
2. **Alternative colormaps:** Pre-test 2–3 size-field colormaps; fall back if current palette lacks contrast
3. **Timing sensitivity analysis:** Log render time vs. node count, edge count; inform future optimizations

---

## Conclusion

**Overall risk assessment:** LOW

**Key confidence drivers:**
1. 90% code reuse from proven Baranja scripts
2. Simpler domain geometry (synthetic notch, no UTM warping)
3. Strong pedagogical signal (2.8× size variation vs. 1.5× Baranja)
4. No new algorithms; faithful re-use of ADMESH size_components()
5. Straightforward Manim patterns (ImageMobject, ValueTracker, always_redraw all battle-tested)

**Highest-risk step:** Data generation (distmesh convergence & size-field reachability). Mitigation: thorough Task 2.3 gate; fallback plans documented.

**Most likely contingency:** Size-field ratio < 2.5×. Mitigation: increase bathymetry heterogeneity (Fallback A, 1–2 hours re-tuning).

**Budget:** 10–16 developer hours + 4–6 compute hours → feasible within 2–3 calendar days.

**Next step:** Proceed to EXECUTE phase; start Task 1.1 (domain parametrization).
