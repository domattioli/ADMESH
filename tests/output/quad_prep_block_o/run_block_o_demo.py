"""Block_O demo: load mesh, run smoother, render before/after.

Manually parses Block_O.14 (which omits the boundary sections that
admesh.fort14 expects) and runs the spec-004 smoother on it. Renders
side-by-side PNG of input vs smoothed mesh, plus a quality histogram.
"""

from __future__ import annotations

import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import admesh
from admesh.in_polygon import in_polygon


HERE = Path(__file__).parent
FORT14 = HERE / "Block_O.14"
OUT_DIR = HERE


def _load_minimal_fort14(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with open(path) as f:
        f.readline()  # description
        ne, nn = map(int, f.readline().split())
        p = np.empty((nn, 2), dtype=np.float64)
        for i in range(nn):
            tokens = f.readline().split()
            p[i, 0] = float(tokens[1])
            p[i, 1] = float(tokens[2])
        t = np.empty((ne, 3), dtype=np.int64)
        for i in range(ne):
            tokens = f.readline().split()
            t[i, 0] = int(tokens[2]) - 1  # ADCIRC is 1-based
            t[i, 1] = int(tokens[3]) - 1
            t[i, 2] = int(tokens[4]) - 1
    return p, t


def _build_boundary_rings(p: np.ndarray, t: np.ndarray) -> list[np.ndarray]:
    """Recover ALL boundary rings from triangle edges (outer + inner holes).

    Boundary edges are those owned by exactly one triangle. Walk every
    such ring; return them sorted with the outer (largest by signed
    area) ring first. Issue #18 — earlier versions returned only the
    largest ring, which silently dropped interior holes and let inner-
    ring nodes drift through the smoother.
    """
    edge_count: dict[tuple[int, int], int] = {}
    edge_dir: dict[tuple[int, int], tuple[int, int]] = {}
    for k in range(len(t)):
        for a, b in [(t[k, 0], t[k, 1]), (t[k, 1], t[k, 2]), (t[k, 2], t[k, 0])]:
            key = (int(min(a, b)), int(max(a, b)))
            edge_count[key] = edge_count.get(key, 0) + 1
            if key not in edge_dir:
                edge_dir[key] = (int(a), int(b))
    boundary_edges = [edge_dir[k] for k, c in edge_count.items() if c == 1]
    return _walk_all_rings(p, boundary_edges)


def _walk_all_rings(p: np.ndarray, edges: list[tuple[int, int]]) -> list[np.ndarray]:
    adj: dict[int, list[int]] = {}
    for a, b in edges:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    visited: set[int] = set()
    ring_idx_lists: list[list[int]] = []
    for start in adj:
        if start in visited:
            continue
        ring = [start]
        visited.add(start)
        prev = -1
        cur = start
        while True:
            nbrs = [n for n in adj[cur] if n != prev]
            if not nbrs:
                break
            nxt = nbrs[0]
            if nxt == start:
                break
            if nxt in visited:
                break
            ring.append(nxt)
            visited.add(nxt)
            prev = cur
            cur = nxt
        if len(ring) > 2:
            ring_idx_lists.append(ring)

    rings_xy = [p[r] for r in ring_idx_lists]
    # Sort by absolute signed area, descending — the first ring is the
    # outer boundary; the rest are holes.
    rings_xy.sort(key=lambda xy: -abs(_signed_area(xy)))
    if not rings_xy:
        raise RuntimeError("no boundary ring found")
    return rings_xy


def _signed_area(xy: np.ndarray) -> float:
    x = xy[:, 0]
    y = xy[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def _make_sdf(rings: list[np.ndarray]):
    """Vectorized signed-distance to a multi-ring polygon (outer + holes).

    Inside-test: inside outer ring AND outside every hole ring.
    Distance: minimum distance to any edge across all rings.
    """
    # Pre-stack all edge segments across all rings.
    seg_a_x_list, seg_a_y_list = [], []
    seg_b_x_list, seg_b_y_list = [], []
    for ring_xy in rings:
        xs = np.asarray(ring_xy[:, 0], dtype=np.float64)
        ys = np.asarray(ring_xy[:, 1], dtype=np.float64)
        seg_a_x_list.append(xs)
        seg_a_y_list.append(ys)
        seg_b_x_list.append(np.roll(xs, -1))
        seg_b_y_list.append(np.roll(ys, -1))
    ax_ = np.concatenate(seg_a_x_list)
    ay_ = np.concatenate(seg_a_y_list)
    bx_ = np.concatenate(seg_b_x_list)
    by_ = np.concatenate(seg_b_y_list)
    dx_ = bx_ - ax_
    dy_ = by_ - ay_
    ll_ = dx_ * dx_ + dy_ * dy_
    ll_ = np.where(ll_ > 1e-30, ll_, 1.0)

    outer = rings[0]
    holes = rings[1:]

    def fd(q: np.ndarray) -> np.ndarray:
        q = np.atleast_2d(q)
        qx = q[:, 0:1]
        qy = q[:, 1:2]
        tt = ((qx - ax_) * dx_ + (qy - ay_) * dy_) / ll_
        tt = np.clip(tt, 0.0, 1.0)
        cx = ax_ + tt * dx_
        cy = ay_ + tt * dy_
        d2 = (qx - cx) ** 2 + (qy - cy) ** 2
        d_min = np.sqrt(d2.min(axis=1))
        inside_outer, _ = in_polygon(q[:, 0], q[:, 1], outer[:, 0], outer[:, 1])
        inside_any_hole = np.zeros(len(q), dtype=bool)
        for h_xy in holes:
            in_h, _ = in_polygon(q[:, 0], q[:, 1], h_xy[:, 0], h_xy[:, 1])
            inside_any_hole |= in_h
        inside = inside_outer & ~inside_any_hole
        return np.where(inside, -d_min, d_min)

    return fd


def _plot_mesh(ax, p, t, title, cmap_q=None, vmin=None, vmax=None):
    ax.triplot(p[:, 0], p[:, 1], t, lw=0.2, color="0.4")
    ax.set_title(title, fontsize=11)
    ax.set_aspect("equal")
    ax.set_xlabel("x")
    ax.set_ylabel("y")


def _per_element_right_iso(p: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Per-triangle right-isoceles quality (same math as
    admesh.right_iso_quality, but returns the array instead of the mean)."""
    x, y = p[:, 0], p[:, 1]
    a = np.hypot(x[t[:, 1]] - x[t[:, 0]], y[t[:, 1]] - y[t[:, 0]])
    b = np.hypot(x[t[:, 2]] - x[t[:, 1]], y[t[:, 2]] - y[t[:, 1]])
    c = np.hypot(x[t[:, 0]] - x[t[:, 2]], y[t[:, 0]] - y[t[:, 2]])
    sides = np.sort(np.column_stack([a, b, c]), axis=1)
    L1, L2, L_hyp = sides[:, 0], sides[:, 1], sides[:, 2]
    leg_eq = 1.0 - np.abs(L1 - L2) / np.maximum(L2, 1e-300)
    cos_apex = np.clip(
        (L1 ** 2 + L2 ** 2 - L_hyp ** 2) / (2.0 * L1 * L2), -1.0, 1.0
    )
    angle_apex = np.arccos(cos_apex)
    right_angle = 1.0 - np.abs(angle_apex - np.pi / 2.0) / (np.pi / 2.0)
    target_hyp = np.sqrt(2.0) * (L1 + L2) / 2.0
    hyp_fit = 1.0 - np.abs(L_hyp - target_hyp) / L_hyp
    q = np.clip(leg_eq, 0, 1) * np.clip(right_angle, 0, 1) * np.clip(hyp_fit, 0, 1)
    return np.where(np.isfinite(q), np.clip(q, 0, 1), 0.0)


def _plot_mesh_quality(ax, p, t, q_elem, title, cmap, vmin=0.0, vmax=1.0):
    """Render mesh with per-triangle face color = q_elem."""
    coll = ax.tripcolor(
        p[:, 0], p[:, 1], t, facecolors=q_elem,
        cmap=cmap, vmin=vmin, vmax=vmax, edgecolors="0.4", linewidth=0.15,
    )
    ax.set_title(title, fontsize=11)
    ax.set_aspect("equal")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    return coll


def main() -> None:
    print(f"Loading {FORT14.name}")
    p_in, t = _load_minimal_fort14(FORT14)
    print(f"  Nodes: {len(p_in)}, Elements: {len(t)}")
    print(f"  BBox x: [{p_in[:,0].min():.2f}, {p_in[:,0].max():.2f}]")
    print(f"  BBox y: [{p_in[:,1].min():.2f}, {p_in[:,1].max():.2f}]")

    print("Building multi-ring SDF (outer + holes; issue #18 fix)")
    rings = _build_boundary_rings(p_in, t)
    print(f"  Rings: {len(rings)}  (sizes: {[len(r) for r in rings]})")
    fd = _make_sdf(rings)

    q_in = admesh.right_iso_quality(p_in, t)
    _, mq_in_mean, mq_in = admesh.mesh_quality(p_in, t)
    print(f"Pre  right_iso_quality = {q_in:.4f}")
    print(f"Pre  mesh_quality (mean) = {mq_in_mean:.4f}")

    print("Running smooth_for_quadrangulation (n_outer=2)")
    t0 = time.perf_counter()
    p_out, _ = admesh.smooth_for_quadrangulation(
        p_in, t, fd=fd, h=None, pair_hint=True, n_outer=2
    )
    elapsed = time.perf_counter() - t0
    print(f"  wall clock: {elapsed:.2f} s")

    q_out = admesh.right_iso_quality(p_out, t)
    _, mq_out_mean, mq_out = admesh.mesh_quality(p_out, t)
    print(f"Post right_iso_quality = {q_out:.4f}  (delta {q_out - q_in:+.4f})")
    print(f"Post mesh_quality (mean) = {mq_out_mean:.4f}")

    # Boundary drift check
    e0 = np.hypot(p_in[t[:,1],0]-p_in[t[:,0],0], p_in[t[:,1],1]-p_in[t[:,0],1])
    geps = 1e-3 * np.median(e0)
    bnd = np.abs(fd(p_in)) < geps
    drift = np.max(np.abs(fd(p_out[bnd]))) if bnd.any() else 0.0
    print(f"Boundary drift: {drift:.2e}  (geps={geps:.2e})")

    # Post-smooth Delaunay retriangulation (still respecting boundaries):
    # Delaunay over smoothed nodes, then keep only triangles whose centroid
    # is inside the domain (signed-distance test fd(centroid) < -geps).
    # This is the standard distmesh-style domain-restricted Delaunay
    # (admesh.distmesh uses the same pattern). Boundary nodes are at
    # exactly the smoothed positions, so the boundary itself is honored.
    from scipy.spatial import Delaunay
    print("Re-triangulating smoothed nodes (Delaunay + domain filter)")
    tri = Delaunay(p_out)
    t_re = tri.simplices.astype(np.int64)
    centroids = (p_out[t_re[:, 0]] + p_out[t_re[:, 1]] + p_out[t_re[:, 2]]) / 3.0
    keep = fd(centroids) < -geps
    t_re = t_re[keep]
    q_re = admesh.right_iso_quality(p_out, t_re)
    _, mq_re_mean, _ = admesh.mesh_quality(p_out, t_re)
    print(f"  retriangulated: {len(p_out)} nodes, {len(t_re)} elements")
    print(f"  Re-tri right_iso = {q_re:.4f}, mesh_quality (mean) = {mq_re_mean:.4f}")

    # Render side-by-side-by-side: input | smoothed | retriangulated
    print("Rendering before/after/retriangulated PNG")
    fig, axes = plt.subplots(1, 3, figsize=(20, 9))
    _plot_mesh(axes[0], p_in, t, f"Input\n(right_iso_q = {q_in:.3f})")
    _plot_mesh(axes[1], p_out, t,
               f"Smoothed (same connectivity)\n(right_iso_q = {q_out:.3f})")
    _plot_mesh(axes[2], p_out, t_re,
               f"Smoothed + Delaunay re-tri\n(right_iso_q = {q_re:.3f})")
    fig.suptitle(
        f"Block_O.14  —  {len(p_in)} nodes  —  "
        f"smooth_for_quadrangulation (n_outer=2) then domain-restricted Delaunay",
        fontsize=12,
    )
    fig.tight_layout()
    out_pair = OUT_DIR / "block_o_before_after.png"
    fig.savefig(out_pair, dpi=150)
    plt.close(fig)
    print(f"  wrote {out_pair}")

    # Per-triangle right_iso_quality heatmap (the answer to "how close is
    # each triangle to right-isoceles?"). Same color scale on both panels
    # so visual diff is meaningful.
    print("Rendering right_iso_quality heatmap (per-triangle)")
    rq_in = _per_element_right_iso(p_in, t)
    rq_out = _per_element_right_iso(p_out, t)
    fig, axes = plt.subplots(1, 2, figsize=(15, 9))
    cmap = plt.get_cmap("RdYlGn")
    coll0 = _plot_mesh_quality(
        axes[0], p_in, t, rq_in,
        f"Input  (mean right_iso_q = {rq_in.mean():.3f})", cmap=cmap,
    )
    _plot_mesh_quality(
        axes[1], p_out, t, rq_out,
        f"Smoothed  (mean right_iso_q = {rq_out.mean():.3f})", cmap=cmap,
    )
    cbar = fig.colorbar(coll0, ax=axes, shrink=0.7, pad=0.02)
    cbar.set_label("per-triangle right_iso_quality  (1.0 = right-isoceles)")
    fig.suptitle(
        "Block_O.14 — per-triangle closeness to right-isoceles target",
        fontsize=12,
    )
    out_heat = OUT_DIR / "block_o_right_iso_heatmap.png"
    fig.savefig(out_heat, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out_heat}")

    # Quality histogram comparison (right_iso, not equilateral)
    print("Rendering right_iso_quality histogram")
    fig, ax = plt.subplots(figsize=(8, 5))
    bins = np.linspace(0, 1, 41)
    ax.hist(rq_in, bins=bins, alpha=0.55, label=f"input (mean={rq_in.mean():.3f})")
    ax.hist(rq_out, bins=bins, alpha=0.55, label=f"smoothed (mean={rq_out.mean():.3f})")
    ax.set_xlabel("per-triangle right_iso_quality (1.0 = right-isoceles)")
    ax.set_ylabel("count")
    ax.set_title("Block_O.14 — right_iso_quality before vs after smoothing")
    ax.legend()
    fig.tight_layout()
    out_riso_hist = OUT_DIR / "block_o_right_iso_histogram.png"
    fig.savefig(out_riso_hist, dpi=150)
    plt.close(fig)
    print(f"  wrote {out_riso_hist}")

    # Equilateral quality histogram (the original)
    fig, ax = plt.subplots(figsize=(8, 5))
    bins = np.linspace(0, 1, 41)
    ax.hist(mq_in, bins=bins, alpha=0.55, label=f"input (mean={mq_in_mean:.3f})")
    ax.hist(mq_out, bins=bins, alpha=0.55, label=f"smoothed (mean={mq_out_mean:.3f})")
    ax.set_xlabel("triangle quality (equilateral target)")
    ax.set_ylabel("count")
    ax.set_title("Block_O.14 — mesh_quality before vs after smoothing")
    ax.legend()
    fig.tight_layout()
    out_hist = OUT_DIR / "block_o_quality_histogram.png"
    fig.savefig(out_hist, dpi=150)
    plt.close(fig)
    print(f"  wrote {out_hist}")

    # Layer/skeletonization plots (onion-peel BFS from boundary)
    print("Rendering mesh layers (skeletonization) for input/smoothed/retriangulated")
    fig, axes = plt.subplots(1, 3, figsize=(20, 9))

    # Create minimal Mesh objects for layer plotting
    input_mesh = admesh.Mesh(nodes=p_in, elements=t, boundaries=[])
    smoothed_mesh = admesh.Mesh(nodes=p_out, elements=t, boundaries=[])
    retri_mesh = admesh.Mesh(nodes=p_out, elements=t_re, boundaries=[])

    input_mesh.plot_layers(ax=axes[0], cmap="viridis")
    axes[0].set_title(f"Input mesh layers\n({len(t)} elements)", fontsize=11)

    smoothed_mesh.plot_layers(ax=axes[1], cmap="viridis")
    axes[1].set_title(f"Smoothed mesh layers\n({len(t)} elements, same connectivity)", fontsize=11)

    retri_mesh.plot_layers(ax=axes[2], cmap="viridis")
    axes[2].set_title(f"Retriangulated mesh layers\n({len(t_re)} elements)", fontsize=11)

    fig.suptitle(
        "Block_O.14 — Mesh layers (skeletonization via onion-peel BFS from boundary)",
        fontsize=12,
    )
    fig.tight_layout()
    out_layers = OUT_DIR / "block_o_layers.png"
    fig.savefig(out_layers, dpi=150)
    plt.close(fig)
    print(f"  wrote {out_layers}")

    print("Done.")


if __name__ == "__main__":
    main()
