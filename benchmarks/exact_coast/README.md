# Exact-coast challenge, round 1

Question: when a mesher is given a coastline polyline, does the mesh keep the
coastline exact, and are the elements near it well spaced and well shaped?

## Method

1. Seven domains, each a closed outer polyline with optional holes
   (`domains.py`): a notched rectangle, two annuli (64 and 32 outer vertices),
   a narrow inlet, an island chain, and two real coasts read from ADCIRC
   fort.14 files (`wnat_test.14` from the repo tests, and `Block_O.14`, which is
   read in place and skipped with a note if missing).
2. One size field per domain, built once with ADMESH's own tools (build_h with
   medial-axis and curvature terms, then gradient limiting at 0.2) and sampled on
   a regular grid. It is saved in `fields/<domain>.npz` (x, y, H, base_H). Every
   tool reads that grid through the same bilinear interpolator (`GridField`).
3. Node budget (track A): ADMESH runs at scale s = 1 and sets the target node
   count. For every other tool the size field is multiplied by s and s is searched
   (at most 12 tries) until the node count is within 5% of the target.
4. Metrics (`metrics.py`, unit tests in `test_metrics.py`): symmetric Hausdorff
   distance between mesh boundary edges and the input coast; percent of input
   vertices present exactly as mesh nodes; coastline length and area relative
   error; median and 95th-percentile boundary edge-length error |L/h - 1|;
   share of triangles with q < 0.3 that sit within 2h of the coast; min, mean and
   5th-percentile quality (q = 2 r_in / r_out, the ADMESH definition); node and
   triangle counts; wall-clock seconds, single thread.
5. Failures are written as rows; they do not stop the run.

Run: `.venv-bench/bin/python benchmarks/exact_coast/run.py [domain ...]`.
Output: `results/round1.csv`, `results/round1.md`, `results/round1_meta.txt`.

## Competitors

- admesh: `triangulate(boundary="fixed", simplify=None)` with the shared grid as
  `size_field`.
- gmsh: input polyline as constrained curves, every vertex kept, size from a
  callback into the shared grid, Frontal-Delaunay (algorithm 6), default
  smoothing. `gmsh_opt` adds five Laplace2D passes on the same mesh and scale.
- triangle: 'pq30', then up to 8 refine rounds with per-triangle area limits from
  the grid. Input segments are kept; Triangle may add points on them.
- oceanmesh: `om.Domain(bbox, sdf)` plus an `om.Grid` holding the shared field,
  `generate_mesh(domain, grid, max_iter=N, seed=0)` with N = 50, 100, 200 as
  separate rows (`oceanmesh`, `_it100`, `_it200`), followed by
  `make_mesh_boundaries_traversable` and `delete_faces_connected_to_one_face`.
  oceanmesh's own examples use `om.Shoreline` on a shapefile, which cannot take a
  plain polygon, so the domain is built from our signed-distance function
  instead. `om.enforce_mesh_gradation` is not applied (the field is already
  gradient-limited). The CSV has `oc_*` columns with quality before and after the
  cleanup, faces and boundary vertices removed, and where bad triangles sit.
  `oceanmesh_pfix` and `oceanmesh_pfix_it200` also pass every input vertex as fixed points. oceanmesh
  does not document pfix for coastlines, so it is reported as a separate row.

## Fairness rules

- Same polyline, same size field values, same node budget (within 5%).
- No tool gets smoothed or simplified input. The one cleaned input is `wnat`
  (see below), and every tool gets the same cleaned rings.
- Single thread. Timing covers set-up and meshing, not the size-field build or
  file reading. Each time is one run, not an average.
- Constrained and smoothing variants are separate rows.

## Known deviations from the plan

- `wnat` loaded rings pinch at shared nodes and are not a simple polygon. They
  are fixed with `shapely.make_valid`, keeping the largest piece (area 820.15 to
  821.13, 44 to 58 rings, 18 small pieces dropped). Metrics for `wnat` are
  against this cleaned polyline.
- ADMESH's lattice spacing h0 is set to the smallest value of the scaled field
  inside the domain. Setting it to the field maximum gave about 5 times too few
  nodes.
- Boundary edge-length error and the sliver distance use each tool's own
  effective field (s times the shared field).
- Sliver rate is divided by all triangles.
- Hausdorff is shapely's discrete version with densify=0.5, not exact.
- Node matching uses a power-law update with a bracket fallback, not plain
  bisection. `gmsh_opt` reuses the plain gmsh scale.
- Only track A (matched nodes) was run.
- Gmsh points are deduplicated by exact coordinate; its start-up PETSc messages
  on stderr are silenced.
- pytest is not in the bench venv; run the tests with the repo `.venv`.
