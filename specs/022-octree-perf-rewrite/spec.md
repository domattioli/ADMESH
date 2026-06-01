# Feature Specification: Scalable Octree Background Grid (O(N log N))

**Feature Branch**: `022-octree-perf-rewrite`  
**Created**: 2026-06-01  
**Status**: Draft  
**Tracks**: Issue #115  
**Predecessor**: Spec 021 (`021-octree-size-field`) — correctness proven, scalability deferred  
**Input**: `admesh/_stages/octree_grid.py` is O(N²) adjacency, O(N³) balance, O(N) queries.
Production targets feature-size ratios up to 10⁴ (millions of leaves); current code times out above ~3 000 leaves.

---

## User Scenarios & Testing

### User Story 1 — Fast Octree Build for High-Ratio Domains (Priority: P1)

A coastal meshing researcher defines a river-into-bay domain where bay span S = 48 and
river width w = 0.048 (ratio = 1 000). They call `build_octree(dom, h_min=0.012, ...)`.
Today this call hangs or OOM-crashes. After this spec it completes in < 30 s on a laptop.

**Why this priority**: Without tractable build, every downstream story is blocked. This is
the single hard bottleneck making spec 021 a prototype rather than a product.

**Independent Test**: Run `build_octree` on a river domain with ratio 1 000; assert it
completes in < 30 s and produces a leaf set whose minimum leaf size ≤ h_min × 1.5.

**Acceptance Scenarios**:

1. **Given** ratio = 100, **When** `build_octree(dom, h_min=w/4)` called, **Then** completes
   in < 5 s; leaf count ≤ 10 × uniform-grid estimate at same h_min.
2. **Given** ratio = 1 000, **When** called, **Then** completes in < 30 s; build does NOT
   rebuild full adjacency inside the split loop.
3. **Given** ratio = 10 000, **When** called with `balance=False`, **Then** leaf count
   stays < 10⁶ and build completes in < 300 s (stretch goal; documented if not achieved).

---

### User Story 2 — Fast Size-Field Queries for distmesh (Priority: P1)

A developer passes a graded octree size field to `admesh.triangulate()`. distmesh calls
`fh(p)` for thousands of query points per iteration. After this spec each query batch of
N_q points costs O(N_q × log N_leaves), not O(N_q × N_leaves).

**Why this priority**: Even if build is fast, a slow query path makes mesh step intractable
at scale. Both build and query must be fixed for end-to-end viability.

**Independent Test**: Build an octree with 50 000 leaves; time 100 000 query points through
`locate(grid, p)`. Assert mean time per query < 10 µs (vs. > 500 µs today at N = 50 k).

**Acceptance Scenarios**:

1. **Given** 50 000 leaves, **When** 100 k query points through `locate`, **Then** total
   time < 1 s (10 µs/query budget).
2. **Given** `RegularGridInterpolator` raster path in `admesh_mesh`, **When** raster
   resolution delta = h_min/2, **Then** raster build < 2 s for N_leaves = 50 k.
3. **Given** size-field callable `fh` wrapping the new `locate`, **When** fed to
   `triangulate()`, **Then** distmesh converges to a mesh resolving the river channel
   (≥ 3 nodes across width) for the river-bay SC-001 domain.

---

### User Story 3 — Numerical Parity with Spec 021 Prototype (Priority: P2)

A developer runs both the spec 021 prototype and the 022 rewrite on identical inputs and
verifies the size fields agree within floating-point tolerance.

**Why this priority**: A faster implementation that silently changes size-field values
breaks downstream meshes. Parity must be documented. The octree is a new non-faithful-port
module (Principle I does not require exact MATLAB parity), but self-consistency between
versions matters.

**Independent Test**: Build octrees with both implementations on the notch domain from
`render_octree_proof.py`; compare per-leaf `h` arrays; assert max|Δh| / h_max < 0.05
(5 % tolerance, accounting for leaf placement differences from data-structure changes).

**Acceptance Scenarios**:

1. **Given** notch domain, ratio = 10, **When** spec 021 and 022 builds compared,
   **Then** size-field arrays agree within 5 % pointwise.
2. **Given** river-bay SC-001 domain, **When** both builds used to generate admesh meshes,
   **Then** element counts within 10 % of each other.

---

### User Story 4 — O(N log N) Complexity Documented and Verified (Priority: P2)

A reviewer (or future contributor) can inspect the rewritten code and see no O(N²) or
O(N³) loops, and a scalability benchmark confirms the empirical growth rate.

**Why this priority**: Complexity documentation is a non-negotiable exit criterion —
without it the improvement is unverifiable and future contributors re-introduce regressions.

**Independent Test**: Run `render_scalability.py` with new implementation at ratios
10 / 100 / 1 000; fit power law to (ratio, build_time); assert exponent < 1.5
(sub-quadratic confirmed).

**Acceptance Scenarios**:

1. **Given** build-time measurements at ratio 10 / 100 / 1 000, **When** power-law fit,
   **Then** exponent < 1.5.
2. **Given** code review, **When** `_build_adjacency` and `_balance_2to1` inspected,
   **Then** no O(N²) or O(N³) loops present.
3. **Given** updated `render_scalability.py`, **When** run, **Then** log-log plot shows
   measured points tracking sub-quadratic trend through at least ratio = 1 000.

---

## Edge Cases

- `h_min == h_max` → single root leaf; build must return gracefully without subdivision.
- Oracle returns h > h_max everywhere → no subdivision; root leaf only.
- 2:1 balance would force leaf below h_min → clamp at h_min; do NOT subdivide below floor.
- Empty domain (zero-area bbox) → raise `ValueError("Empty bounding box")`.
- Tree depth > 30 → guard against infinite recursion / float underflow in leaf size.
- Point outside padded bbox → `locate` returns None; `interpolate` returns h_max.

---

## Requirements

### Functional Requirements

- **FR-001**: `build_octree` MUST find neighbors via parent/sibling pointer links during
  subdivision — NOT an all-pairs O(N²) scan after the fact.
- **FR-002**: `_balance_2to1` MUST use a work queue (BFS/DFS over split candidates) — NOT
  rebuild full adjacency per split.
- **FR-003**: `locate(grid, p)` MUST use tree descent (O(log N)) — NOT a linear scan.
- **FR-004**: `leaf_graph(grid)` edge list MUST be derivable from stored neighbor pointers
  in O(N) — NOT from all-pairs comparison.
- **FR-005**: All current public signatures in `octree_grid.py` MUST be preserved:
  `build_octree`, `locate`, `interpolate`, `leaf_graph`, `OctreeGrid`, `OctreeLeaf`.
- **FR-006**: `OctreeLeaf` (or a renamed equivalent) MUST store parent + child references
  enabling O(log N) descent.
- **FR-007**: `admesh/_stages/octree_medial.py` MUST still work without modification — its
  inputs (`grid.leaves`, per-leaf `D`, `leaf_graph`) must remain valid.
- **FR-008**: `render_sizefield_diff.py`, `render_scalability.py`, `render_octree_proof.py`
  MUST produce output without error after the rewrite.
- **FR-009**: Build wall-clock for ratio = 100 domain MUST be < 5 s on a standard laptop
  (single core, no Numba, pure Python).
- **FR-010**: Query wall-clock for 100 k points against 50 k leaves MUST be < 1 s.
- **FR-011**: 2:1 balance MUST NOT introduce leaves below `h_min`.
- **FR-012**: Existing pytest suite (`tests/`) MUST remain green after the rewrite.
- **FR-013**: No new external dependencies beyond stdlib and packages already in
  `requirements.txt` / `pyproject.toml`.

### Key Entities

- **OctreeNode**: Mutable tree node — center, half-size, depth, D, children[4], parent ref,
  neighbor refs[4 cardinal directions]. Replaces the flat `OctreeLeaf` dataclass with a
  pointer-bearing node enabling O(log N) descent and O(1) neighbor lookup during balance.
- **OctreeGrid**: Top-level container. Public face unchanged (`bbox`, `leaves`, `h_min`),
  but `leaves` list now backed by pointer tree rather than brute-force adjacency.
- **BalanceQueue**: Work queue (`collections.deque`) of nodes to check/split during 2:1
  balancing. One-pass BFS; never rebuilds adjacency.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: `build_octree` on ratio-100 domain: wall-clock < 5 s (current ~13 s at
  ratio 40; extrapolates to > 100 s at ratio 100 under O(N²)).
- **SC-002**: `build_octree` on ratio-1 000 domain: completes without timeout; < 30 s.
- **SC-003**: `locate(grid, p)` for 100 k queries against 50 k leaves: total < 1 s.
- **SC-004**: Log-log power-law exponent for build time vs. ratio: < 1.5 across
  ratios 10 / 100 / 1 000.
- **SC-005**: Spec 021 notch-domain size field: max pointwise |Δh| / h_max < 0.05
  between old and new implementation.
- **SC-006**: All existing pytest tests green on `022-octree-perf-rewrite` branch.
- **SC-007**: `render_sizefield_diff.py` river-bay figure: new octree mesh resolves
  ≥ 3 nodes across the river channel (same quality bar as spec 021).

---

## Assumptions

- Spec 021 correctness is trusted — this spec reuses `octree_medial.py` unchanged and
  only rewrites data structures / algorithms in `octree_grid.py`.
- Pure Python (no Numba) sufficient to hit SC-001–SC-004 for ratio ≤ 1 000; Numba is a
  stretch goal (separate spec / issue if needed).
- `h_min` floor from size oracle already handles minimum-leaf-size constraint; no
  additional guard beyond FR-011.
- Constitution Principle I exception from spec 021 authorization still covers
  `admesh/_stages/octree_grid.py` — this spec is the performance tier of that exception.
- 2D quadtree (not 3D octree) remains correct data structure; 3D is out of scope.
- No new external dependencies — stdlib `collections.deque` for work queue is sufficient.
- The spec 021 branch (`021-octree-size-field`) is the baseline to branch from; this spec
  merges or rebases onto it as needed.
