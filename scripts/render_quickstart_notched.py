"""Render the notched-rectangle quickstart figure for README.

Produces ``docs/papers/quickstart_notched.png`` — a triangulation of the
``notched_rectangle`` MVP domain with a *graded* size field so the
figure shows ADMESH actually doing its job: curvature sizing refines the
elements around the sharp notch and corners, coarsening into the open
interior. Embedded inline from the Quickstart section of the README per
issue #68.

Run:
    python scripts/render_quickstart_notched.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from chilmesh import CHILmesh

from admesh import domains
from admesh._stages import mesh_size as mesh_size_stage
from admesh.quality import mesh_quality
from admesh.routine import triangulate

matplotlib.use("Agg")

OUT = Path(__file__).resolve().parent.parent / "docs" / "papers" / "quickstart_notched.png"

HMIN, HMAX = 0.025, 0.25


def main() -> None:
    np.random.seed(0)
    dom = domains.ALL["notched_rectangle"]

    class _D:  # build_h wants .fd / .bbox
        fd = staticmethod(dom.fd)
        bbox = dom.bbox

    # Graded size field: curvature refines the sharp notch + corners,
    # medial-axis sizing refines along the centreline, and a 10x hmin->hmax
    # range (g=0.2 gradient limit) coarsens the open interior. This shows the
    # ADMESH size function actually grading, not a uniform fill.
    fh = mesh_size_stage.build_h(
        _D, base=HMAX, hmin=HMIN, hmax=HMAX,
        g=0.2, curvature_scale=0.04, medial_scale=0.08,
    )
    p, t = triangulate(dom, h0=HMIN, fh=fh, niter=500, seed=0)
    min_q, mean_q, _ = mesh_quality(p, t)

    # Render the element-quality colormap via CHILmesh so the figure shows
    # both the graded sizing and the resulting element quality.
    pts = np.column_stack([p[:, 0], p[:, 1], np.zeros(len(p))])
    cm = CHILmesh(connectivity=t, points=pts, compute_layers=False,
                  compute_adjacencies=True)
    fig, ax = plt.subplots(figsize=(6.5, 3.4), constrained_layout=True)
    cm.plot_quality(ax=ax, cmap="viridis")
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {OUT} (N={len(p)} T={len(t)} min_q={min_q:.3f} mean_q={mean_q:.3f})")


if __name__ == "__main__":
    main()
