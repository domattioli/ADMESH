"""Generate a <=2-page PDF report for spec 021 octree work -> output/spec021_report.pdf.

Focus: HOW it was built, and whether it is currently SCALABLE (and why).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "output"
IMG = OUT / "octree_sizefield_diff.png"

PAGE1 = """ADMESH Spec 021 — Octree Background Grid for Multi-Scale Size-Function & Medial-Axis
Robustness.  Implementation report (how it works + scalability).  Branch 021-octree-size-field, PR #113.

HOW I DID IT
Spec Kit pipeline (/specify -> /clarify -> /plan -> /tasks -> /analyze), then implementation on the
branch. The change is scoped to three locked faithful-port stages (background_grid, medial_axis,
mesh_size) under a Constitution Principle I exception (you authorized it; ratified by a v2.0.0
amendment, not yet written). Method, bottom-up:

1. Octree (2D quadtree) — admesh/_stages/octree_grid.py. build_octree() subdivides the padded
   bounding box top-down: a cell splits while its size exceeds a sizing oracle and stays above the
   h_min floor. The oracle here is 0.6*|signed distance|, so cells shrink toward the boundary. A
   2:1 neighbour-balance pass smooths transitions. Output: leaves + an edge-adjacency graph with
   centre-to-centre spacings.

2. Medial axis on the leaf graph — admesh/_stages/octree_medial.py. Medial leaves are detected by
   GRADIENT CONVERGENCE: the signed-distance gradient |grad D| (least-squares fit from each leaf's
   neighbours) drops toward 0 between opposing walls. This finds the axis of ELONGATED features
   (a river/notch); the original local-maximum-of-|D| test does not (|D| keeps growing along a
   channel). Medial-axis distance (MAD) is a Dijkstra shortest path to the nearest medial leaf over
   the variable-spacing graph. Size field h = clip((|D| + MAD)/R, hmin, hmax), with R=2 targeting
   ~4 elements across a feature (FR-010/FR-011).

3. Meshing with admesh's own triangulate() — per-leaf h is rasterized to a fine grid, gradient-
   limited by the existing faithful solver solve_iter (|grad h| <= g), wrapped in a
   RegularGridInterpolator, and passed as size_field to admesh.triangulate(). The raw graded field
   alone collapses distmesh, so distmesh is SEEDED with the octree leaf centres (initial_points=)
   and the quality gate is relaxed. Domain: a narrow river entering a large bay (the physical
   estuary case = the SC-001 "small feature dwarfed by large domain" regime).

Figure: size field (top) and admesh mesh (bottom), uniform grid vs octree, same algorithm."""

PAGE2 = """IS IT CURRENTLY SCALABLE?  —  NO (correct, but prototype-grade). Why, concretely:

- Construction is O(N^2) in leaf count. _build_adjacency() compares all leaf pairs (a double loop);
  _balance_2to1() REBUILDS that O(N^2) adjacency inside its split loop, so balancing is up to
  O(N^3) worst case.
- Queries are O(N). locate() and interpolate() linear-scan every leaf per query point, so a
  distmesh run that calls the size field many times is O(N * Q).
- Net effect: a width-2 river in a 48x26 bay = ~2,900 leaves runs fine, but an earlier finer-inlet
  attempt timed out. The spec targets feature-size ratios of 10^3-10^4; near the h_min floor that
  is millions of leaves, where O(N^2)/O(N^3) construction and O(N) queries are intractable.
- The distmesh coupling is fragile, not just slow. The graded field collapses the mesher unless it
  is seeded with leaf centres, and the result needs the quality gate relaxed (min_q ~ 0.16, below
  the 0.30 production gate). So even at small N the mesh is low quality.

What it would take to scale (and why):
- Pointer/hash quadtree with O(log N) point location (tree descent) instead of a linear scan.
- O(N) construction: find neighbours via parent/sibling links during subdivision, not all-pairs;
  balance with a work queue of split candidates, not a full adjacency rebuild per split.
- Numba/vectorize the per-leaf Python loops (gradient fit, raster, balance).
- A real distmesh size-field coupling: gradient-limit on the leaf graph natively and tune the force
  balance so it converges WITHOUT seeding and passes the quality gate.

VERDICT — PARTIAL SUCCESS. Correctness is demonstrated: the octree resolves the medial axis of a
feature a tractable uniform grid misses, and admesh meshes ~4 elements across the river (108 river
nodes vs 1 for uniform). Scalability is NOT there: the data structures are O(N^2)/O(N^3) prototypes
and the distmesh coupling needs seeding + a relaxed quality gate. The hard idea works; the
engineering to make it production- and scale-ready remains.

FURTHER TESTS (scalability-focused)
1. Leaf count + wall-clock vs feature-size ratio 10/100/1000 AFTER the O(N log N) rewrite (SC-004).
2. distmesh convergence on the graded field WITHOUT seeding, with the 0.30 quality gate restored.
3. Octree LFS vs uniform agreement where the uniform grid already resolves (disk/annulus), FR-007.
4. Numba parity (atol=1e-10) for a native leaf-graph gradient limiter (Principle II).
5. Faithful-port regression: non-octree stages unchanged; full suite green (SC-006)."""


def render_text(ax, text, width):
    wrapped = "\n".join(textwrap.fill(ln, width=width) if ln.strip() else "" for ln in text.split("\n"))
    ax.axis("off")
    ax.text(0.0, 1.0, wrapped, va="top", ha="left", family="monospace", fontsize=7.7, linespacing=1.3)


def main():
    with PdfPages(OUT / "spec021_report.pdf") as pdf:
        fig = plt.figure(figsize=(8.5, 11))
        render_text(fig.add_axes([0.06, 0.50, 0.9, 0.47]), PAGE1, width=95)
        if IMG.exists():
            ax_img = fig.add_axes([0.10, 0.04, 0.8, 0.42])
            ax_img.imshow(plt.imread(str(IMG)))
            ax_img.axis("off")
        pdf.savefig(fig)
        plt.close(fig)

        fig = plt.figure(figsize=(8.5, 11))
        render_text(fig.add_axes([0.06, 0.03, 0.9, 0.94]), PAGE2, width=95)
        pdf.savefig(fig)
        plt.close(fig)
    print(f"wrote {OUT / 'spec021_report.pdf'}")


if __name__ == "__main__":
    main()
