# Phase 0 Research: Octree Background Grid

Resolves the Technical-Context unknowns for spec 021. Format per decision: **Decision / Rationale / Alternatives considered**.

## R1 — Octree realisation in 2D (quadtree)

**Decision**: Implement the structure as a **quadtree** (the 2D specialisation of an octree) and keep "octree" as the user-facing feature name.
**Rationale**: ADMESH meshes 2D domains; the background grid is 2D (`X, Y`). A quadtree gives exactly the hierarchical-refinement properties the spec requires (local refinement, bounded transitions) without a spurious third dimension.
**Alternatives considered**: A true 3D octree (rejected — no z dimension; would waste memory and complicate point-location). A k-d tree (rejected — not axis-aligned/level-structured, so 2:1 balance and uniform-cell-degenerate-case don't fall out naturally).

## R2 — Refinement criteria & construction

**Decision**: Top-down subdivision of the padded bbox. A leaf subdivides while its size exceeds the local **target edge length** from a cheap sizing oracle and stays above the `h_min` floor. Oracle = min(distance-to-boundary proxy, curvature-driven size, provisional LFS estimate), reusing the existing per-stage size drivers. Stop at `h_min` (FR-004); no max-depth cap.
**Rationale**: Mirrors how `build_h` already derives targets (curvature `K`, medial `R`); refining to the size field means cells are small exactly where the size field is small. `h_min` as the floor (clarify decision) ties to today's `h_min` and bounds memory via `h_min` × extent.
**Alternatives considered**: Refine purely on boundary distance (rejected — misses curvature/medial drivers, under-refines interior pinches). Fixed max-depth cap (rejected by clarify — user chose `h_min` only).

## R3 — 2:1 balance

**Decision**: Enforce a 2:1 size ratio between edge-adjacent leaves in a post-construction balancing pass (standard restricted/balanced quadtree).
**Rationale**: Smooth size transitions (FR-003) so the gradient limiter has small jumps to absorb and the medial-axis leaf graph has well-conditioned neighbour spacing.
**Alternatives considered**: Unbalanced tree (rejected — abrupt size jumps degrade the gradient limiter and medial detection across cell-size discontinuities).

## R4 — Medial axis on the octree (the crux)

**Decision**: Compute the medial axis and medial-axis distance (MAD) on the **leaf-adjacency graph** using the existing `medial_distance_fmm` (Fast Marching), generalised to variable leaf spacing (edge cost = centre-to-centre distance). Medial leaves are detected by the generalised average-outward-flux (AOF) of the signed-distance gradient over each leaf's neighbours (area/length-weighted), replacing the fixed 8-neighbour pixel stencil; `LFS = |D| + MAD`, `h_lfs = LFS / R` as today.
**Rationale**: FMM already exists in `medial_axis.py:226` and is naturally a graph/variable-spacing algorithm, unlike the pixel-grid Zhang-Suen skeletonization (which assumes equal neighbour spacing — exactly the assumption an octree breaks, spec Edge Case "adjacent cells of very different size"). Detecting medial leaves via generalised AOF avoids 1-pixel-skeleton artefacts on a non-uniform grid.
**Alternatives considered**: (a) Generalise Zhang-Suen skeletonization to the leaf graph — rejected: thinning is defined for regular pixel lattices; ill-defined on mixed cell sizes. (b) Locally rasterize each region to a uniform patch at leaf resolution, run the existing pixel algorithm, then stitch — rejected as a fallback-only option: stitching seams and re-introducing a fine uniform patch defeats the memory win. Kept as a contingency note only.

## R5 — Gradient limiting on the leaf graph

**Decision**: Run the `|∇h| ≤ g` Eikonal limiter (`solve_iter`) on the leaf-adjacency graph, with per-edge spacing = neighbour centre distance instead of a single uniform `delta`. Provide pure-NumPy and `@njit` variants and assert parity (`atol=1e-10`), matching Principle II.
**Rationale**: Gradient limiting must still hold (FR-009); the only change is variable edge spacing. Keeping the two-implementation + parity-test pattern satisfies the constitution.
**Alternatives considered**: Limit on a resampled uniform grid (rejected — reintroduces the uniform-grid memory cost). Skip limiting on the octree (rejected — violates FR-009 / breaks distmesh smoothness).

## R6 — Query interpolation

**Decision**: Replace `RegularGridInterpolator` with octree **point-location + within-leaf interpolation** (bilinear from leaf-corner samples, or constant per leaf at the floor). Preserve the returned `fh(p): (N,2) -> (N,)` callable contract so `api.triangulate()` and distmesh are untouched.
**Rationale**: `RegularGridInterpolator` requires a regular grid, which the octree is not. Point-location in a balanced quadtree is O(log) per query; keeping the `fh` signature means zero changes above the stage layer.
**Alternatives considered**: Scattered-data interpolation (`griddata`/RBF) over leaf centres (rejected — slower, less predictable, and unnecessary given the tree gives O(log) location).

## R7 — Fallback trigger (FR-018)

**Decision**: If octree construction raises or fails a validity check (e.g. degenerate domain, empty leaf set), fall back to the existing uniform `eval_sdf_grid` path with a `UserWarning`, and still return a valid `fh`. The no-multi-scale degenerate case (FR-017) is the octree with effectively one refinement level — no separate code path needed.
**Rationale**: Robustness (FR-018) without losing the legacy path; the uniform path already exists and is parity-tested.
**Alternatives considered**: Hard-error on octree failure (rejected — regresses domains that work today). Always run both and compare (rejected — wasteful).

## R8 — Dependencies

**Decision**: No new third-party dependency. Implement the quadtree in-repo (pure Python + Numba). 
**Rationale**: Principle II (pip-installable, no C toolchain) and "no silent meshing dependency." A balanced quadtree with point-location is small and self-contained.
**Alternatives considered**: `scipy.spatial`-based structures or external octree libs (rejected — heavier dependency surface for a structure we can implement compactly; revisit only if profiling demands it, with a `pyproject.toml` rationale).

## Resolved unknowns

All Technical-Context items are resolved: octree → 2D quadtree (R1); construction/floor (R2/R3); medial axis via FMM on leaf graph (R4); gradient limiting on leaf graph (R5); query via point-location (R6); fallback (R7); no new dependency (R8). No `NEEDS CLARIFICATION` remain for planning.
