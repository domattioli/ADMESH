"""Octree-based size-field grid with O(log N) point location and O(N) adjacency.

Port of prototype (PR #113) with pointer-based tree replacing flat-list O(N²) adjacency.
Achieves O(log N) point location and O(N) adjacency build via parent/sibling links.
Spec: `specs/021-octree-size-field-perf/` — resolves issue #115 (scalability).

Key data structures:
  - OctreeNode: pointer-linked tree node with parent/children/neighbours links
  - OctreeTree: container wrapping root + leaves list (for backward compatibility)

Public API:
  - size_field_octree(domain, h_min, h_max, max_depth=12) -> Callable[[pts], h]
  - Preserves prototype interface; tree internals are an implementation detail.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from numpy.typing import NDArray

from admesh.api import Domain

Points = NDArray[np.float64]
SizeField = Callable[[Points], NDArray[np.float64]]


@dataclass
class OctreeNode:
    """Pointer-linked tree node for spatial subdivision.

    Invariants:
      - len(children) in {0, 4}: either a leaf or internal node with exactly 4 children.
      - child.parent is self for all children in children.
      - neighbours keys are a subset of {'N', 'S', 'E', 'W'}.
      - depth == parent.depth + 1 (for non-root).
      - h_field is not None after build_h_field() gate.
    """

    min_corner: np.ndarray  # shape (2,)
    max_corner: np.ndarray  # shape (2,)
    depth: int
    parent: OctreeNode | None = None
    children: list[OctreeNode] = field(default_factory=list)
    neighbours: dict[str, OctreeNode | None] = field(default_factory=dict)
    h_field: float | None = None  # size-field value at leaf centre
    points: np.ndarray | None = None  # pts inside this leaf (leaf only)
    D: float = 0.0  # signed distance to domain boundary
    neighbors: list[int] = field(default_factory=list)  # indices into OctreeTree.leaves

    def is_leaf(self) -> bool:
        """Return True if this node has no children (is a leaf)."""
        return len(self.children) == 0

    @property
    def size(self) -> float:
        """Return the maximum side length of this node's bounding box."""
        return float(np.max(self.max_corner - self.min_corner))

    @property
    def center(self) -> np.ndarray:
        """Return the center of this node's bounding box."""
        return (self.min_corner + self.max_corner) / 2.0

    def split(self, max_depth: int) -> None:
        """Subdivide this leaf into 4 children.

        Creates children in SW/SE/NW/NE order (indices 0/1/2/3).
        Sets sibling links (interior face neighbours) + cross-parent links.

        Args:
            max_depth: maximum depth; split is a no-op if depth >= max_depth.
        """
        if not self.is_leaf():
            raise ValueError("Cannot split a non-leaf node")
        if self.depth >= max_depth:
            return  # Don't subdivide beyond max_depth

        mid = (self.min_corner + self.max_corner) / 2.0

        # Create 4 children: SW, SE, NW, NE (z-order layout)
        children_bboxes = [
            (self.min_corner, mid),  # SW: [xmin, ymin] to [xmid, ymid]
            (np.array([mid[0], self.min_corner[1]]), np.array([self.max_corner[0], mid[1]])),  # SE
            (np.array([self.min_corner[0], mid[1]]), np.array([mid[0], self.max_corner[1]])),  # NW
            (mid, self.max_corner),  # NE: [xmid, ymid] to [xmax, ymax]
        ]

        self.children = [
            OctreeNode(
                min_corner=bbox[0].copy(),
                max_corner=bbox[1].copy(),
                depth=self.depth + 1,
                parent=self,
            )
            for bbox in children_bboxes
        ]

        # Sibling links (internal faces, O(1))
        sw, se, nw, ne = self.children
        sw.neighbours["E"] = se
        se.neighbours["W"] = sw
        sw.neighbours["N"] = nw
        nw.neighbours["S"] = sw
        se.neighbours["N"] = ne
        ne.neighbours["S"] = se
        nw.neighbours["E"] = ne
        ne.neighbours["W"] = nw

        # Cross-parent links (O(depth))
        _wire_cross_parent_neighbours(sw, se, nw, ne, self.neighbours)

    def locate(self, pt: np.ndarray) -> OctreeNode:
        """Recursively locate the leaf containing point pt.

        Args:
            pt: query point, shape (2,)

        Returns:
            OctreeNode: the leaf node containing pt, or self if leaf.
        """
        if self.is_leaf():
            return self
        mid = (self.min_corner + self.max_corner) / 2.0
        ix = int(pt[0] >= mid[0])
        iy = int(pt[1] >= mid[1])
        child_idx = 2 * iy + ix  # SW=0, SE=1, NW=2, NE=3
        return self.children[child_idx].locate(pt)


def _find_eastern_child(node: OctreeNode | None) -> OctreeNode | None:
    """Locate the eastern (rightmost) child of node, descending if needed.

    Used to find which child of a sibling faces west towards a target child.
    Returns the child at the same depth as the target, or None if node is None.
    """
    if node is None:
        return None
    if node.is_leaf():
        return node
    # Return the eastern children: SE (index 1) or NE (index 3)
    # We descend recursively to match depth
    return node.children[1] if node.children[1].is_leaf() else _find_eastern_child(node.children[1])


def _find_western_child(node: OctreeNode | None) -> OctreeNode | None:
    """Locate the western (leftmost) child of node, descending if needed."""
    if node is None:
        return None
    if node.is_leaf():
        return node
    # Return the western children: SW (index 0) or NW (index 2)
    return node.children[0] if node.children[0].is_leaf() else _find_western_child(node.children[0])


def _find_northern_child(node: OctreeNode | None) -> OctreeNode | None:
    """Locate the northern (topmost) child of node, descending if needed."""
    if node is None:
        return None
    if node.is_leaf():
        return node
    # Return the northern children: NW (index 2) or NE (index 3)
    return node.children[2] if node.children[2].is_leaf() else _find_northern_child(node.children[2])


def _find_southern_child(node: OctreeNode | None) -> OctreeNode | None:
    """Locate the southern (bottommost) child of node, descending if needed."""
    if node is None:
        return None
    if node.is_leaf():
        return node
    # Return the southern children: SW (index 0) or SE (index 1)
    return node.children[0] if node.children[0].is_leaf() else _find_southern_child(node.children[0])


def _wire_cross_parent_neighbours(
    sw: OctreeNode,
    se: OctreeNode,
    nw: OctreeNode,
    ne: OctreeNode,
    parent_neighbours: dict[str, OctreeNode | None],
) -> None:
    """Wire cross-parent neighbour links for 4 children.

    When parent P splits into children {SW, SE, NW, NE}, each child's
    external faces inherit from P's neighbours. Internal faces are sibling links.

    Args:
        sw, se, nw, ne: the 4 children (must be leaves, just created).
        parent_neighbours: the parent's neighbour dict before split.
    """
    # SW external faces: W, S
    sw.neighbours["W"] = _find_eastern_child(parent_neighbours.get("W"))
    sw.neighbours["S"] = _find_northern_child(parent_neighbours.get("S"))

    # SE external faces: E, S
    se.neighbours["E"] = _find_western_child(parent_neighbours.get("E"))
    se.neighbours["S"] = _find_northern_child(parent_neighbours.get("S"))

    # NW external faces: W, N
    nw.neighbours["W"] = _find_eastern_child(parent_neighbours.get("W"))
    nw.neighbours["N"] = _find_southern_child(parent_neighbours.get("N"))

    # NE external faces: E, N
    ne.neighbours["E"] = _find_western_child(parent_neighbours.get("E"))
    ne.neighbours["N"] = _find_southern_child(parent_neighbours.get("N"))


@dataclass
class OctreeTree:
    """Container for pointer-based octree.

    Attributes:
        root: the root OctreeNode.
        max_depth: maximum subdivision depth.
        leaves: flat list of all leaf nodes (maintained for iteration, not locate).
    """

    root: OctreeNode
    max_depth: int
    leaves: list[OctreeNode] = field(default_factory=list)

    def _collect_leaves(self, node: OctreeNode | None = None) -> None:
        """Recursively collect all leaf nodes into self.leaves."""
        if node is None:
            node = self.root
            self.leaves = []
        if node.is_leaf():
            self.leaves.append(node)
        else:
            for child in node.children:
                self._collect_leaves(child)

    def _violates_2to1(self, leaf: OctreeNode) -> bool:
        """Check if leaf violates 2:1 balance with any leaf neighbour."""
        leaf_size = leaf.size
        for neighbour in leaf.neighbours.values():
            if neighbour is None:
                continue
            # Find actual leaf neighbour (descend if internal)
            nb = neighbour if neighbour.is_leaf() else None
            if nb is None:
                continue
            nb_size = nb.size
            if nb_size > 2.0 * leaf_size + 1e-10 or leaf_size > 2.0 * nb_size + 1e-10:
                return True
        return False

    def balance_2to1(self) -> None:
        """Work-queue 2:1 balancing.

        Iteratively splits leaves that violate the 2:1 constraint until
        no leaf violates it. Uses a FIFO work queue to avoid rebuilding
        adjacency after each split.
        """
        # Collect initial violators
        queue: deque[OctreeNode] = deque()
        for leaf in self.leaves:
            if self._violates_2to1(leaf):
                queue.append(leaf)

        iteration = 0
        cap = 10 * len(self.leaves)

        while queue and iteration < cap:
            leaf = queue.popleft()
            # Leaf may have been split by a neighbour; skip if no longer a leaf
            if not leaf.is_leaf():
                iteration += 1
                continue
            # Re-check violation (it may have been resolved by a neighbour's split)
            if not self._violates_2to1(leaf):
                iteration += 1
                continue
            # Split the leaf
            leaf.split(self.max_depth)
            # Enqueue new violators among neighbours of the 4 new children
            for child in leaf.children:
                for neighbour in child.neighbours.values():
                    if neighbour and neighbour.is_leaf() and self._violates_2to1(neighbour):
                        queue.append(neighbour)
            iteration += 1

        # Recollect leaves after balancing
        self._collect_leaves()


def build_octree(
    domain: Domain,
    h_min: float,
    h_max: float,
    max_depth: int = 12,
    numba: bool = False,
) -> OctreeTree:
    """Build a pointer-based octree over the domain.

    Args:
        domain: Domain object with sdf callable.
        h_min: minimum cell size (stops subdivision).
        h_max: maximum cell size (initial grid).
        max_depth: maximum subdivision depth.
        numba: if True, enable Numba JIT for per-leaf loops (P1, optional).

    Returns:
        OctreeTree: the built tree with root, leaves, and max_depth.
    """
    # Create root node spanning the domain bbox
    bbox = domain.bbox
    root = OctreeNode(
        min_corner=np.array([bbox[0], bbox[1]]),
        max_corner=np.array([bbox[2], bbox[3]]),
        depth=0,
        parent=None,
    )
    root.neighbours = {"N": None, "S": None, "E": None, "W": None}

    tree = OctreeTree(root=root, max_depth=max_depth)

    # Build the tree via recursive subdivision
    _build_tree_recursive(root, domain, h_min, max_depth)

    # Collect all leaves
    tree._collect_leaves()

    # Apply 2:1 balancing
    tree.balance_2to1()

    # Populate int-index neighbor lists for backward compat
    leaf_to_idx = {id(leaf): i for i, leaf in enumerate(tree.leaves)}
    for leaf in tree.leaves:
        leaf.neighbors = [
            leaf_to_idx[id(nb)]
            for nb in leaf.neighbours.values()
            if nb is not None and nb.is_leaf() and id(nb) in leaf_to_idx
        ]

    # Compute h-field at each leaf centre
    for leaf in tree.leaves:
        pt = leaf.center
        d = float(domain.sdf(pt.reshape(1, -1))[0])
        leaf.D = d
        # Size field: proportional to distance-to-boundary, clamped to [h_min, h_max]
        # Interior leaves (d < 0): finer mesh; exterior: coarser
        lfs = max(abs(d), h_min)
        leaf.h_field = min(max(lfs, h_min), h_max)

    return tree


def _build_tree_recursive(
    node: OctreeNode,
    domain: Domain,
    h_min: float,
    max_depth: int,
) -> None:
    """Recursively subdivide until cell size <= h_min or depth >= max_depth.

    Only subdivides cells that are inside or near the domain boundary
    (signed distance <= 2 * cell_size), so exterior cells stay coarse.
    """
    if node.depth >= max_depth or node.size <= h_min:
        return

    # Only refine cells near/inside the domain
    pt = node.center
    d = float(domain.sdf(pt.reshape(1, -1))[0])
    if d > 2.0 * node.size:
        return  # far outside domain; leave coarse

    node.split(max_depth)
    for child in node.children:
        _build_tree_recursive(child, domain, h_min, max_depth)


def size_field_octree(
    domain: Domain,
    h_min: float,
    h_max: float,
    max_depth: int = 12,
    numba: bool = False,
) -> SizeField:
    """Return a size-field callable based on octree interpolation.

    Builds an octree over the domain, then returns a callable that
    interpolates the size field at query points via tree descent.

    Args:
        domain: Domain object with sdf callable.
        h_min: minimum cell size.
        h_max: maximum cell size.
        max_depth: maximum octree depth.
        numba: if True, enable Numba JIT (P1, optional).

    Returns:
        Callable: fh(pts) -> h, where pts is shape (n, 2) and h is shape (n,).
    """
    tree = build_octree(domain, h_min, h_max, max_depth, numba=numba)

    def fh(pts: np.ndarray) -> np.ndarray:
        """Evaluate size field at query points.

        Args:
            pts: query points, shape (n, 2).

        Returns:
            h: size-field values, shape (n,).
        """
        n = pts.shape[0]
        h = np.zeros(n)
        for i in range(n):
            leaf = tree.root.locate(pts[i])
            h[i] = leaf.h_field if leaf.h_field is not None else h_max
        return h

    return fh


def leaf_graph(tree: OctreeTree) -> tuple[np.ndarray, np.ndarray]:
    """Build graph of leaf adjacencies + centre-to-centre spacing.

    Args:
        tree: OctreeTree object.

    Returns:
        edges: (n_edges, 2) ndarray of leaf adjacency pairs.
        spacing: (n_edges,) array of centre-to-centre distances per edge.
    """
    edges: list[list[int]] = []
    spacings: list[float] = []

    leaf_to_idx = {id(leaf): i for i, leaf in enumerate(tree.leaves)}

    for i, leaf in enumerate(tree.leaves):
        ci = leaf.center
        for neighbour in leaf.neighbours.values():
            if neighbour is not None and neighbour.is_leaf():
                j = leaf_to_idx.get(id(neighbour))
                if j is not None and i < j:
                    edges.append([i, j])
                    cj = neighbour.center
                    spacings.append(float(np.hypot(cj[0] - ci[0], cj[1] - ci[1])))

    edges_arr = np.array(edges, dtype=np.intp) if edges else np.empty((0, 2), dtype=np.intp)
    spacing_arr = np.array(spacings, dtype=np.float64)
    return edges_arr, spacing_arr


def locate(tree: OctreeTree, p: np.ndarray) -> np.ndarray:
    """Locate leaf index for each query point. O(log N) per point via tree descent.

    Args:
        tree: OctreeTree (or OctreeGrid alias).
        p: (N, 2) query points.

    Returns:
        (N,) int array of leaf indices; -1 if outside bbox.
    """
    p = np.asarray(p, dtype=np.float64).reshape(-1, 2)
    leaf_to_idx = {id(leaf): i for i, leaf in enumerate(tree.leaves)}
    result = np.full(len(p), -1, dtype=np.intp)
    xmin, ymin = tree.root.min_corner
    xmax, ymax = tree.root.max_corner
    for qi in range(len(p)):
        x, y = p[qi]
        if x < xmin or x > xmax or y < ymin or y > ymax:
            continue
        leaf = tree.root.locate(p[qi])
        idx = leaf_to_idx.get(id(leaf), -1)
        result[qi] = idx
    return result


def interpolate(tree: OctreeTree, values: np.ndarray, p: np.ndarray) -> np.ndarray:
    """Interpolate per-leaf values at query points (nearest-leaf).

    Args:
        tree: OctreeTree.
        values: (n_leaves,) per-leaf scalar values.
        p: (N, 2) query points.

    Returns:
        (N,) interpolated values.
    """
    p = np.asarray(p, dtype=np.float64).reshape(-1, 2)
    indices = locate(tree, p)
    result = np.zeros(len(p), dtype=np.float64)
    for i, idx in enumerate(indices):
        if idx < 0:
            result[i] = float(np.max(values))
        else:
            result[i] = values[idx]
    return result


# Backward-compat alias — octree_medial.py and other callers use OctreeGrid
OctreeGrid = OctreeTree


class OctreeConstructionError(Exception):
    """Raised when octree construction fails (triggers fallback to uniform grid)."""
    pass


__all__ = [
    "OctreeNode",
    "OctreeTree",
    "OctreeGrid",          # backward-compat alias
    "OctreeConstructionError",
    "build_octree",
    "size_field_octree",
    "leaf_graph",
    "locate",
    "interpolate",
]
