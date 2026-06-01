# Data Model: Spec 022 — Scalable Octree

## OctreeLeaf (rewritten)

Extends spec 021 `OctreeLeaf` with pointer fields. All existing public fields preserved.

```python
@dataclass
class OctreeLeaf:
    # --- existing public fields (spec 021, unchanged) ---
    center: tuple[float, float]
    size: float          # cell side length
    depth: int
    D: float             # signed distance at center (negative = inside)

    # --- new internal pointer fields ---
    _parent_idx: int = -1                         # -1 = root
    _children_idx: list[int] = field(default_factory=lambda: [-1,-1,-1,-1])
                                                  # order: SW, SE, NW, NE
    _neighbor_idx: list[int] = field(default_factory=lambda: [-1,-1,-1,-1])
                                                  # order: W, E, S, N

    # --- public property (back-compat with octree_medial.py) ---
    @property
    def neighbors(self) -> list["OctreeLeaf"]:
        """Return live neighbor leaf objects from the flat node list."""
        ...  # implementation resolves via the shared _nodes list ref
```

**Child quadrant indexing (Morton / Z-order)**:
```
  NW=2 | NE=3
  -----+-----
  SW=0 | SE=1
```
When splitting, child SW center = parent center + (-size/4, -size/4), etc.

**Neighbor direction indexing**:
```
  W=0, E=1, S=2, N=3
```
So `lf._neighbor_idx[0]` = western neighbor index, `lf._neighbor_idx[3]` = northern.

---

## OctreeGrid (unchanged public face)

```python
@dataclass
class OctreeGrid:
    bbox: tuple[float, float, float, float]  # xmin, ymin, xmax, ymax
    root: int                                 # index of root node in `nodes`
    leaves: list[OctreeLeaf]                  # all nodes (internal + leaf)
    h_min: float
```

`leaves` is a misnomer inherited from spec 021 — after the rewrite it contains ALL nodes
(internal + leaf). The name is kept for back-compat; callers that used to iterate
`grid.leaves` and check `lf.D` etc. still work because `_children_idx` tells us if a
node is a true leaf (all children == -1).

Helper predicate:
```python
def _is_leaf(node: OctreeLeaf) -> bool:
    return all(c == -1 for c in node._children_idx)
```

`OctreeGrid.leaves` property filters to true leaves only for back-compat:
Actually — keeping `leaves` as a property returning only leaf nodes would break iteration
inside `build_octree` itself. The flat list of ALL nodes is stored as `_nodes`; the public
`grid.leaves` property returns `[n for n in _nodes if _is_leaf(n)]`. This is O(N_total)
on access but called infrequently (rendering, medial computation).

---

## MedialAxisResult (unchanged from spec 021)

```python
@dataclass
class MedialAxisResult:
    mask: NDArray[bool]    # per-leaf medial flag
    dist: NDArray[float]   # per-leaf medial-axis distance (Dijkstra)
```

No changes needed — `octree_medial.py` consumes `grid.leaves` (now filtered to true
leaves via property) and leaf fields unchanged.

---

## BalanceQueue (internal, not exported)

```python
# Internal only — not part of public API
queue: collections.deque[int]  # indices into _nodes list
```

Used only inside `_balance_2to1`. Not exposed.

---

## Interface invariants

After any call to `build_octree`:

1. Every leaf satisfies: `leaf.size / 2 >= grid.h_min`.
2. Every leaf pair that are true neighbors satisfies: `|leaf.depth - neighbor.depth| <= 1`
   (2:1 balance).
3. Neighbor pointers are symmetric: if `i` in `j._neighbor_idx` then `j` in `i._neighbor_idx`.
4. `leaf.D` is the signed-distance value at `leaf.center` evaluated by the domain's `fd`.
