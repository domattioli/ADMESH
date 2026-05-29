"""Size-field difference: uniform grid vs octree, on a river-into-bay domain.

Physical SC-001 case: a narrow river channel (width w) entering a large bay
(the small feature dwarfed by the big water body). Fair comparison — the SAME
size_field_octree algorithm is run on two grids; only the grid differs:

  LEFT  : uniform grid (constant oracle = basin-tractable Δ). Δ > river width,
          so the river is under-resolved → size field stays coarse in the river.
  RIGHT : adaptive octree (oracle ∝ |distance to boundary|). Refines into the
          river → size field is fine there.

Shared colour scale, so the river is the visible difference.

Run:  python scripts/render_sizefield_diff.py  ->  output/octree_sizefield_diff.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import PatchCollection  # noqa: E402
from matplotlib.patches import Polygon, Rectangle  # noqa: E402
from matplotlib.path import Path as MplPath  # noqa: E402

from scipy.interpolate import RegularGridInterpolator  # noqa: E402

from admesh.api import Domain, triangulate  # noqa: E402
from admesh._stages.mesh_size import solve_iter  # noqa: E402
from admesh._stages.octree_grid import build_octree  # noqa: E402
from admesh._stages.octree_medial import size_field_octree  # noqa: E402

OUTDIR = Path(__file__).resolve().parent.parent / "output"
OUTDIR.mkdir(parents=True, exist_ok=True)


def river_bay_verts(Hx, Hy, w, river_len):
    """Large bay [-Hx,Hx]x[-Hy,0] with a thin river channel of width w going up."""
    return [
        (-Hx, -Hy), (Hx, -Hy), (Hx, 0.0),
        (w / 2, 0.0), (w / 2, river_len), (-w / 2, river_len), (-w / 2, 0.0),
        (-Hx, 0.0),
    ]


def polygon_sdf(verts):
    V = np.asarray(verts, dtype=np.float64)
    A, B = V, np.roll(V, -1, axis=0)
    path = MplPath(V)

    def fd(p):
        p = np.asarray(p, dtype=np.float64).reshape(-1, 2)
        best = np.full(len(p), np.inf)
        for a, b in zip(A, B):
            ab = b - a
            denom = ab @ ab
            t = np.zeros(len(p)) if denom == 0 else np.clip((p - a) @ ab / denom, 0.0, 1.0)
            proj = a + t[:, None] * ab
            best = np.minimum(best, np.hypot(p[:, 0] - proj[:, 0], p[:, 1] - proj[:, 1]))
        return np.where(path.contains_points(p), -best, best)

    return fd


def river_min_h(grid, h, w, river_len):
    cx = np.array([lf.center[0] for lf in grid.leaves])
    cy = np.array([lf.center[1] for lf in grid.leaves])
    D = np.array([lf.D for lf in grid.leaves])
    in_river = (D < 0) & (np.abs(cx) < w / 2) & (cy > 0) & (cy < river_len)
    if not in_river.any():
        return np.nan, 0
    return float(h[in_river].min()), int(in_river.sum())


def panel(ax, grid, h, vmin, vmax, verts, title):
    rects = [Rectangle((lf.center[0] - lf.size / 2, lf.center[1] - lf.size / 2),
                       lf.size, lf.size) for lf in grid.leaves]
    pc = PatchCollection(rects, cmap="viridis", edgecolor="white", linewidth=0.1)
    pc.set_array(np.clip(h, vmin, vmax))
    pc.set_clim(vmin, vmax)
    ax.add_collection(pc)
    ax.add_patch(Polygon(verts, fill=False, ec="k", lw=1.4))
    ax.set_title(title, fontsize=10)
    ax.set_aspect("equal")
    return pc


def _raster(grid, values, xmin, ymin, delta, nx, ny, hmax):
    """Paint per-leaf values onto a fine regular grid (fast; leaves tile, no overlap)."""
    H = np.full((ny, nx), np.nan)
    for lf, val in zip(grid.leaves, values):
        cx, cy = lf.center
        s = lf.size / 2.0
        ix0 = max(0, int((cx - s - xmin) / delta))
        ix1 = min(nx, int(np.ceil((cx + s - xmin) / delta)))
        iy0 = max(0, int((cy - s - ymin) / delta))
        iy1 = min(ny, int(np.ceil((cy + s - ymin) / delta)))
        H[iy0:iy1, ix0:ix1] = val
    H[np.isnan(H)] = hmax
    return H


def admesh_mesh(fd, grid, h_leaf, hmin, hmax, g=0.2):
    """Mesh with admesh's own triangulate(): rasterize octree h -> gradient-limit
    (solve_iter) -> RegularGridInterpolator size field -> distmesh."""
    xmin, ymin, xmax, ymax = grid.bbox
    delta = hmin
    nx = int(np.ceil((xmax - xmin) / delta)) + 1
    ny = int(np.ceil((ymax - ymin) / delta)) + 1
    xs = xmin + delta * np.arange(nx)
    ys = ymin + delta * np.arange(ny)
    X, Y = np.meshgrid(xs, ys)
    H = np.clip(_raster(grid, h_leaf, xmin, ymin, delta, nx, ny, hmax), hmin, hmax)
    Dabs = np.abs(fd(np.column_stack([X.ravel(), Y.ravel()])).reshape(ny, nx))
    Hs = solve_iter(H, Dabs, hmax, hmin, g, delta)
    interp = RegularGridInterpolator((ys, xs), Hs, method="linear", bounds_error=False, fill_value=hmax)

    def fh(p):
        p = np.asarray(p, dtype=float).reshape(-1, 2)
        return interp(np.column_stack([p[:, 1], p[:, 0]]))

    # Seed distmesh with interior octree leaf centers (dense in the river) — the raw
    # graded field alone collapses distmesh; seeding + a relaxed quality gate lets
    # admesh's own mesher resolve the channel. Low min_q is a known caveat (see report).
    ctr = np.array([lf.center for lf in grid.leaves], dtype=np.float64)
    Dl = np.array([lf.D for lf in grid.leaves])
    ip = ctr[Dl < 0]
    dom = Domain(sdf=fd, bbox=(xmin, ymin, xmax, ymax))
    mesh = triangulate(dom, h_min=hmin, h_max=hmax, size_field=fh,
                       initial_points=ip, quality_gate=(0.0, 0.0), max_iter=80, seed=0)
    return np.asarray(mesh.nodes), np.asarray(mesh.elements)


def mesh_panel(ax, p, tri, verts, title):
    if len(tri):
        ax.triplot(p[:, 0], p[:, 1], tri, lw=0.3, color="#1f77b4")
    if len(p):
        ax.plot(p[:, 0], p[:, 1], ".", ms=1.5, color="#d62728")
    ax.add_patch(Polygon(verts, fill=False, ec="k", lw=1.4))
    ax.set_title(title, fontsize=10)
    ax.set_aspect("equal")


def main():
    Hx, Hy, w, river_len = 24.0, 14.0, 2.0, 12.0
    hmin, hmax, R = 0.5, 5.0, 2.0
    delta_uni = 4.0  # basin-tractable, > river width w=2

    verts = river_bay_verts(Hx, Hy, w, river_len)
    fd = polygon_sdf(verts)

    class _D:
        pass

    dom = _D()
    dom.fd = fd
    vx = [v[0] for v in verts]; vy = [v[1] for v in verts]
    dom.bbox = (min(vx), min(vy), max(vx), max(vy))

    oracle_oct = lambda x, y: max(hmin, min(hmax, 0.6 * abs(fd(np.array([[x, y]]))[0])))  # noqa: E731
    oracle_uni = lambda x, y: delta_uni  # noqa: E731

    g_uni = build_octree(dom, h_min=delta_uni, h_max=hmax, size_oracle=oracle_uni, balance=False)
    g_oct = build_octree(dom, h_min=hmin, h_max=hmax, size_oracle=oracle_oct, balance=True)
    h_uni, _ = size_field_octree(g_uni, R=R, hmin=hmin, hmax=hmax)
    h_oct, med = size_field_octree(g_oct, R=R, hmin=hmin, hmax=hmax)

    ruh, ruc = river_min_h(g_uni, h_uni, w, river_len)
    roh, roc = river_min_h(g_oct, h_oct, w, river_len)
    vmin = min(np.min(h_uni), np.min(h_oct))
    vmax = max(np.max(h_uni), np.max(h_oct))

    uni_line = (f"river UNRESOLVED — 0 cells inside width-{w:.0f} river"
                if ruc == 0 else
                f"river min h = {ruh:.2f}  (~{w/ruh:.1f} elems across, {ruc} cells)")
    oct_line = (f"river UNRESOLVED — 0 cells"
                if roc == 0 else
                f"river min h = {roh:.2f}  (~{w/roh:.1f} elems across, {roc} cells)")

    def _safe_mesh(grid, hleaf):
        try:
            return admesh_mesh(fd, grid, hleaf, hmin, hmax)
        except Exception as e:  # noqa: BLE001
            print(f"admesh mesh failed: {type(e).__name__}: {e}")
            return np.empty((0, 2)), np.empty((0, 3), dtype=int)

    pu, tu = _safe_mesh(g_uni, h_uni)
    po, to = _safe_mesh(g_oct, h_oct)

    def in_river(p):
        return (np.abs(p[:, 0]) < w / 2) & (p[:, 1] > 0) & (p[:, 1] < river_len) if len(p) else np.array([])
    ru_n = int(in_river(pu).sum()) if len(pu) else 0
    ro_n = int(in_river(po).sum()) if len(po) else 0

    fig, ((axU, axO), (axMU, axMO)) = plt.subplots(2, 2, figsize=(14, 11))
    panel(axU, g_uni, h_uni, vmin, vmax, verts,
          f"UNIFORM Δ={delta_uni:.0f} ({len(g_uni.leaves)} cells)\n{uni_line}")
    pc = panel(axO, g_oct, h_oct, vmin, vmax, verts,
               f"OCTREE ({len(g_oct.leaves)} leaves)\n{oct_line}")
    mesh_panel(axMU, pu, tu, verts, f"UNIFORM mesh — {len(tu)} elements\nriver nodes = {ru_n} (channel bridged / unresolved)")
    mesh_panel(axMO, po, to, verts, f"OCTREE mesh — {len(to)} elements\nriver nodes = {ro_n} (channel resolved)")
    for ax in (axU, axO, axMU, axMO):
        ax.set_xlim(dom.bbox[0], dom.bbox[2]); ax.set_ylim(dom.bbox[1], dom.bbox[3])
    fig.colorbar(pc, ax=(axU, axO), label="size-field target edge length  h = LFS / R", shrink=0.8)
    fig.suptitle("Spec 021 — size field (top) and resulting mesh (bottom): uniform vs octree, "
                 "river-into-bay (same algorithm, grid differs)", fontsize=12)
    out = OUTDIR / "octree_sizefield_diff.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")
    print(f"uniform: river_min_h={ruh:.2f} river_cells={ruc} mesh_elems={len(tu)} river_nodes={ru_n}")
    print(f"octree:  river_min_h={roh:.2f} river_cells={roc} mesh_elems={len(to)} river_nodes={ro_n}")


if __name__ == "__main__":
    main()
