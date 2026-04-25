# Research: Algorithmic Formulation for the Pre-Quadrangulation Triangle Smoother

**Feature**: 004-quad-prep-smoother
**Status**: Draft — pre-/speckit-plan
**Created**: 2026-04-25

## Context

The spec defers one architectural decision to /speckit-plan: how the
smoother determines which corner of each triangle becomes the right
angle in the right-isoceles target. The intent stated in the spec is
"let the FEM formulation determine it", with a deterministic heuristic
fallback. This research note surveys three candidate formulations,
each of which resolves the corner-choice ambiguity differently, and
ends with a recommendation.

All three formulations satisfy the spec's non-negotiables (no
connectivity change, boundary stays on SDF zero set within `geps`,
leg length tracks `h`). They differ on: how the per-element target is
defined, what global structure (if any) is precomputed, and how
boundaries and varying-`h` are handled.

The user's intuition that "the smoother could minimize distance to a
gridded underlying field" maps directly to **Formulation 2**
(frame-field guided). It is a real, well-established technique in the
quad-meshing literature.

## Formulation 1 — FEM target-Jacobian with SVD-invariant shape target

### Idea

Knupp's target-matrix paradigm defines a per-element energy

```
E_k = || A_k - W_k ||_F² / det(W_k)
```

where `A_k` is the element's actual Jacobian (reference triangle →
physical) and `W_k` is the target Jacobian. For an equilateral target,
`W_eq` is fixed. For a right-isoceles target, the naive choice
`W_ri = I` pins the right-angle corner to reference vertex 0 — exactly
the rigidity we want to avoid.

The fix: replace the fixed `W_ri` with a target *family* parameterised
by a per-element rotation `R_k`, then minimise over `R_k` in closed
form per element each outer iteration:

```
W_k(R_k) = R_k * diag(σ_k, σ_k)         # σ_k = h_bar(centroid) / sqrt(2)
R_k* = argmin_R || A_k - R diag(σ_k, σ_k) ||_F²
     = closed form via SVD of A_k
```

Equivalently: use a **shape metric** that is invariant to the choice
of right-angle corner — depends only on singular values of
`A_k W_k^{-1}`, not on rotations. Knupp 2012 §4 documents both forms.

### Math sketch

Per outer iteration:

1. For each element `k`: compute `A_k`, SVD it (`A_k = U_k S_k V_k^T`),
   set `R_k* = U_k V_k^T`, build the local 6×6 stiffness block.
2. Assemble the global sparse stiffness matrix; pin boundary nodes
   with `kinf = 1e12` on the diagonal.
3. One sparse linear solve to advance interior nodes.
4. SDF-project boundary nodes that drifted past `geps`.

The right-angle corner emerges per-element from the SVD's rotation
alignment: whichever orientation of the right-isoceles target is
closest in Frobenius norm to the current `A_k` wins.

### Cost (10K nodes / ~20K elements)

- Per outer iteration: O(M) local assembly + O(N) sparse solve →
  ~50 ms with scipy.sparse Cholesky.
- No up-front cost.
- 2 outer iterations (the spec default): ~100 ms total.

### Varying `h`

Per-element scale by `h_bar(centroid) / sqrt(2)` (so leg length tracks
`h`). Standard.

### Boundary handling

Same as issue #1's smoother: pin via `kinf` diagonal entries, project
post-solve. Boundary-band quality degradation is local; the spec's
2*h_local rotation cap maps to clamping the per-element rotation `R_k*`
near the boundary.

### Right-angle-corner

Resolved per-element by the SVD argmin. **No global coherence**:
neighbouring elements can pick conflicting orientations, and the
energy has 4 (modulo 90°) local minima per element. Practical impact:
on regions with weak shape constraints (e.g. the interior of a wide,
uniform-`h` patch), elements may flip-flop between iterations and the
right-iso quality plateau may be 0.10-0.20 below the achievable
maximum.

### Pros / cons

- ✅ Closest to issue #1's architecture; the SVD-invariant target is
  a natural generalisation; research findings inform issue #1 too.
- ✅ Pure local; no preprocessing; cheap.
- ✅ No external dependencies.
- ❌ No global coherence; potential local-minima oscillation.
- ❌ Pair-hint regularizer must be a soft post-fix on top, not
  intrinsic to the formulation.

### References

- Knupp, "Introducing the Target-Matrix Paradigm for Mesh
  Optimization via Node-Movement", Eng. w/ Comp. 2012.
- Balendran, "A direct smoothing method for surface meshes", IMR 1999.
- Issue #1's draft `admesh/smoother.py`.

## Formulation 2 — Frame-field guided (4-RoSy) target

### Idea

A 4-RoSy ("4-rotationally-symmetric") field is a direction field
defined up to 90° rotation: at each point of the domain, it specifies
4 orthogonal directions, equivalent to a single representative angle
`θ ∈ [0, π/2)`. Compute this field once over the domain; then each
element's target shape becomes a right-isoceles triangle aligned to
the field's local orientation.

The right-angle corner is no longer ambiguous: it's whichever corner's
two outgoing edges align with the field's `u` and `R(π/2)·u`
directions. Globally, the field is smooth (low-energy in the dual
mesh), so neighbouring elements pick consistent orientations
automatically.

### Math sketch

Field computation (Knöppel-Crane-Pinkall-Schröder 2013, the modern
standard):

1. Represent the per-vertex (or per-element) angle as a complex unit
   `z_i = e^{4 i θ_i}`.
2. Solve the smallest-eigenvalue problem of the connection Laplacian:
   `L z = λ z`, with boundary constraints `z_b = e^{4 i θ_tangent}`
   on each boundary node (so the field aligns to the boundary
   tangent).
3. Recover `θ_i = arg(z_i) / 4` mod `π/2`.

Smoother per outer iteration:

1. Per element `k`: form the local target `W_k = R(θ_k) · diag(σ_k, σ_k)`
   where `θ_k` is the field's angle at the centroid.
2. Assemble + solve as in Formulation 1.
3. SDF-project boundary nodes.

### Cost (10K nodes / ~20K elements)

- Up-front field solve: O(N) sparse complex eigensolve, ~100-200 ms
  with ARPACK or LOBPCG.
- Per outer iteration: same as Formulation 1, ~50 ms.
- 2 outer iterations: ~200 ms total (~50% overhead vs. Formulation 1).

### Varying `h`

Per-element scale `σ_k = h_bar(centroid) / sqrt(2)` as in Formulation
1. The field itself is independent of `h`.

### Boundary handling

The field's boundary constraint is `θ = boundary tangent angle`, so
the per-element target near the boundary is automatically aligned to
the boundary direction. The 2*h_local rotation cap from the spec is
no longer strictly necessary — the field already enforces tangent
alignment in a smooth way. Boundary-band quality degradation drops
sharply.

### Right-angle-corner

Resolved by the field. Globally coherent. The pair-hint regularizer
becomes implicit: the field's smoothness already biases neighbours
toward shared orientations, so longest-edge-mutuality emerges
naturally.

### Singularities

Frame fields on irregular domains have isolated points (typically near
sharp boundary corners or holes) where the field is undefined — these
are called field singularities. Handling: detect them post-solve
(places where `|z_i|` collapses or `θ` has high variation), exempt
their incident elements from the field-guided target, and fall back to
Formulation 1's local SVD-invariant target there. Singularity count
on coastal-grade domains is typically O(boundary-corner count) — small.

### Pros / cons

- ✅ Globally coherent; no neighbour-conflict local minima.
- ✅ Boundary alignment is automatic; near-zero boundary degradation
  in the well-aligned regions.
- ✅ Pair-hint becomes implicit; no soft post-fix needed.
- ✅ Resolves the spec's right-angle-corner deferral cleanly.
- ❌ Higher implementation cost (~400 LOC; +100-200 ms upfront).
- ❌ Singularity handling adds case logic.
- ❌ Outside admesh's existing toolbox; eats new vocabulary.

### References

- Bommes, Zimmer, Kobbelt, "Mixed-Integer Quadrangulation",
  SIGGRAPH 2009.
- Knöppel, Crane, Pinkall, Schröder, "Globally Optimal Direction
  Fields", SIGGRAPH 2013.
- Diamanti, Vaxman, Panozzo, Sorkine-Hornung, "Designing N-PolyVector
  Fields with Complex Polynomials", SGP 2014.
- Vaxman, Campen, Diamanti et al., "Directional Field Synthesis,
  Design, and Processing", Eurographics STAR 2016 (survey).
- libigl: `igl::cross_field_mismatch`, `igl::comb_cross_field`,
  `igl::frame_field` — reference implementations.

## Formulation 3 — Distmesh-style force balance with lattice attractor

### Idea

Reuse `admesh/distmesh.py`'s force-balance infrastructure. Generate
(or implicitly define) a target lattice that tiles the plane with
right-isoceles triangles — easiest is a square grid with one diagonal
per square. For each existing node, add an attractor force toward the
nearest target-lattice vertex. Combine with the standard
distmesh edge-spring forces.

### Math sketch

Per outer iteration:

1. Build a KD-tree over the target lattice points.
2. For each node `p_i`, query nearest lattice point `q_i*`.
3. Add attractor force `F_attract_i = k_attract * (q_i* - p_i)`.
4. Compute distmesh edge-spring forces as today.
5. Sum, scale by step, project to SDF zero set.

### Cost (10K nodes)

- KD-tree build: O(N log N), ~10 ms.
- Nearest-neighbour queries: O(N log N), ~20 ms.
- Force-balance solve: scipy.sparse CG, ~10 ms.
- Per outer iteration: ~40 ms.
- 2 outer iterations: ~80 ms total.

No up-front cost.

### Varying `h`

The hard part. Options:

- **Uniform lattice + per-edge `h`-scaling**: keep the lattice
  uniform; scale spring rest-lengths by `h`. Mismatch between
  attractor target (uniform spacing) and spring target (varying
  spacing) — quality degrades sharply where `h` varies.
- **Conformally warped lattice**: precompute an isothermal coordinate
  map of the domain (one PDE solve), build the lattice in the mapped
  space, transform back. Adds complexity and a global solve, eroding
  the simplicity advantage.

### Boundary handling

Same as `distmesh`: SDF projection after each iteration. No special
treatment.

### Right-angle-corner

Implicit in the lattice. But aligning existing triangles to a rigid
lattice may require *non-local rearrangements* that node-movement
alone cannot drive — connectivity is fixed. This is the killer
weakness: where the input triangulation's topology is incompatible
with the chosen lattice (e.g. a row of triangles oriented differently
than the lattice's diagonal direction), the attractor pulls nodes into
poor-quality compromise positions.

### Pros / cons

- ✅ Reuses `admesh.distmesh` infrastructure.
- ✅ Cheapest to implement (~150 LOC).
- ✅ Intuitive.
- ❌ Rigid lattice is incompatible with topology-fixed inputs.
- ❌ Varying-`h` is hard (the main blocker for coastal-grade domains).
- ❌ No graceful boundary alignment.

### References

- Persson, "Mesh generation for implicit geometries", PhD thesis,
  MIT 2005 (distmesh).
- The existing `admesh/distmesh.py`.

## Tradeoff matrix

| Aspect | F1: SVD-invariant FEM | F2: Frame-field | F3: Lattice attractor |
|---|---|---|---|
| Resolves right-angle-corner | ✅ per-element | ✅ globally coherent | ✅ via lattice |
| Global coherence | ❌ | ✅ | ✅ rigid |
| Implementation LOC | ~200 | ~400 | ~150 |
| Up-front cost (10K nodes) | none | ~150 ms | none |
| Per-iter cost (10K nodes) | ~50 ms | ~50 ms | ~40 ms |
| Varying-`h` coupling | easy | easy | hard |
| Boundary alignment | manual | automatic | manual |
| Handles topology-incompatible input | ✅ | ✅ | ❌ |
| Pair-hint behaviour | soft post-fix | implicit | implicit (rigid) |
| Local-minima risk | medium-high | low | medium |
| Reuses existing admesh code | modest | little | high |
| External deps | none | optional libigl | none |
| Informs issue #1 | yes | partly | no |

## Recommendation

Ship **Formulation 1 as v1**, treat **Formulation 2 as a v2 follow-up
spec**. Eliminate Formulation 3.

Rationale:

- F1 is the path to a working preprocessor in ~200 LOC. Its weakness
  (no global coherence) is a quality-floor problem, not a
  correctness problem; the spec's acceptance criteria (≥ 0.10
  right_iso_quality lift, ≥ 0.8 leg/`h` correlation) are achievable
  without global coherence on the MVP and Tier-1 fixtures.
- F1's research and code investment transfers directly to issue #1's
  FEM smoother — both gain from a shared SVD-invariant target
  formulation.
- F2 is the right *long-term* answer (globally coherent, automatic
  boundary alignment, implicit pair-hint, resolves every gap the spec
  deferred), but it is a meaningfully larger v1 commitment with a
  steeper learning curve and a new vocabulary (frame fields,
  singularities, complex-Laplacian eigensolvers). Ship v1 first; let
  the v1 quality numbers quantify how much F2 actually buys before
  paying for it.
- F3 is a poor fit for the use case. Its lattice rigidity fights the
  fixed input topology, and its varying-`h` story is weak — the wrong
  tool for coastal-grade domains.

The right-angle-corner clarification deferred from /speckit-clarify
resolves under F1 as **"per-element argmin via SVD of the local
Jacobian"** — concrete, testable, no upfront design decision needed
beyond adopting the SVD-invariant target.

The pair-hint regularizer (story 3) under F1 stays as the spec
describes it: a soft penalty on the local stiffness that biases
mutual longest-edge alignment. Under F2 it would have been implicit
in the field; under F1 it remains an explicit feature.

## Open questions for /speckit-plan

- Does `scipy.sparse` ship the SVD-stiffness assembly we need, or do
  we need a per-element 6×6 closed form?
- What is the `kinf` boundary-pin scale that keeps boundary nodes
  within `geps` after the solve on the WNAT-class fixtures?
  (Expectation: 1e12 same as CHILmesh, but verify.)
- How do we record the v1 → v2 carry-forward? A separate spec or a
  note appended to this research doc once the F1 quality numbers
  land?
- For the soft pair-hint penalty, what scale relative to the
  per-element shape stiffness keeps it from dominating the solve?
  (Empirical; expect to tune in implementation.)
