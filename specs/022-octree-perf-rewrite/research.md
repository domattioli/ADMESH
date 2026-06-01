# Research: Spec 022 — Scalable Octree

## R1 — Why the spec 021 prototype is O(N²)/O(N³)

`_build_adjacency(leaves)` in `octree_grid.py`:
```python
for i, a in enumerate(leaves):
    for j, b in enumerate(leaves[i+1:], start=i+1):
        if _are_neighbors(a, b):
            ...
```
This is N*(N-1)/2 pair checks → O(N²).

`_balance_2to1(leaves, ...)`:
```python
changed = True
while changed:
    changed = False
    adjacency = _build_adjacency(leaves)   # O(N²) rebuild each pass
    for leaf in leaves:
        for nb in adjacency[id(leaf)]:
            if leaf.size < nb.size / 2:
                ...split nb...
                changed = True
```
Each split may trigger another pass → O(N³) worst case.

`locate(grid, p)`:
```python
for leaf in grid.leaves:
    if (abs(p[0]-leaf.center[0]) <= leaf.size/2 and
        abs(p[1]-leaf.center[1]) <= leaf.size/2):
        return leaf
```
O(N) per query.

## R2 — Correct approach: pointer quadtree with flat node array

**Core insight**: during top-down subdivision, the parent knows exactly which children it
creates and which of its own neighbors are adjacent to each child. Neighbor wiring can be
done at split time in O(1) per child, not O(N) globally after the fact.

Classic algorithm (Samet 1990, "The Design and Analysis of Spatial Data Structures"):
- Each node stores 4 children (NW, NE, SW, SE) and 4 cardinal neighbors (N, S, E, W).
- At split: new children's inter-sibling neighbors are wired directly.
- New children's external neighbors (facing the parent's old neighbors) are found by
  a O(log N) descent into the neighbor tree (`find_neighbor_of_greater_depth`).
- Net: O(N log N) total for a complete build.

**Implementation choice for ADMESH**: flat Python list of `OctreeLeaf` objects + integer
index fields. Avoids circular references, easy to inspect, numpy-convertible. Internal
arrays: `children: np.ndarray[4, int]`, `parent: int`, `neighbors: np.ndarray[4, int]`.
Sentinel -1 = absent (root has parent=-1; leaves have children=[-1,-1,-1,-1]).

## R3 — Neighbor-of-greater-depth algorithm (Samet)

```
neighbor_of_equal_or_greater_depth(node, direction):
    if node.parent == -1:          # root has no neighbor
        return -1
    parent = nodes[node.parent]
    if node is interior child of parent in `direction`:
        # sibling is directly adjacent in that direction
        return parent.children[reflect(child_index, direction)]
    else:
        # recurse up, then descend
        mu = neighbor_of_equal_or_greater_depth(parent, direction)
        if mu == -1 or is_leaf(nodes[mu]):
            return mu
        return nodes[mu].children[reflect(child_index, direction)]
```
This is O(depth) = O(log N) per neighbor lookup. Called once per child per direction at
split time → O(4 × log N) per split × N splits = O(N log N) total.

## R4 — O(N) balance with work queue

Instead of rebuilding adjacency and re-scanning all leaves, a work queue (BFS):
```
queue = deque(all leaves initially)
while queue:
    node = queue.popleft()
    if is_leaf(node):
        for each cardinal neighbor nb of node:
            if nb is coarser by > 1 level:
                split(nb)
                push nb's new children to queue
```
Each node is enqueued at most O(1) times per balance pass (amortized under 2:1 constraint).
Total work: O(N) amortized. No full adjacency rebuild inside the loop.

## R5 — O(log N) point location via tree descent

```
locate(root_idx, nodes, p):
    idx = root_idx
    while not is_leaf(nodes[idx]):
        quadrant = which_child(nodes[idx].center, p)
        child = nodes[idx].children[quadrant]
        if child == -1:  # this quadrant not subdivided
            return idx   # current node is the deepest covering node
        idx = child
    return idx
```
Descent depth = O(log N). Handles out-of-bounds by clamping p to bbox before descent.

## R6 — `leaf_graph` in O(N)

With neighbor pointers stored per leaf, `leaf_graph` is:
```python
edges = []
for i, lf in enumerate(nodes):
    if not is_leaf(lf): continue
    for nb_idx in lf.neighbors:
        if nb_idx != -1 and nb_idx > i:   # each edge once
            spacing = (lf.size + nodes[nb_idx].size) / 2
            edges.append((i, nb_idx, spacing))
return edges
```
O(N) — one pass over leaves, O(1) per leaf.

## R7 — Compatibility preservation

`OctreeLeaf` keeps existing fields (`center`, `size`, `depth`, `D`, `neighbors`). The
`neighbors` attribute is currently a `dict` keyed by object id. After rewrite it becomes
a list of actual `OctreeLeaf` objects (same external access pattern `lf.neighbors`) —
`octree_medial.py` iterates over `lf.neighbors` without knowing the storage type, so it
remains unchanged.

Internally: `OctreeLeaf._neighbor_idx: list[int]` (integer indices into flat node list)
is stored for tree operations; the public `.neighbors` property reconstructs the
neighbor leaf list from indices on demand. This decouples the fast internal representation
from the external API.

## R8 — No new dependencies

`collections.deque` (stdlib) for work queue. `numpy` array fields on `OctreeLeaf` for
child/parent indices. Both already available.

## R9 — Benchmark design

Three domains at ratios 10 / 100 / 1 000:
- `build_octree` wall-clock
- `len(grid.leaves)` 
- Power-law fit: `t ∝ N^α` — expect α ≈ 1.0–1.2 (sub-linear due to boundary-dominated
  leaf count + O(N log N) build)
- Comparison curve: spec 021 prototype at same ratios (if tractable; expected to fail at
  ratio 100+)
