"""Render the notched-rectangle quickstart figure for README.

Produces ``papers/quickstart_notched.png`` — a clean triangulation of the
``notched_rectangle`` MVP domain meshed at h=0.04 with the default
size-field stack. Embedded inline from the Quickstart section of the
README per issue #68.

Run:
    python scripts/render_quickstart_notched.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from admesh import domains
from admesh.quality import mesh_quality
from admesh.routine import triangulate

matplotlib.use("Agg")

OUT = Path(__file__).resolve().parent.parent / "papers" / "quickstart_notched.png"


def main() -> None:
    np.random.seed(0)
    dom = domains.ALL["notched_rectangle"]
    p, t = triangulate(dom, h0=0.04, niter=200, seed=0)
    min_q, mean_q, _ = mesh_quality(p, t)

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.triplot(p[:, 0], p[:, 1], t, lw=0.5, color="#1f77b4")
    xmin, ymin, xmax, ymax = dom.bbox
    pad = 0.04 * max(xmax - xmin, ymax - ymin)
    ax.set_xlim(xmin - pad, xmax + pad)
    ax.set_ylim(ymin - pad, ymax + pad)
    ax.set_aspect("equal")
    ax.set_title(
        f"notched_rectangle  |  N={len(p)}  T={len(t)}  "
        f"min_q={min_q:.3f}  mean_q={mean_q:.3f}",
        fontsize=10,
    )
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {OUT} (N={len(p)} T={len(t)} min_q={min_q:.3f} mean_q={mean_q:.3f})")


if __name__ == "__main__":
    main()
