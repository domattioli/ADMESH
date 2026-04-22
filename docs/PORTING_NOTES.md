# Porting notes

Running log of MATLAB → Python substitutions and behavior differences
encountered during the port. One entry per decision; newest at top.

Template:

```
## YYYY-MM-DD — <stage> — <title>

**MATLAB**: `function(args)` in `<path>.m`
**Python**: `admesh.<module>.function(args)`
**Substitution**: <what was replaced>
**Behavior diff**: <closed-vs-open boundary, tie-break, ordering, etc.>
**Impact**: <how tests / callers are affected>
```

---

## 2026-04-23 — distmesh — ADMESH variant pathway (clean-room)

**MATLAB**: `10_Distmesh_2d/{distmesh2d,createInitialPointList,
rejectionMethod,GetMeshConstraints,projectBackToBoundary,
BoundaryCleanUp,createMeshStruct}.m`
**Python**: `admesh.distmesh.distmesh2d_admesh`,
`admesh.distmesh._boundary_cleanup`,
`admesh.distmesh.MeshOutput`,
`admesh.routine.triangulate` (dispatcher)
**Substitution**: Clean-room — MATLAB source still not available in
this environment (2nd `SOURCE_UNAVAILABLE` row; see
`docs/persistence_journal.md` 2026-04-23T(s3-start)). The new path
layers on top of the canonical `distmesh2d`: seeds `pfix` with all
PTS ring vertices; synthesizes an SDF from the PTS via inside-test
+ per-segment Euclidean distance when the caller doesn't supply
`fd`; runs `_boundary_cleanup` to drop near-collinear slivers with
2+ nodes on the same ring (same pattern that motivated session-1's
stale-`t` bugfix); classifies every node by `(ring_id, BC)` via
`admesh.boundary.enforce_boundary_conditions`. Returns a typed
`MeshOutput` dataclass. The MVP `triangulate(Domain)` tuple path is
preserved verbatim; a new `triangulate(PTS)` branch dispatches to
the admesh path and returns `MeshOutput`.
**Behavior diff**: The MVP binding gate
(`tests/test_mvp_domains.py::test_mvp_domain`) passes unchanged —
54 of 82 tests run along the pre-existing canonical path. The
admesh path is exercised by 6 new `tests/test_distmesh_admesh.py`
cases and produces annulus meshes labeled across both rings with
`min_q ≥ 0.25, mean_q ≥ 0.55`. Faithful-port backfill against the
MATLAB helper set is deferred.
**Impact**: `admesh.routine.triangulate` now accepts a `PTS` for
rich-boundary workflows; rings and BC tags flow through to the
output without the caller managing the plumbing.

## 2026-04-23 — mesh_size — `build_h` gains PTS boundary reduction

**MATLAB**: boundary-distance contribution is folded into MATLAB's
mesh-size pipeline inside `ADmeshRoutine.m`; there is no standalone
function for it.
**Python**: `admesh.mesh_size.build_h(..., pts=, boundary_scale=)`
+ `_pts_boundary_field` helper.
**Substitution**: Adds two new kwargs to the existing composer.
When set, the composer samples each PTS segment's distance to every
grid cell, then composes `h_bnd[type] = max(scale[type], d)` per
BC type and takes the elementwise min. Composes with existing
`curvature_scale` / `medial_scale`. Zero-enrichment path is
preserved — `build_h(domain, pts=pts, boundary_scale=None)` still
returns the uniform-`base` lambda.
**Behavior diff**: Accepts a dict keyed by
`BoundaryType`-int so callers can refine OPEN vs. WALL asymmetrically.
Unit-square near-boundary `fh ≤ 0.1` vs. interior `fh ≥ 2 × that`
(for `boundary_scale=0.04, base=0.2`).
**Impact**: `build_h` is now PTS-aware without breaking any
existing callers. End-to-end `triangulate(pts, fh=build_h(...))`
works by passing the returned `fh` through the new admesh path.

## 2026-04-23 — boundary — PTS + BC enforcement (clean-room)

**MATLAB**: `08_Enforce_Boundary_Conditions/{EnforceBoundaryConditions,
create_polygon_structure}.m`
**Python**: `admesh.boundary.PTS`, `admesh.boundary.BoundaryType`,
`admesh.boundary.enforce_boundary_conditions`,
`admesh.boundary.PTS.from_polygons`, `admesh.boundary.PTS.from_domain`
**Substitution**: Clean-room — MATLAB source not accessible. The
port defines a **minimum-viable** PTS: list of polygon rings
(outer + holes), per-vertex BC tag (2-value `IntEnum`: `OPEN`,
`WALL`; MATLAB has more subtypes), and an opaque `attributes` dict
for passthrough data. `PTS.from_domain` uses a clean-room
marching-squares contour extractor on the SDF grid, chains segments
into closed rings, resamples each by arc-length. Orients outer CCW
/ holes CW.
**Behavior diff**: MATLAB's PTS has additional fields
(hydraulic-constraint subtypes, per-node attributes) — expand in a
faithful-port backfill when MATLAB source is available. The 2-BC
subset handles the P3-lift requirements (enforce_boundary_conditions
drives cleanup + per-type sizing). `from_domain` has a
``3·delta`` pad on the sampled bbox so the zero-level set is
strictly interior to the grid (avoids fencepost loss when ``delta``
doesn't evenly divide the bbox extent).
**Impact**: Unblocks PTS-driven `build_h` and
`distmesh2d_admesh`. Round-trips on `unit_square`, `annulus`, and
`unit_disk` with per-ring orientation correct and
`|r_outer - 1| ≤ 2e-2` on the disk.

## 2026-04-23 — mesh_size — `build_h` composer (new, not ported)

**MATLAB**: size-field composition is distributed across
`03_Distance_Function`, `04_Curvature_Function`, `05_Medial_Axis`,
`06_Bathymetry_Function`, `07_Dominate_Tide`, and the solver entry
in `09_Mesh_Size` — there is no single MATLAB function that wires
them together; `ADmeshRoutine.m` does the orchestration.
**Python**: `admesh.mesh_size.build_h`
**Substitution**: New-in-Python composer that builds an
``fh(p) -> np.ndarray`` callable from optional curvature + medial
contributions, applies `solve_iter` (gradient limiting), and wraps
the result in a `scipy.interpolate.RegularGridInterpolator`.
**Behavior diff**: Zero-enrichment path (no `curvature_scale` /
`medial_scale`) returns a uniform lambda with no grid work — keeps
the MVP `triangulate(domain)` default path unchanged.
**Impact**: `triangulate(domain, fh=build_h(domain, ...))` accepts
enriched size fields; verified by `tests/test_mesh_size.py::
test_triangulate_accepts_composed_fh`.

## 2026-04-23 — medial_axis — clean-room (MATLAB source unavailable)

**MATLAB**: `MedialAxisFunction.m`, `TriMedialAxisFunction.m`,
`medial_distance_FMM.m`, heap helper in `05_Medial_Axis/`
**Python**: `admesh.medial_axis.medial_distance_fmm`
**Substitution**: The session-2 environment lacks the MATLAB clone
(see `docs/persistence_journal.md` row dated 2026-04-23). Clean-room
implementation: `scipy.ndimage.distance_transform_edt` computes the
L2 distance transform (equivalent Eikonal with unit speed). Medial
cells are detected as interior cells where ``|∇D_edt| < 0.85``,
with a ``1.5·delta`` buffer against the boundary staircase (true
distance functions satisfy ``|∇D| = 1`` a.e.; the skeleton is
where that fails). Then EDT again from the medial mask yields
``medial_dist``.
**Behavior diff**: Validated against analytic references only
(unit disk: medial = origin, medial_dist = r; annulus(0.4, 1.0):
medial = circle r=0.7, medial_dist = |r - 0.7|) to
``2.5..3.0·delta``. Faithful-port pass against the MATLAB heap-FMM
is deferred to the first session with the MATLAB clone mounted.
**Impact**: `build_h(..., medial_scale=...)` works. No test yet
exercises domains with multi-branch medial skeletons like
`notched_rectangle`; that's a fixture to add when the MATLAB
reference is available.

## 2026-04-23 — curvature — clean-room (MATLAB source unavailable)

**MATLAB**: `CurvatureFunction.m` + helpers in
`04_Curvature_Function/`
**Python**: `admesh.curvature.curvature_function`,
`admesh.curvature.curvature_grid`
**Substitution**: The session-2 environment lacks the MATLAB clone
(see `docs/persistence_journal.md` 2026-04-23). Clean-room
implementation of the textbook formula
``κ = ∇·(∇f / |∇f|)`` on a rectangular grid, using the existing
``admesh.distance.grad_sdf`` 4th-order stencil twice (once for
``∇f``, once for the divergence of the normalized gradient). Cells
with ``|∇f| < 1e-3`` are masked ``NaN`` to avoid the medial-axis
singularities. Reference: Osher & Fedkiw (2003) §1.4.
**Behavior diff**: On `unit_disk` (analytic κ=1/r), coarse-grid
L∞ error ≤ 5e-2 at `delta=0.05`; halving `delta` reduces the
error (tests only a monotonic refinement — not a rate). On
`annulus` the sign flip between inner and outer halves matches
analytic to ≤ 1e-1. On `unit_square` (kinked SDF), flat-face
regions yield κ ≈ 0; diagonals produce spurious large values —
unavoidable for the 4th-order stencil across a C⁰ kink.
**Impact**: `build_h(..., curvature_scale=...)` works. Faithful-port
pass deferred.

## 2026-04-21 — distmesh — stale-`t` bug: final Delaunay added

**MATLAB**: `distmesh2d.m` in `10_Distmesh_2d/`
**Python**: `admesh.distmesh.distmesh2d`
**Substitution**: The canonical Persson algorithm re-runs Delaunay
only when `max(nodal-motion)/h0 > ttol`. The Python port followed
that literally, which meant a final set of force-step node motions
(including boundary-projection of drifted nodes) could leave the
most recent `t` slightly stale. On straight boundaries
(`unit_square`) three boundary-projected nodes at `x=0.5±1e-10` can
form a near-colinear, zero-area sliver. Added a final
`Delaunay(p)` + centroid-`fd` filter after the loop exits (either
`niter` or `dptol`), before `fixmesh`.
**Behavior diff**: `unit_square` min_q went `0.000 → 0.804`; every
other MVP domain min_q improved by ≥ 0.04. Node counts unchanged;
`unit_square` triangle count went `139 → 138` (the sliver removed).
Canonical Persson doesn't have this problem in MATLAB because the
MATLAB script ends the iteration differently; our Python port's
loop-exit conditions made it observable.
**Impact**: `tests/test_mvp_domains.py` binding gate (`min_q ≥ 0.30`)
passes. No other tests affected.

## 2026-04-18 — distmesh — canonical-only port; ADMESH helpers deferred

**MATLAB**: `distmesh2d.m` in `10_Distmesh_2d/` (plus ADMESH helpers
`createInitialPointList.m`, `rejectionMethod.m`,
`GetMeshConstraints.m`, `projectBackToBoundary.m`,
`BoundaryCleanUp.m`, `createMeshStruct.m`)
**Python**: `admesh.distmesh.distmesh2d` (canonical Persson only)
**Substitution**: The MATLAB file is a GUI-wrapped, PTS-aware variant
of Persson & Strang (2004) layered with ADMESH-specific constraint
handling. The MVP port implements the canonical algorithm only —
equilateral lattice initial distribution, probability rejection,
truss-force relaxation, boundary projection along `-grad fd` — and
omits all PTS / mesh-constraint machinery.
**Behavior diff**: MVP meshes are valid canonical DistMesh output;
they will not match the ADMESH-variant output node-for-node on
domains that exercise `GetMeshConstraints` / `BoundaryCleanUp`. On
the five MVP test domains (pure SDF inputs, no PTS constraints)
this is a non-issue.
**Impact**: Full ADMESH `distmesh2d` variant lands in post-MVP
phase P3 (boundary + full routine). Any caller needing PTS
structures or boundary-segment constraints must wait.

## 2026-04-18 — distance — SignedDistanceFunction MVP subset

**MATLAB**: `SignedDistanceFunction.m` + `PTS2PointList.m` in
`03_Distance_Function/`
**Python**: `admesh.distance.signed_distance`, `admesh.distance.grad_sdf`
**Substitution**: The MATLAB function is much heavier than the MVP
needs — it operates on a `PTS` structure (kd-tree nearest-neighbor
over per-segment exact-distance queries) and returns a full grid
distance field plus metadata. The MVP port provides grid evaluation
of a caller-supplied analytic SDF plus a 4th-order finite-difference
gradient. No kd-tree, no PTS I/O.
**Behavior diff**: Analytic SDFs are exact to floating-point
precision; the 4th-order gradient converges to 4th order on smooth
fields. For MVP domains (all analytic), this yields strictly
higher accuracy than the MATLAB path. The PTS-driven path handles
polygon inputs with arbitrary segments — the MVP path does not.
**Impact**: PTS + kd-tree implementation deferred to post-MVP
phase P4 (reference-fixture validation). MVP domains are analytic,
so this is sufficient for the triangulation gate.

## 2026-04-18 — in_polygon — mex-only MATLAB; canonical reimpl

**MATLAB**: `12_In_Polygon/` is **mex-only** in the upstream repo
(no `.m` source), so there is nothing to diff against.
**Python**: `admesh.in_polygon.in_polygon`
**Substitution**: Vectorized ray-cast test, plus an on-boundary
second-return that matches MATLAB's documented canonical
`inpolygon(xq, yq, xv, yv)` two-return signature (`in`, `on`). This
is what every ADMESH call site assumes. Chose a pure-NumPy
implementation over `matplotlib.path.Path.contains_points` because
the latter doesn't expose an `on`-boundary result.
**Behavior diff**: Matches MATLAB's canonical inpolygon on the
stage's fixture tests to the documented tolerance. Floating-point
ties on polygon vertices are resolved by a small `geps`-style
epsilon, which differs from MATLAB's implementation choice by an
unobservable amount in practice (no test has surfaced a difference).
**Impact**: Every downstream caller (distance, distmesh, routine)
gets drop-in compatibility.

## 2026-04-18 — general — `.mex*` binaries discarded

**MATLAB**: `.mexw64`, `.mexmaci64`, `.mexa64` files throughout the
upstream tree (chiefly builds of `MeshSizeIterativeSolver.c`).
**Python**: n/a — these platform binaries are skipped.
**Substitution**: Constitution Article II.8 declares them
throwaway; the Python port replaces the C source with Numba
(`admesh.mesh_size._solve_iter_nb`) and never ships a binary.
**Behavior diff**: None at the API level; the `.mex*` files are
build artifacts, not source.
**Impact**: `pip install admesh` needs no C toolchain — satisfies
the Article I north-star "installs without a C toolchain".
