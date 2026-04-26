"""Zoom in on the WNAT source mesh near Bermuda to see what's there.

Diagnostic for the user's observation that "the source definitely has
[Bermuda]". We've already confirmed via element topology + fort.14 BC
section that there's no hole or land boundary segment for Bermuda; this
script shows what the actual source mesh looks like at that location.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import admesh  # noqa: E402
from admesh.api import _derive_boundary_segments  # noqa: E402


def main() -> None:
    src = admesh.read_fort14(
        str(ROOT / "tests" / "fixtures" / "fort14" / "adcirc_examples" / "wnat_test.14")
    )

    # Bermuda is around (-64.78, 32.30).
    cx, cy = -64.78, 32.30

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # Wide view: all of WNAT, mark Bermuda's position.
    ax = axes[0]
    ax.triplot(
        src.nodes[:, 0], src.nodes[:, 1], src.elements,
        color="0.7", linewidth=0.2,
    )
    # Outer ring (largest-area, post-#11 fix).
    segs = _derive_boundary_segments(src.elements, src.nodes)
    if segs:
        outer = src.nodes[segs[0].node_ids]
        loop = np.vstack([outer, outer[:1]])
        ax.plot(loop[:, 0], loop[:, 1], "-", color="C3", linewidth=1.0,
                label="recovered outer ring")
    ax.plot(cx, cy, "*", color="gold", markersize=20, markeredgecolor="black",
            label="Bermuda's actual location")
    ax.set_aspect("equal")
    ax.set_title("WNAT source mesh — full extent")
    ax.legend(loc="lower right", fontsize=8)
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")

    # Mid zoom: 5° around Bermuda.
    ax = axes[1]
    pad = 5.0
    ax.triplot(
        src.nodes[:, 0], src.nodes[:, 1], src.elements,
        color="0.5", linewidth=0.5,
    )
    if segs:
        loop = np.vstack([outer, outer[:1]])
        ax.plot(loop[:, 0], loop[:, 1], "-", color="C3", linewidth=1.5)
    ax.plot(cx, cy, "*", color="gold", markersize=20, markeredgecolor="black")
    ax.set_xlim(cx - pad, cx + pad)
    ax.set_ylim(cy - pad, cy + pad)
    ax.set_aspect("equal")
    ax.set_title(f"Zoomed ±{pad:.0f}° around Bermuda")
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")

    # Tight zoom: 1° around Bermuda.
    ax = axes[2]
    pad = 1.0
    ax.triplot(
        src.nodes[:, 0], src.nodes[:, 1], src.elements,
        color="0.3", linewidth=0.7,
    )
    # Highlight nearest source nodes.
    target = np.array([cx, cy])
    d = np.linalg.norm(src.nodes - target, axis=1)
    near = np.argsort(d)[:10]
    ax.scatter(src.nodes[near, 0], src.nodes[near, 1],
               c="C0", s=30, zorder=5, label="10 nearest source nodes")
    ax.plot(cx, cy, "*", color="gold", markersize=20, markeredgecolor="black",
            label="Bermuda's actual location", zorder=6)
    ax.set_xlim(cx - pad, cx + pad)
    ax.set_ylim(cy - pad, cy + pad)
    ax.set_aspect("equal")
    ax.set_title(f"Zoomed ±{pad:.0f}° (closest source-mesh detail)")
    ax.legend(loc="lower right", fontsize=8)
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")

    fig.suptitle(
        "WNAT source-mesh inspection at Bermuda — the source has zero "
        "declared BC segments\n"
        "and Bermuda is not a topological hole. Fine-triangulation patches "
        "are bathymetry-driven mesh density, not boundaries.",
        fontsize=10,
    )
    fig.tight_layout()
    out = ROOT / "tests" / "output" / "wnat_bermuda_inspect.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
