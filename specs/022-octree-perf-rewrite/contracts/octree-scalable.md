# Internal Interface Contracts: Spec 022

## C1 — `build_octree` (rewritten)

**Signature** (unchanged):
```python
def build_octree(
    domain,
    *,
    h_min: float,
    h_max: float,
    size_oracle: Callable[[float, float], float],
    padding: float | None = None,
    balance: bool = True,
) -> OctreeGrid
```

**Complexity**: O(N log N) in leaf count N.  
**Guarantee**: No O(N²) all-pairs scan; no adjacency rebuild inside balance loop.  
**Invariants**: see data-model.md §Interface invariants.

## C2 — `locate` (rewritten)

**Signature** (unchanged):
```python
def locate(grid: OctreeGrid, p: array_like) -> OctreeLeaf
```

**Complexity**: O(log N).  
**Out-of-bounds**: clamps `p` to `grid.bbox` before descent; returns nearest boundary leaf.  
**Never returns None** (changed from spec 021 edge-case behavior; safer for distmesh).

## C3 — `interpolate` (unchanged signature, faster path)

**Signature** (unchanged):
```python
def interpolate(grid: OctreeGrid, values: NDArray, p: array_like) -> float
```

Delegates to `locate`; inherits O(log N) from C2. `values` must be indexed parallel to
`grid.leaves` (true leaves only, same order as returned by `grid.leaves` property).

## C4 — `leaf_graph` (rewritten)

**Signature** (unchanged):
```python
def leaf_graph(grid: OctreeGrid) -> tuple[NDArray[int], NDArray[float]]
```
Returns `(edges [M×2], spacing [M])`.  
**Complexity**: O(N) — single pass over leaf nodes using stored neighbor pointers.  
**Output**: same format as spec 021 (no caller changes needed).

## C5 — `_balance_2to1` (rewritten, internal)

**Signature** (internal):
```python
def _balance_2to1(nodes: list[OctreeLeaf], root_idx: int, h_min: float, domain, size_oracle) -> None
```
Mutates `nodes` in-place. Uses BFS work queue. Does NOT call `_build_adjacency`.  
**Complexity**: O(N log N) amortized (each leaf enqueued O(1) times under 2:1 constraint).

## C6 — `_split_leaf` (new internal helper)

```python
def _split_leaf(nodes: list[OctreeLeaf], idx: int, domain, size_oracle) -> list[int]
```
Splits leaf at `idx` into 4 children; appends children to `nodes`; wires sibling neighbors
using direct index arithmetic; wires external neighbors via `_find_neighbor_of_greater_depth`.
Returns list of 4 new child indices.  
**Complexity**: O(log N) per call (dominated by neighbor-of-greater-depth descent).

## C7 — `_find_neighbor_of_greater_depth` (new internal helper)

```python
def _find_neighbor_of_greater_depth(nodes, idx, direction) -> int
```
Samet (1990) algorithm. Returns index of neighbor leaf at same or greater depth,
or -1 if none (boundary). Direction: 0=W, 1=E, 2=S, 3=N.  
**Complexity**: O(depth) = O(log N).

## C8 — Backward compatibility with `octree_medial.py`

`octree_medial.py` uses:
- `grid.leaves` → still returns list of true leaf `OctreeLeaf` objects ✓
- `lf.center`, `lf.size`, `lf.depth`, `lf.D` → unchanged fields ✓
- `lf.neighbors` → still a list of `OctreeLeaf` objects (via property) ✓
- `leaf_graph(grid)` → same signature and output format ✓

**No changes to `octree_medial.py` required.**

## C9 — Backward compatibility with rendering scripts

`render_octree_proof.py`, `render_sizefield_diff.py`, `render_scalability.py` access:
- `grid.leaves` (iteration) ✓
- `lf.center`, `lf.size`, `lf.D` ✓
- `build_octree(dom, h_min=..., h_max=..., size_oracle=..., balance=...)` ✓

**No changes to rendering scripts required** (they should run unchanged after the rewrite).
