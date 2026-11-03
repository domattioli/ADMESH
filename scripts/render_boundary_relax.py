"""Render the 1D boundary DistMesh relaxation, then the final fixed-mode mesh.

API-layer demo (not a MATLAB port) for ``admesh.boundary_relax`` and
``triangulate(boundary="fixed")``.  Output: an MP4 with the boundary nodes
relaxing along a graded, cornered coastline-like polygon, an inset of bar
length / target h against arc length, then the final 2D mesh held for a few
seconds.

Needs matplotlib and ffmpeg (/opt/homebrew/bin/ffmpeg or on PATH).

    python scripts/render_boundary_relax.py [out.mp4] [--toy]

Default size field is ADMESH's build_h (curvature + medial axis); --toy uses
the radial demo field ``fh``.
"""

from __future__ import annotations

import dataclasses
import shutil
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np

import admesh
from admesh.boundary_relax import relax_ring, ring_arclength
from admesh.loaders import _domain_from_polygon
from admesh.size_field import limit_gradient

OUT = Path.home() / "Desktop" / "admesh_boundary_1d_distmesh.mp4"
FPS = 12
HOLD_S = 4.0
H0 = 0.06

# Notched rectangle with a ragged "coast" along the top-left.
RING = np.array(
    [
        [0.0, 0.0], [4.0, 0.0], [4.0, 1.6], [3.3, 1.7], [3.0, 2.0],
        [2.15, 2.0], [2.15, 1.35], [1.85, 1.35], [1.85, 2.0],
        [1.2, 2.0], [0.9, 1.75], [0.4, 1.9], [0.0, 1.5],
    ]
)
CENTRE = np.array([2.0, 1.5])


def fh(p: np.ndarray) -> np.ndarray:
    p = np.atleast_2d(p)
    d = np.linalg.norm(p - CENTRE, axis=1)
    return H0 + 0.22 * np.clip(d / 2.6, 0.0, 1.0)


def real_size_field():
    """ADMESH size field (curvature + medial axis) via build_h, gradient-limited
    over the full domain (|grad h| <= 0.2) with limit_gradient."""
    from admesh._stages.domains import Domain as PortDomain
    from admesh._stages.mesh_size import build_h

    d = _domain_from_polygon([RING])
    pd = PortDomain(name="demo", fd=d.sdf, bbox=d.bbox, fixed_points=np.empty((0, 2)))
    h = build_h(pd, base=0.25, curvature_scale=0.5, medial_scale=0.3,
                hmin=H_REAL_MIN, hmax=0.25)
    return limit_gradient(h, d.bbox, g=0.2, delta=0.01)


H_REAL_MIN = 0.03


def bar_ratio(xy: np.ndarray, fh=fh):
    s = np.sort(ring_arclength(RING, xy))
    L = float(np.linalg.norm(np.diff(np.vstack([RING, RING[:1]]), axis=0), axis=1).sum())
    ext = np.append(s, s[0] + L)
    l = np.diff(ext)
    order = np.argsort(ring_arclength(RING, xy))
    q = xy[order]
    mid = 0.5 * (q + np.roll(q, -1, axis=0))
    return 0.5 * (ext[:-1] + ext[1:]), l / fh(mid)


def main(out: Path, size: str = "real") -> None:
    size_fn, h0 = (real_size_field(), H_REAL_MIN) if size == "real" else (fh, H0)
    ff = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
    matplotlib.rcParams["animation.ffmpeg_path"] = ff

    xy, hist = relax_ring(RING, size_fn, h0, record_history=True,
                          init="random", rng_seed=7, max_iter=600)
    print(f"relax: {len(hist)} snapshots, {len(hist[0])} -> {len(xy)} nodes")
    stride = max(1, len(hist) // 150)
    idx = list(range(0, len(hist), stride))
    if idx[-1] != len(hist) - 1:
        idx.append(len(hist) - 1)

    # Hand the relaxed boundary nodes to triangulate as the polygon, so the
    # 2D solve pins exactly the red nodes shown in the 1D stage.
    dom = dataclasses.replace(_domain_from_polygon([RING]), pts=xy)
    trace: list[tuple[int, np.ndarray, np.ndarray]] = []
    mesh = admesh.triangulate(
        dom, h_max=h0, size_field=size_fn, seed=0, boundary="fixed",
        quality_gate=(0.0, 0.0),
        on_iter=lambda k, p, t: trace.append((k, np.array(p), np.array(t))),
    )
    print(f"2D: {len(trace)} keyframes")
    tstride = max(1, len(trace) // 120)
    tidx = list(range(0, len(trace), tstride))
    if trace and tidx[-1] != len(trace) - 1:
        tidx.append(len(trace) - 1)
    print(f"mesh: {len(mesh.nodes)} nodes, {len(mesh.elements)} tris, "
          f"min_q={mesh.quality.min():.3f}")

    n_hold = int(HOLD_S * FPS)
    slow = [("relax", i) for i in idx for _ in range(4 if i < 25 else 1)]
    frames = ([("relax", 0)] * (2 * FPS) + slow + [("relax", idx[-1])] * FPS
              + [("solve", j) for j in tidx] + [("mesh", 0)] * n_hold)

    fig = plt.figure(figsize=(10, 7.2), dpi=100)
    ax = fig.add_axes([0.04, 0.30, 0.92, 0.66])
    axi = fig.add_axes([0.08, 0.06, 0.86, 0.18])
    closed = np.vstack([RING, RING[:1]])

    def draw(k):
        kind, i = frames[k]
        ax.clear()
        axi.clear()
        ax.plot(closed[:, 0], closed[:, 1], "-", color="0.55", lw=1)
        ax.set_aspect("equal")
        ax.set_xlim(-0.1, 4.1)
        ax.set_ylim(-0.1, 2.1)
        ax.axis("off")
        if kind == "relax":
            p = hist[i]
            ax.plot(p[:, 0], p[:, 1], "o", ms=4, color="C3")
            ax.plot(RING[:, 0], RING[:, 1], "s", ms=6, mfc="none", color="k")
            ax.set_title(f"1D boundary DistMesh from random start: "
                         f"iteration {i}, {len(p)} nodes")
            s, r = bar_ratio(p, size_fn)
            axi.axhspan(0.6, 1.6, color="0.9")
            axi.axhline(1.0, color="0.4", lw=0.8)
            axi.plot(s, r, "o-", ms=3, color="C0", lw=1)
            axi.set_ylim(0, 2.5)
            axi.set_xlim(0, float(np.linalg.norm(np.diff(closed, axis=0), axis=1).sum()))
            axi.set_xlabel("arc length s")
            axi.set_ylabel("bar length / h")
        elif kind == "solve":
            k, p, t = trace[i]
            ax.triplot(p[:, 0], p[:, 1], t, lw=0.5, color="C0")
            ax.plot(xy[:, 0], xy[:, 1], "o", ms=3, color="C3")
            ax.set_title(f"2D truss solve (boundary nodes fixed): step {k}, "
                         f"{len(p)} nodes")
            axi.axis("off")
            axi.text(0.5, 0.5, "interior nodes relax; red boundary nodes stay put",
                     ha="center", va="center", transform=axi.transAxes)
        else:
            ax.triplot(mesh.nodes[:, 0], mesh.nodes[:, 1], mesh.elements,
                       lw=0.5, color="C0")
            ax.plot(closed[:, 0], closed[:, 1], "-", color="k", lw=1)
            ax.plot(xy[:, 0], xy[:, 1], "o", ms=3, color="C3")
            ax.set_title(f"Final mesh, boundary='fixed': {len(mesh.nodes)} nodes, "
                         f"{len(mesh.elements)} triangles")
            axi.axis("off")
            axi.text(0.5, 0.5, f"min quality {mesh.quality.min():.2f}, "
                     f"mean {mesh.quality.mean():.2f}", ha="center", va="center",
                     transform=axi.transAxes)

    anim = animation.FuncAnimation(fig, draw, frames=len(frames), interval=1000 / FPS)
    out.parent.mkdir(parents=True, exist_ok=True)
    anim.save(out, writer=animation.FFMpegWriter(fps=FPS, bitrate=2400))
    print(f"wrote {out} ({len(frames)} frames)")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(Path(args[0]).expanduser() if args else OUT,
         size="toy" if "--toy" in sys.argv else "real")
