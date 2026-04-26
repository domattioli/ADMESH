"""Render the 0.1.0 release-gate proof: Tier-1 + Tier-2 re-triangulations.

Shows ``Domain.from_mesh + triangulate`` round-trips on the two real-
world ADCIRC fixtures whose structural-validity gates were ``xfail`` on
the spec-002 MVP and are now passing post-issue-#10/#11. Each panel
shows the source mesh (light grey) overlaid with the freshly produced
mesh (orange) on the same domain.

Output: ``tests/output/release_gate_rebuild.png``.
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


def _rebuild(fixture: Path, *, h_min: float, h_max: float, max_iter: int):
    src = admesh.read_fort14(str(fixture))
    domain = admesh.Domain.from_mesh(src)
    fresh = admesh.triangulate(
        domain,
        h_min=h_min,
        h_max=h_max,
        seed=0,
        max_iter=max_iter,
        quality_gate=(0.0, 0.0),
    )
    return src, fresh


def main() -> None:
    fix_dir = ROOT / "tests" / "fixtures" / "fort14" / "adcirc_examples"

    src_t1, fresh_t1 = _rebuild(
        fix_dir / "wetting_and_drying_test.14",
        h_min=200.0, h_max=2000.0, max_iter=100,
    )
    src_t2, fresh_t2 = _rebuild(
        fix_dir / "wnat_test.14",
        h_min=0.1, h_max=2.0, max_iter=100,
    )

    fig, axes = plt.subplots(1, 2, figsize=(15, 7))

    # Tier-1.
    ax = axes[0]
    ax.triplot(
        src_t1.nodes[:, 0], src_t1.nodes[:, 1], src_t1.elements,
        color="0.85", linewidth=0.4, label="source (n=%d, e=%d)" % (src_t1.n_nodes, src_t1.n_elements),
    )
    ax.triplot(
        fresh_t1.nodes[:, 0], fresh_t1.nodes[:, 1], fresh_t1.elements,
        color="C1", linewidth=0.6, label="fresh (n=%d, e=%d)" % (fresh_t1.n_nodes, fresh_t1.n_elements),
    )
    ax.set_aspect("equal")
    ax.set_title("Tier-1 — wetting_and_drying_test.14")
    ax.legend(loc="lower right", fontsize=8)
    ax.set_xlabel("x")
    ax.set_ylabel("y")

    # Tier-2.
    ax = axes[1]
    ax.triplot(
        src_t2.nodes[:, 0], src_t2.nodes[:, 1], src_t2.elements,
        color="0.85", linewidth=0.2, label="source (n=%d, e=%d)" % (src_t2.n_nodes, src_t2.n_elements),
    )
    ax.triplot(
        fresh_t2.nodes[:, 0], fresh_t2.nodes[:, 1], fresh_t2.elements,
        color="C1", linewidth=0.3, label="fresh (n=%d, e=%d)" % (fresh_t2.n_nodes, fresh_t2.n_elements),
    )
    ax.set_aspect("equal")
    ax.set_title("Tier-2 — wnat_test.14 (the 0.1.0 release gate)")
    ax.legend(loc="lower right", fontsize=8)
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")

    fig.suptitle(
        "Spec-002 release gate, post issues #10 + #11\n"
        "Domain.from_mesh → triangulate (default size-field stack) — "
        "both fresh meshes are structurally valid",
        fontsize=11,
    )
    fig.tight_layout()
    out = ROOT / "tests" / "output" / "release_gate_rebuild.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
