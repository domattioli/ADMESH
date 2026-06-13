"""Adaptive quadtree (octree) for multiscale background-grid size fields.

Pure-NumPy struct-of-arrays implementation. Spec-029 — level-synchronous
adaptive quadtree refinement with optional 2:1 balance constraint.

This is an **additive-layer** module (not a faithful-port stage). It
composes with ``SizeFieldFn`` oracles to build multiscale mesh size
grids for background refinement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

__all__ = ["Octree", "build_octree", "leaf_graph", "locate", "interpolate", "octree_size_field"]

SizeFieldFn = Callable[[np.ndarray], np.ndarray]


@dataclass(frozen=True, slots=True)
class Octree:
    """Struct-of-arrays adaptive quadtree (2D mesh refinement grid).

    Attributes
    ----------
    cx : ndarray
        Leaf cell center x-coordinates, shape ``(L,)``, dtype ``float64``.
    cy : ndarray
        Leaf cell center y-coordinates, shape ``(L,)``, dtype ``float64``.
    size : ndarray
        Leaf cell edge lengths, shape ``(L,)``, dtype ``float64``.
    depth : ndarray
        Leaf refinement depth (0 = root), shape ``(L,)``, dtype ``int32``.
    ix : ndarray
        Leaf integer cell x-coordinate at its depth, shape ``(L,)``,
        dtype ``int64``.
    iy : ndarray
        Leaf integer cell y-coordinate at its depth, shape ``(L,)``,
        dtype ``int64``.
    x0 : float
        Padded bounding box x-minimum.
    y0 : float
        Padded bounding box y-minimum.
    root_size : float
        Root cell size (= h_max). ``depth-0`` cell edge length.
    root_nx : int
        Number of root cells in x-direction.
    root_ny : int
        Number of root cells in y-direction.
    bbox : tuple
        Padded bounding box ``(xmin, ymin, xmax, ymax)``.

    Notes
    -----
    All arrays have length ``L`` (number of leaves) and are immutable.
    Built via ``build_octree()``; coordinates are 0-based.
    """

    cx: np.ndarray
    cy: np.ndarray
    size: np.ndarray
    depth: np.ndarray
    ix: np.ndarray
    iy: np.ndarray
    x0: float
    y0: float
    root_size: float
    root_nx: int
    root_ny: int
    bbox: tuple[float, float, float, float]

    @property
    def n_leaves(self) -> int:
        """Number of leaf cells in the tree."""
        return len(self.cx)

    @property
    def centers(self) -> np.ndarray:
        """Leaf centers as ``(L, 2)`` array (columns: x, y)."""
        return np.column_stack([self.cx, self.cy])


def build_octree(
    domain,
    *,
    h_min: float,
    h_max: float,
    oracle: "SizeFieldFn | Callable",
    max_depth: int = 16,
    padding: float | None = None,
    balance: bool = True,
) -> Octree:
    """Build an adaptive level-synchronous quadtree.

    Parameters
    ----------
    domain : object
        Must have ``.bbox`` attribute: ``(xmin, ymin, xmax, ymax)`` tuple.
    h_min : float
        Minimum target cell size.
    h_max : float
        Maximum target cell size (root cell size).
    oracle : callable
        Batched size-field oracle. Takes ``pts`` (N, 2) float64 array of
        coordinates, returns ``(N,)`` float64 target sizes. Called once per
        refinement level on all active (to-be-refined-or-kept) cell centers.
    max_depth : int, optional
        Maximum subdivision depth. Default 16.
    padding : float, optional
        Absolute padding (not fraction) added to each side of bbox.
        Default: ``h_max``.
    balance : bool, optional
        Enforce 2:1 balance constraint if ``True``. Default ``True``.

    Returns
    -------
    Octree
        Struct-of-arrays quadtree with all leaves satisfying the refinement
        criterion and, if ``balance=True``, the 2:1 constraint.
    """
    if padding is None:
        padding = h_max

    xmin, ymin, xmax, ymax = domain.bbox

    # Pad bbox
    xmin -= padding
    xmax += padding
    ymin -= padding
    ymax += padding
    w = xmax - xmin
    h = ymax - ymin

    # Root grid: cell size s0 = h_max
    s0 = h_max
    root_nx = int(np.ceil(w / s0))
    root_ny = int(np.ceil(h / s0))
    x0, y0 = xmin, ymin

    # Start with root cells
    ix_active = np.arange(root_nx, dtype=np.int64)
    iy_active = np.arange(root_ny, dtype=np.int64)
    ix_active, iy_active = np.meshgrid(ix_active, iy_active, indexing="ij")
    ix_active = ix_active.ravel()
    iy_active = iy_active.ravel()
    depth_active = np.zeros(len(ix_active), dtype=np.int32)

    # Leaf storage
    leaf_ix = np.array([], dtype=np.int64)
    leaf_iy = np.array([], dtype=np.int64)
    leaf_depth = np.array([], dtype=np.int32)

    # Process level-by-level
    while len(ix_active) > 0:
        # Cell size at current depth
        d = depth_active[0]
        s_d = s0 / (2**d)

        # Compute centers
        cx = x0 + (ix_active + 0.5) * s_d
        cy = y0 + (iy_active + 0.5) * s_d
        pts = np.column_stack([cx, cy])

        # Query oracle (batched)
        target_sizes = oracle(pts)
        target_sizes = np.clip(target_sizes, h_min, h_max)

        # Split decision: refine if cell size > target AND can still refine
        split_mask = (s_d > target_sizes) & (s_d / 2 >= h_min * 0.999) & (d < max_depth)

        # Non-split cells -> leaves
        leaf_ix = np.append(leaf_ix, ix_active[~split_mask])
        leaf_iy = np.append(leaf_iy, iy_active[~split_mask])
        leaf_depth = np.append(leaf_depth, depth_active[~split_mask])

        # Split cells -> 4 children each
        if np.any(split_mask):
            ix_split = ix_active[split_mask]
            iy_split = iy_active[split_mask]

            # 4 children per split cell: broadcast via tile and repeat
            n_split = len(ix_split)
            child_offsets = np.array([0, 1, 0, 1], dtype=np.int64)
            child_offsets_y = np.array([0, 0, 1, 1], dtype=np.int64)

            ix_children = (2 * ix_split[:, None] + child_offsets[None, :]).ravel()
            iy_children = (2 * iy_split[:, None] + child_offsets_y[None, :]).ravel()
            depth_children = np.repeat(depth_active[split_mask] + 1, 4)

            ix_active = ix_children
            iy_active = iy_children
            depth_active = depth_children
        else:
            ix_active = np.array([], dtype=np.int64)
            iy_active = np.array([], dtype=np.int64)
            depth_active = np.array([], dtype=np.int32)

    # Apply 2:1 balance if requested
    if balance:
        leaf_ix, leaf_iy, leaf_depth = _enforce_balance(
            leaf_ix, leaf_iy, leaf_depth, s0, x0, y0, h_min
        )

    # Compute sizes and centers for output
    sizes = s0 / (2**leaf_depth)
    cx = x0 + (leaf_ix + 0.5) * sizes
    cy = y0 + (leaf_iy + 0.5) * sizes

    return Octree(
        cx=cx,
        cy=cy,
        size=sizes,
        depth=leaf_depth,
        ix=leaf_ix,
        iy=leaf_iy,
        x0=x0,
        y0=y0,
        root_size=s0,
        root_nx=root_nx,
        root_ny=root_ny,
        bbox=(xmin, ymin, xmax, ymax),
    )


def _enforce_balance(
    leaf_ix: np.ndarray,
    leaf_iy: np.ndarray,
    leaf_depth: np.ndarray,
    s0: float,
    x0: float,
    y0: float,
    h_min: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Enforce 2:1 balance constraint (worklist-based refinement)."""
    # Build dict: (d, ix, iy) -> leaf index
    leaf_dict = {}
    for i, (d, ix, iy) in enumerate(zip(leaf_depth, leaf_ix, leaf_iy)):
        leaf_dict[(int(d), int(ix), int(iy))] = i

    # Worklist: entries to check
    worklist = set(leaf_dict.keys())

    while worklist:
        d, ix, iy = worklist.pop()
        if (d, ix, iy) not in leaf_dict:
            continue

        idx = leaf_dict[(d, ix, iy)]

        # Check 4 edge-adjacent neighbors at same depth
        for dix, diy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            neighbor_ix, neighbor_iy = ix + dix, iy + diy

            # Walk up to find a leaf at same or coarser depth
            found_idx = None
            found_depth = None
            for dd in range(d, -1, -1):
                nix, niy = neighbor_ix >> (d - dd), neighbor_iy >> (d - dd)
                if (dd, nix, niy) in leaf_dict:
                    found_idx = leaf_dict[(dd, nix, niy)]
                    found_depth = dd
                    break

            if found_idx is not None and found_depth is not None:
                # Check 2:1 constraint
                if found_depth < d - 1:
                    # Neighbor is too coarse; must split it
                    if (found_depth, neighbor_ix >> (d - found_depth),
                        neighbor_iy >> (d - found_depth)) in leaf_dict:
                        # Remove this leaf
                        old_key = (found_depth, neighbor_ix >> (d - found_depth),
                                   neighbor_iy >> (d - found_depth))
                        del leaf_dict[old_key]

                        # Add 4 children
                        nix_coarse = neighbor_ix >> (d - found_depth)
                        niy_coarse = neighbor_iy >> (d - found_depth)
                        for cix, ciy in [(0, 0), (1, 0), (0, 1), (1, 1)]:
                            new_ix = 2 * nix_coarse + cix
                            new_iy = 2 * niy_coarse + ciy
                            new_d = found_depth + 1
                            new_key = (new_d, new_ix, new_iy)
                            leaf_dict[new_key] = len(leaf_dict)
                            worklist.add(new_key)

                        # Re-check current cell's neighbors
                        worklist.add((d, ix, iy))

    # Rebuild arrays from leaf_dict
    items = sorted(leaf_dict.items())
    leaf_depth_new = np.array([k[0] for k, v in items], dtype=np.int32)
    leaf_ix_new = np.array([k[1] for k, v in items], dtype=np.int64)
    leaf_iy_new = np.array([k[2] for k, v in items], dtype=np.int64)

    return leaf_ix_new, leaf_iy_new, leaf_depth_new


def leaf_graph(tree: Octree) -> tuple[np.ndarray, np.ndarray]:
    """Compute edge-adjacent leaf pairs and their center distances.

    Returns
    -------
    edges : ndarray
        Shape ``(E, 2)``, dtype ``intp``. Each row is a pair ``(i, j)``
        with ``i < j``, representing leaves that share an edge.
    spacing : ndarray
        Shape ``(E,)``, dtype ``float64``. Euclidean distance between
        centers of paired leaves.

    Notes
    -----
    O(N) via dict-based ancestor walk-up (not O(N^2) brute-force).
    Each edge listed exactly once.
    """
    ix, iy, depth = tree.ix, tree.iy, tree.depth
    s0 = tree.root_size
    x0, y0 = tree.x0, tree.y0

    # Build dict (d, ix, iy) -> leaf index
    leaf_dict = {}
    for i, (d, x, y) in enumerate(zip(depth, ix, iy)):
        leaf_dict[(int(d), int(x), int(y))] = i

    edges = set()

    for i in range(len(ix)):
        d, x, y = int(depth[i]), int(ix[i]), int(iy[i])

        # Check 4 neighbors at same depth
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, ny = x + dx, y + dy

            # Walk up to find a leaf
            for dd in range(d, -1, -1):
                nnx, nny = nx >> (d - dd), ny >> (d - dd)
                if (dd, nnx, nny) in leaf_dict:
                    j = leaf_dict[(dd, nnx, nny)]
                    if i != j:
                        edges.add(tuple(sorted([i, j])))
                    break

    edges = np.array(list(edges), dtype=np.intp)

    if len(edges) == 0:
        return edges.reshape(0, 2), np.array([], dtype=np.float64)

    # Compute spacing (center distances)
    cx_i = tree.cx[edges[:, 0]]
    cy_i = tree.cy[edges[:, 0]]
    cx_j = tree.cx[edges[:, 1]]
    cy_j = tree.cy[edges[:, 1]]
    spacing = np.sqrt((cx_i - cx_j) ** 2 + (cy_i - cy_j) ** 2)

    return edges, spacing


def locate(tree: Octree, pts: np.ndarray) -> np.ndarray:
    """Find the leaf cell containing each query point.

    Parameters
    ----------
    pts : ndarray
        Shape ``(M, 2)``, dtype ``float64``. Query points (x, y).

    Returns
    -------
    ndarray
        Shape ``(M,)``, dtype ``intp``. Leaf index for each point.
        Points outside padded bbox are clamped to the boundary.

    Notes
    -----
    Never returns -1. Points are mapped to the deepest leaf containing them
    via dict-ladder walk from max depth down to 0.
    """
    ix, iy, depth = tree.ix, tree.iy, tree.depth
    s0 = tree.root_size
    x0, y0 = tree.x0, tree.y0

    # Build dict (d, ix, iy) -> leaf index
    leaf_dict = {}
    for i, (d, x, y) in enumerate(zip(depth, ix, iy)):
        leaf_dict[(int(d), int(x), int(y))] = i

    max_depth = int(np.max(depth))
    result = np.zeros(len(pts), dtype=np.intp)

    for m, (px, py) in enumerate(pts):
        # Clamp to padded bbox
        xmin, ymin, xmax, ymax = tree.bbox
        px = np.clip(px, xmin, xmax)
        py = np.clip(py, ymin, ymax)

        # Start at max depth and walk up
        for d in range(max_depth, -1, -1):
            s_d = s0 / (2**d)
            cell_ix = int((px - x0) / s_d)
            cell_iy = int((py - y0) / s_d)

            if (d, cell_ix, cell_iy) in leaf_dict:
                result[m] = leaf_dict[(d, cell_ix, cell_iy)]
                break

    return result


def interpolate(tree: Octree, values: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Interpolate per-leaf values at query points (nearest-leaf).

    Parameters
    ----------
    values : ndarray
        Shape ``(L,)``, dtype ``float64``. Value per leaf.
    pts : ndarray
        Shape ``(M, 2)``, dtype ``float64``. Query points.

    Returns
    -------
    ndarray
        Shape ``(M,)``, dtype ``float64``. ``values[locate(tree, pts)]``.
    """
    leaf_indices = locate(tree, pts)
    return values[leaf_indices]


def octree_size_field(
    domain,
    oracle: SizeFieldFn,
    *,
    h_min: float,
    h_max: float,
    g: float = 0.2,
    max_depth: int = 16,
    balance: bool = True,
    gradient_limit: bool = True,
    max_relax_iter: int = 200,
) -> SizeFieldFn:
    """Build an octree-backed size field from a batched size oracle.

    Builds an adaptive octree over domain.bbox refined by ``oracle``, samples
    the oracle at leaf centers, optionally applies a mesh-grading gradient
    limit on the leaf-adjacency graph (enforce |h_i - h_j| <= g * dist_ij,
    the ADMESH gradation constraint), and returns a size-field callable
    fh(pts:(N,2)) -> (N,) that nearest-leaf-interpolates the limited sizes.

    Parameters
    ----------
    domain : object with .bbox
        Bounding box ``(xmin, ymin, xmax, ymax)`` tuple.
    oracle : callable
        Batched target size function. Takes ``pts`` (N, 2) → (N,) float64.
    h_min, h_max : float
        Refinement floor and root size.
    g : float, optional
        Max allowed |dh|/dist (gradation slope); default 0.2.
    max_depth : int, optional
        Maximum octree depth; default 16.
    balance : bool, optional
        Enforce 2:1 balance constraint; default True.
    gradient_limit : bool, optional
        Apply leaf-graph limiter; default True.
    max_relax_iter : int, optional
        Maximum relaxation iterations; default 200.

    Returns
    -------
    callable
        Size-field function (pts) -> sizes.
    """
    # Build octree refined by oracle
    tree = build_octree(
        domain,
        h_min=h_min,
        h_max=h_max,
        oracle=oracle,
        max_depth=max_depth,
        balance=balance,
    )

    # Sample oracle at leaf centers and clip
    sizes = np.clip(
        np.asarray(oracle(tree.centers), dtype=np.float64),
        h_min,
        h_max,
    ).copy()

    # Apply gradient limiter if enabled
    if gradient_limit and tree.n_leaves > 1:
        edges, spacing = leaf_graph(tree)
        if len(edges) > 0:
            # Iterative relaxation: enforce |h_i - h_j| <= g * d_ij
            for _ in range(max_relax_iter):
                sizes_old = sizes.copy()

                # Both directions per sweep
                i_idx, j_idx = edges[:, 0], edges[:, 1]
                np.minimum.at(sizes, i_idx, sizes[j_idx] + g * spacing)
                np.minimum.at(sizes, j_idx, sizes[i_idx] + g * spacing)

                max_change = np.max(np.abs(sizes - sizes_old))
                if max_change < 1e-9 * h_max:
                    break

            # Re-clip after relaxation
            np.clip(sizes, h_min, h_max, out=sizes)

    # Return interpolation closure
    return lambda pts: interpolate(tree, sizes, np.atleast_2d(np.asarray(pts, dtype=np.float64)))

