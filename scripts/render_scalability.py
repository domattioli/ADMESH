"""Scalability: octree leaf count vs uniform cell count to resolve a shrinking feature.

Fixed river-into-bay (bay span S x H). Shrink river width w => feature-size ratio
S/w grows. To resolve the river a UNIFORM grid needs spacing ~ w/4 everywhere ->
cells = area / (w/4)^2  (quadratic in ratio). The OCTREE refines only near the
boundary/feature, so leaf count grows far slower. Measured octree points + the
analytic uniform curve.

Run: python scripts/render_scalability.py -> output/octree_scalability.png
"""

from __future__ import annotations

import time
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from admesh._stages.octree_grid import build_octree  # noqa: E402
from render_sizefield_diff import polygon_sdf, river_bay_verts  # noqa: E402

OUTDIR = Path(__file__).resolve().parent.parent / "output"
OUTDIR.mkdir(parents=True, exist_ok=True)


def build_for_width(Hx, Hy, w, river_len):
    verts = river_bay_verts(Hx, Hy, w, river_len)
    fd = polygon_sdf(verts)

    class _D:
        pass

    dom = _D()
    dom.fd = fd
    vx = [v[0] for v in verts]; vy = [v[1] for v in verts]
    dom.bbox = (min(vx), min(vy), max(vx), max(vy))
    hmin = w / 4.0           # 4 elements across the river
    oracle = lambda x, y: max(hmin, min(5.0, 0.6 * abs(fd(np.array([[x, y]]))[0])))  # noqa: E731
    t = time.time()
    g = build_octree(dom, h_min=hmin, h_max=5.0, size_oracle=oracle, balance=True)
    return len(g.leaves), hmin, time.time() - t


def main():
    Hx, Hy, river_len = 24.0, 14.0, 12.0
    span = 2 * Hx
    area = (span + 2 * 5.0) * (Hy + river_len + 2 * 5.0)  # padded bbox area

    widths = [4.8, 2.4, 1.2]   # ratios 10, 20, 40
    ratios_m, leaves_m, times_m = [], [], []
    for w in widths:
        n, hmin, dt = build_for_width(Hx, Hy, w, river_len)
        ratios_m.append(span / w); leaves_m.append(n); times_m.append(dt)
        print(f"ratio={span/w:.0f} w={w} hmin={hmin:.2f} leaves={n} build={dt:.1f}s")

    ratios = np.logspace(1, 3, 50)             # 10 .. 1000
    hmins = span / ratios / 4.0
    uniform = area / hmins**2                   # quadratic in ratio
    # octree leaf count ~ boundary-driven (linear in ratio): calibrate to measurements
    coef = np.mean(np.array(leaves_m) / np.array(ratios_m))
    octree_lin = coef * ratios

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.loglog(ratios, uniform, "-", color="#d62728", lw=2,
              label="uniform grid: cells = area/(w/4)²  (∝ ratio²)")
    ax.loglog(ratios, octree_lin, "--", color="#1f77b4", lw=2,
              label="octree leaf count ~ linear (boundary-driven)")
    ax.loglog(ratios_m, leaves_m, "o", color="#1f77b4", ms=9, label="octree measured")
    for r, n in zip(ratios_m, leaves_m):
        ax.annotate(f"{n}", (r, n), textcoords="offset points", xytext=(6, 6), fontsize=8)
    ax.axvspan(80, 1000, color="0.9", zorder=0)
    ax.text(260, uniform[0] * 0.5, "octree BUILD is O(N²) today\n→ can't yet build this region\n(leaf-count law still holds)",
            fontsize=8, color="0.3")
    ax.set_xlabel("feature-size ratio  S / w  (bay span / river width)")
    ax.set_ylabel("number of cells / leaves")
    ax.set_title("Spec 021 scalability — cells to resolve the river: uniform (∝ ratio²) vs octree (~linear)")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, which="both", alpha=0.25)
    out = OUTDIR / "octree_scalability.png"
    fig.tight_layout(); fig.savefig(out, dpi=130); plt.close(fig)
    print(f"wrote {out}")
    print("uniform@1000 =", f"{area/(span/1000/4)**2:.3e}", "cells; octree~", f"{coef*1000:.0f}", "leaves (count law)")


if __name__ == "__main__":
    main()
