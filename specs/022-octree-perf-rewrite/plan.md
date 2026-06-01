# Implementation Plan: Spec 022 — Scalable Octree

**Branch**: `022-octree-perf-rewrite` | **Date**: 2026-06-01 | **Spec**: spec.md  
**Input**: Feature specification + research.md + data-model.md + contracts/

---

## Summary

Rewrite `admesh/_stages/octree_grid.py` from O(N²) all-pairs adjacency + O(N³) balance +
O(N) linear-scan queries to O(N log N) pointer quadtree with work-queue balance and O(log N)
tree-descent queries. Spec 021 proved correctness; this spec makes it production-grade.
`octree_medial.py` and all rendering scripts remain unchanged (backwards-compatible via
`OctreeLeaf.neighbors` property and `grid.leaves` property that filter to true leaves).

---

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: numpy (already in requirements), collections.deque (stdlib)  
**Storage**: In-memory flat list of `OctreeLeaf` objects with integer pointer fields  
**Testing**: pytest, existing suite in `tests/`  
**Target Platform**: Linux laptop / CI (single core, pure Python)  
**Performance Goals**: build < 5 s at ratio 100, < 30 s at ratio 1 000; query < 10 µs each  
**Constraints**: No new external deps; no Numba in Phase 1; backwards-compatible public API  
**Scale/Scope**: 10³–10⁶ leaves; ratios up to 10⁴  
**Project Type**: Library internals — no public API surface change

**Clarifications applied** (see spec.md §Clarifications):
- CL-001: flat list of `OctreeLeaf` + integer index fields (NOT object pointers)
- CL-002: single cardinal neighbor (W/E/S/N)
- CL-003: keep `OctreeLeaf` class name
- CL-004: `locate` clamps OOB to bbox, returns nearest leaf
- Native (Rust/C++) rewrite OUT OF SCOPE — defer to spec 023 if Python misses SC-002

---

## Constitution Check

**GATE: Principle I**  
`octree_grid.py` is NOT a faithful-port locked module — it is a new additive module
introduced in spec 021. The spec 021 authorization covers it. No new Constitution
violation here.

**GATE: Principle II (Numba parity)**  
No Numba in Phase 1. Numba path is a stretch goal; if added, parity test (atol=1e-10)
required. Not a blocker for this spec.

**GATE: Public API**  
`build_octree`, `locate`, `interpolate`, `leaf_graph`, `OctreeGrid`, `OctreeLeaf` — all
preserved. `octree_medial.py` API unchanged. Rendering scripts unchanged.

**Verdict**: No Constitution violation. Proceed.

---

## Project Structure

### Documentation (this feature)

```text
specs/022-octree-perf-rewrite/
├── spec.md              ✓ (this feature)
├── research.md          ✓
├── data-model.md        ✓
├── quickstart.md        ✓
├── contracts/
│   └── octree-scalable.md  ✓
├── plan.md              ✓ (this file)
└── tasks.md             (next: /speckit-tasks)
```

### Source Code

```text
admesh/_stages/
├── octree_grid.py       REWRITE — flat pointer-quadtree, work-queue balance, tree descent
└── octree_medial.py     NO CHANGE (backwards-compatible via contracts C8)

scripts/
├── render_scalability.py   MINOR UPDATE — extend ratio range to 1000
├── render_sizefield_diff.py  NO CHANGE (contracts C9)
└── render_octree_proof.py    NO CHANGE (contracts C9)

tests/
└── test_octree_grid.py  NEW (or update if exists) — parity + speed + invariant tests
```

---

## Phase Strategy

### Phase 1 (P1 blocker): Core data structure + build

Replace `OctreeLeaf` with pointer-bearing version + rewrite `build_octree` to use
`_split_leaf` + `_find_neighbor_of_greater_depth` (Samet 1990). This is the O(N log N)
build. `_balance_2to1` rewritten with work queue.

### Phase 2 (P1 query): Tree descent `locate`

Replace linear scan in `locate` with tree descent. Update `interpolate` to use new
`locate`. Update `leaf_graph` to use stored neighbor pointers (O(N)).

### Phase 3 (P2 parity): Verify parity + benchmark

Run parity check vs spec 021 prototype. Run scalability benchmark. Update
`render_scalability.py` to cover ratio = 1 000. Document results.

### Phase 4 (Polish): Tests + CLAUDE.md update

Add/update `tests/test_octree_grid.py`. Update CLAUDE.md SPECKIT block. Commit + push.

---

## Complexity Tracking

No Constitution violations. No complexity notes required.

---

## Key Algorithms (implementation reference)

### `_find_neighbor_of_greater_depth(nodes, idx, direction) -> int`

```
direction: 0=W, 1=E, 2=S, 3=N
opposite:  0→1, 1→0, 2→3, 3→2

# Child quadrant layout:
# SW=0, SE=1, NW=2, NE=3

# For each direction, which children of a node face that direction:
# W: SW=0, NW=2  → children[0], children[2]
# E: SE=1, NE=3  → children[1], children[3]
# S: SW=0, SE=1  → children[0], children[1]
# N: NW=2, NE=3  → children[2], children[3]

# If node is a "south" child of its parent (SW or SE), then:
#   its northern neighbor is its parent's other child (NW or NE) = sibling
# Otherwise: recurse up to parent, get parent's neighbor in that direction,
#   then descend into the appropriate child.
```

See research.md R3 for full pseudocode.

### `_split_leaf(nodes, idx, domain, size_oracle) -> list[int]`

1. Compute 4 child centers (parent center ± size/4 in x and y).
2. Evaluate `fd` and `size_oracle` at each child center.
3. Append 4 new `OctreeLeaf` objects to `nodes`; set parent_idx; wire sibling neighbors.
4. For each child, for each of its external cardinal directions, call
   `_find_neighbor_of_greater_depth` to wire cross-subtree neighbor pointers.
5. Invalidate parent (mark as internal: `nodes[idx]._children_idx = [c0, c1, c2, c3]`).
6. Return child indices.

### `_balance_2to1(nodes, root_idx, h_min, domain, size_oracle)`

```python
from collections import deque
queue = deque(i for i, n in enumerate(nodes) if _is_leaf(n))
while queue:
    idx = queue.popleft()
    node = nodes[idx]
    if not _is_leaf(node):
        continue  # already split by a prior step
    for nb_idx in node._neighbor_idx:
        if nb_idx == -1:
            continue
        nb = nodes[nb_idx]
        if _is_leaf(nb) and nb.size > node.size * 2 + 1e-9:
            if nb.size / 2 >= h_min:
                new_children = _split_leaf(nodes, nb_idx, domain, size_oracle)
                queue.extend(new_children)
```
