# TASKS: Manim ADMESH Notch-Seamount Visualization (Issue #97)

**Phase:** EXECUTE  
**Total subtasks:** 13  
**Parallelizable groups:** 3  
**Estimated developer time:** 10–16 hours over 2–3 days  

---

## Execution Strategy

**Sequential groups (mandatory dependencies):**
1. **Setup (Tasks 1.1–1.3):** Domain geometry + bathymetry (2–4 hours)
2. **Data generation (Tasks 2.1–2.3):** NPZ creation + validation (4–6 hours compute, 2–3 hours developer)
3. **Animation (Tasks 3.1–3.5):** Manim skeleton → full render (4–6 hours)
4. **Validation (Tasks 4.1–4.3):** Gate checks + handoff (1–2 hours)

**Parallelizable within groups:**
- Tasks 1.1 and 1.3 can overlap (geometry parametrization ∥ bathymetry tuning)
- Task 3.4 (low-res test) can overlap with Task 2.3 validation

---

## PHASE 1: SETUP (Sequential, ~2–4 hours developer time)

### Task 1.1: Parametrize Notch Boundary as Bezier/Arc Piecewise Curve
**Owner:** Developer  
**Input:** CLARIFY.md specifications (60° V-notch, 1 km deep, 3 km × 2 km extent)  
**Output:** `scripts/viz_data/notch_seamount_domain.json`  

**Subtasks:**
1. Define notch geometry in normalized coordinates (−1 to 1 range, origin at domain center):
   - Straight shelf edge: from (−1.5, −1) to (1.5, −1) [depth: negative y = deep]
   - V-notch: apex at (0, 1), two 60° sides opening downward
   - Outer boundary: semicircle or smooth arc exterior
2. Parametrize as piecewise Bezier curves or line segments (~100 points total, matching Baranja resolution)
3. Export to JSON: `{ "bbox": [xmin, ymin, xmax, ymax], "rings": [[x0,y0], [x1,y1], ...] }`
4. **Validation checkpoints:**
   - SDF computation (via `fast_sdf`) returns negative inside, positive outside
   - Curvature at notch apex ≥ 100 m⁻¹ when mapped to physical units (1 km domain width)
   - Boundary renders crisply (no self-intersections, smooth continuity)

**Expected output file size:** ~5 KB  
**Time estimate:** 1–2 hours  

---

### Task 1.2: Generate Domain JSON and Validate SDF
**Owner:** Developer  
**Input:** Task 1.1 parametrization  
**Output:** `scripts/viz_data/notch_seamount_domain.json` (finalized)  

**Subtasks:**
1. Use Python script or manual JSON to create domain file
2. Load domain JSON in `gen_notch_seamount_data.py` (skeleton; see Task 2.1)
3. Compute SDF on a coarse test grid (50×50) for 10 spot-check points:
   - 5 inside points (should have negative SDF)
   - 3 boundary points (should have SDF ≈ 0)
   - 2 outside points (should have positive SDF)
4. Visualize boundary as PNG: `output/notch_boundary_check.png` (use matplotlib)
5. Document notch curvature value in gen_data.py header comment
6. **Gate:** All SDF spot-checks pass; boundary PNG shows crisp V-notch with no artifacts

**Time estimate:** 0.5–1 hour  

---

### Task 1.3: Implement Bathymetry Function z(x,y)
**Owner:** Developer  
**Input:** Domain JSON (Task 1.2), physical unit specs from CLARIFY  
**Output:** Python function in `gen_notch_seamount_data.py`  

**Subtasks:**
1. Implement shelf profile:
   - Cross-shelf depth profile: z(x) = 0 (coastline) → −20 m (shelf edge ~2 km offshore) → −100 m (deep)
   - Smooth function: e.g., z(x) = −20 × erf(x / 1000) − 80 × (1 + erf((x − 2500) / 1500))
   - Convert to normalized coords (map domain [−1.5, 1.5] → physical [−1500 m, 1500 m])
2. Implement seamount feature:
   - Gaussian bump: z(x,y) += 4 × exp(−((x − x0)² + (y − y0)²) / 400²) meters
   - Location: offset onshore of notch apex (e.g., at (0, 0.5) in normalized coords)
3. Compute gradient |∇z| on interior test grid (80×80):
   - Finite difference: (∂z/∂x, ∂z/∂y) with 3-point stencil
   - Check max(|∇z|) ≥ 0.30; expect peak in seamount flank and shelf edge
4. Generate bathymetry heatmap PNG: `output/notch_bathymetry_check.png`
   - Show colormap with gradient magnitude overlay
5. **Gate:** max(|∇z|) ≥ 0.30; shelf edge visible as blue band; seamount visible as red spot

**Time estimate:** 1–2 hours  

---

## PHASE 2: DATA GENERATION (Sequential, ~4–6 hours compute + 2–3 hours developer)

### Task 2.1: Implement `gen_notch_seamount_data.py` Script
**Owner:** Developer  
**Input:** Domain JSON (Task 1.2), bathymetry function (Task 1.3), reference from `gen_baranja_viz_data.py`  
**Output:** `scripts/gen_notch_seamount_data.py` (complete, executable)  

**Subtasks:**
1. Copy skeleton from `gen_baranja_viz_data.py`:
   - Keep: `load_normalized_rings()`, `_ring_curvature()`, `size_components()`
   - Swap: `fake_bathymetry()` → new notch bathymetry from Task 1.3
   - Update: `DOMAIN_JSON` path, output path → `notch_seamount_admesh.npz`
2. Parametrize tuning knobs (initially from CLARIFY recommendations):
   ```python
   H_MIN = 0.08       # fine-cell target
   H_MAX = 0.25       # coarse-cell target
   DECAY_LENGTH = 0.30  # curvature decay distance
   GRID_RES = 240     # background grid resolution (pixels)
   DISTMESH_ITERS = 120  # iteration count cap
   SEED = 0           # reproducibility
   ```
3. Main loop:
   - Load domain JSON and rings
   - Create background grid (240×240)
   - Compute SDF on grid
   - Compute bathymetry on grid
   - Compute size_components() [h_curv, h_grad, h_depth, h_combined]
   - Initialize random point cloud (h0-scaled, ~50 initial points)
   - Run instrumented distmesh (recording every iteration)
   - Collect snapshots: p{i}, b{i} for i in 0..n_snaps
4. Output NPZ with all arrays:
   ```python
   np.savez_compressed(OUT,
       ring=ring,
       bbox=bbox,
       bathy=bathy_grid,
       h_curv=h_curv_grid,
       h_grad=h_grad_grid,
       h_depth=h_depth_grid,
       sizef=h_combined_grid,
       inside=inside_mask,
       n_snaps=n_snaps,
       **{f"p{i}": pts for i, pts in enumerate(p_snaps)},
       **{f"b{i}": bars for i, bars in enumerate(bar_snaps)},
   )
   ```
5. Print summary: "Generated X snapshots, final mesh Y nodes, Z triangles"
6. **Gate:** Script runs without errors; NPZ file created; file size 2–5 MB

**Files to edit/create:**
- Create: `scripts/gen_notch_seamount_data.py` (~250 lines)
- Reference (do not edit): `gen_baranja_viz_data.py` (copy ~95%)

**Time estimate:** 2–3 hours (mostly copy-paste with parameter adjustments)  

---

### Task 2.2: Run Data Generation and Measure Performance
**Owner:** Developer  
**Input:** `gen_notch_seamount_data.py` (Task 2.1), domain JSON (Task 1.2)  
**Output:** `scripts/viz_data/notch_seamount_admesh.npz`  

**Subtasks:**
1. Execute: `python scripts/gen_notch_seamount_data.py`
2. Log output to file: `gen_notch_seamount.log`
3. Measure wall-clock time (target: 4–6 hours on modern CPU)
4. Check file size of NPZ: should be 2–5 MB
5. Spot-check loaded data:
   ```python
   d = np.load("viz_data/notch_seamount_admesh.npz")
   print(f"Iterations: {d['n_snaps']}")
   print(f"Final mesh nodes: {len(d['p' + str(d['n_snaps']-1)])}")
   print(f"Final mesh edges: {len(d['b' + str(d['n_snaps']-1)])}")
   ```
6. Generate diagnostic plots:
   - `output/notch_mesh_final.png`: final mesh nodes + edges overlay on domain
   - `output/notch_node_count_vs_iteration.png`: node count over iterations (should plateau)
7. **Gate:** NPZ file exists; ≥ 40 iterations captured; final mesh nodes ≥ 50

**Time estimate:** 5–10 minutes developer (execution is automatic); 4–6 hours compute wall-clock

---

### Task 2.3: Validate Size-Field Range and Mesh Quality
**Owner:** Developer  
**Input:** `notch_seamount_admesh.npz` (Task 2.2)  
**Output:** Validation report (text/plot); decision on h_min/h_max tuning  

**Subtasks:**
1. Load NPZ and extract size-field grids:
   ```python
   d = np.load("viz_data/notch_seamount_admesh.npz")
   h_curv = d['h_curv']
   h_grad = d['h_grad']
   h_depth = d['h_depth']
   h_combined = d['sizef']
   ```
2. Compute statistics:
   - h_min = min(h_combined[inside])
   - h_max = max(h_combined[inside])
   - ratio = h_min / h_max
   - Expected: ratio ≤ 0.35 (i.e., ≥ 2.8× variation)
3. Compute mesh quality of final mesh:
   ```python
   final_p = d[f"p{d['n_snaps']-1}"]
   final_b = d[f"b{d['n_snaps']-1}"]
   tri = scipy.spatial.Delaunay(final_p)
   q = admesh.quality.MeshQuality(admesh.Mesh(final_p, tri.simplices))
   print(f"Q_min: {q.min_quality}, Q_mean: {q.mean_quality}")
   ```
4. Generate size-field statistics plot: `output/notch_sizef_stats.png`
   - Histogram of h_combined values
   - Component contributions (h_curv, h_grad, h_depth)
   - Text overlay: ratio, Q_min, Q_mean
5. **Gate criteria:**
   - h_min / h_max ≤ 0.35 (success) or note tuning needed
   - Q_min ≥ 0.40 (acceptable for distmesh)
   - Q_mean ≥ 0.65 (target; if < 0.60, note for future iterations)
6. If ratio < 2.8×: recommend tuning (increase h_max or decrease h_min) and re-run Task 2.1–2.3
7. **Decision:** "PASS" (proceed to animation) or "ITERATE" (adjust h_min/h_max, re-run)

**Time estimate:** 1–2 hours (including iteration if needed)  

---

## PHASE 3: ANIMATION (Sequential, ~4–6 hours)

### Task 3.1: Build Manim Scene Skeleton (5 Acts)
**Owner:** Developer  
**Input:** `notch_seamount_admesh.npz` (Task 2.2), reference from `manim_admesh_baranja.py`  
**Output:** `scripts/manim_notch_seamount.py` (structure only, no rendering yet)  

**Subtasks:**
1. Copy skeleton from `manim_admesh_baranja.py`:
   - Keep: `to_scene()`, `_cmap_terrain()`, `_cmap_size()`, `_heatmap_rgba()`
   - Keep: `AdmeshNotchSeamount` Scene class
   - Update: DATA path, window dimensions (if needed)
2. Implement `construct()` method outline:
   ```python
   def construct(self):
       # Act I: Domain boundary appears
       # Act II: Size-field components (3 heatmaps)
       # Act III: Combined size field
       # Act IV: Mesh animation (ValueTracker + always_redraw)
       # Act V: Final quality colormap
   ```
3. Stub out each act with comments and minimal geometry:
   - Act I: Create boundary polygon, add title
   - Act II: Load heatmap images (3 heat maps), setup crossfades
   - Act III: Load combined heatmap
   - Act IV: Create initial nodes + edges; add ValueTracker
   - Act V: Add quality colormap overlay
4. Add helper methods:
   - `_caption(text)`: fade in/out caption text (copy from Baranja)
   - `_heat(field, cmap)`: load heatmap from NPZ
5. **Gate:** Script loads without import errors; 5 scene sections compile to Manim objects (no errors on `construct()`)

**Files to create:**
- Create: `scripts/manim_notch_seamount.py` (~300 lines)

**Time estimate:** 1–2 hours  

---

### Task 3.2: Integrate Heatmap Rendering (Bathymetry + 3 Size-Field Components)
**Owner:** Developer  
**Input:** Task 3.1 skeleton, `notch_seamount_admesh.npz`  
**Output:** Acts I–III fully functional  

**Subtasks:**
1. Implement heatmap generation in script:
   - Reuse `_heatmap_rgba()` from Baranja
   - Load bathymetry grid, h_curv, h_grad, h_depth, h_combined
   - Apply colormaps (terrain for bathy; hot/cool for size fields)
   - Apply opacity mask (transparent outside domain)
2. Act I (Domain):
   - Create boundary polygon from ring coordinates
   - Add title text ("ADMESH — Coastal Notch Visualization")
   - Add domain label ("3 km × 2 km notch + seamount domain")
   - Timing: 1.5 sec
3. Act II (Size Factors):
   - Heatmap 1: h_curv (text: "Component 1/3 — Boundary Curvature")
   - Fade in over 1 sec, hold for 2 sec, note where concentrated
   - Heatmap 2: h_grad (text: "Component 2/3 — Bathymetric Slope")
   - Crossfade from 1→2 over 0.5 sec, hold for 2 sec
   - Heatmap 3: h_depth (text: "Component 3/3 — Water Depth")
   - Crossfade from 2→3 over 0.5 sec, hold for 2 sec
   - Timing: 6.5 sec total
4. Act III (Combined):
   - Heatmap 4: h_combined (text: "Adaptive mesh size = min(3 factors)")
   - Crossfade from 3→4 over 0.5 sec, hold for 1.5 sec
   - Timing: 2 sec
5. **Gate:** All 4 heatmaps render correctly at low quality; crossfades smooth; colors perceptually distinct

**Time estimate:** 1.5–2 hours  

---

### Task 3.3: Wire Mesh Animation (Node + Edge Interpolation via ValueTracker)
**Owner:** Developer  
**Input:** Task 3.2 progress, `notch_seamount_admesh.npz` snapshots  
**Output:** Act IV fully functional  

**Subtasks:**
1. Load snapshot data:
   ```python
   n_snaps = d['n_snaps']
   p_snaps = [d[f'p{i}'] for i in range(n_snaps)]
   b_snaps = [d[f'b{i}'] for i in range(n_snaps)]
   ```
2. Implement frame sampling (every 5th iteration to keep animation smooth):
   - Skip frames where node motion is negligible (< 1% of domain width)
   - Result: 15–20 key frames for ~4–5 sec animation
3. Implement node position interpolation:
   ```python
   tracker = ValueTracker(0.0)
   def nodes_redraw():
       t = tracker.get_value()
       i = int(np.floor(t))
       j = min(i + 1, n_frames - 1)
       frac = t - i
       P = scene_pts[i] * (1 - frac) + scene_pts[j] * frac
       return VGroup(*[Dot(pt, radius=NODE_R, color=YELLOW) for pt in P])
   live_nodes = always_redraw(nodes_redraw)
   ```
4. Implement edge animation (bars rebuild on re-triangulation):
   ```python
   def truss_redraw():
       t = tracker.get_value()
       i = int(np.floor(t))
       bars = b_snaps[i]
       grp = VGroup()
       for a, b in bars:
           grp.add(Line(P[a], P[b], stroke_width=0.5, color="#56b6ff"))
       return grp
   ```
5. Set up Act IV animation:
   - Fade in size-field heatmap underlay (opacity 0.30)
   - Fade in initial nodes + edges (iteration 0)
   - Add caption: "Distmesh relaxation — nodes move toward force equilibrium"
   - Play tracker animation: `tracker.animate.set_value(n_frames - 1)` over 4 sec
   - Hold final frame for 1 sec
   - Timing: 5 sec
6. **Gate:** Nodes move smoothly; edges rebuild without flickering; animation fluent at 30 fps

**Time estimate:** 1.5–2 hours  

---

### Task 3.4: Test Render at Low Quality (360p, 15 fps, 5 min)
**Owner:** Developer  
**Input:** Tasks 3.1–3.3 complete  
**Output:** Test MP4 (low resolution), timing feedback  

**Subtasks:**
1. Configure Manim for low-quality test:
   ```bash
   manim -ql --resolution 360 --fps 15 scripts/manim_notch_seamount.py AdmeshNotchSeamount
   ```
2. Monitor render time; target < 5 min wall-clock
3. Review output:
   - Does Act I boundary render crisply?
   - Do heatmaps crossfade smoothly?
   - Is mesh animation fluent (no popping, smooth interpolation)?
   - Timing: is 12–15 sec realistic? Adjust if rushed or dragging
4. Screenshot key frames: `output/notch_act1_boundary.png`, `notch_act2_curvature.png`, etc. (manual inspection)
5. Make minor timing adjustments if needed:
   - If rushed: extend crossfades from 0.5 → 1.0 sec, or hold heatmaps longer
   - If dragging: reduce hold times by 0.3–0.5 sec
6. **Gate:** Low-res render completes; all 5 acts present; timing acceptable (developer judgment)

**Time estimate:** 2–3 hours (including re-renders if timing adjusted)  

---

### Task 3.5: Render at Full Quality (720p, 30 fps, ~30 min)
**Owner:** Developer  
**Input:** Manim script finalized (Task 3.4), timing locked  
**Output:** `output/notch_seamount_admesh.mp4` (final)  

**Subtasks:**
1. Configure for full quality:
   ```bash
   manim -ql --resolution 1280 --fps 30 scripts/manim_notch_seamount.py AdmeshNotchSeamount
   ```
   (Note: `-ql` is Manim's "low quality" preset; for "high", use no flag or `-qh`)
2. Monitor render; target 20–40 min wall-clock
3. Verify output MP4:
   - Duration 12–15 sec (check via `ffprobe`)
   - Resolution 720p or better
   - Frame count = duration × 30 fps (no dropped frames)
4. Spot-check playback (VLC or similar):
   - Acts I–V play in sequence
   - Heatmaps visible and color-distinct
   - Mesh animation smooth, edge rebuild visible
   - No artifacts (black bars, pixel glitches)
5. Store final MP4: `output/notch_seamount_admesh.mp4`
6. **Gate:** MP4 file created, 12–15 sec, plays back smoothly

**Time estimate:** 1 hour (30 min render + 30 min verification/re-render if needed)  

---

## PHASE 4: VALIDATION & HANDOFF (Sequential, ~1–2 hours)

### Task 4.1: Verify Animation Meets 5 Success Criteria
**Owner:** Developer  
**Input:** Final MP4 (Task 3.5)  
**Output:** Validation checklist (text document)  

**Subtasks:**
1. **Criterion 1: Domain bathymetry has |∇z| ≥ 0.30 somewhere**
   - Check: `output/notch_bathymetry_check.png` gradient peak ≥ 0.30
   - Result: PASS / FAIL
2. **Criterion 2: Notch geometry has curvature ≥ 100 m⁻¹**
   - Check: Task 1.2 documented curvature value
   - Result: PASS / FAIL
3. **Criterion 3: Size-field range h_min / h_max ≤ 0.35 (≥ 2.8× variation)**
   - Check: `output/notch_sizef_stats.png` ratio value
   - Result: PASS (if ≤ 0.35) / CLOSE (if 0.35–0.40) / FAIL (if > 0.40)
4. **Criterion 4: Final mesh Q_min ≥ 0.40, Q_mean ≥ 0.65**
   - Check: Task 2.3 validation report
   - Result: PASS / MARGINAL (Q_mean 0.60–0.65) / FAIL
5. **Criterion 5: Animation runtime 8–12 sec @ 720p**
   - Check: `ffprobe output/notch_seamount_admesh.mp4`
   - Result: PASS (if 8–12 sec) / PASS (if 12–15 sec, acceptable stretch) / FAIL
6. **Criterion 6 (Bonus): Viewer can name 3 size-field factors**
   - Check: Animation Act II clearly labels curvature, slope, depth
   - Result: PASS / MARGINAL (2/3 factors clear)
7. Compile checklist: `output/notch_validation_checklist.txt`
   - Summarize all 6 criteria with PASS/FAIL/MARGINAL
   - Note any criteria failing → recommend iteration
8. **Gate:** ≥ 5 criteria PASS, max 1 MARGINAL, 0 FAIL → RELEASE; else → discuss with issue author

**Time estimate:** 0.5–1 hour  

---

### Task 4.2: Generate Validation Plots and Static Images
**Owner:** Developer  
**Input:** All intermediate data (NPZ, meshes, heatmaps)  
**Output:** PNG plots for documentation  

**Subtasks:**
1. Create composite validation figure: `output/notch_summary.png`
   - Panel 1: Domain boundary + curvature overlay
   - Panel 2: Bathymetry heatmap
   - Panel 3: Combined size field
   - Panel 4: Final mesh (nodes + edges)
   - Text: h_min/h_max ratio, Q_min, Q_mean, iteration count
2. Generate per-act preview images:
   - `notch_act1_domain.png` — boundary only
   - `notch_act2a_curvature.png` — h_curv heatmap
   - `notch_act2b_gradient.png` — h_grad heatmap
   - `notch_act2c_depth.png` — h_depth heatmap
   - `notch_act3_combined.png` — h_combined heatmap
   - `notch_act4_mesh_final.png` — mesh overlay on heatmap
3. Generate time-series plot: `output/notch_convergence.png`
   - X: iteration index
   - Y: total edge length (scale)
   - Shows distmesh convergence (should plateau by iter 80–120)
4. All plots go to `output/` directory (gitignored)
5. **Gate:** All PNGs created, no empty/corrupt files

**Time estimate:** 0.5–1 hour  

---

### Task 4.3: Document and Commit
**Owner:** Developer  
**Input:** All deliverables (py scripts, NPZ, MP4, validation plots)  
**Output:** GitHub commit(s) with clear messages  

**Subtasks:**
1. Add docstrings to both Python scripts:
   - `gen_notch_seamount_data.py`: header docstring explaining domain, bathymetry, size-field tuning, distmesh instrumentation
   - `manim_notch_seamount.py`: header docstring listing 5-act storyboard, timing, Manim patterns used
2. Create or update `README.md` in `scripts/` directory:
   - Execution instructions: "Run `python gen_notch_seamount_data.py` (takes 4–6 hours), then `manim -ql manim_notch_seamount.py AdmeshNotchSeamount`"
   - Output locations and file sizes
   - Success criteria checklist
3. Add inline comments to key functions:
   - `fake_bathymetry()` — explain shelf profile + seamount formula
   - `size_components()` — reference ADMESH algorithm (already done in Baranja; copy)
   - `distmesh()` instrumentation loop — explain snapshot recording
4. Commit structure (3–4 atomic commits):
   - Commit 1: "Add gen_notch_seamount_data.py — data generation pipeline"
   - Commit 2: "Add manim_notch_seamount.py — 5-act animation skeleton + rendering"
   - Commit 3: "Add validation plots and summary documentation"
   - Commit 4 (if needed): "Finalize README and docstrings"
5. Push all commits to feature branch (per speckit naming convention)
6. Create PR: link to issue #97, reference acceptance criteria from CLARIFY.md
7. **Gate:** All commits have clear messages, PR links issue, validation plots visible in PR

**Time estimate:** 1–1.5 hours  

---

## Parallelization Notes

### Possible parallelization opportunities (if multiple developers):
- **Tasks 1.1 + 1.3** can overlap: one developer parametrizes geometry while another tunes bathymetry
- **Task 3.4 (low-res test)** can run in parallel with **Task 2.3 (quality validation)** once Task 2.1 data generation is done
- **Task 4.2 (plots)** can start as soon as Task 2.3 data is available, independent of animation rendering

### Sequential dependencies (cannot parallelize):
- Task 1.2 requires Task 1.1 (SDF validation needs parametrization)
- Task 2.1 requires Task 1.2 (script loads domain JSON)
- Task 3.1 requires Task 2.2 (Manim loads NPZ)
- Task 3.5 requires Task 3.4 (full render only after low-res timing locked)
- Task 4.1 requires Task 3.5 (validation checks final MP4)

---

## Contingency Tasks (if tests fail)

### If h_min / h_max < 2.5× (Task 2.3 FAIL):
- **Contingency 2a:** Increase notch depth (modify Task 1.3, re-run Tasks 2.1–2.3)
- **Contingency 2b:** Increase seamount height (modify Task 1.3, re-run Tasks 2.1–2.3)
- **Contingency 2c:** Decrease h_max or increase h_min in distmesh tuning (modify Task 2.1, re-run Tasks 2.1–2.3)
- Estimated add'l time: 2–4 hours compute, 1–2 hours developer

### If Q_mean < 0.60 (Task 2.3 FAIL):
- **Contingency 3a:** Increase distmesh iteration count (DISTMESH_ITERS: 120 → 150), re-run
- **Contingency 3b:** Adjust h_min/h_max to smooth size field transitions, re-run
- Estimated add'l time: 2–4 hours compute, 0.5–1 hour developer

### If Manim render > 1 hour @ 720p (Task 3.5 FAIL):
- **Contingency 5a:** Pre-render heatmap images as PNGs, load via ImageMobject (faster than on-the-fly computation)
- **Contingency 5b:** Reduce mesh edge count (downsample distmesh output), re-run Tasks 3.1–3.5
- Estimated add'l time: 1–2 hours developer

---

## Checklist for EXECUTE Phase

- [ ] Task 1.1: Notch boundary parametrized and JSON created
- [ ] Task 1.2: Domain JSON validated; SDF spot-checks pass
- [ ] Task 1.3: Bathymetry function implemented; |∇z| ≥ 0.30 confirmed
- [ ] Task 2.1: `gen_notch_seamount_data.py` written and tested (dry run on 10 iterations)
- [ ] Task 2.2: Full data generation run complete; NPZ file created
- [ ] Task 2.3: Size-field range and mesh quality gates passed (or contingency triggered)
- [ ] Task 3.1: Manim skeleton script compiles; 5 acts stubbed out
- [ ] Task 3.2: Heatmaps render correctly; Acts I–III functional
- [ ] Task 3.3: Mesh animation fluent; ValueTracker + always_redraw working
- [ ] Task 3.4: Low-res test render successful; timing adjusted if needed
- [ ] Task 3.5: Full-quality MP4 rendered; 12–15 sec, plays smoothly
- [ ] Task 4.1: All 5 success criteria checked and documented
- [ ] Task 4.2: Validation plots generated and saved
- [ ] Task 4.3: Code documented, committed, and PR created

---

## File Inventory (End of EXECUTE)

**Generated files:**
- `scripts/viz_data/notch_seamount_domain.json` (~5 KB)
- `scripts/gen_notch_seamount_data.py` (~250 lines)
- `scripts/viz_data/notch_seamount_admesh.npz` (2–5 MB)
- `scripts/manim_notch_seamount.py` (~300 lines)
- `output/notch_seamount_admesh.mp4` (30–50 MB)
- `output/notch_*.png` (validation plots, ~20 files, <2 MB total)
- `output/notch_validation_checklist.txt` (success criteria)

**Total size:** ~40–60 MB (including MP4 and NPZ; PNGs negligible)
