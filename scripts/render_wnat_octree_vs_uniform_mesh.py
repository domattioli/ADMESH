"""WNAT-Onur graded-mesh comparison: uniform vs spec-022 octree size fields.

Same graded size oracle (0.3 * |fd|, clamped to [h_min, h_max]) is backed
by two different sampling structures:

  A — UNIFORM background grid (scipy RegularGridInterpolator)
  B — spec-022 octree leaves (admesh._stages.octree_grid.interpolate)

Each backing structure is wrapped as a size_field callable and fed to
admesh.triangulate(). Wall-clock is split into:

  1. size-field setup time   (uniform grid sample / octree build)
  2. triangulate() time      (distmesh under that field)

Both yield non-uniform meshes with the same target h_min near the
coastline and h_max offshore. Comparison answers: what does the spec-022
octree buy us *as a size-field source for distmesh*?

Run:  python scripts/render_wnat_octree_vs_uniform_mesh.py
Out:  output/wnat_octree_vs_uniform_mesh.png  +  stdout timing table.
"""

from __future__ import annotations

import json
import pathlib
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import shapely  # noqa: E402
from scipy.interpolate import RegularGridInterpolator  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402

import admesh  # noqa: E402
from admesh._stages.octree_grid import build_octree  # noqa: E402
from admesh._stages.octree_grid import _is_leaf  # noqa: E402
from admesh._stages.octree_grid import interpolate as octree_interp  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
ONUR = REPO / "benchmarks" / "data" / "wnat_onur_boundary.json"
OUT = REPO / "output" / "wnat_octree_vs_uniform_mesh.png"

H_MIN = 0.25  # degrees — fine resolution near boundary
H_MAX = 1.5   # degrees — coarse offshore
UNIFORM_DELTA = H_MIN   # uniform background grid spacing — match octree finest level
MAX_ITER = 40   # distmesh cap
SEED = 0
HOLE_MIN_VERTS = 8  # drop tiny holes that bog distmesh


def load_polygon_and_domain():
    data = json.loads(ONUR.read_text())
    rings = data["rings"]
    outer = rings[0]
    holes = [r for r in rings[1:] if len(r) >= HOLE_MIN_VERTS]
    poly = Polygon(outer, holes=holes)
    bbox = tuple(data["bbox"])
    return poly, bbox, outer, holes


def make_sdf(poly: Polygon):
    boundary = poly.boundary

    def fd(p):
        p = np.asarray(p, dtype=np.float64).reshape(-1, 2)
        pts = shapely.points(p[:, 0], p[:, 1])
        d = shapely.distance(pts, boundary)
        inside = shapely.contains(poly, pts)
        return np.where(inside, -d, d)

    return fd


def graded_oracle_scalar(fd):
    """Per-point scalar oracle used by build_octree."""
    def oracle(x, y):
        d = abs(float(fd(np.array([[x, y]]))[0]))
        return max(H_MIN, min(H_MAX, 0.3 * d))
    return oracle


def graded_oracle_batch(fd):
    """Vectorized batch oracle for uniform-grid sampling."""
    def oracle(p):
        d = np.abs(fd(p))
        return np.clip(0.3 * d, H_MIN, H_MAX)
    return oracle


def build_uniform_size_field(bbox, fd):
    xmin, ymin, xmax, ymax = bbox
    pad = H_MAX
    xs = np.arange(xmin - pad, xmax + pad + UNIFORM_DELTA, UNIFORM_DELTA)
    ys = np.arange(ymin - pad, ymax + pad + UNIFORM_DELTA, UNIFORM_DELTA)
    t0 = time.perf_counter()
    X, Y = np.meshgrid(xs, ys, indexing="xy")
    pts = np.c_[X.ravel(), Y.ravel()]
    h_vals = graded_oracle_batch(fd)(pts).reshape(len(ys), len(xs))
    interp = RegularGridInterpolator((ys, xs), h_vals,
                                     bounds_error=False, fill_value=H_MAX)
    setup_dt = time.perf_counter() - t0

    def size_field(p):
        p = np.asarray(p, dtype=np.float64).reshape(-1, 2)
        return interp(np.c_[p[:, 1], p[:, 0]])

    return size_field, setup_dt, len(pts)


def build_octree_size_field(bbox, fd):
    class _Dom:
        pass
    dom = _Dom()
    dom.fd = fd
    dom.bbox = bbox
    oracle = graded_oracle_scalar(fd)
    t0 = time.perf_counter()
    grid = build_octree(dom, h_min=H_MIN, h_max=H_MAX,
                        size_oracle=oracle, balance=True)
    leaves = grid.leaves
    h_per_leaf = np.array([lf.size for lf in leaves], dtype=np.float64)
    h_max_val = float(h_per_leaf.max())
    # Spec-022 perf bug workaround: locate() rebuilds an O(N²) node→leaf
    # dict every call. Precompute it once here and descend per-point inline.
    node_to_leaf = {}
    for li, lf in enumerate(leaves):
        for ni, nd in enumerate(grid._nodes):
            if nd is lf:
                node_to_leaf[ni] = li
                break
    nodes = grid._nodes
    root = grid.root
    xmin, ymin, xmax, ymax = grid.bbox
    setup_dt = time.perf_counter() - t0

    def size_field(p):
        p = np.asarray(p, dtype=np.float64).reshape(-1, 2)
        out = np.empty(len(p), dtype=np.float64)
        for qi in range(len(p)):
            x = min(max(p[qi, 0], xmin), xmax)
            y = min(max(p[qi, 1], ymin), ymax)
            idx = root
            while not _is_leaf(nodes[idx]):
                cx, cy = nodes[idx].center
                q = (1 if x > cx else 0) + (2 if y > cy else 0)
                ci = nodes[idx]._children_idx[q]
                if ci == -1:
                    break
                idx = ci
            li = node_to_leaf.get(idx, 0)
            out[qi] = h_per_leaf[li]
        return out

    return size_field, setup_dt, len(leaves)


def run_triangulate(domain, size_field, h_max, label):
    print(f"  [{label}] triangulating (max_iter={MAX_ITER}) …", end=" ", flush=True)
    t0 = time.perf_counter()
    try:
        # Pass h_max=H_MIN so distmesh seeds at the finest scale; size_field
        # tells it to coarsen offshore. Without this, h0=h_max → sparse seed.
        mesh = admesh.triangulate(
            domain,
            h_max=H_MIN,
            size_field=size_field,
            max_iter=MAX_ITER,
            seed=SEED,
            quality_gate=(0.0, 0.0),  # disabled — render whatever distmesh produces
        )
        dt = time.perf_counter() - t0
        print(f"{dt:.2f}s  ({mesh.n_nodes} nodes / {mesh.n_elements} elements)")
        return mesh, dt
    except Exception as e:
        dt = time.perf_counter() - t0
        print(f"FAILED in {dt:.2f}s — {type(e).__name__}: {e}")
        return None, dt


def plot_mesh(ax, mesh, outer, holes, label, sub_title):
    if mesh is None:
        ax.text(0.5, 0.5, f"{label}\n(triangulate failed)",
                ha="center", va="center", transform=ax.transAxes, fontsize=12)
        ax.set_aspect("equal")
        return
    ax.triplot(mesh.nodes[:, 0], mesh.nodes[:, 1],
               mesh.elements, lw=0.25, color="#1f77b4", alpha=0.7)
    outer_arr = np.array(outer)
    ax.plot(outer_arr[:, 0], outer_arr[:, 1], color="black", lw=0.6)
    for h in holes:
        h_arr = np.array(h)
        ax.plot(h_arr[:, 0], h_arr[:, 1], color="black", lw=0.4)
    ax.set_aspect("equal")
    ax.set_title(f"{label}\n{sub_title}", fontsize=10)


def main():
    print(f"=== WNAT-Onur graded-mesh comparison ===")
    print(f"  h_min={H_MIN}° h_max={H_MAX}° ratio={H_MAX/H_MIN:.1f} "
          f"max_iter={MAX_ITER} drop_holes<{HOLE_MIN_VERTS}_verts")

    poly, bbox, outer, holes = load_polygon_and_domain()
    print(f"  loaded: {len(outer)} outer verts, {len(holes)} holes kept")

    fd = make_sdf(poly)

    # Build a Domain object once; share between both runs
    class _ApiDomain:
        pass
    dom = _ApiDomain()
    dom.sdf = fd
    dom.bbox = bbox
    dom.pfix = None
    dom.bc_segments = None
    # admesh.api.triangulate checks isinstance(domain, Domain). Quickest path
    # is to construct a real Domain via the JSON loader (it handles polygon).
    domain = admesh.load_domain_from_json(str(ONUR))

    print(f"\nA. UNIFORM background grid (delta={UNIFORM_DELTA}°) ")
    sf_u, setup_u, n_grid = build_uniform_size_field(bbox, fd)
    print(f"  size-field setup: {setup_u:.2f}s  ({n_grid:,} grid pts)")
    mesh_u, tri_u = run_triangulate(domain, sf_u, H_MAX, "uniform")

    print(f"\nB. SPEC-022 OCTREE size field ")
    sf_o, setup_o, n_leaves = build_octree_size_field(bbox, fd)
    print(f"  size-field setup: {setup_o:.2f}s  ({n_leaves:,} leaves)")
    mesh_o, tri_o = run_triangulate(domain, sf_o, H_MAX, "octree")

    print()
    print("=== timing breakdown ===")
    print(f"{'phase':<24} {'uniform':>12} {'octree':>12}")
    print(f"{'-'*24} {'-'*12} {'-'*12}")
    print(f"{'size-field setup':<24} {setup_u:>10.2f}s {setup_o:>10.2f}s")
    print(f"{'triangulate':<24} {tri_u:>10.2f}s {tri_o:>10.2f}s")
    total_u = setup_u + tri_u
    total_o = setup_o + tri_o
    print(f"{'TOTAL':<24} {total_u:>10.2f}s {total_o:>10.2f}s")
    if total_u > 0 and total_o > 0:
        ratio = total_o / total_u
        print(f"  octree / uniform total ratio: {ratio:.2f}×  "
              f"({'octree slower' if ratio > 1 else 'octree faster'})")

    print()
    print("=== mesh stats ===")
    print(f"{'metric':<20} {'uniform':>12} {'octree':>12}")
    print(f"{'-'*20} {'-'*12} {'-'*12}")
    if mesh_u is not None:
        u_q = mesh_u.quality
        print(f"{'nodes':<20} {mesh_u.n_nodes:>12,} "
              f"{mesh_o.n_nodes if mesh_o else 0:>12,}")
        print(f"{'elements':<20} {mesh_u.n_elements:>12,} "
              f"{mesh_o.n_elements if mesh_o else 0:>12,}")
        print(f"{'min quality':<20} {u_q.min():>12.3f} "
              f"{mesh_o.quality.min() if mesh_o else 0:>12.3f}")
        print(f"{'mean quality':<20} {u_q.mean():>12.3f} "
              f"{mesh_o.quality.mean() if mesh_o else 0:>12.3f}")

    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    sub_u = (f"setup {setup_u:.1f}s + triangulate {tri_u:.1f}s = {total_u:.1f}s\n"
             f"{mesh_u.n_elements if mesh_u else 0} elements") if mesh_u else f"{total_u:.1f}s (failed)"
    sub_o = (f"setup {setup_o:.1f}s + triangulate {tri_o:.1f}s = {total_o:.1f}s\n"
             f"{mesh_o.n_elements if mesh_o else 0} elements") if mesh_o else f"{total_o:.1f}s (failed)"
    plot_mesh(axes[0], mesh_u, outer, holes,
              f"A · uniform background grid (Δ={UNIFORM_DELTA}°)", sub_u)
    plot_mesh(axes[1], mesh_o, outer, holes,
              "B · spec-022 octree size field", sub_o)
    fig.suptitle(
        f"WNAT-Onur graded mesh · uniform vs spec-022 octree size field  "
        f"(h_min={H_MIN}°, h_max={H_MAX}°, ratio={H_MAX/H_MIN:.0f}×)",
        fontsize=12,
    )
    fig.tight_layout()
    OUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUT, dpi=140)
    plt.close(fig)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
