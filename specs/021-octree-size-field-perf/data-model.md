# Data Model: OctreeNode (pointer tree)

**Feature**: specs/021-octree-size-field-perf | **Date**: 2026-06-02

## OctreeNode

Replaces the prototype's flat-list node with a pointer-linked tree node.

```python
@dataclass
class OctreeNode:
    bbox: tuple[np.ndarray, np.ndarray]   # (min_corner, max_corner) shape (2,)
    depth: int
    parent: OctreeNode | None             # NEW — root has parent=None
    children: list[OctreeNode]            # len 4 (internal) or 0 (leaf)
    neighbours: dict[str, OctreeNode | None]  # keys: 'N', 'S', 'E', 'W'
    # Prototype fields retained:
    h_field: float | None                 # size-field value at leaf centre
    points: np.ndarray | None             # pts inside this leaf (leaf only)
```

### Invariants

| Invariant | Enforced by |
|---|---|
| `len(children) in {0, 4}` | `split()` always produces exactly 4 children |
| `child.parent is self` for all children | `split()` sets on creation |
| `neighbours` keys subset of `{'N','S','E','W'}` | `split()` + `wire_neighbours()` |
| `depth == parent.depth + 1` | `split()` constructor call |
| `h_field is not None` for leaves | `build_h_field()` gate |

### State transitions

```
(root, depth=0, leaf)
    │  split()
    ▼
(internal, depth=0, 4 children) → each child is a leaf at depth=1
    │  child.split()
    ▼
(internal, depth=1, 4 children) → ...
    └── max_depth reached: split() blocked → leaf persists
```

### Neighbour-finding during split()

When a node `P` splits into children `C[0..3]` (layout: `C[0]=SW, C[1]=SE, C[2]=NW, C[3]=NE`):

**Sibling links (O(1)):**
```
C[0].neighbours['E'] = C[1]   C[1].neighbours['W'] = C[0]
C[0].neighbours['N'] = C[2]   C[2].neighbours['S'] = C[0]
C[1].neighbours['N'] = C[3]   C[3].neighbours['S'] = C[1]
C[2].neighbours['E'] = C[3]   C[3].neighbours['W'] = C[2]
```

**Cross-parent links (O(depth)):**
Locate `P.neighbours[dir]`, descend to its appropriate child (opposite face). Wire. Example: `C[0].neighbours['W'] = find_eastern_child(P.neighbours['W'])`.

## OctreeTree (container)

```python
@dataclass
class OctreeTree:
    root: OctreeNode
    max_depth: int
    leaves: list[OctreeNode]   # flat list maintained for iteration (NOT for locate)
```

`leaves` is used by `interpolate_batch()` and `balance_2to1()` candidate detection only. It is NOT the locate index.

## Public interface (unchanged from prototype)

```python
def size_field_octree(
    domain: Domain,
    h_min: float,
    h_max: float,
    max_depth: int = 12,
    numba: bool = False,          # NEW: gate for P4 Numba path
) -> Callable[[np.ndarray], np.ndarray]:
    """Return fh(pts) -> h callable. Interface identical to prototype."""
```

Caller (e.g. `triangulate()`) sees no change — same `fh` callable contract. Internal tree structure is an implementation detail.
