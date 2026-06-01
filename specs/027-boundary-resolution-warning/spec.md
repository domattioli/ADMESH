# Spec 027 — Boundary Resolution Warning (resolves #127)

**Status:** Planning-phase only. No code shipping in this commit (ADMESH planning profile).
**Issue:** [#127 not certain but i'm looking at the demo on the pages and it looks like we don't perfectly resolve the boundary](https://github.com/domattioli/ADMESH/issues/127)
**Related:** [#85](https://github.com/domattioli/ADMESH/issues/85) (cross-repo tracker), Spec 007 (1D boundary seeding), Spec 024 (grid-agnostic boundary seeding), Spec 026 (boundary two-edge triangle prevention)
**Branch:** `daily-maintenance`
**Token budget:** SMALL

---

## 1. Problem Statement

A boundary segment is **fully resolved** when the arc-length distance between consecutive boundary nodes along the segment does not exceed the local target element size fh evaluated at the segment midpoint. More concretely, for a boundary segment s with total arc length L_s and midpoint x_s:

> s is fully resolved ⟺ max inter-node arc spacing along s ≤ fh(x_s)

A mesh is **boundary-resolved** when every boundary segment satisfies this condition. Equivalently, every curved or straight feature of the domain boundary has at least enough nodes that no two adjacent boundary nodes are farther apart than the local target spacing fh.

The rule-of-thumb "≥ 4 nodes across every feature" is a coarser statement of the same constraint applied to the narrowest dimension of a geometric feature (e.g., the inner ring of an annulus has circumference 2π r_inner; at hmin this should be resolved by ≥ 2π r_inner / hmin nodes, with a floor of 4).

**Observed failure mode.** The annulus demo rendered on the ADMESH GitHub Pages site — inner radius r_inner, outer radius r_outer, default `hmin` — shows the inner boundary ring with visibly coarse node spacing. Gaps exist between consecutive boundary nodes on the inner ring; the arcs between nodes are noticeably longer than hmin. The boundary is not fully resolved at the default hmin setting. This is not caught, flagged, or documented at mesh generation time.

---

## 2. Root Cause

The 1D boundary seeding step (Spec 007, Spec 024) places nodes along each boundary segment at spacing ≈ hmin, where hmin is provided by the operator or set to a global default. The default hmin is chosen for demonstration speed (fast triangulation), not for geometric fidelity on small-radius or high-curvature features.

For the annulus inner ring: circumference = 2π r_inner. At the default hmin, node count on the inner ring ≈ 2π r_inner / hmin. If hmin is comparable to r_inner (e.g., hmin = 0.3 * r_inner or coarser), the inner ring receives fewer than ~6–7 nodes. A polygon approximation of a circle with fewer than ~8 nodes has visible chord errors and the boundary is perceptually and geometrically unresolved.

ADMESH currently performs no post-seeding or post-triangulation check that node density along boundary segments matches fh. The operator receives no feedback. The mesh silently under-resolves curved boundaries at coarse hmin.

---

## 3. Proposed Fix

Two-part fix: **detection** then **warning emission**.

### Part A — Detection: post-mesh boundary segment scan

After triangulation and convergence, iterate over all boundary segments. For each segment s:

1. Collect the ordered sequence of boundary nodes along s (ordered by arc-length parameter).
2. Compute the arc-length distance d_i between each consecutive node pair (n_i, n_{i+1}).
3. Evaluate fh at the midpoint of the chord (n_i, n_{i+1}) — or at the segment midpoint x_s as a cheaper proxy.
4. Compare: if d_i > fh(x_s) * tolerance (default tolerance = 1.5, allowing up to 50% overshoot before warning), flag the pair (n_i, n_{i+1}) as under-resolved.
5. If any pair on segment s is under-resolved, record s in the **under-resolved segment list** with:
   - Segment ID (index or label in the domain boundary representation).
   - Measured maximum inter-node spacing on s.
   - Expected spacing: fh(x_s).
   - Node count on s.
   - Expected minimum node count: ceil(L_s / fh(x_s)).

The tolerance of 1.5 is a planning-phase default. It may need calibration once tested against real domains.

### Part B — Warning emission

If the under-resolved segment list is non-empty, emit a `RuntimeWarning` (Python `warnings.warn`, category `RuntimeWarning`) with a structured message:

```
ADMESH boundary resolution warning: N segment(s) are under-resolved at current hmin.
  Segment <id>: max inter-node spacing = <measured> (expected ≤ <fh>), nodes = <count> (expected ≥ <min_count>).
  [... one line per under-resolved segment ...]
Consider reducing hmin or increasing node density along these segments.
```

The warning is emitted once per mesh generation call. It does not raise an exception and does not block convergence or return. The mesh is returned normally; the operator decides what to do.

### Where the warning lives

The detection and warning should live in a **post-validate helper** called at the end of `triangulate()` (or whatever the top-level mesh generation entry point is). This keeps the main triangulation loop free of validation logic. The helper signature (planning only, not shipping):

```
_check_boundary_resolution(mesh, domain, fh, tolerance=1.5) -> list[UnderResolvedSegment]
```

`triangulate()` calls this helper after convergence, collects the result, and emits the `RuntimeWarning` if the list is non-empty. This structure allows the helper to be called independently in tests.

---

## 4. Cross-Repo Integration

**ADMESH-Domains.**

The mesh validation metadata stored in ADMESH-Domains should include a `boundary_resolution_warnings` field: a list of segment IDs that were flagged, plus the measured vs. expected spacing for each. Downstream consumers (CHILmesh, analysis tools) can query this field to decide whether to proceed or request a finer mesh.

**CHILmesh.**

CHILmesh's layer-traversal and quad-prep algorithms assume boundary nodes are dense enough that the boundary polygon approximation is faithful to the true domain geometry. If coarse boundary resolution propagates from ADMESH to CHILmesh, quad layers near the inner boundary of an annulus-type domain will have distorted elements. The ADMESH warning gives the operator the opportunity to correct hmin before CHILmesh ingests the mesh. No CHILmesh code ships in this spec.

**Downstream note (ADMESH planning profile).** The warning is an ADMESH-internal quality gate. The ADMESH↔CHILmesh seam document (ADR-001 follow-up) should note that a mesh with non-empty `boundary_resolution_warnings` is not guaranteed to meet CHILmesh's geometric fidelity assumptions.

---

## 5. Acceptance Criteria

- [ ] **AC-1 Detection.** Given the annulus demo domain at the default hmin that produces the visible inner-ring gap (as observed in issue #127), the post-validate helper identifies the inner boundary ring segment as under-resolved. The warning is emitted to `stderr` with the correct segment ID, measured spacing, and expected spacing.
- [ ] **AC-2 No false positives at fine hmin.** At hmin = 0.05 (or whatever value fully resolves the annulus inner ring), the helper returns an empty under-resolved list and no `RuntimeWarning` is emitted.
- [ ] **AC-3 Warning is non-blocking.** When the warning is triggered, `triangulate()` still returns a valid mesh object (not None, not an exception). The operator can suppress the warning with Python's standard `warnings.filterwarnings` mechanism.
- [ ] **AC-4 No regression.** All existing Tier-0, Tier-1, and Tier-2 acceptance tests pass without `xfail` after the post-validate helper is integrated into `triangulate()`. The `pytest -q` exit code is 0.

---

## 6. Out of Scope

- **Auto-refinement.** ADMESH does not automatically reduce hmin or re-seed when under-resolution is detected. The warning is informational only. Automatic refinement is a separate, larger spec.
- **Changing the default hmin.** The default hmin is a usability and performance choice. This spec does not change it. The warning exists precisely because the default hmin is intentionally coarse.
- **Interior resolution warnings.** This spec covers boundary segments only. Interior node density relative to fh is a separate concern.
- **Curvature-adaptive seeding.** Detecting that a boundary segment has high curvature and automatically reducing local hmin is out of scope. Curvature adaptation belongs to the seeding specs (007, 024).
- **Visual or HTML report output.** The warning is a plain-text `RuntimeWarning`. No structured report file, no plot, no HTML artifact.
