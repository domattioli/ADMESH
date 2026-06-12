# Concepts

Conceptual primer for ADMESH. Skim this once before reading the
[Architecture overview](Architecture-Overview.md) or
[Pipeline](Pipeline.md) pages. Authoritative algorithm references live
inline next to each topic.

---

## 1. The problem ADMESH solves

ADCIRC-style shallow-water solvers need an **unstructured triangle
mesh** that:

1. Resolves coastal geometry (small triangles near boundaries / sharp
   features, big triangles offshore).
2. Resolves the **physics** (small triangles in shallow water where
   wave celerity is slow, big triangles in deep water).
3. Stays well-conditioned for finite-element / finite-volume
   discretisation (no sliver triangles).
4. Round-trips through the ADCIRC `fort.14` format without losing
   boundary-condition metadata.

ADMESH automates this: take a `Domain` (an outer polygon + optional
holes, encoded as an SDF) and produce a `Mesh` that satisfies all
four criteria. Bathymetry and tide-period information are carried
into the size-field stack as user contributions (or, via spec-002
wiring, eventually as auto-on defaults when present on the source
mesh). The decision of "how big should a triangle be at point `x`?"
is encoded in the **size field** `h(x) > 0`. Everything else flows
from that.

---

## 2. The size field — what controls triangle size

The size field `h(x)` is a scalar function over the domain. It is the
target edge length the mesher tries to enforce at each point.

ADMESH builds `h(x)` by **taking the elementwise minimum** of several
contributions:

```
h(x) = min(
    h_h            ,   # uniform floor (h_target)
    h_curvature(x) ,   # finer near high-curvature boundary
    h_medial(x)    ,   # finer near narrow channels
    h_bathy(x)     ,   # finer in shallow water (optional)
    h_tide(x)      ,   # finer where wavelength is short (optional)
    h_user_1(x)    ,   # caller-supplied contribution (optional)
    ...
)
```

The min operator means **the most restrictive contribution wins** at
every point. Each contribution is a faithful port of the
corresponding MATLAB function (see
[Architecture overview](Architecture-Overview.md) §"13 stages"). The
public composer that assembles them lives in
[`admesh/size_field.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/size_field.py)
and is two-phase:

- **Phase 1** — built-ins always combined by `min` (Constitution
  Principle I).
- **Phase 2** — user contributions combined by a caller-chosen
  reduction (`min`, `mean`, weighted, …).

### 2.1 Curvature contribution

Near a boundary turn with radius of curvature `r`, the triangle size
should be a fraction of `r`. ADMESH narrow-bands the curvature signal
along the boundary so it does not bleed into the interior:

`h_curvature(x) = max(h_min, k · κ⁻¹(x) · w(d_boundary(x)))`

where `κ` is curvature, `w` is a narrow-band weighting, `d_boundary`
is signed distance to the boundary, and `k` is a tuning scale. Ported
from MATLAB's `CurvatureFunction.m`. See
[`admesh/curvature.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/curvature.py).

<p align="center">
  <img src="https://raw.githubusercontent.com/domattioli/ADMESH/main/output/demo_notched_boundary_curvature.png" alt="Curvature contribution on a notched-rectangle domain" width="60%">
</p>

### 2.2 Medial-axis contribution

In a long narrow channel, the triangle size should be a fraction of
the local **channel width**. The medial axis is the set of points
equidistant from at least two boundary points; the distance from a
point `x` to the medial axis is a proxy for half the local width.

ADMESH computes the medial axis using a Zhang-Suen-style thinning on
a binary mask of the domain interior, plus an outward-flux pruning
pass that removes spurious branches. Implemented in
[`admesh/medial_axis.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/medial_axis.py)
as a faithful port of `MedialAxisFunction.m`.

<p align="center">
  <img src="https://raw.githubusercontent.com/domattioli/ADMESH/main/output/demo_unit_disk_medial.png" alt="Medial-axis contribution on a unit disk" width="40%">
  &nbsp;&nbsp;
  <img src="https://raw.githubusercontent.com/domattioli/ADMESH/main/output/demo_notched_rectangle_medial.png" alt="Medial-axis contribution on a notched rectangle" width="40%">
</p>

### 2.3 Bathymetry contribution

In a shallow-water solver, wave speed `c = √(g·|h|)`. To preserve
the Courant number, the triangle size should shrink with depth:

`h_bathy(x) = s · |Z(x)| / |∇Z(x)|`

where `Z` is the per-node depth field, `∇Z` is computed by a
fourth-order interior stencil + first-order boundary stencil, and `s`
is a scale (defaults to `dt`-derived per CFL). See
[`admesh/bathymetry.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/bathymetry.py).
Wire today by passing a bathymetry contribution function in
`triangulate(domain, user_contribs=(bathy_fn,))`; spec-002 sequences
toward auto-on detection when the source `Mesh` carries
`bathymetry`.

### 2.4 Dominate-tide contribution

For tidally driven simulations, triangles should resolve the
dominant-tide wavelength `L = T · √(g·|Z|)`:

`h_tide(x) = (T / sz) · √(g · |Z(x)|)`

with `T` the tide period (seconds), `sz` elements-per-wavelength
target (default 100), `g = 9.81`. See
[`admesh/dominate_tide.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/dominate_tide.py).
Wired today the same way as bathymetry — via `user_contribs=`.

### 2.5 Custom contribution

Pass a callable to `triangulate(domain, user_contribs=[fn])`. `fn`
takes an `(N, 2)` array of points and returns an `(N,)` array of size
values. Used for refinement near a surveyed feature (e.g., a breaker
line) without modifying the size-field stages.

---

## 3. Signed distance functions (SDFs)

A signed distance function returns, for any point `x`, the **shortest
distance from `x` to the domain boundary**, with the sign indicating
inside vs outside:

- `f(x) > 0` → outside the domain
- `f(x) = 0` → exactly on the boundary
- `f(x) < 0` → inside the domain

SDFs are the geometric primitive that distmesh uses to enforce
boundary conformity. Every node-movement step in distmesh
re-projects out-of-domain points back to the boundary by reading the
SDF gradient. ADMESH supports two kinds of domain:

| Domain spec | SDF source |
|---|---|
| Closed-form (rectangle, disk, L-shape, …) | analytic `f(x)` plus its gradient |
| Polygon (one outer ring + optional hole rings) | numeric `f(x)` via the [`shapely`](https://shapely.readthedocs.io/) distance kernel + segment-by-segment sign assignment |

The SDF + utilities live in
[`admesh/distance.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/distance.py),
a faithful port of `SignedDistanceFunction.m`.

---

## 4. Distmesh — how the mesh is actually built

[Persson & Strang's distmesh](http://persson.berkeley.edu/distmesh/)
is a force-based mesh generator. Conceptually:

1. **Seed** the domain with points placed at density `1/h(x)`
   (rejection-sampled against the size field).
2. Treat each edge as a spring with rest length proportional to its
   midpoint `h` and current length its actual length. Compute the
   resulting force on each node.
3. **Move** each node by a damped Euler step under the spring forces.
4. **Re-project** any node that moved outside the domain back to the
   boundary using the SDF gradient.
5. **Re-triangulate** with a Delaunay step every few iterations
   (cheap; mesh topology stays nearly fixed).
6. Repeat until the maximum node motion per iteration is small.

ADMESH's distmesh is a faithful port of `distmesh2d.m` from the
MATLAB reference, plus a `BoundaryCleanUp.m` final pass that removes
sliver triangles that touch the boundary at near-zero angle. See
[`admesh/distmesh.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/distmesh.py).

<p align="center">
  <img src="https://raw.githubusercontent.com/domattioli/ADMESH/main/output/mvp_l_shape.png" alt="Distmesh output on an L-shape domain" width="45%">
  &nbsp;&nbsp;
  <img src="https://raw.githubusercontent.com/domattioli/ADMESH/main/output/mvp_notched_rectangle.png" alt="Distmesh output on a notched rectangle" width="45%">
</p>

---

## 5. ADCIRC `fort.14` and the BC types you need to know

`fort.14` is ADCIRC's grid + boundary file. The geometry section is
straightforward (one line per node, one per element). The
**boundary-condition (BC) section** is where most of the complexity
lives — see the [fort.14 cheat sheet](fort14-Cheat-Sheet.md) for the
full IBTYPE table.

The four BC categories that matter most:

| Category | IBTYPE codes | What it represents |
|---|---|---|
| **Mainland / island** | 0, 1, 10, 11 | Land boundary; no normal flow |
| **External barrier** | 2, 3, 12, 13 | Outer barrier (levee, seawall) with prescribed flux or weir overflow |
| **Internal barrier** | 4, 24 | Weir or levee that splits the domain; **paired edges** — two nodes per line |
| **Open ocean** | (`NOPE` section) | Where boundary forcings are applied |

The "paired edge" structure for internal barriers is the trickiest
part of `fort.14` to parse correctly: each line in the BC record
lists **two** node IDs, one for each side of the structure. A naïve
reader that splits per-node silently drops half the pairing. ADMESH's
reader handles paired-edge records explicitly per
[`specs/002-size-field-defaults/contracts/fort14-paired-edge.md`](https://github.com/domattioli/ADMESH/blob/main/specs/002-size-field-defaults/contracts/fort14-paired-edge.md).

---

## 6. Mesh quality — what "good" means

Per-element shape quality is reported as the **shape-q metric**
(0 = degenerate, 1 = equilateral):

`q = (4·√3 · A) / (l₁² + l₂² + l₃²)`

where `A` is element area and `l_i` are edge lengths. The shape-q
distribution over the whole mesh is the headline correctness signal.
A WNAT mesh produced by the source MATLAB has `shape-q-mean ≈ 0.99`;
ADMESH's current Python port hits `≈ 0.92` on the same input
(tracked by [issue #10](https://github.com/domattioli/ADMESH/issues/10)
as the dominant blocker to 0.1.0). See
[`admesh/quality.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/quality.py).
A regenerated 4-panel shape-q histogram (source vs. fresh) lands in
`tests/output/wnat_quality.png` after a Tier-2 pytest run.

---

## 7. The 0-based vs 1-based gotcha

MATLAB indexes from 1. NumPy indexes from 0. `fort.14` files store
node IDs starting from 1. ADMESH stores everything **0-based
internally** and subtracts 1 on read / adds 1 on write. Anywhere a
ported MATLAB algorithm indexes into an array, the port subtracts 1.
This is the single most common porting bug — see
[`docs/PORTING_NOTES.md`](https://github.com/domattioli/ADMESH/blob/main/docs/PORTING_NOTES.md)
for the substitution log.

---

## 8. Where these concepts live in code

| Concept | Module | MATLAB origin |
|---|---|---|
| Size field composer | [`admesh/size_field.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/size_field.py) | — (Python additive) |
| Size field assembler | [`admesh/mesh_size.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/mesh_size.py) | `MeshSizeFunction.m` + iterative solver |
| Curvature contribution | [`admesh/curvature.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/curvature.py) | `CurvatureFunction.m` |
| Medial-axis contribution | [`admesh/medial_axis.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/medial_axis.py) | `MedialAxisFunction.m` |
| Bathymetry contribution | [`admesh/bathymetry.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/bathymetry.py) | `BathymetryFunction.m` |
| Tide contribution | [`admesh/dominate_tide.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/dominate_tide.py) | `DominateTideFunction.m` |
| SDF | [`admesh/distance.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/distance.py) | `SignedDistanceFunction.m` |
| Distmesh | [`admesh/distmesh.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/distmesh.py) | `distmesh2d.m` + `fixmesh.m` + `BoundaryCleanUp.m` |
| BC enforcement | [`admesh/boundary.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/boundary.py) | `EnforceBoundaryConditions.m` |
| `fort.14` I/O | [`admesh/fort14.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/fort14.py) | — (Python additive) |
| Per-element quality | [`admesh/quality.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/quality.py) | `MeshQuality.m` |
