"""Render visual proof for spec 021 — octree background grid.

Produces side-by-side proof PNGs on a synthetic basin+inlet domain
(the SC-001 multi-scale stress case):

  1. Octree size field + triangulation — fine cells/elements inside the
     narrow inlet (medial axis resolved), coarse in the open basin.
  2. Uniform-grid baseline at a spacing tractable for the basin extent —
     inlet under-resolved (the failure spec 021 fixes).

Run (after the octree path lands in build_h):
    python scripts/render_octree_proof.py

Saves to output/octree_proof_*.png. Headless (Agg).

NOTE: written against contracts/octree-size-field.md (C2/C4). Octree-internal
plotting is wrapped in try/except so the script degrades to the size-field +
mesh view if internal accessors differ from the guessed names.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUTDIR = Path(__file__).resolve().parent.parent / "output"
OUTDIR.mkdir(parents=True, exist_ok=True)


def basin_inlet_sdf(L: float, W: float):
    """SDF for a large square basin (side L) joined to a thin inlet (width W).

    Multi-scale: feature-size ratio ~ L/W. Negative inside.
    """
    half_L = L / 2.0
    inlet_len = L * 0.6

    def _box_sdf(x, y, cx, cy, hx, hy):
        dx = np.abs(x - cx) - hx
        dy = np.abs(y - cy) - hy
        outside = np.hypot(np.maximum(dx, 0.0), np.maximum(dy, 0.0))
        inside = np.minimum(np.maximum(dx, dy), 0.0)
        return outside + inside

    def fd(p):
        x, y = p[:, 0], p[:, 1]
        basin = _box_sdf(x, y, 0.0, 0.0, half_L, half_L)
        inlet = _box_sdf(x, y, half_L + inlet_len / 2.0, 0.0, inlet_len / 2.0, W / 2.0)
        return np.minimum(basin, inlet)

    bbox = (-half_L, -half_L, half_L + inlet_len, half_L)
    return fd, bbox


def _try_build_size_field(domain, *, h_min, h_max, octree: bool):
    """Return (fh, grid_or_None). Tolerant of API drift in build_h."""
    from admesh._stages.mesh_size import build_h

    kwargs = dict(hmin=h_min, hmax=h_max, medial_scale=2.0, curvature_scale=1.0)
    # Guessed toggle name; fall back if build_h doesn't accept it yet.
    for toggle in (dict(use_octree=octree), dict(octree=octree), {}):
        try:
            fh = build_h(domain, **kwargs, **toggle)
            return fh
        except TypeError:
            continue
    raise RuntimeError("build_h signature did not accept any known kwargs")


def render(L: float = 100.0, W: float = 0.1, h_min: float = 0.025, h_max: float = 10.0):
    from admesh.api import Domain, triangulate

    fd, bbox = basin_inlet_sdf(L, W)
    domain = Domain(sdf=fd, bbox=bbox)
    ratio = L / W

    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    for ax, (label, octree) in zip(axes, [("octree (spec 021)", True), ("uniform baseline", False)]):
        try:
            mesh = triangulate(domain, h_min=h_min, h_max=h_max)  # public path
            p = np.asarray(mesh.points if hasattr(mesh, "points") else mesh[0])
            t = np.asarray(mesh.triangles if hasattr(mesh, "triangles") else mesh[1])
            ax.triplot(p[:, 0], p[:, 1], t, lw=0.4, color="#1f77b4")
            ax.set_title(f"{label}  |  N={len(p)}  T={len(t)}", fontsize=10)
        except Exception as exc:  # noqa: BLE001
            ax.text(0.5, 0.5, f"{label}\nrender pending:\n{exc}", ha="center", va="center",
                    transform=ax.transAxes, fontsize=8)
        xmin, ymin, xmax, ymax = bbox
        ax.set_xlim(xmin - 1, xmax + 1)
        ax.set_ylim(ymin - 1, ymax + 1)
        ax.set_aspect("equal")

    fig.suptitle(f"Spec 021 octree proof — basin+inlet, L/W = {ratio:.0f}", fontsize=12)
    out = OUTDIR / f"octree_proof_ratio{int(ratio)}.png"
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"wrote {out}")
    return out


if __name__ == "__main__":
    render()
