# Spec 021 — Octree size-field scalability: O(log N) build + query (resolves #115)

**Status:** Planning-phase only. No code shipping in this commit (ADMESH planning profile).
**Issue:** [#115 perf: octree size-field (spec 021) build is O(N²)–O(N³), queries O(N) — not scalable](https://github.com/domattioli/ADMESH/issues/115) — `status: ready`, `type: refactor`, `priority: normal`.
**Related:** PR [#113](https://github.com/domattioli/ADMESH/pull/113) (original octree spec on branch `021-octree-size-field`), [#114](https://github.com/domattioli/ADMESH/issues/114) (grid-agnostic boundary seeding), [#8](https://github.com/domattioli/ADMESH/issues/8) (GPU/CPU acceleration), `admesh/_stages/octree_grid.py`, `scripts/render_scalability.py`, `output/octree_scalability.png`.
**Branch:** `daily-maintenance` (planning); implementation on `021-octree-size-field` or a new feature branch.
**Token budget:** LARGE (data-structure rewrite of `octree_grid.py`; new benchmarks).

---

## 1. Problem statement

The spec 021 octree prototype (`admesh/_stages/octree_grid.py`, PR #113) is **algorithmically correct** but does not scale to the feature-size ratios (10³–10⁴) that real hydrodynamic domains require. Three bottlenecks were identified and measured:

| Bottleneck | Location | Complexity |
|---|---|---|
| `_build_adjacency()` — all-pairs leaf comparison | `octree_grid.py` | **O(N²)** |
| `_balance_2to1()` — rebuilds full adjacency each split | `octree_grid.py` | **O(N³)** worst case |
| `locate()` / `interpolate()` — linear scan per query | `octree_grid.py` | **O(N)** per query → **O(N·Q)** total |

Measured on river-into-bay domain (`scripts/render_scalability.py`):

| Feature-size ratio | Leaves (N) | Build time |
|---|---|---|
| 10 | 1 342 | 1.0 s |
| 20 | 2 920 | 3.7 s |
| 40 | 5 950 | 13.2 s |

Leaf count scales ~linearly with feature-size ratio; build time scales **quadratically**. At a feature-size ratio of 1 000 (modest coastal domain), the current build is intractable (~1 000 s extrapolated). A finer inlet run already timed out (see `output/octree_scalability.png`). The target production ratio 10³–10⁴ requires sub-10-second build+query on a workstation.

## 2. Root cause

The prototype chose Python-dict node storage and a flat list of leaf references. Lookup, adjacency construction, and balancing all operate by iterating that flat list rather than exploiting the implicit tree structure. Three data-structure decisions must change:

1. **No pointer/parent links** → `locate` cannot descend the tree; it must scan all leaves.
2. **Flat adjacency matrix rebuilt each split** → `_balance_2to1` pays O(N²) per split iteration.
3. **No spatial index on leaves** → `interpolate` scans all leaves per query point.

## 3. Proposed fix

Four independent improvements, prioritized by impact:

### 3.1 O(log N) point location via tree descent (P0 — critical)

Replace `locate()` linear scan with a **recursive tree descent**:
- At each internal node, compare query point's coordinates against the node's split axis and threshold; descend into the child that contains the point.
- Depth is bounded by `max_depth`; worst-case cost is O(max_depth) = O(log N).
- `interpolate()` calls `locate()` once per query point; total query cost becomes **O(Q log N)** vs. current O(N·Q).

Key change: internal nodes must store child references (pointer links). Currently only leaves are stored in a flat list; the tree must track the full node hierarchy.

### 3.2 O(N) neighbour finding via parent/sibling links during subdivision (P0 — critical)

Replace `_build_adjacency()` all-pairs loop with **parent/sibling link traversal** during subdivision:
- When a leaf is split, its four children acquire known face-neighbours via the parent's adjacency entries (the T-junction refinement neighbour-finding algorithm — see Samet 1990, §2.3).
- Each split produces O(1) new adjacency entries by re-using the parent's and siblings' already-known links.
- Full adjacency build: **O(N)** rather than O(N²).

### 3.3 Work-queue balancing: O(N log N) 2:1 balancing (P0 — critical)

Replace `_balance_2to1()` (which rebuilds the full adjacency inside its split loop) with a **FIFO work queue** of split candidates:
- Initialize queue with all leaves that violate the 2:1 balance constraint.
- Pop a leaf, split it, enqueue any new violating neighbours (O(4) checks via sibling links from §3.2).
- Repeat until queue is empty.
- Each leaf is enqueued at most once (amortized); total cost **O(N log N)** — dominated by the initial violation scan.

### 3.4 Numba vectorization of per-leaf Python loops (P1 — performance)

Wrap the per-leaf loops in `octree_medial.medial_leaves` and the rasterization step with `@njit` (Numba ahead-of-time compilation):
- Eliminates Python-interpreter overhead for the innermost loops; typical speedup 10–100× on similar stencils.
- Does NOT change output values; parity test against the pre-Numba path at `atol=1e-12` is required.
- Out of scope: GPU offload (issue #8); this is single-threaded Numba only.

## 4. Acceptance criteria

- [ ] **SC-001** (scalability): Build + size-field query for feature-size ratio **≥ 1 000** completes in **< 10 seconds** on the river-into-bay domain on a commodity workstation (8-core, 16 GB RAM). This is the primary deliverable.
- [ ] **SC-002** (leaf count): Leaf count at ratio 1 000 is **≥ 10× below** the uniform-at-finest-resolution baseline (confirming the octree is adaptive, not degenerate). Carries over from spec 021 original SC-004.
- [ ] **SC-003** (build complexity): `scripts/render_scalability.py` reports build time sub-quadratic in leaf count at ratios 10, 20, 40, 80, 160 — specifically, build time grows as O(N log N) or better (verified by log-log slope < 1.2 on those 5 points).
- [ ] **SC-004** (query complexity): Per-query cost grows as O(log N) — verified by profiling `locate()` call count vs. leaf count at the 5 ratio points above.
- [ ] **SC-005** (numerical parity): `size_field_octree(test_points)` output is within `atol=1e-10` of the pre-refactor prototype on the `tests/fixtures/octree/river-into-bay*.npz` fixture set. No numerical regression.
- [ ] **SC-006** (regression): All existing `tests/test_octree_grid.py` tests pass. No regression on the broader suite (`pytest -q` exits 0).
- [ ] **SC-007** (Numba opt, P1): If §3.4 is implemented, a parity test asserts `@njit` and pure-Python paths agree within `atol=1e-12`.
- [ ] **SC-008** (benchmark update): `scripts/render_scalability.py` is extended to ratio 1 000 and produces an updated `output/octree_scalability.png` demonstrating sub-quadratic scaling.

## 5. Implementation notes

### Data model change (critical path)

Current structure (schematic):
```python
class OctreeNode:
    bbox: tuple        # (xmin, xmax, ymin, ymax)
    depth: int
    children: list     # None if leaf
    value: float       # h at leaf centroid
# leaves stored in: self._leaves = [OctreeNode, ...]  # flat list
```

Required additions:
```python
class OctreeNode:
    ...
    parent: 'OctreeNode | None'     # NEW — enables sibling traversal
    neighbours: dict[str, 'OctreeNode | None']  # NEW — face neighbours by direction ('N','S','E','W')
```

The root node's `neighbours` are all `None` (boundary). When a node is split, its four children inherit the parent's neighbours on the external faces and acquire each other as interior face-neighbours.

### Locate algorithm (tree descent)

```python
def locate(self, point):
    node = self._root
    while not node.is_leaf():
        # bisect on the splitting axis (alternating x/y by depth parity)
        mid = 0.5 * (node.bbox[0] + node.bbox[1])  # x midpoint
        if point[0] < mid:
            node = node.children[LEFT]
        else:
            node = node.children[RIGHT]
        # similarly for y axis
    return node
```

### Neighbour-finding during split (Samet 1990 §2.3)

When node `P` (with known neighbours `P.neighbours`) is split into four children `{NW, NE, SW, SE}`:
- `NW.neighbours['N'] = P.neighbours['N']` (external)
- `NW.neighbours['E'] = NE` (internal sibling)
- `NW.neighbours['S'] = SW` (internal sibling)
- `NW.neighbours['W'] = P.neighbours['W']` (external)
- ... (symmetric for NE, SW, SE)

External neighbours (`P.neighbours[d]`) may need to be updated to point back to the child that now faces them (same-depth update O(1); coarser-level neighbour at `P`'s parent stays valid).

### Work-queue balancing

```python
from collections import deque
queue = deque(leaves_violating_2to1())
while queue:
    leaf = queue.popleft()
    if leaf.is_leaf() and violates_2to1(leaf):
        leaf.split()           # O(1) with sibling links
        queue.extend(new_violation_candidates(leaf))  # O(4)
```

## 6. Test plan

| Test | Fixture | Assertion |
|---|---|---|
| `test_locate_descent` | unit-square 4-level octree | `locate(p)` returns correct leaf for 100 random points; call count ≤ `max_depth + 1` |
| `test_adjacency_sibling_links` | hand-constructed 3-level tree | All child neighbour dicts consistent after 2 split operations |
| `test_balance_2to1_queue` | river-into-bay ratio=20 | No leaf in `_leaves` violates 2:1 after `_balance_2to1()`; timing < 1 s |
| `test_scalability_ratio_1000` | river-into-bay ratio=1000 | Build + query < 10 s; leaf count ≥ 10× below uniform baseline |
| `test_parity_vs_prototype` | `tests/fixtures/octree/river-into-bay*.npz` | `size_field_octree(pts)` within `atol=1e-10` of reference output |
| `test_numba_parity` (P1) | unit-square | `@njit` path within `atol=1e-12` of pure-Python path |

## 7. Files likely touched (implementation session)

- `admesh/_stages/octree_grid.py` — `OctreeNode` data model (add `parent`, `neighbours`), rewrite `_build_adjacency`, `_balance_2to1`, `locate`, `interpolate`.
- `admesh/_stages/octree_medial.py` — Numba `@njit` wrapping of per-leaf loops (P1).
- `tests/test_octree_grid.py` — new scalability and parity tests; existing tests preserved.
- `scripts/render_scalability.py` — extend to ratio 1 000; regenerate `output/octree_scalability.png`.
- `docs/PORTING_NOTES.md` — note the data-structure change and its non-impact on numerical output.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Sibling-link correctness is subtle near tree boundaries | Unit-test the neighbour dict exhaustively on a hand-constructed 3-level tree before integration |
| Numba `@njit` compilation adds first-run latency (~1–3 s) | Gate behind `ADMESH_NUMBA=1` env var (same pattern as existing `_solve_iter_nb`); default off in CI |
| Parity regression: pointer-based traversal returns a different leaf for queries near cell boundaries (floating-point tie-breaking) | Use `< mid` consistently (same as the prototype split rule); assert `atol=1e-10` not `==` |
| 2:1 work-queue may loop if split rule has a cycle | Assert `len(queue)` decreases monotonically (add a safety counter cap at `10 * len(leaves)`) |

## 9. Out of scope

- GPU offload of the octree build or query (issue #8).
- Changes to the 13 locked faithful-port stage modules outside `octree_grid.py` / `octree_medial.py` (Constitution Principle I).
- Extending the octree to 3D (current codebase is 2D only).
- Grid-agnostic boundary seeding (spec 024, issue #114 — orthogonal, depends on this spec's `size_field_octree` callable being fast).

## 10. Cross-references

- #115 — this issue's root-cause thread with scalability measurements.
- PR #113 / branch `021-octree-size-field` — original octree prototype; the `spec.md` there is the predecessor to this perf spec.
- #114 / spec 024 — boundary seeding that consumes `size_field_octree`; benefits directly from O(log N) queries.
- #8 — GPU acceleration; builds on the scalable CPU baseline this spec delivers.
- Samet, H. (1990). *The Design and Analysis of Spatial Data Structures.* Addison-Wesley. §2.3 — neighbour-finding algorithm reference.
