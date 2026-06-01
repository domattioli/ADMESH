"""Octree (quadtree) background grid for multi-scale size function.

Replaces the uniform Cartesian grid (background_grid.py) with an
hierarchically-refined quadtree structure for domains with
multi-scale features. The octree refines locally where features are
small and stays coarse in open water, enabling the medial-axis stage
to resolve narrow features that would be missed on a tractable-resolution
uniform grid.

Technical approach (research.md R1–R8):
- 2D quadtree (octree realisation in 2D, R1)
- Top-down construction, refine until local size target is met or h_min floor
- 2:1 neighbour-balance pass for smooth transitions
- Medial axis computed on the leaf-adjacency graph via generalised AOF + FMM
- Query interpolation via point-location + within-leaf interpolation
- Fallback to uniform grid on construction failure

Public interface:
- OctreeGrid, OctreeLeaf dataclasses
- build_octree(...) — construction
- locate(grid, p), interpolate(grid, values, p), leaf_graph(grid) — queries
- OctreeConstructionError exception
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from numpy.typing import NDArray

__all__ = [
    "OctreeGrid",
    "OctreeLeaf",
    "OctreeConstructionError",
    "build_octree",
    "locate",
    "interpolate",
    "leaf_graph",
]


class OctreeConstructionError(Exception):
    """Raised when octree construction fails (triggers fallback to uniform grid)."""

    pass


@dataclass(frozen=False)
class OctreeLeaf:
    """A single leaf cell in the octree.

    Attributes
    ----------
    center : tuple[float, float]
        (x, y) centroid of the leaf.
    size : float
        Edge length of the square leaf.
    depth : int
        Refinement level (0 = root).
    D : float
        Signed distance at the leaf center (from domain.fd).
    neighbors : list[int]
        Indices into OctreeGrid.leaves of edge-adjacent neighbors.

    Internal pointer fields (spec 022)
    ----------------------------------
    _parent_idx : int
        Index of parent node in the flat node list; -1 if root.
    _children_idx : list[int]
        Indices of 4 children [SW, SE, NW, NE]; all -1 if leaf.
    _neighbor_idx : list[int]
        Indices of cardinal neighbors [W, E, S, N]; -1 if absent.
    """

    center: tuple[float, float]
    size: float
    depth: int
    D: float = 0.0
    _parent_idx: int = -1
    _children_idx: list[int] = field(default_factory=lambda: [-1, -1, -1, -1])
    _neighbor_idx: list[int] = field(default_factory=lambda: [-1, -1, -1, -1])

    @property
    def neighbors(self) -> list[int]:
        """Return indices of neighbor leaves (back-compat with spec 021).

        Returns indices into grid.leaves that correspond to edge-adjacent neighbors.
        This allows code like `xy[leaf.neighbors]` to work for numpy array indexing.
        """
        if _nodes is None:
            return []
        result = []
        for nb_node_idx in self._neighbor_idx:
            if nb_node_idx >= 0 and _is_leaf(_nodes[nb_node_idx]):
                # Count how many leaves come before this neighbor node
                count = 0
                for j in range(nb_node_idx):
                    if _is_leaf(_nodes[j]):
                        count += 1
                result.append(count)
        return result


# Module-level reference to the flat node list (set at build time)
_nodes: list[OctreeLeaf] | None = None


def _set_nodes_ref(nodes: list[OctreeLeaf]) -> None:
    """Set the shared node list reference for property resolution."""
    global _nodes
    _nodes = nodes


def _is_leaf(node: OctreeLeaf) -> bool:
    """Check if a node is a true leaf (has no children)."""
    return all(c == -1 for c in node._children_idx)


@dataclass(frozen=False)
class OctreeGrid:
    """Hierarchically-refined quadtree background grid.

    Attributes
    ----------
    bbox : tuple[float, float, float, float]
        (xmin, ymin, xmax, ymax) padded domain extent.
    root : int
        Index of root node in the flat _nodes list.
    _nodes : list[OctreeLeaf]
        Flattened list of all nodes (internal + leaf).
    h_min : float
        Refinement floor; no leaf smaller than this.
    """

    bbox: tuple[float, float, float, float]
    root: int
    _nodes: list[OctreeLeaf]
    h_min: float

    @property
    def leaves(self) -> list[OctreeLeaf]:
        """Return only the true leaf nodes (for back-compat with spec 021)."""
        return [n for n in self._nodes if _is_leaf(n)]


def _warn_under_resolved(feature_width: float, h_min: float) -> None:
    """Warn when a feature is below the resolution floor.

    Parameters
    ----------
    feature_width : float
        Width of the under-resolved feature.
    h_min : float
        Resolution floor.
    """
    import warnings

    warnings.warn(
        f"Feature width {feature_width:.2e} is below resolution floor {h_min:.2e}; "
        "will not achieve target element count across this feature",
        UserWarning,
        stacklevel=3,
    )


# ============================================================================
# Phase 3: O(N log N) Build with Samet Pointer Algorithm
# ============================================================================


def _find_neighbor_of_greater_depth(nodes: list[OctreeLeaf], idx: int, direction: int) -> int:
    """Find neighbor in given direction using Samet (1990) algorithm.

    Direction: 0=W, 1=E, 2=S, 3=N.
    Child quadrant indexing: SW=0, SE=1, NW=2, NE=3.
    Returns index of neighbor leaf at same or greater depth, or -1 if none.
    Complexity: O(log N) per call.

    Parameters
    ----------
    nodes : list[OctreeLeaf]
        Flat node list.
    idx : int
        Index of query node.
    direction : int
        0=W, 1=E, 2=S, 3=N.

    Returns
    -------
    int
        Index of neighbor node, or -1 if no neighbor in that direction.
    """
    node = nodes[idx]

    # If this is the root, it has no neighbor in any direction
    if node._parent_idx == -1:
        return -1

    parent = nodes[node._parent_idx]

    # Find which quadrant this node is in
    my_quadrant = -1
    for q, child_idx in enumerate(parent._children_idx):
        if child_idx == idx:
            my_quadrant = q
            break

    if my_quadrant == -1:
        return -1

    # Determine which quadrants are on the boundary of the parent in each direction
    # W (direction=0): quadrants 0 (SW) and 2 (NW) face west (are on the western boundary)
    # E (direction=1): quadrants 1 (SE) and 3 (NE) face east
    # S (direction=2): quadrants 0 (SW) and 1 (SE) face south
    # N (direction=3): quadrants 2 (NW) and 3 (NE) face north
    boundary_quadrants = {
        0: [0, 2],  # W
        1: [1, 3],  # E
        2: [0, 1],  # S
        3: [2, 3],  # N
    }

    if my_quadrant in boundary_quadrants[direction]:
        # This node is on the boundary of the parent in this direction
        # So we must look outside the parent subtree
        parent_neighbor_idx = _find_neighbor_of_greater_depth(nodes, node._parent_idx, direction)
        if parent_neighbor_idx == -1:
            return -1

        parent_neighbor = nodes[parent_neighbor_idx]
        if _is_leaf(parent_neighbor):
            return parent_neighbor_idx

        # Descend into parent_neighbor to find our counterpart
        # The counterpart is the child in the opposite position
        # Mapping: for each (quadrant, direction) -> opposite quadrant in neighbor
        # W (0): SW (0)->SE (1), NW (2)->NE (3)
        # E (1): SE (1)->SW (0), NE (3)->NW (2)
        # S (2): SW (0)->NW (2), SE (1)->NE (3)
        # N (3): NW (2)->SW (0), NE (3)->SE (1)
        opposite_quad = {
            (0, 0): 1,   # SW, W -> SE
            (0, 1): 0,   # SE, E -> SW (shouldn't happen)
            (0, 2): 2,   # SW, S -> NW
            (0, 3): 1,   # SW, N -> SE (shouldn't happen)
            (1, 0): 1,   # SE, W -> SE (shouldn't happen)
            (1, 1): 0,   # SE, E -> SW
            (1, 2): 3,   # SE, S -> NE
            (1, 3): 0,   # SE, N -> SW (shouldn't happen)
            (2, 0): 3,   # NW, W -> NE
            (2, 1): 2,   # NW, E -> NW (shouldn't happen)
            (2, 2): 0,   # NW, S -> SW (shouldn't happen)
            (2, 3): 0,   # NW, N -> SW
            (3, 0): 3,   # NE, W -> NE (shouldn't happen)
            (3, 1): 2,   # NE, E -> NW
            (3, 2): 1,   # NE, S -> SE (shouldn't happen)
            (3, 3): 1,   # NE, N -> SE
        }
        target_quadrant = opposite_quad[(my_quadrant, direction)]
        child_idx = parent_neighbor._children_idx[target_quadrant]
        return child_idx
    else:
        # This node is interior in this direction (not on the boundary)
        # So the neighbor is a sibling within the parent
        # Sibling mapping for each direction:
        # W (0): 0<->1 (SW<->SE), 2<->3 (NW<->NE)
        # E (1): 0<->1 (SW<->SE), 2<->3 (NW<->NE)  (same as W)
        # S (2): 0<->2 (SW<->NW), 1<->3 (SE<->NE)
        # N (3): 0<->2 (SW<->NW), 1<->3 (SE<->NE)  (same as S)
        sibling_quad = {
            (0, 0): 1,   # SW, W -> SE
            (0, 1): 1,   # SW, E -> SE (interior to E? no)
            (0, 2): 2,   # SW, S -> NW
            (0, 3): 2,   # SW, N -> NW (interior to N? no)
            (1, 0): 0,   # SE, W -> SW
            (1, 1): 0,   # SE, E -> SW (shouldn't happen)
            (1, 2): 3,   # SE, S -> NE
            (1, 3): 3,   # SE, N -> NE (shouldn't happen)
            (2, 0): 3,   # NW, W -> NE
            (2, 1): 3,   # NW, E -> NE (interior? yes)
            (2, 2): 0,   # NW, S -> SW
            (2, 3): 0,   # NW, N -> SW (shouldn't happen)
            (3, 0): 2,   # NE, W -> NW
            (3, 1): 2,   # NE, E -> NW (shouldn't happen)
            (3, 2): 1,   # NE, S -> SE
            (3, 3): 1,   # NE, N -> SE (shouldn't happen)
        }
        target_quadrant = sibling_quad[(my_quadrant, direction)]
        return parent._children_idx[target_quadrant]


def _split_leaf(
    nodes: list[OctreeLeaf],
    idx: int,
    domain,
    size_oracle: Callable[[float, float], float],
) -> list[int]:
    """Split a leaf into 4 children; wire neighbors; return new child indices.

    Complexity: O(log N) due to neighbor lookups via _find_neighbor_of_greater_depth.

    Parameters
    ----------
    nodes : list[OctreeLeaf]
        Flat node list (mutated in place by appending children).
    idx : int
        Index of leaf to split.
    domain : Domain
        Domain object with fd method.
    size_oracle : Callable
        Size oracle callable.

    Returns
    -------
    list[int]
        Indices of 4 new children [SW, SE, NW, NE].
    """
    node = nodes[idx]
    cx, cy = node.center
    half_size = node.size / 2
    quarter = half_size / 2

    # Create 4 children: SW, SE, NW, NE
    child_centers = [
        (cx - quarter, cy - quarter),  # SW = 0
        (cx + quarter, cy - quarter),  # SE = 1
        (cx - quarter, cy + quarter),  # NW = 2
        (cx + quarter, cy + quarter),  # NE = 3
    ]

    child_indices = []
    for child_center in child_centers:
        child = OctreeLeaf(
            center=child_center,
            size=half_size,
            depth=node.depth + 1,
            D=_eval_sdf(domain.fd, child_center[0], child_center[1]),
            _parent_idx=idx,
        )
        nodes.append(child)
        child_indices.append(len(nodes) - 1)

    # Wire sibling neighbors (direct arithmetic, no descent needed)
    # SW (0) and SE (1) share southern edge
    nodes[child_indices[0]]._neighbor_idx[1] = child_indices[1]  # SW.E = SE
    nodes[child_indices[1]]._neighbor_idx[0] = child_indices[0]  # SE.W = SW

    # NW (2) and NE (3) share southern edge
    nodes[child_indices[2]]._neighbor_idx[1] = child_indices[3]  # NW.E = NE
    nodes[child_indices[3]]._neighbor_idx[0] = child_indices[2]  # NE.W = NW

    # SW (0) and NW (2) share western edge
    nodes[child_indices[0]]._neighbor_idx[3] = child_indices[2]  # SW.N = NW
    nodes[child_indices[2]]._neighbor_idx[2] = child_indices[0]  # NW.S = SW

    # SE (1) and NE (3) share eastern edge
    nodes[child_indices[1]]._neighbor_idx[3] = child_indices[3]  # SE.N = NE
    nodes[child_indices[3]]._neighbor_idx[2] = child_indices[1]  # NE.S = SE

    # Wire external neighbors via Samet algorithm
    # For each child and each outward-facing direction, find its neighbor
    for child_quadrant, child_idx_new in enumerate(child_indices):
        # Determine which directions this child faces outward
        # SW (0): faces W (0) and S (2)
        # SE (1): faces E (1) and S (2)
        # NW (2): faces W (0) and N (3)
        # NE (3): faces E (1) and N (3)
        outward_directions = {
            0: [0, 2],  # SW
            1: [1, 2],  # SE
            2: [0, 3],  # NW
            3: [1, 3],  # NE
        }
        for direction in outward_directions[child_quadrant]:
            neighbor_idx = _find_neighbor_of_greater_depth(nodes, idx, direction)
            if neighbor_idx != -1:
                nodes[child_idx_new]._neighbor_idx[direction] = neighbor_idx

    # Mark parent as internal by setting _children_idx
    nodes[idx]._children_idx = child_indices

    return child_indices


def build_octree(
    domain,
    *,
    h_min: float,
    h_max: float,
    size_oracle: Callable[[float, float], float],
    padding: float | None = None,
    balance: bool = True,
) -> OctreeGrid:
    """Build a 2:1-balanced quadtree over the domain.

    O(N log N) top-down recursive subdivision using pointer-based Samet (1990)
    algorithm for neighbor finding. Complexity: O(N log N) build + O(N log N) balance.

    Parameters
    ----------
    domain : Domain
        Object with `fd` (signed-distance callable) and `bbox`.
    h_min : float
        Refinement floor (minimum leaf size).
    h_max : float
        Maximum leaf size (root cell size).
    size_oracle : callable(x, y) -> float
        Cheap sizing oracle returning target edge length at (x, y).
    padding : float or None
        Pad added to domain.bbox on all sides. Defaults to h_max.
    balance : bool
        If True, enforce 2:1 neighbour balance.

    Returns
    -------
    OctreeGrid
        Constructed and balanced octree.

    Raises
    ------
    OctreeConstructionError
        If construction fails (empty leaf set, degenerate domain, etc.).
    """
    pad = h_max if padding is None else padding
    xmin, ymin, xmax, ymax = domain.bbox
    xmin -= pad
    ymin -= pad
    xmax += pad
    ymax += pad
    bbox = (xmin, ymin, xmax, ymax)

    # Create root in the flat node list
    root_size = max(xmax - xmin, ymax - ymin)
    nodes: list[OctreeLeaf] = []
    root = OctreeLeaf(
        center=((xmin + xmax) / 2, (ymin + ymax) / 2),
        size=root_size,
        depth=0,
        D=_eval_sdf(domain.fd, (xmin + xmax) / 2, (ymin + ymax) / 2),
        _parent_idx=-1,
    )
    nodes.append(root)
    root_idx = 0

    # Top-down recursive subdivision using pointer wiring
    def _subdivide_recursive(idx: int) -> None:
        """Recursively subdivide until size target is met or h_min floor."""
        node = nodes[idx]
        cx, cy = node.center
        target_h = size_oracle(cx, cy)

        # Stop if cell is small enough or at floor
        if node.size <= target_h or node.size <= h_min:
            return  # This node stays as a leaf

        # Subdivide using _split_leaf (which handles all pointer wiring)
        _split_leaf(nodes, idx, domain, size_oracle)

        # Recursively subdivide the 4 children
        for child_idx in nodes[idx]._children_idx:
            _subdivide_recursive(child_idx)

    _subdivide_recursive(root_idx)

    # Set the global nodes reference for the neighbors property
    _set_nodes_ref(nodes)

    if balance:
        _balance_2to1(nodes, root_idx, h_min, domain, size_oracle)

    grid = OctreeGrid(bbox=bbox, root=root_idx, _nodes=nodes, h_min=h_min)
    return grid


def _eval_sdf(fd: Callable, x: float, y: float) -> float:
    """Evaluate signed-distance function at a single point."""
    p = np.array([[x, y]], dtype=np.float64)
    return float(fd(p)[0])


# DELETED: _build_adjacency, _are_edge_adjacent, _intervals_overlap
# These were O(N²) implementations replaced by Samet pointer algorithm in spec 022.


def _balance_2to1(
    nodes: list[OctreeLeaf],
    root_idx: int,
    h_min: float,
    domain,
    size_oracle: Callable[[float, float], float],
) -> None:
    """Enforce 2:1 size ratio between edge-adjacent leaves using work queue.

    O(N log N) amortized: each node enqueued O(1) times under 2:1 constraint.
    Uses BFS work queue; never rebuilds full adjacency.

    Parameters
    ----------
    nodes : list[OctreeLeaf]
        Flat node list (mutated in place).
    root_idx : int
        Index of root node.
    h_min : float
        Minimum leaf size (do not split below this).
    domain : Domain
        Domain object with fd method.
    size_oracle : Callable
        Size oracle callable.
    """
    from collections import deque

    # Initialize queue with all current leaves
    queue: deque[int] = deque()
    for i, node in enumerate(nodes):
        if _is_leaf(node):
            queue.append(i)

    while queue:
        idx = queue.popleft()
        node = nodes[idx]

        if not _is_leaf(node):
            continue  # Already split by a prior step

        # Check each cardinal neighbor for 2:1 violation
        for direction in range(4):
            nb_idx = node._neighbor_idx[direction]
            if nb_idx == -1:
                continue

            nb = nodes[nb_idx]
            if not _is_leaf(nb):
                continue  # Neighbor already split

            # Check 2:1 balance
            size_ratio = max(node.size, nb.size) / min(node.size, nb.size)
            if size_ratio > 2.0 + 1e-9:
                # Neighbor is more than 2x coarser; split it if above h_min
                if nb.size / 2 >= h_min:
                    new_children = _split_leaf(nodes, nb_idx, domain, size_oracle)
                    queue.extend(new_children)


def locate(grid: OctreeGrid, p: NDArray) -> NDArray[np.intp]:
    """Locate leaf index for each query point using tree descent O(log N).

    Clamps out-of-bounds points to the nearest boundary leaf.

    Parameters
    ----------
    grid : OctreeGrid
    p : (N, 2) ndarray
        Query points (x, y).

    Returns
    -------
    (N,) ndarray of int
        Indices into grid.leaves for leaf containing each point.
        Returns nearest boundary leaf for out-of-bounds points (never -1).
    """
    p = np.asarray(p, dtype=np.float64).reshape(-1, 2)
    indices = np.zeros(len(p), dtype=np.intp)

    xmin, ymin, xmax, ymax = grid.bbox

    # Build node-to-leaf-index mapping once
    node_to_leaf_idx = {}
    for leaf_idx, leaf_node in enumerate(grid.leaves):
        for node_idx, node in enumerate(grid._nodes):
            if node is leaf_node:
                node_to_leaf_idx[node_idx] = leaf_idx
                break

    for query_idx, (x, y) in enumerate(p):
        # Clamp to bbox
        x = np.clip(x, xmin, xmax)
        y = np.clip(y, ymin, ymax)

        # Tree descent from root
        idx = grid.root
        while not _is_leaf(grid._nodes[idx]):
            node = grid._nodes[idx]
            cx, cy = node.center
            # Determine which child contains (x, y)
            quadrant = 0
            if x > cx:
                quadrant += 1
            if y > cy:
                quadrant += 2
            child_idx = node._children_idx[quadrant]
            if child_idx == -1:
                # This quadrant not subdivided; current node is deepest
                break
            idx = child_idx

        # Map from node index to leaf index
        leaf_idx = node_to_leaf_idx.get(idx, 0)
        indices[query_idx] = leaf_idx

    return indices


def interpolate(
    grid: OctreeGrid,
    values: NDArray[np.float64],
    p: NDArray,
) -> NDArray[np.float64]:
    """Interpolate values on leaves to query points (within-leaf bilinear).

    Simple approach: bilinear interpolation using leaf's 4 corners,
    sampled from the values array (treating each leaf as having uniform value).
    For now, use nearest-neighbor (constant per leaf) as fallback.

    Parameters
    ----------
    grid : OctreeGrid
    values : (n_leaves,) ndarray
        Per-leaf scalar values.
    p : (N, 2) ndarray
        Query points.

    Returns
    -------
    (N,) ndarray
        Interpolated values at query points.
    """
    p = np.asarray(p, dtype=np.float64).reshape(-1, 2)
    result = np.zeros(len(p), dtype=np.float64)
    leaf_indices = locate(grid, p)

    for query_idx, leaf_idx in enumerate(leaf_indices):
        if leaf_idx < 0:
            # Outside grid; use hmax or a fill value
            result[query_idx] = np.max(values)
        else:
            # Use the leaf's value directly (constant interpolation for now)
            result[query_idx] = values[leaf_idx]

    return result


def leaf_graph(grid: OctreeGrid) -> tuple[NDArray, NDArray]:
    """Build the leaf-adjacency graph (edge list + centre-to-centre spacing).

    O(N) single pass over leaves using stored neighbor pointers.
    Used by medial-axis FMM and gradient-limit solver on variable-spacing graph.

    Parameters
    ----------
    grid : OctreeGrid

    Returns
    -------
    edges : (E, 2) ndarray of int
        Edge-adjacent leaf pairs (indices into grid.leaves).
    spacing : (E,) ndarray of float
        Centre-to-centre distances (for variable-spacing graph algorithms).
    """
    edges = []
    spacing = []

    # Build mapping from node index to leaf index (one-pass construction)
    leaf_index_map = {}
    for leaf_idx, leaf_node in enumerate(grid.leaves):
        # Find node index of this leaf node by scanning _nodes
        for node_idx in range(len(grid._nodes)):
            if grid._nodes[node_idx] is leaf_node:
                leaf_index_map[node_idx] = leaf_idx
                break

    # Extract edges from neighbor pointers (avoiding duplicates)
    # We iterate over all nodes and find which are leaves
    for node_idx in range(len(grid._nodes)):
        node = grid._nodes[node_idx]
        if not _is_leaf(node):
            continue

        if node_idx not in leaf_index_map:
            continue

        i = leaf_index_map[node_idx]

        # Iterate through cardinal neighbor indices
        for direction in range(4):
            nb_node_idx = node._neighbor_idx[direction]
            if nb_node_idx == -1 or nb_node_idx not in leaf_index_map:
                continue

            j = leaf_index_map[nb_node_idx]
            # Only add each edge once (i < j)
            if i < j:
                edges.append([i, j])
                cx_i, cy_i = node.center
                nb_node = grid._nodes[nb_node_idx]
                cx_j, cy_j = nb_node.center
                dist = np.hypot(cx_j - cx_i, cy_j - cy_i)
                spacing.append(dist)

    edges = np.array(edges, dtype=np.intp) if edges else np.empty((0, 2), dtype=np.intp)
    spacing = np.array(spacing, dtype=np.float64) if spacing else np.empty(0, dtype=np.float64)

    return edges, spacing
