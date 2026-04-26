"""Render the WNAT before/after for the issue #11 fix.

Issue #11: ``Domain.from_mesh`` previously sorted boundary rings by node
count, so on real-world coastal fixtures (Western North Atlantic) where
the longest-by-node-count ring is an interior coastline rather than the
open Atlantic, the recovered domain shrank to a sub-region.

This script visualises:
  - the source WNAT mesh (light grey),
  - every boundary ring recovered by ``_derive_boundary_segments``
    coloured by descending area,
  - the recovered ``Domain.from_mesh(...)`` bbox after the fix.

Output: ``tests/output/wnat_from_mesh_fix.png``.
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

import admesh
from admesh.api import _derive_boundary_segments


def main() -> None:
    src_path = (
        ROOT / "tests" / "fixtures" / "fort14" / "adcirc_examples" / "wnat_test.14"
    )
    src = admesh.read_fort14(str(src_path))
    rings_segs = _derive_boundary_segments(src.elements, src.nodes)

    def _ring_area(seg) -> float:
        pts = src.nodes[seg.node_ids]
        x, y = pts[:, 0], pts[:, 1]
        return 0.5 * abs(
            np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))
        )

    ring_areas = [(_ring_area(s), s) for s in rings_segs]
    ring_areas.sort(reverse=True, key=lambda t: t[0])

    dom = admesh.Domain.from_mesh(src)
    src_min = src.nodes.min(0)
    src_max = src.nodes.max(0)

    fig, axes = plt.subplots(1, 2, figsize=(14, 7))

    # Left: full mesh + outer ring + bbox.
    ax = axes[0]
    ax.triplot(
        src.nodes[:, 0],
        src.nodes[:, 1],
        src.elements,
        color="0.85",
        linewidth=0.2,
    )
    outer_seg = ring_areas[0][1]
    outer_xy = src.nodes[outer_seg.node_ids]
    outer_loop = np.vstack([outer_xy, outer_xy[:1]])
    ax.plot(outer_loop[:, 0], outer_loop[:, 1], "-", color="C3", linewidth=1.2,
            label=f"outer ring (n={len(outer_seg.node_ids)}, area={ring_areas[0][0]:.0f})")
    src_rect = plt.Rectangle(
        (src_min[0], src_min[1]),
        src_max[0] - src_min[0], src_max[1] - src_min[1],
        fill=False, edgecolor="C0", linewidth=1.5, linestyle="--",
        label="source mesh bbox",
    )
    rec_rect = plt.Rectangle(
        (dom.bbox[0], dom.bbox[1]),
        dom.bbox[2] - dom.bbox[0], dom.bbox[3] - dom.bbox[1],
        fill=False, edgecolor="C2", linewidth=1.0,
        label="Domain.from_mesh bbox",
    )
    ax.add_patch(src_rect)
    ax.add_patch(rec_rect)
    ax.set_aspect("equal")
    ax.set_title("WNAT — outer ring + bbox (issue #11 fix)")
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.legend(loc="lower right", fontsize=8)

    # Right: every recovered ring, colored by area rank.
    ax = axes[1]
    ax.triplot(
        src.nodes[:, 0],
        src.nodes[:, 1],
        src.elements,
        color="0.92",
        linewidth=0.15,
    )
    cmap = plt.get_cmap("viridis")
    n_show = min(len(ring_areas), 20)
    for rank, (area, seg) in enumerate(ring_areas[:n_show]):
        xy = src.nodes[seg.node_ids]
        loop = np.vstack([xy, xy[:1]])
        c = cmap(rank / max(n_show - 1, 1))
        ax.plot(loop[:, 0], loop[:, 1], "-", color=c, linewidth=0.9)
    ax.set_aspect("equal")
    ax.set_title(
        f"All recovered rings ({len(rings_segs)} total)\n"
        "Top-20 shown; ring 0 (yellow) is the open Atlantic + Gulf coast"
    )
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")

    fig.suptitle(
        "issue #11 — Domain.from_mesh now sorts rings by signed area + walks "
        "junction nodes correctly\n"
        f"source bbox = [{src_min[0]:.2f}, {src_min[1]:.2f}, "
        f"{src_max[0]:.2f}, {src_max[1]:.2f}]; "
        f"recovered bbox = [{dom.bbox[0]:.2f}, {dom.bbox[1]:.2f}, "
        f"{dom.bbox[2]:.2f}, {dom.bbox[3]:.2f}]",
        fontsize=10,
    )
    fig.tight_layout()

    out = ROOT / "tests" / "output" / "wnat_from_mesh_fix.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
