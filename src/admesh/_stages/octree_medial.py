"""Medial axis + local-feature-size on the octree leaf graph (spec 021, US1).

Computes the medial axis and size field directly on the quadtree leaves,
so narrow features dwarfed by a large domain still resolve (the failure
that motivates spec 021). Operates on the leaf-adjacency graph from
``octree_grid.leaf_graph`` (research.md R4).

Method (proof-of-concept for US1):
- Medial leaves = interior leaves that are local maxima of |D| (distance to
  boundary). The medial axis is the ridge of the distance function.
- MAD (medial-axis distance) = shortest-path distance to the nearest medial
  leaf over the variable-spacing leaf graph (Dijkstra).
- LFS = |D| + MAD ; size field h = clip(LFS / R, hmin, hmax).

This lives in a new module (not the locked medial_axis.py) while the octree
path is proven; folding into medial_axis.py is tracked by tasks T012-T014.
"""

from __future__ import annotations

import heapq

import numpy as np
from numpy.typing import NDArray

from admesh._stages.octree_grid import OctreeGrid, leaf_graph

__all__ = ["medial_leaves", "medial_distance", "size_field_octree"]


def medial_leaves(grid: OctreeGrid, grad_thresh: float = 0.6) -> NDArray[np.bool_]:
    """Detect medial-axis leaves via distance-gradient convergence (AOF-style).

    For a signed-distance field, |∇D| ≈ 1 in smooth regions and drops toward 0
    on the medial axis, where contributions from opposing boundaries cancel
    (research.md R4). This detects the medial axis of *elongated* features
    (channels, notches) — unlike a local-maximum-of-|D| test, which only fires
    at isolated distance peaks.

    The gradient at each interior leaf is estimated by least squares from its
    edge-adjacent neighbours on the variable-spacing leaf graph. A leaf is
    medial if it is interior (D < 0) and the estimated |∇D| < grad_thresh.
    """
    leaves = grid.leaves
    D = np.array([lf.D for lf in leaves], dtype=np.float64)
    xy = np.array([lf.center for lf in leaves], dtype=np.float64)
    interior = D < 0.0
    mask = np.zeros(len(leaves), dtype=bool)

    for i, leaf in enumerate(leaves):
        if not interior[i]:
            continue
        nb = leaf.neighbors
        if len(nb) < 2:
            continue
        dp = xy[nb] - xy[i]          # (m, 2) neighbour offsets
        dd = D[nb] - D[i]            # (m,) distance differences
        # Least-squares gradient g: minimise || dp @ g - dd ||
        M = dp.T @ dp               # (2, 2)
        det = M[0, 0] * M[1, 1] - M[0, 1] * M[1, 0]
        if abs(det) < 1e-12:        # collinear neighbours -> ill-posed, skip
            continue
        rhs = dp.T @ dd
        gx = (M[1, 1] * rhs[0] - M[0, 1] * rhs[1]) / det
        gy = (-M[1, 0] * rhs[0] + M[0, 0] * rhs[1]) / det
        if np.hypot(gx, gy) < grad_thresh:
            mask[i] = True
    return mask


def medial_distance(grid: OctreeGrid, medial_mask: NDArray[np.bool_]) -> NDArray[np.float64]:
    """Shortest-path distance from each leaf to the nearest medial leaf.

    Dijkstra over the leaf-adjacency graph with centre-to-centre edge weights
    (research.md R4 — generalises the uniform-grid distance transform to the
    variable-spacing octree). Leaves with no path get a large finite value.
    """
    n = len(grid.leaves)
    edges, spacing = leaf_graph(grid)
    adj: list[list[tuple[int, float]]] = [[] for _ in range(n)]
    for (a, b), w in zip(edges, spacing):
        adj[int(a)].append((int(b), float(w)))
        adj[int(b)].append((int(a), float(w)))

    dist = np.full(n, np.inf, dtype=np.float64)
    heap: list[tuple[float, int]] = []
    for i in range(n):
        if medial_mask[i]:
            dist[i] = 0.0
            heap.append((0.0, i))
    heapq.heapify(heap)
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    # Unreached leaves (disconnected): fall back to a large but finite value
    if np.isinf(dist).any():
        finite_max = dist[np.isfinite(dist)].max() if np.isfinite(dist).any() else 0.0
        dist[np.isinf(dist)] = finite_max
    return dist


def size_field_octree(
    grid: OctreeGrid,
    *,
    R: float = 2.0,
    hmin: float,
    hmax: float,
) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
    """Per-leaf size field h = clip((|D| + MAD)/R, hmin, hmax) and medial mask.

    R = elements-per-local-feature-size unit. R=2 yields ~4 elements across a
    feature of width 2*LFS (spec FR-010/FR-011, "four elements per feature").
    """
    D = np.array([leaf.D for leaf in grid.leaves], dtype=np.float64)
    mask = medial_leaves(grid)
    mad = medial_distance(grid, mask)
    lfs = np.abs(D) + mad
    h = np.clip(lfs / R, hmin, hmax)
    return h, mask
