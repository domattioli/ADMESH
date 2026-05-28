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

    fig, (axU, axO) = plt.subplots(1, 2, figsize=(14, 6))
    panel(axU, g_uni, h_uni, vmin, vmax, verts,
          f"UNIFORM Δ={delta_uni:.0f} ({len(g_uni.leaves)} cells)\n{uni_line}")
    pc = panel(axO, g_oct, h_oct, vmin, vmax, verts,
               f"OCTREE ({len(g_oct.leaves)} leaves)\n{oct_line}")
    for ax in (axU, axO):
        ax.set_xlim(dom.bbox[0], dom.bbox[2]); ax.set_ylim(dom.bbox[1], dom.bbox[3])
    fig.colorbar(pc, ax=(axU, axO), label="size-field target edge length  h = LFS / R", shrink=0.8)
    fig.suptitle("Spec 021 — size field: uniform vs octree on a river-into-bay domain "
                 "(same algorithm, grid differs)", fontsize=12)
    out = OUTDIR / "octree_sizefield_diff.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")
    print(f"uniform: river_min_h={ruh:.2f} cells_in_river={ruc} | octree: river_min_h={roh:.2f} cells_in_river={roc}")


if __name__ == "__main__":
    main()
