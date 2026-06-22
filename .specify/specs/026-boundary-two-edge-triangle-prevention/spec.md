# Spec 026 — Boundary Two-Edge Triangle Prevention (resolves #129)

**Status:** Planning-phase only. No code shipping in this commit (ADMESH planning profile).
**Issue:** [#129 should admesh not allow any triangle that has two edges on the boundary](https://github.com/domattioli/ADMESH/issues/129)
**Related:** [#85](https://github.com/domattioli/ADMESH/issues/85) (cross-repo tracker), spec 018 (boundary tri-pair degeneracy), spec 007 (1D boundary seeding), spec 024 (grid-agnostic boundary seeding)
**Branch:** `daily-maintenance`
**Token budget:** MEDIUM (edgeswap scan + gate condition + fallback vertex perturbation + 5 acceptance tests)

---

## 1. Problem statement

A triangle T in a triangulated domain mesh is called a **two-boundary-edge triangle** (2BE-tri) if exactly two of its three edges lie on the domain boundary. Formally, let B be the set of boundary edges (edges belonging to exactly one triangle). Then:

> T is a 2BE-tri ⟺ |{e ∈ edges(T) : e ∈ B}| = 2

The third edge of a 2BE-tri is interior, shared with exactly one neighbor triangle. The two boundary edges of T meet at a boundary vertex that is a **corner** (or near-corner) of the domain. The non-boundary vertex of T is an interior node.

This configuration arises in distmesh boundary triangulation as follows. During 1D boundary seeding (spec 007), nodes are placed along the boundary at spacing ≈ fh. When the boundary has a sharp inward corner (e.g., a concave bay tip, an annulus inner-ring arc of tight curvature), two adjacent boundary segments can be short relative to fh. The distmesh force-balance step then finds the nearest interior node and draws both short segments as triangle edges — the corner region is filled by a single triangle pinned against two boundary segments simultaneously.

This configuration is problematic for two independent reasons:

1. **Quad implications (CHILmesh downstream).** The CHILmesh quad-prep layer (spec 004, spec 015) requires each triangle to contribute exactly one edge to a candidate quad pair. A 2BE-tri contributes only one interior edge (its shared edge with the neighbor). That shared edge can participate in at most one quad pair. But the two boundary edges are unpairable — CHILmesh's layer-traversal algorithm assumes each triangle has at least two interior edges available for matching. A 2BE-tri hard-blocks one traversal path per occurrence, degrading quad conversion coverage.

2. **Mesh quality.** The interior vertex of a 2BE-tri is often far from the two corner boundary vertices. The triangle is typically acute or right-angled at the corner vertex, producing a low minimum angle and low quality metric q = 2r_in / r_out. These are the minimum-quality triangles (min-q tris) that are fully constrained by the boundary — they cannot be improved by smoothing because both long edges are boundary-locked.

**Distinction from spec 018.** Spec 018 addresses a two-triangle pair configuration: two triangles each with one boundary edge sharing a common interior edge (a "boundary tri-pair"). That is a different graph-theoretic predicate involving two triangles. This spec addresses the single-triangle predicate above.

---

## 2. Root cause

Two conditions conspire to produce 2BE-tris:

**A. Boundary seeding at corners.** Spec 007 seeds nodes along the 1D boundary polygon at arc-length spacing ≈ fh. At a domain corner where two segments meet, the two segments adjacent to the corner vertex are each seeded independently. When the corner interior angle is sharp (< 60°) and the seeded segments are short, the triangulation has no interior node close enough to the corner to insert a triangle between the two boundary segments — so Delaunay triangulation places a single triangle spanning both.

**B. distmesh force-balance pinning.** The distmesh spring-force model moves interior nodes to minimize edge-length residuals. Boundary nodes are fixed (they were placed by spec 007). The interior node of the eventual 2BE-tri is attracted to the centroid of the local star but cannot escape the force from the two long boundary edges — it is pulled toward the corner but the two boundary edges grow as it approaches, reinforcing the configuration rather than breaking it.

The result is a stable fixed point of distmesh iteration that contains a 2BE-tri. The algorithm converges without detecting that the configuration is undesirable.

---

## 3. Proposed fix

The fix operates in two stages: **prevention via edgeswap** (primary) and **vertex perturbation fallback** (secondary).

### Stage 1 — Edgeswap scan and prevention

After each distmesh iteration pass (or as a post-convergence cleanup), scan all triangles for the 2BE-tri predicate:

```
for each triangle T:
    boundary_edge_count = sum(1 for e in edges(T) if e in boundary_edge_set)
    if boundary_edge_count >= 2:
        flag T as a 2BE-tri candidate
```

For each flagged T, attempt an **edgeswap** on its single interior edge (the edge shared with T's unique neighbor N):

- Identify the quadrilateral Q formed by T and N (four vertices: the two boundary vertices of T, the interior vertex of T, and the opposite vertex of N).
- Check if the alternate diagonal of Q (the swap) is valid: the swapped edge must not cross the boundary, the resulting triangles must both have positive area, and neither resulting triangle must itself be a 2BE-tri.
- If valid, perform the swap. The swap removes the interior edge of T and replaces it with the alternate diagonal. The two new triangles each have at most one boundary edge (the boundary edges of T are distributed one-per-new-triangle).
- If the swap would produce another 2BE-tri, mark T as unresolvable by edgeswap and proceed to Stage 2.

The swap validity check must be performed in the correct order — edgeswap should run before the truss function so that the truss function sees a cleaner topology and can resolve residual edge-length imbalance.

### Stage 2 — Vertex perturbation fallback

If the edgeswap cannot resolve a 2BE-tri (e.g., the swap is geometrically invalid or produces a new 2BE-tri), move the interior vertex of T **toward the boundary corner vertex** by a fraction α of the current distance:

> v_new = v_interior + α * (v_corner − v_interior),  α ∈ (0.2, 0.5)

The perturbation shortens the interior edge and shifts the force-balance fixed point. On the next distmesh iteration, the truss function re-equilibrates the surrounding star. In most cases one perturbation step breaks the 2BE-tri configuration without further manual intervention.

The perturbation is applied only to the **non-boundary** vertex of T. Boundary vertices remain fixed per the 1D seeding contract (spec 007).

If after perturbation the 2BE-tri persists through convergence, emit a `RuntimeWarning` identifying the triangle (by vertex indices) and the corner vertex coordinates. Do not raise an error — convergence takes priority.

---

## 4. Convergence risk and mitigation

Edgeswap on a 2BE-tri is topologically safe: it removes one interior edge and inserts another, preserving the node count and boundary node positions. The truss function's spring forces remain well-defined after the swap.

Vertex perturbation is the higher-risk step. Moving an interior vertex mid-iteration can temporarily increase edge-length residuals in the surrounding star and delay convergence by a few iterations. Mitigations:

| Risk | Mitigation |
|---|---|
| Perturbation cascades into adjacent stars, delaying convergence beyond the iteration budget | Cap perturbation at one application per 2BE-tri per convergence run; do not re-perturb if the triangle is already improving. |
| Swapped edge immediately flips back in the next iteration | After a swap, freeze the new interior edge for one iteration (exclude it from the flip candidate list). |
| Perturbation moves interior vertex outside the domain SDF | Clamp v_new to the domain interior using the SDF before applying: if sdf(v_new) > 0, bisect α until sdf(v_interior + α*(v_corner − v_interior)) ≤ 0. |
| Edgeswap produces a triangle with near-zero area (sliver) | Reject the swap if min(area(T1), area(T2)) < ε * fh² for a small ε (e.g., 0.01). |

The expected convergence impact is negligible on smooth domains (few 2BE-tris). On domains with many sharp corners (e.g., a fjord polygon with interior angles < 30°), the 2BE-tri count may be proportional to the number of corners — in that regime the perturbation fallback activates for the unresolvable cases and the remaining 2BE-tris are flagged via `RuntimeWarning` without blocking convergence.

---

## 5. Cross-repo integration

### CHILmesh

CHILmesh's quad-prep layer (tracked in ADMESH spec 015 and the CHILmesh overlap analysis) relies on each triangle contributing exactly one candidate interior edge for quad pairing. The 2BE-tri hard-blocks one traversal path per occurrence. Eliminating 2BE-tris at the ADMESH stage means CHILmesh receives a mesh where every triangle has at least two interior edges, making the quad-matching graph fully connected in theory. This is a prerequisite for high quad-conversion coverage on domains with sharp corners.

**Downstream note (ADMESH planning profile):** No CHILmesh code ships in this spec. The downstream impact is documented here so that the CHILmesh team can plan their quad-prep assumptions against the ADMESH contract. When this spec is implemented, the ADMESH↔CHILmesh seam document (ADR-001 follow-up, spec 015) should be updated to reflect that 2BE-tris are guaranteed absent post-convergence (or flagged via `RuntimeWarning` if unresolvable).

### ADMESH-Domains

The domain registry (ADMESH-Domains) stores mesh validation metadata. Once this spec is implemented, the post-mesh validation metadata should include a `two_boundary_edge_triangle_count` field so that downstream consumers can assert the count is zero on clean meshes.

---

## 6. Acceptance criteria

- [ ] **AC-1 Detection.** Given a synthetic domain with a known sharp corner that produces a 2BE-tri under default seeding, the scan correctly identifies the 2BE-tri by vertex indices before any fix is applied. Test fixture: a unit square with one inward triangular notch at a corner, `hmin` set coarse enough to guarantee a 2BE-tri on initial triangulation.
- [ ] **AC-2 Edgeswap resolution.** After applying the edgeswap stage, the synthetic fixture from AC-1 contains zero 2BE-tris and the mesh passes the structural-validity gate (positive area, all nodes inside SDF, mesh area ≥ 95% of source polygon area).
- [ ] **AC-3 Quality improvement.** The minimum quality metric q_min of the post-fix mesh is strictly greater than q_min of the pre-fix mesh on the AC-1 fixture. The 2BE-tri that was removed was the min-q triangle (it was fully boundary-constrained and therefore the worst triangle in the mesh).
- [ ] **AC-4 Convergence.** On the annulus demo domain (inner radius 0.3, outer radius 1.0, default `hmin`), the mesh converges within the standard iteration budget with zero 2BE-tris in the final mesh. No `RuntimeWarning` is emitted for this domain.
- [ ] **AC-5 No regression.** All existing Tier-0, Tier-1, and Tier-2 acceptance tests pass without `xfail` after the edgeswap scan and perturbation fallback are integrated. The `pytest -q` exit code is 0.

---

## 7. Out of scope

- Preventing 2BE-tris from forming in the first place by modifying the 1D boundary seeding step (spec 007 / spec 024). That approach would change the seeding contract and carries broader regression risk. The edgeswap + perturbation approach operates after seeding and is additive.
- Handling triangles with **three** boundary edges (a triangle fully enclosed by the boundary — geometrically impossible in a simply-connected triangulation of a domain with interior nodes, but a possible artifact of degenerate input). Not addressed here.
- Automated corner detection or angle-threshold classification for "how sharp is too sharp." This spec treats any 2BE-tri as a defect regardless of corner angle.
- CHILmesh code changes. The CHILmesh team may choose to add a defensive check for 2BE-tris on input, but that is their decision and is out of scope for this ADMESH spec.
- Changes to the distmesh spring-force model or iteration schedule. The fix is post-iteration, not mid-iteration.
