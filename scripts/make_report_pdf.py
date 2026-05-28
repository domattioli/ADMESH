"""Generate a <=2-page PDF report for spec 021 octree work -> output/spec021_report.pdf."""

from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "output"
IMG = OUT / "octree_meshcompare.png"

PAGE1 = """ADMESH Spec 021 — Octree Background Grid for Multi-Scale Size-Function
& Medial-Axis Robustness.  Implementation report.  Branch 021-octree-size-field, PR #113.

WHAT I DID
- Ran the full Spec Kit pipeline on the feature "compute the size function on an octree
  grid instead of a cartesian grid": /specify -> /clarify -> /plan -> /tasks -> /analyze,
  each committed to PR #113. Output: spec (4 user stories, 18 functional requirements,
  8 success criteria), 4 recorded clarifications, an implementation plan, 32 ordered tasks,
  and a cross-artifact analysis.
- Key governance call: the change touches three LOCKED faithful-port stage modules
  (background_grid, medial_axis, mesh_size), which violates Constitution Principle I
  (numerical identity with MATLAB). You authorized unlocking them; the plan scopes a
  Principle I exception to be ratified by a v2.0.0 Constitution amendment. Uniform grid is
  kept as the fallback path.
- Implementation (branch): an octree/quadtree core (construction, 2:1 balance, point
  location, interpolation, leaf-adjacency graph) landed first. Then the medial axis was
  moved onto the leaf graph: medial leaves are detected where the distance-field gradient
  converges (|grad D| -> 0 between opposing walls), medial-axis distance is a Dijkstra
  shortest path over the variable-spacing graph, and the size field is
  h = clip((|D| + MAD)/R, hmin, hmax). A graph gradient-limiter smooths size jumps.
- Validation domain: a parallelogram with a thin notch — a narrow feature dwarfed by the
  domain (the exact regime where the medial axis fails today). Figure below: admesh node
  resolution at the notch WITHOUT vs WITH the octree size field (zoom)."""

PAGE2 = """SUCCESS / FAILURE ASSESSMENT  —  PARTIAL SUCCESS.

What works (evidence):
- The octree resolves the medial axis inside the narrow notch where a tractable uniform
  grid cannot. The original local-maximum-of-|D| medial test failed on elongated features
  (|D| grows along a channel, so channel cells are not local maxima) — it found 1 medial
  cell in the notch. Replacing it with a gradient-convergence (AOF-style) detector fixed
  this.
- The size field is correct: fine in the notch, coarse in the basin. In the with/without
  comparison, nodes spanning the notch went from 1 (uniform) to 40 (octree). This is the
  core spec claim (SC-001): a feature dwarfed by the domain is resolved.

What does NOT yet work / is incomplete:
- The octree size field does not yet flow through admesh's distmesh: distmesh collapsed on
  the raw graded field (large unsmoothed size ratios). The proof therefore places nodes
  from the size field and triangulates by Delaunay (interior triangles only). This isolates
  the size-field effect but is NOT the full mesher (tasks T015/T016).
- The medial code lives in a new module (octree_medial.py), not folded into the locked
  medial_axis.py as the plan requires.
- Performance: octree adjacency, point-location, and balancing are O(N^2). ~2,700 leaves is
  fine, but an early fine-inlet run timed out — this will not reach the 10^3-10^4
  feature-size ratios the spec targets without O(N log N) structures.
- US2 (>=4 elements verified on a real distmesh output), US3 (tractability + fallback
  tests), and US4 (the v2.0.0 amendment) are not implemented.
- The new medial detector is a proof of concept; it has not been validated against MATLAB
  or the existing faithful-port tests.

Why I judge it a partial success: the hardest, most uncertain part — making the medial axis
resolve a dwarfed feature — is demonstrably solved at the size-field level, which is the
quantity spec 021 actually changes. The remainder (distmesh wiring, scaling, governance) is
known, bounded engineering rather than open research.

FURTHER TESTS I WANT TO RUN
1. Wire the field through distmesh using its gradient-limited solver on the leaf graph, then
   assert >=4 element edges across the notch in the ACTUAL mesh (SC-002), not a Delaunay proxy.
2. Agreement test: octree LFS vs the uniform result on a domain the uniform grid already
   resolves (unit disk, annulus) to atol=1e-8/rtol=1e-6 (FR-007).
3. Scaling: leaf count and wall-clock vs feature-size ratio 10/100/1000 — after replacing the
   O(N^2) primitives — to confirm sub-quadratic growth and >=10x fewer cells than uniform (SC-004).
4. Large-domain memory completion (SC-005) and degenerate no-multiscale overhead (SC-008).
5. A real multi-scale ADCIRC mesh on the test ladder (SC-007).
6. Numba parity (atol=1e-10) for the leaf-graph gradient limiter (Principle II).
7. Faithful-port regression: confirm every non-octree stage stays numerically identical and
   the suite passes (SC-006), before the v2.0.0 amendment lands."""


def render_text(ax, text, width):
    wrapped = "\n".join(textwrap.fill(line, width=width) if line.strip() else "" for line in text.split("\n"))
    ax.axis("off")
    ax.text(0.0, 1.0, wrapped, va="top", ha="left", family="monospace", fontsize=8.0, linespacing=1.35)


def main():
    with PdfPages(OUT / "spec021_report.pdf") as pdf:
        # Page 1: text (top) + figure (bottom)
        fig = plt.figure(figsize=(8.5, 11))
        ax_txt = fig.add_axes([0.06, 0.55, 0.9, 0.42])
        render_text(ax_txt, PAGE1, width=92)
        if IMG.exists():
            ax_img = fig.add_axes([0.06, 0.05, 0.9, 0.46])
            ax_img.imshow(plt.imread(str(IMG)))
            ax_img.axis("off")
        pdf.savefig(fig)
        plt.close(fig)

        # Page 2: text
        fig = plt.figure(figsize=(8.5, 11))
        ax_txt = fig.add_axes([0.06, 0.03, 0.9, 0.94])
        render_text(ax_txt, PAGE2, width=92)
        pdf.savefig(fig)
        plt.close(fig)
    print(f"wrote {OUT / 'spec021_report.pdf'}")


if __name__ == "__main__":
    main()
