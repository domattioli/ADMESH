"""With/without octree comparison for spec 021 — zoom on the problem feature.

Demonstrates the effect of the octree size field on mesh resolution at a narrow
notch dwarfed by a parallelogram domain:

  - WITHOUT octree: nodes from a uniform grid (the tractable pre-021 density).
    The notch is narrower than the spacing, so interior triangulation bridges
    /leaves it under-resolved.
  - WITH octree: nodes graded by the octree/medial size field — dense in the
    notch, coarse in the basin — so the notch is resolved with fine elements.

Both node sets are triangulated (Delaunay) and clipped to interior triangles,
then zoomed to the notch. (This isolates the size-field/node-density effect that
spec 021 changes; wiring the octree field through distmesh is task T015/T016.)

Run:  python scripts/render_octree_meshcompare.py -> output/octree_meshcompare.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Polygon  # noqa: E402
from matplotlib.path import Path as MplPath  # noqa: E402
from scipy.spatial import Delaunay  # noqa: E402

from admesh._stages.octree_grid import build_octree  # noqa: E402

OUTDIR = Path(__file__).resolve().parent.parent / "output"
OUTDIR.mkdir(parents=True, exist_ok=True)

hX, hY, k = 12.0, 8.0, 0.6
notch_w, notch_len = 2.0, 7.0
hmin, hmax = 0.6, 5.0


def corners(nw=notch_w, nl=notch_len):
    def w(u, y):
        return (u + k * y, y)
    yb = hY - nl
    return [w(-hX, -hY), w(hX, -hY), w(hX, hY), w(nw / 2, hY),
            w(nw / 2, yb), w(-nw / 2, yb), w(-nw / 2, hY), w(-hX, hY)]


def make_sdf(verts):
    V = np.asarray(verts)
    A, B = V, np.roll(V, -1, axis=0)
    path = MplPath(V)

    def fd(p):
        p = np.asarray(p, dtype=np.float64).reshape(-1, 2)
        best = np.full(len(p), np.inf)
        for a, b in zip(A, B):
            ab = b - a
            d = ab @ ab
            t = np.zeros(len(p)) if d == 0 else np.clip((p - a) @ ab / d, 0, 1)
            pr = a + t[:, None] * ab
            best = np.minimum(best, np.hypot(p[:, 0] - pr[:, 0], p[:, 1] - pr[:, 1]))
        return np.where(path.contains_points(p), -best, best)
    return fd


def interior_mesh(pts, fd):
    """Delaunay-triangulate pts, keep triangles whose centroid is inside (fd<0)."""
    tri = Delaunay(pts)
    cent = pts[tri.simplices].mean(axis=1)
    keep = fd(cent) < 0.0
    return tri.simplices[keep]


def octree_nodes(fd, bbox):
    class _Shim:
        pass
    s = _Shim()
    s.fd = staticmethod(fd)
    s.bbox = bbox
    oracle = lambda x, y: max(hmin, min(hmax, 0.6 * abs(fd(np.array([[x, y]]))[0])))  # noqa: E731
    g = build_octree(s, h_min=hmin, h_max=hmax, size_oracle=oracle, balance=True)
    c = np.array([lf.center for lf in g.leaves])
    D = np.array([lf.D for lf in g.leaves])
    return c[D < 0.0], len(g.leaves)


def uniform_nodes(fd, bbox, delta):
    xmin, ymin, xmax, ymax = bbox
    xs = np.arange(xmin, xmax + delta, delta)
    ys = np.arange(ymin, ymax + delta, delta)
    X, Y = np.meshgrid(xs, ys)
    p = np.c_[X.ravel(), Y.ravel()]
    return p[fd(p) < 0.0]


def nodes_in_notch(p):
    u = p[:, 0] - k * p[:, 1]
    return int(np.sum((np.abs(u) < notch_w / 2 + 0.3) & (p[:, 1] > hY - notch_len) & (p[:, 1] < hY)))


def main():
    verts = corners()
    fd = make_sdf(verts)
    bbox = (min(v[0] for v in verts), min(v[1] for v in verts),
            max(v[0] for v in verts), max(v[1] for v in verts))

    p_w, n_leaves = octree_nodes(fd, bbox)
    p_wo = uniform_nodes(fd, bbox, delta=3.0)
    t_w = interior_mesh(p_w, fd)
    t_wo = interior_mesh(p_wo, fd)

    fig, axes = plt.subplots(1, 2, figsize=(13, 6.5))
    for ax, p, t, label in [
        (axes[0], p_wo, t_wo, "WITHOUT octree (uniform Δ=3 nodes)"),
        (axes[1], p_w, t_w, "WITH octree size-field nodes"),
    ]:
        ax.triplot(p[:, 0], p[:, 1], t, lw=0.6, color="#1f77b4")
        ax.plot(p[:, 0], p[:, 1], ".", ms=3, color="#d62728")
        ax.add_patch(Polygon(verts, fill=False, ec="k", lw=1.6))
        ax.set_xlim(-3, 9)
        ax.set_ylim(0.5, 9)
        ax.set_aspect("equal")
        ax.set_title(f"{label}\nnodes in notch = {nodes_in_notch(p)}", fontsize=11)

    fig.suptitle("Spec 021 — admesh notch resolution with vs without octree size field (zoom)", fontsize=12)
    out = OUTDIR / "octree_meshcompare.png"
    fig.tight_layout()
    fig.savefig(out, dpi=135)
    plt.close(fig)
    print(f"wrote {out}  (octree leaves={n_leaves})")
    print(f"without: nodes={len(p_wo)} notch={nodes_in_notch(p_wo)} tris={len(t_wo)}")
    print(f"with:    nodes={len(p_w)} notch={nodes_in_notch(p_w)} tris={len(t_w)}")


if __name__ == "__main__":
    main()
