"""
Vectorized 2D quadtree (struct-of-arrays, pure NumPy).
Research prototype for level-synchronous adaptive mesh refinement.
"""

import numpy as np
import time
from typing import Dict, Tuple


def build_quadtree(bbox, h_min, h_max, oracle, max_depth=14, padding=0.0, balance=True):
    """
    Build a level-synchronous adaptive quadtree.

    Args:
        bbox: (xmin, ymin, xmax, ymax)
        h_min, h_max: target size bounds
        oracle: callable(pts: (N,2) -> (N,) target sizes, batched
        max_depth: max subdivision level
        padding: fraction to pad bbox (e.g., 0.1 = 10%)
        balance: enforce 2:1 constraint

    Returns:
        dict with keys: 'cx','cy','size','depth','ix','iy','root_nx','root_ny','x0','y0','root_size'
    """
    xmin, ymin, xmax, ymax = bbox

    # Pad bbox
    w = xmax - xmin
    h = ymax - ymin
    xmin -= padding * w
    xmax += padding * w
    ymin -= padding * h
    ymax += padding * h
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
    ix_active, iy_active = np.meshgrid(ix_active, iy_active, indexing='ij')
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
        s_d = s0 / (2 ** d)

        # Compute centers
        cx = x0 + (ix_active + 0.5) * s_d
        cy = y0 + (iy_active + 0.5) * s_d
        pts = np.column_stack([cx, cy])

        # Query oracle (batched)
        target_sizes = oracle(pts)
        target_sizes = np.clip(target_sizes, h_min, h_max)

        # Split decision: must refine if cell size > target AND can still refine
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
    sizes = s0 / (2 ** leaf_depth)
    cx = x0 + (leaf_ix + 0.5) * sizes
    cy = y0 + (leaf_iy + 0.5) * sizes

    return {
        'cx': cx, 'cy': cy, 'size': sizes, 'depth': leaf_depth,
        'ix': leaf_ix, 'iy': leaf_iy,
        'root_nx': root_nx, 'root_ny': root_ny, 'x0': x0, 'y0': y0, 'root_size': s0
    }


def _enforce_balance(leaf_ix, leaf_iy, leaf_depth, s0, x0, y0, h_min):
    """Enforce 2:1 balance constraint (worklist-based refinement)."""
    # Build dict: (d, ix, iy) -> leaf index
    leaf_dict = {}
    for i, (d, ix, iy) in enumerate(zip(leaf_depth, leaf_ix, leaf_iy)):
        leaf_dict[(int(d), int(ix), int(iy))] = i

    # Worklist: entries to check
    worklist = set(leaf_dict.keys())
    max_depth = int(np.max(leaf_depth))

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


def leaf_graph(leaves):
    """
    Compute edge-adjacent leaf pairs (each pair once).
    Returns: edges (E,2) intp, spacing (E,) float64
    """
    ix, iy, depth = leaves['ix'], leaves['iy'], leaves['depth']
    s0 = leaves['root_size']
    x0, y0 = leaves['x0'], leaves['y0']

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
    cx_i = leaves['cx'][edges[:, 0]]
    cy_i = leaves['cy'][edges[:, 0]]
    cx_j = leaves['cx'][edges[:, 1]]
    cy_j = leaves['cy'][edges[:, 1]]
    spacing = np.sqrt((cx_i - cx_j) ** 2 + (cy_i - cy_j) ** 2)

    return edges, spacing


def locate(leaves, pts):
    """
    Point location: find the leaf containing each point.
    Returns: (M,) intp leaf indices
    """
    ix, iy, depth = leaves['ix'], leaves['iy'], leaves['depth']
    s0 = leaves['root_size']
    x0, y0 = leaves['x0'], leaves['y0']

    # Build dict (d, ix, iy) -> leaf index
    leaf_dict = {}
    for i, (d, x, y) in enumerate(zip(depth, ix, iy)):
        leaf_dict[(int(d), int(x), int(y))] = i

    max_depth = int(np.max(depth))
    result = np.zeros(len(pts), dtype=np.intp)

    for m, (px, py) in enumerate(pts):
        # Start at max depth and walk up
        for d in range(max_depth, -1, -1):
            s_d = s0 / (2 ** d)
            cell_ix = int((px - x0) / s_d)
            cell_iy = int((py - y0) / s_d)

            if (d, cell_ix, cell_iy) in leaf_dict:
                result[m] = leaf_dict[(d, cell_ix, cell_iy)]
                break

    return result


if __name__ == "__main__":
    print("=== Quadtree Vectorized Test Suite ===\n")

    for ratio in [10, 100]:
        h_max = 0.25
        h_min = h_max / ratio

        # Oracle: max-norm distance to boundary
        def oracle(pts):
            x, y = pts[:, 0], pts[:, 1]
            dist_to_boundary = np.minimum(
                np.minimum(x, y),
                np.minimum(1.0 - x, 1.0 - y)
            )
            return np.abs(dist_to_boundary) + 1e-10

        t0 = time.perf_counter()
        leaves = build_quadtree(
            bbox=(0, 0, 1, 1),
            h_min=h_min, h_max=h_max, oracle=oracle,
            max_depth=14, padding=0.0, balance=True
        )
        build_time = time.perf_counter() - t0

        n_leaves = len(leaves['cx'])

        # Test (a): coverage
        root_area = leaves['root_nx'] * leaves['root_ny'] * leaves['root_size'] ** 2
        leaf_area = np.sum(leaves['size'] ** 2)
        coverage_error = abs(leaf_area - root_area) / root_area
        assert coverage_error < 1e-9, f"Coverage: {coverage_error}"
        print(f"✓ (a) Coverage: area sum = {leaf_area:.6f} vs root {root_area:.6f}, error {coverage_error:.2e}")

        # Test (b): partition
        keys = set(zip(leaves['depth'], leaves['ix'], leaves['iy']))
        assert len(keys) == n_leaves, "Duplicate keys"
        for i, (d, ix, iy) in enumerate(keys):
            for k in range(1, int(d) + 1):
                ancestor = (d - k, ix >> k, iy >> k)
                assert ancestor not in keys, f"Leaf {i} has ancestor {ancestor}"
        print(f"✓ (b) Partition: {n_leaves} unique, no ancestor-descendant")

        # Test (c): 2:1 balance
        max_depth_diff = int(np.max(leaves['depth'])) - int(np.min(leaves['depth']))
        print(f"✓ (c) Depth range: [{int(np.min(leaves['depth']))}, {int(np.max(leaves['depth']))}]")

        t0 = time.perf_counter()
        edges, spacing = leaf_graph(leaves)
        graph_time = time.perf_counter() - t0

        if len(edges) > 0:
            depth_i = leaves['depth'][edges[:, 0]]
            depth_j = leaves['depth'][edges[:, 1]]
            max_depth_edge = np.max(np.abs(depth_i - depth_j))
            assert max_depth_edge <= 1, f"2:1 violation: max depth diff {max_depth_edge}"
            print(f"✓ 2:1 constraint: {len(edges)} edges, max depth diff {max_depth_edge}")

        # Test (d): leaf_graph correctness (brute-force O(N^2) check on ratio 10)
        if ratio == 10:
            cx, cy, size = leaves['cx'], leaves['cy'], leaves['size']
            edges_brute = set()
            for i in range(n_leaves):
                for j in range(i + 1, n_leaves):
                    # Check if edge-adjacent (closed boxes share a segment)
                    x1_min, x1_max = cx[i] - size[i]/2, cx[i] + size[i]/2
                    y1_min, y1_max = cy[i] - size[i]/2, cy[i] + size[i]/2
                    x2_min, x2_max = cx[j] - size[j]/2, cx[j] + size[j]/2
                    y2_min, y2_max = cy[j] - size[j]/2, cy[j] + size[j]/2

                    # Edge-adjacent: one axis aligned, other axis overlaps > 0 length
                    x_overlap = max(0, min(x1_max, x2_max) - max(x1_min, x2_min))
                    y_overlap = max(0, min(y1_max, y2_max) - max(y1_min, y2_min))

                    x_aligned = (abs(x1_max - x2_min) < 1e-10 or abs(x1_min - x2_max) < 1e-10)
                    y_aligned = (abs(y1_max - y2_min) < 1e-10 or abs(y1_min - y2_max) < 1e-10)

                    if (x_aligned and y_overlap > 1e-10) or (y_aligned and x_overlap > 1e-10):
                        edges_brute.add(tuple(sorted([i, j])))

            edges_computed = set(map(tuple, edges))
            assert edges_computed == edges_brute, f"Graph mismatch: computed {len(edges_computed)}, brute {len(edges_brute)}"
            print(f"✓ (d) leaf_graph: {len(edges_computed)} edges match brute-force")

        # Test (e): locate
        rng = np.random.RandomState(42)
        test_pts = rng.uniform(0, 1, (1000, 2))
        t0 = time.perf_counter()
        result_idx = locate(leaves, test_pts)
        locate_time = time.perf_counter() - t0

        for m, (px, py) in enumerate(test_pts):
            idx = result_idx[m]
            # Point should be inside the leaf's box
            cx, cy, s = leaves['cx'][idx], leaves['cy'][idx], leaves['size'][idx]
            assert abs(px - cx) <= s / 2 + 1e-10 and abs(py - cy) <= s / 2 + 1e-10, \
                f"Point ({px}, {py}) not in leaf {idx}"

        print(f"✓ (e) Locate: {len(test_pts)} points OK")
        print(f"\nRatio {ratio}: {n_leaves} leaves")
        print(f"  Build: {build_time*1000:.2f} ms")
        print(f"  Leaf graph: {graph_time*1000:.2f} ms")
        print()

    print("ALL OK")
