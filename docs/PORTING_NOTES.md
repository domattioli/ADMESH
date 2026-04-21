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
