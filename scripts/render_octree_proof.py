"""Visual proof for spec 021 — octree background grid (US1 / SC-001).

Domain: a slanted PARALLELOGRAM basin with a thin NOTCH cut into its top edge
(the narrow feature, dwarfed by the parallelogram). Exact polygon SDF so the
distance field — and therefore the medial axis — is accurate. Two panels:

  A. Octree size field h = LFS/R per leaf — small (fine) in the narrow notch,
     large (coarse) in the open parallelogram.
  B. Medial-axis leaves (red) thread the notch (resolved), overlaid with a
     uniform grid at a basin-tractable spacing whose cells are wider than the
     notch — a tractable uniform grid cannot resolve the notch medial axis.

Run:  python scripts/render_octree_proof.py   ->  output/octree_proof.png
Headless (Agg). Uses the landed octree core + admesh._stages.octree_medial.
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


def corners_with_notch(hX, hY, k, nw, nl):
    """Vertices of a parallelogram (rect sheared by x += k*y) with a top notch."""
    def w(u, y):
        return (u + k * y, y)

    yb = hY - nl
    return [
        w(-hX, -hY), w(hX, -hY), w(hX, hY),      # bottom + right side + top-right
        w(nw / 2, hY), w(nw / 2, yb), w(-nw / 2, yb), w(-nw / 2, hY),  # notch
        w(-hX, hY),                               # top-left
    ]


def polygon_sdf(verts):
    """Exact signed distance to a (possibly concave) polygon. Negative inside."""
    V = np.asarray(verts, dtype=np.float64)
    A = V
    B = np.roll(V, -1, axis=0)
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
        inside = path.contains_points(p)
        return np.where(inside, -best, best)

    return fd


def main():
    hX, hY, k = 12.0, 8.0, 0.6
    notch_w, notch_len = 2.0, 7.0
    hmin, hmax, R_elem = 0.6, 5.0, 2.0
    verts = corners_with_notch(hX, hY, k, notch_w, notch_len)
    fd = polygon_sdf(verts)

    class _D:
        pass

    dom = _D()
    dom.fd = fd
    vx = [v[0] for v in verts]
    vy = [v[1] for v in verts]
    dom.bbox = (min(vx), min(vy), max(vx), max(vy))

    oracle = lambda x, y: max(hmin, min(hmax, 0.6 * abs(fd(np.array([[x, y]]))[0])))  # noqa: E731
    grid = build_octree(dom, h_min=hmin, h_max=hmax, size_oracle=oracle, balance=True)
    h, medial = size_field_octree(grid, R=R_elem, hmin=hmin, hmax=hmax)

    leaves = grid.leaves
    cx = np.array([lf.center[0] for lf in leaves])
    cy = np.array([lf.center[1] for lf in leaves])
    D = np.array([lf.D for lf in leaves])
    interior = D < 0
    u = cx - k * cy
    notch_medial = int(np.sum(medial & interior & (np.abs(u) < notch_w) & (cy > hY - notch_len)))
    xmin, ymin, xmax, ymax = grid.bbox
    area = (xmax - xmin) * (ymax - ymin)
    n_uni = area / (notch_w / 4.0) ** 2

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(14, 6))

    rects = [Rectangle((lf.center[0] - lf.size / 2, lf.center[1] - lf.size / 2), lf.size, lf.size) for lf in leaves]
    pc = PatchCollection(rects, cmap="viridis", edgecolor="white", linewidth=0.15)
    pc.set_array(h)
    axA.add_collection(pc)
    axA.add_patch(Polygon(verts, fill=False, ec="k", lw=1.5))
    fig.colorbar(pc, ax=axA, label="size-field target edge length  h = LFS / R")
    axA.set_title(f"A. Octree size field — fine in notch, coarse in basin\n{len(leaves)} leaves", fontsize=10)

    axB.scatter(cx[interior], cy[interior], s=4, c="0.8", label="octree leaves (interior)")
    axB.scatter(cx[medial & interior], cy[medial & interior], s=16, c="red",
                label=f"medial-axis leaves ({int((medial & interior).sum())})")
    axB.add_patch(Polygon(verts, fill=False, ec="k", lw=1.5))
    delta_uni = 4.0
    for gx in np.arange(xmin, xmax + delta_uni, delta_uni):
        axB.axvline(gx, color="0.6", lw=0.4, ls=":")
    for gy in np.arange(ymin, ymax + delta_uni, delta_uni):
        axB.axhline(gy, color="0.6", lw=0.4, ls=":")
    axB.set_title(
        f"B. Medial axis threads the notch ({notch_medial} medial leaves in notch)\n"
        f"uniform Δ={delta_uni:.0f} (basin-tractable) > notch width {notch_w:.0f} → notch unresolved",
        fontsize=10,
    )
    axB.legend(loc="lower left", fontsize=7)

    for ax in (axA, axB):
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.set_aspect("equal")

    fig.suptitle(
        f"Spec 021 octree proof — parallelogram + notch width {notch_w:.0f}  |  "
        f"octree {len(leaves)} leaves vs uniform-to-resolve-notch ~{n_uni:.0f} cells",
        fontsize=12,
    )
    out = OUTDIR / "octree_proof.png"
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"wrote {out}")
    print(f"leaves={len(leaves)} medial={int((medial & interior).sum())} notch_medial={notch_medial} n_uniform_resolve={n_uni:.0f}")


if __name__ == "__main__":
    main()
