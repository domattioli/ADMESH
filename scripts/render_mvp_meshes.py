"""Render triangulations of the 5 MVP test domains to PNG.

Pre-M.4 preview — exercises the current end-to-end pipeline
(`admesh.routine.triangulate`) on every registered domain and writes
one PNG per domain to ``tests/output/mvp_<name>.png``. The formal
M.4 tests (gated min_q/mean_q assertions) land in session 1; this
script is the visual artifact.

Run:
    python scripts/render_mvp_meshes.py
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

OUTDIR = Path(__file__).resolve().parent.parent / "output"
OUTDIR.mkdir(parents=True, exist_ok=True)

# Per-domain h0 and niter (tuned for a reasonable first-pass preview).
CONFIG: dict[str, dict[str, float | int]] = {
    "unit_square":       {"h0": 0.12, "niter": 200},
    "l_shape":           {"h0": 0.15, "niter": 200},
    "unit_disk":         {"h0": 0.15, "niter": 200},
    "annulus":           {"h0": 0.12, "niter": 200},
    "notched_rectangle": {"h0": 0.08, "niter": 200},
}


def render(name: str) -> dict[str, float | int]:
    dom = domains.ALL[name]
    cfg = CONFIG[name]
    p, t = triangulate(dom, h0=float(cfg["h0"]), niter=int(cfg["niter"]), seed=0)
    min_q, mean_q, _ = mesh_quality(p, t)

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.triplot(p[:, 0], p[:, 1], t, lw=0.5, color="#1f77b4")
    ax.plot(p[:, 0], p[:, 1], ".", ms=2, color="#d62728")
    xmin, ymin, xmax, ymax = dom.bbox
    pad = 0.05 * max(xmax - xmin, ymax - ymin)
    ax.set_xlim(xmin - pad, xmax + pad)
    ax.set_ylim(ymin - pad, ymax + pad)
    ax.set_aspect("equal")
    ax.set_title(
        f"{name}  |  N={len(p)}  T={len(t)}  "
        f"min_q={min_q:.3f}  mean_q={mean_q:.3f}",
        fontsize=10,
    )
    ax.grid(True, alpha=0.2)
    out = OUTDIR / f"mvp_{name}.png"
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return {"N": len(p), "T": len(t), "min_q": min_q, "mean_q": mean_q, "path": str(out)}


def main() -> None:
    np.random.seed(0)
    print(f"Rendering MVP meshes to {OUTDIR}\n")
    print(f"{'domain':<22} {'N':>5} {'T':>5} {'min_q':>8} {'mean_q':>8}")
    print("-" * 52)
    for name in CONFIG:
        r = render(name)
        print(f"{name:<22} {r['N']:>5} {r['T']:>5} {r['min_q']:>8.3f} {r['mean_q']:>8.3f}")
    print("\nDone.")


if __name__ == "__main__":
    main()
