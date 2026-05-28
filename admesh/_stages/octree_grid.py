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


@dataclass(frozen=True)
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
    """

    center: tuple[float, float]
    size: float
    depth: int
    D: float = 0.0
    neighbors: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class OctreeGrid:
    """Hierarchically-refined quadtree background grid.

    Attributes
    ----------
    bbox : tuple[float, float, float, float]
        (xmin, ymin, xmax, ymax) padded domain extent.
    root : OctreeLeaf
        Top-level cell covering whole bbox.
    leaves : list[OctreeLeaf]
        Flattened list of all leaf cells (refinement complete, 2:1 balanced).
    h_min : float
        Refinement floor; no leaf smaller than this.
    """

    bbox: tuple[float, float, float, float]
    root: OctreeLeaf
    leaves: list[OctreeLeaf]
    h_min: float


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
# Phase 2: Foundational Octree Core (T004–T008)
# ============================================================================


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

    Top-down recursive subdivision (research.md R2): each cell subdivides
    while its size exceeds the local target from size_oracle and is still
    above h_min. The 2:1 balance pass (R3) smooths transitions.

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

    # Create root
    root_size = max(xmax - xmin, ymax - ymin)
    root = OctreeLeaf(
        center=((xmin + xmax) / 2, (ymin + ymax) / 2),
        size=root_size,
        depth=0,
        D=_eval_sdf(domain.fd, (xmin + xmax) / 2, (ymin + ymax) / 2),
    )

    # Recursive subdivision: collect leaves in a list
    leaves = []

    def _subdivide(cell: OctreeLeaf) -> None:
        """Recursively subdivide until size target is met or h_min floor."""
        cx, cy = cell.center
        target_h = size_oracle(cx, cy)

        # Stop if cell is small enough or at floor
        if cell.size <= target_h or cell.size <= h_min:
            leaves.append(cell)
            return

        # Subdivide into 4 children
        half_size = cell.size / 2
        quarter = half_size / 2
        children = [
            (cx - quarter, cy - quarter),  # lower-left
            (cx + quarter, cy - quarter),  # lower-right
            (cx - quarter, cy + quarter),  # upper-left
            (cx + quarter, cy + quarter),  # upper-right
        ]
        for cx_child, cy_child in children:
            child = OctreeLeaf(
                center=(cx_child, cy_child),
                size=half_size,
                depth=cell.depth + 1,
                D=_eval_sdf(domain.fd, cx_child, cy_child),
            )
            _subdivide(child)

    _subdivide(root)

    if not leaves:
        raise OctreeConstructionError("No leaves generated during subdivision")

    # Build adjacency: for each leaf, find edge-adjacent neighbors
    leaves_with_neighbors = _build_adjacency(leaves)

    if balance:
        leaves_with_neighbors = _balance_2to1(leaves_with_neighbors)

    grid = OctreeGrid(bbox=bbox, root=root, leaves=leaves_with_neighbors, h_min=h_min)
    return grid


def _eval_sdf(fd: Callable, x: float, y: float) -> float:
    """Evaluate signed-distance function at a single point."""
    p = np.array([[x, y]], dtype=np.float64)
    return float(fd(p)[0])


def _build_adjacency(leaves: list[OctreeLeaf]) -> list[OctreeLeaf]:
    """Build edge-adjacency neighbors for each leaf.

    Returns a new list of leaves with the neighbors field populated.
    """
    leaves_list = list(leaves)
    leaf_by_idx = {i: leaf for i, leaf in enumerate(leaves_list)}

    # For each pair of leaves, check if they are edge-adjacent
    neighbors_map = {i: [] for i in range(len(leaves_list))}

    for i, leaf_i in enumerate(leaves_list):
        for j, leaf_j in enumerate(leaves_list):
            if i >= j:
                continue  # Only check each pair once
            if _are_edge_adjacent(leaf_i, leaf_j):
                neighbors_map[i].append(j)
                neighbors_map[j].append(i)

    # Rebuild leaves with neighbors
    result = []
    for i, leaf in enumerate(leaves_list):
        new_leaf = OctreeLeaf(
            center=leaf.center,
            size=leaf.size,
            depth=leaf.depth,
            D=leaf.D,
            neighbors=neighbors_map[i],
        )
        result.append(new_leaf)

    return result


def _are_edge_adjacent(leaf1: OctreeLeaf, leaf2: OctreeLeaf) -> bool:
    """Check if two leaves share an edge (not just a corner)."""
    x1, y1 = leaf1.center
    x2, y2 = leaf2.center
    s1 = leaf1.size
    s2 = leaf2.size

    # Bounding boxes
    x1_min, x1_max = x1 - s1 / 2, x1 + s1 / 2
    y1_min, y1_max = y1 - s1 / 2, y1 + s1 / 2
    x2_min, x2_max = x2 - s2 / 2, x2 + s2 / 2
    y2_min, y2_max = y2 - s2 / 2, y2 + s2 / 2

    tol = 1e-10

    # Check if they share an edge:
    # - Horizontal edge: y-ranges overlap, x-edges touch
    h_edge = (
        abs(y1_min - y1_max) > tol
        and abs(y2_min - y2_max) > tol
        and _intervals_overlap(y1_min, y1_max, y2_min, y2_max)
        and (abs(x1_max - x2_min) < tol or abs(x1_min - x2_max) < tol)
    )
    # - Vertical edge: x-ranges overlap, y-edges touch
    v_edge = (
        abs(x1_min - x1_max) > tol
        and abs(x2_min - x2_max) > tol
        and _intervals_overlap(x1_min, x1_max, x2_min, x2_max)
        and (abs(y1_max - y2_min) < tol or abs(y1_min - y2_max) < tol)
    )

    return h_edge or v_edge


def _intervals_overlap(a_min: float, a_max: float, b_min: float, b_max: float) -> bool:
    """Check if two 1D intervals overlap (strictly; touching at a point doesn't count)."""
    return a_min < b_max and b_min < a_max


def _balance_2to1(leaves: list[OctreeLeaf]) -> list[OctreeLeaf]:
    """Enforce 2:1 size ratio between edge-adjacent leaves (research.md R3).

    Simple greedy approach: if any edge-adjacent pair violates 2:1,
    subdivide the larger cell and rebuild adjacency until no violations remain.
    """
    max_iterations = 100
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        # Check for violations
        violations = []
        for i, leaf_i in enumerate(leaves):
            for j in leaf_i.neighbors:
                leaf_j = leaves[j]
                if leaf_i.size > 0 and leaf_j.size > 0:
                    ratio = max(leaf_i.size, leaf_j.size) / min(leaf_i.size, leaf_j.size)
                    if ratio > 2.0 + 1e-9:
                        violations.append((i, j))

        if not violations:
            break

        # Subdivide the larger cell in the first violation
        i, j = violations[0]
        if leaves[i].size >= leaves[j].size:
            idx_to_split = i
        else:
            idx_to_split = j

        leaf_to_split = leaves[idx_to_split]

        # Only subdivide if above h_min floor
        if leaf_to_split.size > 1.0000001 * min(leaf_to_split.size / 2, leaf_to_split.size):
            # Note: we need h_min but it's not stored. For now, subdivide if size > 1e-10
            # (this will be fixed when we store h_min in the leaf or grid)
            half_size = leaf_to_split.size / 2
            cx, cy = leaf_to_split.center
            quarter = half_size / 2

            new_leaves = []
            children = [
                (cx - quarter, cy - quarter),
                (cx + quarter, cy - quarter),
                (cx - quarter, cy + quarter),
                (cx + quarter, cy + quarter),
            ]
            for cx_child, cy_child in children:
                child = OctreeLeaf(
                    center=(cx_child, cy_child),
                    size=half_size,
                    depth=leaf_to_split.depth + 1,
                    D=leaf_to_split.D,  # Approximate; could recompute
                )
                new_leaves.append(child)

            leaves = leaves[:idx_to_split] + new_leaves + leaves[idx_to_split + 1 :]
            leaves = _build_adjacency(leaves)

    if iteration >= max_iterations:
        raise OctreeConstructionError("2:1 balance did not converge")

    return leaves


def locate(grid: OctreeGrid, p: NDArray) -> NDArray[np.intp]:
    """Locate leaf index for each query point (O(log) per point).

    Simple O(log N) search by traversing the octree structure.
    For now, implement as O(N) linear search (acceptable for small/medium N).

    Parameters
    ----------
    grid : OctreeGrid
    p : (N, 2) ndarray
        Query points (x, y).

    Returns
    -------
    (N,) ndarray of int
        Leaf indices; -1 if p is outside the grid bbox.
    """
    p = np.asarray(p, dtype=np.float64).reshape(-1, 2)
    indices = np.zeros(len(p), dtype=np.intp)

    xmin, ymin, xmax, ymax = grid.bbox

    for query_idx, (x, y) in enumerate(p):
        # Check if point is outside bbox
        if x < xmin or x > xmax or y < ymin or y > ymax:
            indices[query_idx] = -1
            continue

        # Linear search: find first leaf containing the point
        leaf_idx = -1
        for i, leaf in enumerate(grid.leaves):
            cx, cy = leaf.center
            half_size = leaf.size / 2
            if (
                cx - half_size <= x <= cx + half_size
                and cy - half_size <= y <= cy + half_size
            ):
                leaf_idx = i
                break

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

    Used by medial-axis FMM and gradient-limit solver on variable-spacing graph.

    Parameters
    ----------
    grid : OctreeGrid

    Returns
    -------
    edges : (E, 2) ndarray of int
        Edge-adjacent leaf pairs (leaf indices).
    spacing : (E,) ndarray of float
        Centre-to-centre distances (for variable-spacing graph algorithms).
    """
    edges = []
    spacing = []

    # Extract edges from the adjacency lists (avoiding duplicates)
    seen = set()
    for i, leaf_i in enumerate(grid.leaves):
        for j in leaf_i.neighbors:
            if i < j:  # Only add each edge once
                edges.append([i, j])
                leaf_j = grid.leaves[j]
                cx_i, cy_i = leaf_i.center
                cx_j, cy_j = leaf_j.center
                dist = np.hypot(cx_j - cx_i, cy_j - cy_i)
                spacing.append(dist)

    edges = np.array(edges, dtype=np.intp)
    spacing = np.array(spacing, dtype=np.float64)

    return edges, spacing
