# Feature Specification: Pre-Quadrangulation Triangle Smoother

**Feature Branch**: `claude/smooth-quad-preprocessing-FmMxF`
**Created**: 2026-04-25
**Status**: Draft
**Input**: User description: "Speckit specify a smoother addressing the latest issue on a quadrangulation preprocessing smoothing algorithm for tri meshes" (GitHub issue #15)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Prepare a triangulation for quad fusion (Priority: P1)

A coastal modeller has produced an ADMESH triangulation of a coastal domain
and now wants to feed it into a downstream quadrangulation tool (CHILmesh
`tri2quad`, OceanMesh2D's quad converter, or any other tri-to-quad fusion
step) so that the final mesh can be consumed by ADCIRC v55+, which accepts
quads. Today, the triangulation is near-equilateral by design; pairs of
equilateral triangles fuse into rhombi rather than rectangles, and the
downstream quad smoother has to do disproportionate work to recover usable
quads. The modeller wants a single preprocessing call that takes their
triangulation and nudges its triangles toward the right-isoceles target
shape — two same-length legs meeting at 90°, hypotenuses paired — so that
fusion is geometrically clean.

**Why this priority**: This is the entire point of the feature. Without
this slice, the downstream quad pipeline cannot rely on ADMESH output as
its input. With this slice (and only this slice), an external quad
converter can fuse the prepped tris with minimal post-processing.

**Independent Test**: Run the smoother on each of the 5 MVP polygon
domains (square, L-shape, U-shape, square-with-hole, doughnut). Verify
that (a) the same node count and triangle connectivity are returned, (b)
boundary nodes still lie on the domain's signed-distance zero level-set
within `geps`, and (c) the new right-isoceles quality metric increases by
at least 0.10 on every domain. The smoother delivers value as soon as
this slice is green; the downstream quad fusion is out of scope.

**Acceptance Scenarios**:

1. **Given** a valid ADMESH triangulation `(p, t)` of one of the 5 MVP
   domains and the domain's signed-distance function `fd`, **When** the
   user calls the pre-quadrangulation smoother with default arguments,
   **Then** the call returns `(p_new, t)` with `len(p_new) == len(p)` and
   `t` element-for-element identical to the input.
2. **Given** the same input as above with the input's boundary nodes
   sitting on the SDF zero level-set within `geps`, **When** the smoother
   returns, **Then** every boundary node in `p_new` is still within
   `geps` of the SDF zero level-set.
3. **Given** a triangulation whose right-isoceles quality score is `q0`,
   **When** the smoother is run with default settings, **Then** the
   right-isoceles quality of the output is at least `q0 + 0.10` on every
   one of the 5 MVP domains and on at least one Tier-1 real-world coastal
   fixture.

---

### User Story 2 - Couple the smoother to a spatially varying size field (Priority: P2)

A modeller has a domain with strong feature-size variation — a coastline
where the mainland boundary needs ~1 km resolution but a narrow inlet or
nearshore feature needs ~50 m resolution. They have already produced an
ADMESH size field `h(x, y)` that captures this variation. When the
smoother nudges triangles toward right-isoceles, the modeller needs the
final triangle leg lengths (not hypotenuse lengths) to track `h`, because
the leg is the edge length the post-fusion quad will inherit. Without
this coupling, the smoother either ignores the size field (uniform
triangles, wrong everywhere off-uniform) or scales by hypotenuse (quads
end up `sqrt(2)`× too coarse).

**Why this priority**: A uniform-`h` smoother is useful for the MVP
polygon domains but not for real-world coastal work. P2 because the P1
slice already delivers value on uniform domains; size-field coupling is
the bridge to production.

**Independent Test**: On a synthetic test domain with a known spatially
varying `h` (e.g. linear ramp across the domain), run the smoother and
compute the per-triangle leg length and the per-triangle `h` evaluated
at the centroid. The Pearson correlation of `(leg_length, h_centroid)`
across all triangles must be at least 0.8.

**Acceptance Scenarios**:

1. **Given** a triangulation, an SDF `fd`, and a size field `h` with
   spatial variation, **When** the user calls the smoother with `h`
   provided, **Then** per-triangle leg lengths in the output correlate
   with `h(centroid)` across the mesh with Pearson r ≥ 0.8.
2. **Given** the same inputs but `h=None`, **When** the smoother runs,
   **Then** it still returns a valid output (uniform target) and does
   not crash.

---

### User Story 3 - Bias the smoother toward pairing-aware alignment (Priority: P3)

A user wants to maximise the number of triangles that will pair cleanly
in the downstream fusion step. ADMESH's tri pairing heuristic (and most
others) selects each triangle's partner as the neighbour with which it
shares its longest edge; the pair fuses across that shared edge. If many
triangles' longest-edge neighbours don't reciprocate (i.e. the
"longest-edge graph" has weak mutual matching), the fusion step has to
fall back to suboptimal pairs. The user wants the smoother to apply a
soft regularizer that biases the geometry toward mutual longest-edge
alignment, increasing the fraction of cleanly pairable triangles without
changing the topology.

**Why this priority**: This is a quality-of-pairing optimization layered
on top of the geometric target. P3 because P1 + P2 already produce a
right-isoceles mesh that pairs well in the typical case; this slice
sharpens the worst case and is gated by being a soft constraint (no
topology change).

**Independent Test**: On a fixed reference triangulation, run the
smoother twice — once with `pair_hint=False`, once with `pair_hint=True`
— with all other arguments equal. Compute the fraction of triangles
whose longest-edge neighbour is mutual (i.e. the neighbour's longest
edge is also the shared edge). Verify the `True` case exceeds the
`False` case by at least 25 percentage points relative.

**Acceptance Scenarios**:

1. **Given** a triangulation with `pair_hint=True`, **When** the
   smoother runs, **Then** the fraction of triangles whose longest-edge
   neighbour reciprocates the choice increases by ≥ 25% (relative)
   compared to the same input with `pair_hint=False`.
2. **Given** `pair_hint=True` and a degenerate input where no
   longest-edge pairing is possible (e.g. a strip of one-element-wide
   triangles), **When** the smoother runs, **Then** it falls back to the
   non-pair-hint behaviour and does not error.

---

### Edge Cases

- **Boundary-incident elements**: Triangles with one or more nodes on
  the SDF zero level-set cannot always be made right-isoceles without
  violating the boundary constraint. The smoother caps rotation
  magnitude near the boundary (within `2 * h_local` of the SDF zero) and
  accepts a slight equilateral-bias there. The right-isoceles quality
  drop in the boundary band must be reported, not concealed.
- **Sliver triangles in the input**: A near-degenerate input triangle
  (one very small angle) is not guaranteed to recover to right-isoceles
  in the configured `n_outer` iterations. The smoother returns the best
  it has and does not iterate to convergence; quality reporting flags
  any sliver that survives.
- **Disconnected components or holes touching the boundary**: The
  smoother treats every closed boundary ring identically (outer ring,
  hole rings) — boundary nodes on any ring are projected back onto the
  SDF zero level-set after each outer iteration.
- **Empty or single-element mesh**: Inputs with `len(t) == 0` or
  `len(t) == 1` return the input unchanged without error.
- **Standard `mesh_quality` drop**: The existing equilateral-targeted
  `mesh_quality` is expected to decrease after the smoother runs (that
  is the trade — equilateral and right-isoceles are different shapes).
  The smoother does not modify or wrap `mesh_quality`; it adds a
  companion `right_iso_quality` metric and the user reports both as a
  delta.
- **Constitution Principle I**: The smoother does not edit any of the
  13 faithful-port stage modules. Any size-field, SDF, or geometry
  helper it needs is consumed via the public surface of those modules
  unchanged.
- **Right-angle-corner ambiguity**: The right-isoceles target shape
  is unique only up to choice of right-angle vertex. The intent for
  this feature is for the FEM target-Jacobian formulation itself to
  determine the corner — either via a corner-invariant shape target
  (e.g. SVD-based: enforce equal singular values plus a 90° apex)
  or via a per-element energy-minimisation over the three corner
  choices, picking the lowest-energy assignment per outer iteration.
  Concrete resolution is deferred to `/speckit-plan`. If neither
  formulation proves tractable, the plan documents a fallback
  heuristic (e.g. corner opposite the longest input edge) as a
  follow-up clarification.

## Clarifications

### Session 2026-04-25

- Q: When the caller does not provide a signed-distance function
  (`fd=None`), how should the smoother decide which nodes are
  boundary nodes? → A: It does not — `fd` is required in practice.
  The canonical caller is admesh, which always supplies a
  `Domain.fd`; external callers must explicitly pass an SDF rather
  than relying on a topology-based fallback.
- Q: How thick is `quad_prep.smooth_for_quadrangulation` relative to
  issue #1's `fem_smooth(target="right_isoceles")`? → A: Independent
  reimplementation. `quad_prep` ships its own target-Jacobian
  smoother tuned for the right-isoceles target, with no runtime
  dependency on issue #1. The two implementations may share design
  references (Knupp 2012, Balendran) but MUST NOT import each other.
  This relaxes the sequencing constraint — `quad_prep` may ship
  before, alongside, or after #1.
- Q: Which corner of each triangle gets the 90° angle in the
  right-isoceles target shape? → A: Deferred to `/speckit-plan`. The
  intent is for the FEM formulation to determine the corner (via a
  corner-invariant shape target or per-element energy minimisation).
  If neither approach is tractable in the plan, fall back to a
  deterministic heuristic and re-clarify.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The package MUST expose a single public entry point
  `smooth_for_quadrangulation(p, t, fd=None, h=None, target="right_isoceles", pair_hint=True, n_outer=2)`
  in a new module `admesh/quad_prep.py` that accepts an `(N, 2)` node
  array `p` and an `(M, 3)` triangle index array `t`.
- **FR-002**: The smoother MUST return `(p_new, t)` such that
  `len(p_new) == len(p)` and `t` is element-for-element identical to the
  input — no node insertion, deletion, or re-indexing.
- **FR-003**: Every node in `p_new` whose input position lay on the
  SDF zero level-set within `geps` (per the required `fd` callable —
  see FR-013) MUST also lie on the zero level-set within `geps` after
  smoothing.
- **FR-004**: When `h` is provided, the smoother MUST scale the
  per-element target shape so that the resulting triangle's *leg* length
  (not hypotenuse) tracks `h` evaluated at the element centroid. This
  difference from a hypotenuse-tracking convention MUST be documented in
  `docs/PORTING_NOTES.md`.
- **FR-005**: When `pair_hint=True`, the smoother MUST run a greedy
  longest-edge-neighbour pairing pre-pass and bias the geometry toward
  aligning paired hypotenuses, implemented as a soft penalty in the
  local stiffness — never as a topology change.
- **FR-006**: The package MUST expose a companion quality metric
  `right_iso_quality(p, t)` in `admesh/quality.py` that scores deviation
  from right-isoceles (analogous to how the existing `mesh_quality`
  scores deviation from equilateral). The existing `mesh_quality`
  function MUST NOT be modified.
- **FR-007**: The smoother MUST cap rotation magnitude for boundary-band
  nodes (those within `2 * h_local` of the SDF zero level-set) so that
  boundary projection remains feasible. The boundary degradation MUST be
  reported by the test suite, not hidden.
- **FR-008**: The smoother MUST accept `n_outer ≥ 1` and run that many
  outer-iteration passes, where each pass alternates a smoothing step
  with a boundary-projection step.
- **FR-009**: The package MUST NOT modify any of the 13 faithful-port
  stage modules in `admesh/` (Constitution Principle I). Any helpers
  needed from those modules MUST be consumed via their existing public
  surface.
- **FR-010**: The package MUST NOT implement triangle-to-quad fusion,
  quad-mesh smoothing, or mixed tri/quad output. Fusion is downstream;
  ADMESH output remains pure-tri.
- **FR-011**: The package SHOULD expose an opt-in shortcut on the
  existing `triangulate(...)` API (e.g. `triangulate(..., for_quads=True)`)
  that runs the pre-quadrangulation smoother as the final stage of a
  triangulation. This shortcut is additive and MUST NOT change the
  default behaviour of `triangulate(...)`.
- **FR-012**: The implementation MUST be self-contained — it ships
  its own target-Jacobian smoother tuned for the right-isoceles
  target, with no runtime dependency on issue #1's
  `admesh/smoother.py`. The two implementations may share design
  references (Knupp 2012, Balendran) and test infrastructure but
  MUST NOT import each other. This relaxes the sequencing constraint
  — `quad_prep` may ship before, alongside, or after issue #1.
- **FR-013**: When the caller does not supply `fd`, the smoother
  MUST raise a clear, actionable error rather than silently falling
  back to topology-based boundary detection. The canonical caller
  (`admesh.triangulate(..., for_quads=True)`) always supplies
  `Domain.fd`; external callers must pass an SDF explicitly.

### Key Entities *(include if feature involves data)*

- **Triangulation `(p, t)`**: An ADMESH-produced triangle mesh. `p` is
  an `(N, 2)` array of node coordinates; `t` is an `(M, 3)` array of
  zero-based node-index triples. Connectivity is preserved end-to-end by
  the smoother.
- **Signed-distance function `fd`**: A callable `fd(p) -> distance` that
  returns the signed distance from each query point to the domain
  boundary (negative inside, positive outside). Used to identify
  boundary-band nodes and to project them back to the zero level-set
  after each outer iteration.
- **Size field `h`**: A callable `h(p) -> edge_length` that returns the
  target edge length at each query point. Drives per-element scaling so
  that the post-smoothing triangle's leg length tracks `h(centroid)`.
- **Right-isoceles quality `right_iso_quality(p, t)`**: A per-mesh
  scalar in `[0, 1]` that measures how close the triangulation is to a
  right-isoceles target shape. Companion to the existing
  equilateral-targeted `mesh_quality`; the two are reported side by
  side as a delta after smoothing.
- **Pairing-aware regularizer**: A per-element soft penalty added to the
  local stiffness when `pair_hint=True`, biasing the smoother toward
  geometries where each triangle's longest edge is also its
  longest-edge neighbour's longest edge. Never modifies topology.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On each of the 5 MVP polygon domains (square, L-shape,
  U-shape, square-with-hole, doughnut), the smoother increases
  `right_iso_quality` by at least 0.10 in a single end-to-end run with
  default arguments.
- **SC-002**: On at least one Tier-1 real-world coastal fixture, the
  smoother increases `right_iso_quality` by at least 0.10 without
  pushing any boundary node further than `geps` from the SDF zero
  level-set.
- **SC-003**: On a synthetic varying-`h` test domain, the per-element
  leg lengths in the output correlate with `h` evaluated at the
  centroid with Pearson r ≥ 0.8.
- **SC-004**: With `pair_hint=True`, the fraction of triangles whose
  longest-edge neighbour reciprocates the longest-edge choice exceeds
  the `pair_hint=False` fraction (same input, same other args) by at
  least 25 percentage points relative.
- **SC-005**: The smoother completes one end-to-end run on a 10K-node
  triangulation in under 10 seconds wall-clock on a developer laptop.
  This bounds runtime for typical coastal-grade domains and guards
  against quadratic regressions in the pair-hint pre-pass.
- **SC-006**: All 13 faithful-port stage modules in `admesh/` remain
  byte-identical to their pre-feature versions (Constitution Principle
  I). Verified by a git-diff check in the test suite or in CI.
- **SC-007**: Calling the existing `mesh_quality(p, t)` on the
  smoother's output produces a finite scalar in `[0, 1]` (no NaN, no
  crash). Its value is expected to drop relative to the input — the
  test reports the delta but does not gate on its sign.

## Assumptions

- The implementation is independent of issue #1. Both features may
  ship in either order. They are expected to share design references
  (Knupp 2012, Balendran) and possibly test scaffolding, but neither
  imports the other. If a unification is desired post-v1 it lives in
  a follow-up spec, not this one.
- `geps` is the existing ADMESH boundary-projection tolerance constant
  used elsewhere in the codebase. The smoother adopts it without
  introducing a new tolerance.
- `h` is a callable returning a positive scalar at every query point
  inside the domain. Behaviour at points outside the domain is
  undefined; the smoother only evaluates `h` at element centroids,
  which lie inside the domain by construction.
- The 5 MVP polygon domains are the same set already used by the
  existing test suite (`unit_square`, `l_shape`, `u_shape` /
  `notched_rectangle`, `square_with_hole`, `annulus` / `doughnut`). The
  Tier-1 real-world fixture is one of the ADCIRC-examples fort.14
  fixtures already in `tests/fixtures/fort14/adcirc_examples/`,
  unblocked by issues #10 / #11 / #12 if those fixtures are needed for
  the pre-fusion smoother test (the smoother runs on any valid
  triangulation, so a synthetic Tier-1 substitute can be used if the
  real fixture is still gated).
- Triangulation node ordering within each triangle is consistent with
  the rest of the codebase (counter-clockwise, the convention used by
  `admesh.routine.triangulate`).
- The canonical caller is admesh's pipeline: `Domain.fd` supplies the
  required SDF, `admesh.mesh_size.build_h` supplies the optional size
  field, and admesh has the per-element geometry it needs for any
  pre-orientation step the plan ends up choosing. Initial v1 use is
  in-tree with admesh; external callers must supply their own `fd`
  (and, optionally, `h`) — the smoother does not synthesize them
  from mesh topology.
- The pair-hint regularizer is a *soft* constraint. The smoother never
  swaps, splits, or merges triangles; topology in equals topology out.
- Performance target SC-005 (10K nodes in 10 s) assumes the
  feature's own target-Jacobian solve is linear per outer iteration
  and the pair-hint pre-pass is at most `O(M log M)` in element
  count. If profiling on a representative coastal fixture shows the
  solver is super-linear, SC-005 is the place to renegotiate, not
  the API surface.
- Triangle-to-quad fusion, quad smoothing, and any mixed tri/quad
  output are explicitly out of scope and live downstream (CHILmesh
  `tri2quad` or equivalent).
