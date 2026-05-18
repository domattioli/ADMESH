"""Render an annulus-meshing animation for the README.

Sweeps ``admesh.triangulate(..., max_iter=k)`` for an exponentially-
spaced sequence of k values to capture frames without touching
``distmesh2d``. See ``specs/011-annulus-meshing-animation/spec.md``.

Outputs (both committed to ``papers/``):

- ``annulus_meshing.gif``  — canonical, GitHub-friendly.
- ``annulus_meshing.mp4``  — optional, only when ffmpeg is on PATH.

Dependencies (dev/docs only — not pinned in core):

    pip install matplotlib pillow            # GIF
    # ffmpeg on PATH (optional)              # MP4

Run from repo root::

    python scripts/render_annulus_animation.py
"""

from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np

import admesh
from admesh._stages import domains

CAPS: tuple[int, ...] = (1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 160, 200)
# Graded sizing: tight at the rings (mimics curvature refinement) loose in
# the body. Issue #65 documents that `triangulate(..., h_min, h_max)` alone
# currently yields a uniform clamped field (admesh/api.py:729) — to force
# real grading we hand triangulate() an explicit size_field that returns
# H_MIN at either circle and grades smoothly out to H_MAX at mid-annulus.
H_MAX: float = 0.16
H_MIN: float = 0.035
# Distance-to-nearer-ring band over which the field grades.
RING_BAND: float = 0.25
SEED: int = 0


def graded_size_field(p: np.ndarray) -> np.ndarray:
    """H_MIN at outer (r=1) or inner (r=0.4) ring → H_MAX at mid-annulus."""
    r = np.linalg.norm(p, axis=1)
    d_ring = np.minimum(np.abs(r - 1.0), np.abs(r - 0.4))
    t = np.clip(d_ring / RING_BAND, 0.0, 1.0)
    s = t * t * (3.0 - 2.0 * t)  # smoothstep
    return H_MIN + (H_MAX - H_MIN) * s


def _seeded_graded_lattice(seed: int = SEED) -> np.ndarray:
    """Dense triangular lattice over the annulus bbox, rejected by ``graded_size_field``.

    ``triangulate``'s default path sets ``h0 = h_max`` (admesh/api.py:668), so
    a large H_MAX means a sparse initial lattice and the rejection step has
    nothing graded to work with. We build the dense lattice ourselves at
    H_MIN spacing (a fine grid everywhere), SDF-filter to inside-annulus,
    then apply distmesh's rejection criterion (probability ∝ (h_min/h)^2)
    so the surviving lattice already grades from H_MIN → H_MAX before
    the first force-balance step.
    """
    rng = np.random.default_rng(seed)
    spacing = H_MIN
    # Equilateral triangular lattice (distmesh's _initial_distribution shape).
    xs = np.arange(-1.1, 1.1 + spacing, spacing)
    ys = np.arange(-1.1, 1.1 + spacing, spacing * np.sqrt(3.0) / 2.0)
    xx, yy = np.meshgrid(xs, ys)
    xx[::2] += spacing / 2.0
    pts = np.column_stack([xx.ravel(), yy.ravel()])
    # SDF filter — keep points strictly inside the annulus.
    inside = domains.ANNULUS.fd(pts) < -spacing / 8.0
    pts = pts[inside]
    # Rejection on the size field — probability ∝ (h_min / h(p))^2.
    h_vals = graded_size_field(pts)
    keep_prob = (h_vals.min() / h_vals) ** 2
    pts = pts[rng.uniform(size=len(pts)) < keep_prob]
    return pts


FPS: int = 6
FIG_INCHES: tuple[float, float] = (4.0, 4.0)
DPI: int = 80

OUT_DIR = Path(__file__).resolve().parents[1] / "papers"

LOG = logging.getLogger("render_annulus_animation")

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "font.size": 11,
    "axes.titlesize": 12,
})


def capture_frames() -> list[tuple[np.ndarray, np.ndarray, int, float, float]]:
    """Replay ``triangulate`` at each cap; return list of (p, t, k, q_mean, q_min)."""
    frames: list[tuple[np.ndarray, np.ndarray, int, float, float]] = []
    prev_p: np.ndarray | None = None
    prev_t: np.ndarray | None = None
    seeded_lattice = _seeded_graded_lattice()
    LOG.info("graded initial lattice: %d nodes", len(seeded_lattice))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for cap in CAPS:
            mesh = admesh.triangulate(
                domains.ANNULUS,
                size_field=graded_size_field,
                initial_points=seeded_lattice,
                max_iter=cap,
                seed=SEED,
                quality_gate=(0.0, 0.0),
            )
            p = np.asarray(mesh.nodes, dtype=float)
            t = np.asarray(mesh.elements, dtype=np.int64)
            q = np.asarray(mesh.quality, dtype=float)
            q_mean = float(np.mean(q)) if q.size else 0.0
            q_min = float(np.min(q)) if q.size else 0.0
            if (
                prev_p is not None
                and prev_t is not None
                and prev_p.shape == p.shape
                and prev_t.shape == t.shape
                and np.allclose(prev_p, p)
                and np.array_equal(prev_t, t)
            ):
                LOG.info("cap=%d  → dedupe (converged)", cap)
                continue
            LOG.info("cap=%d  → %d pts, %d tri, q_mean=%.3f", cap, len(p), len(t), q_mean)
            frames.append((p, t, cap, q_mean, q_min))
            prev_p, prev_t = p, t
    return frames


def _boundary_circles(ax: plt.Axes) -> None:
    theta = np.linspace(0.0, 2.0 * np.pi, 256)
    ax.plot(np.cos(theta), np.sin(theta), color="#222", lw=1.2)
    ax.plot(0.4 * np.cos(theta), 0.4 * np.sin(theta), color="#222", lw=1.2)


def _size_field_grid(resolution: int = 220) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """Sample ``graded_size_field`` on a regular grid over the annulus bbox."""
    lin = np.linspace(-1.1, 1.1, resolution)
    xx, yy = np.meshgrid(lin, lin)
    pts = np.column_stack([xx.ravel(), yy.ravel()])
    field = graded_size_field(pts).reshape(xx.shape)
    sdf = domains.ANNULUS.fd(pts).reshape(xx.shape)
    field[sdf > 0.0] = np.nan
    return field, (-1.1, 1.1, -1.1, 1.1)


_FIELD_GRID, _FIELD_EXTENT = _size_field_grid()


SIZE_CMAP = "coolwarm_r"  # red = small element size, blue = large


def render_frame(ax: plt.Axes, p: np.ndarray, t: np.ndarray, k: int) -> None:
    ax.clear()
    ax.imshow(
        _FIELD_GRID, extent=_FIELD_EXTENT, origin="lower", cmap=SIZE_CMAP,
        alpha=0.55, interpolation="bilinear", vmin=H_MIN, vmax=H_MAX, zorder=0,
    )
    _boundary_circles(ax)
    if len(t):
        ax.triplot(p[:, 0], p[:, 1], t, lw=0.7, color="#111", zorder=2)
    ax.plot(p[:, 0], p[:, 1], "o", ms=1.2, color="#000", zorder=3)
    ax.set_xlim(-1.12, 1.12)
    ax.set_ylim(-1.12, 1.12)
    ax.set_aspect("equal")
    ax.set_xticks([-1.0, 0.0, 1.0])
    ax.set_yticks([-1.0, 0.0, 1.0])
    ax.tick_params(axis="both", which="major", labelsize=8, length=3, pad=2)
    for spine in ax.spines.values():
        spine.set_linewidth(0.8)
        spine.set_color("#888")
    ax.set_title(
        f"iter ≤ {k:>3d} · {len(p):>3d} nodes · {len(t):>3d} tris",
        fontfamily="monospace", fontsize=11,
    )


def render_convergence(
    ax: plt.Axes,
    all_iters: list[int],
    all_q_mean: list[float],
    all_q_min: list[float],
    frame_idx: int,
) -> None:
    ax.clear()
    ax.plot(all_iters, all_q_mean, "-", color="#1f77b4", lw=1.2, label="mean q")
    ax.plot(all_iters, all_q_min, "--", color="#888", lw=0.9, label="min q")
    ax.plot(all_iters[frame_idx], all_q_mean[frame_idx], "o", color="#d62728", ms=4)
    ax.set_xscale("log")
    ax.set_xlim(1, max(all_iters) * 1.1)
    ax.set_ylim(0.0, 1.0)
    ax.set_xlabel("iter ≤ k  (log)", fontsize=9, labelpad=3)
    ax.set_ylabel("element quality  q", fontsize=9, labelpad=4)
    ax.set_title("convergence", fontsize=10, pad=4)
    ax.tick_params(axis="both", which="major", labelsize=7, length=2, pad=1)
    ax.grid(True, which="both", lw=0.3, color="#ccc")
    ax.legend(loc="lower right", fontsize=8, frameon=False)


def _fmt_tick(x: float) -> str:
    s = f"{x:.4f}".rstrip("0").rstrip(".")
    return s if s else "0"


def write_gif(
    frames: list[tuple[np.ndarray, np.ndarray, int, float, float]],
    out_path: Path,
) -> None:
    from PIL import Image
    import matplotlib as mpl

    fig = plt.figure(figsize=(FIG_INCHES[0] + 4.2, FIG_INCHES[1]), dpi=DPI)
    gs = fig.add_gridspec(
        nrows=1, ncols=4, width_ratios=[18, 1, 5, 14],
        wspace=0.10, left=0.05, right=0.96, top=0.90, bottom=0.12,
    )
    ax_mesh = fig.add_subplot(gs[0, 0])
    cax = fig.add_subplot(gs[0, 1])
    ax_conv = fig.add_subplot(gs[0, 3])
    out_path.parent.mkdir(parents=True, exist_ok=True)

    sm = mpl.cm.ScalarMappable(
        norm=mpl.colors.Normalize(vmin=H_MIN, vmax=H_MAX), cmap=SIZE_CMAP,
    )
    cbar = fig.colorbar(sm, cax=cax)
    cbar.set_label("size function  h(x, y)", fontsize=9)
    cbar.ax.tick_params(labelsize=8)
    tick_vals = list(np.linspace(H_MIN, H_MAX, 5))
    cbar.set_ticks(tick_vals)
    cbar.set_ticklabels([_fmt_tick(v) for v in tick_vals])

    all_iters = [k for (_, _, k, _, _) in frames]
    all_q_mean = [q for (_, _, _, q, _) in frames]
    all_q_min = [q for (_, _, _, _, q) in frames]

    pil_frames: list[Image.Image] = []
    for i, (p, t, k, _, _) in enumerate(frames):
        render_frame(ax_mesh, p, t, k)
        render_convergence(ax_conv, all_iters, all_q_mean, all_q_min, i)
        fig.canvas.draw()
        buf = np.asarray(fig.canvas.buffer_rgba())
        img = Image.fromarray(buf, mode="RGBA").convert("RGB").quantize(colors=64, method=Image.MEDIANCUT)
        pil_frames.append(img)
    plt.close(fig)

    duration_ms = int(1000 / FPS)
    durations = [duration_ms] * (len(pil_frames) - 1) + [duration_ms * 8]
    pil_frames[0].save(
        out_path, save_all=True, append_images=pil_frames[1:],
        duration=durations, optimize=True, disposal=2,
    )
    LOG.info("wrote %s  (%.1f KB)", out_path, out_path.stat().st_size / 1024)


def write_mp4(
    frames: list[tuple[np.ndarray, np.ndarray, int, float, float]],
    out_path: Path,
) -> bool:
    try:
        writer = animation.FFMpegWriter(fps=FPS, bitrate=800)
    except Exception as exc:  # noqa: BLE001
        LOG.warning("FFMpegWriter unavailable: %s — skipping MP4", exc)
        return False
    fig, ax = plt.subplots(figsize=FIG_INCHES, dpi=DPI)

    def update(i: int) -> tuple:
        p, t, k, _, _ = frames[i]
        render_frame(ax, p, t, k)
        return ()

    anim = animation.FuncAnimation(
        fig, update, frames=len(frames), interval=1000 // FPS, blit=False,
    )
    try:
        anim.save(out_path, writer=writer)
    except (FileNotFoundError, OSError, RuntimeError) as exc:
        LOG.warning("ffmpeg not on PATH or save failed (%s) — skipping MP4", exc)
        plt.close(fig)
        return False
    plt.close(fig)
    LOG.info("wrote %s  (%.1f KB)", out_path, out_path.stat().st_size / 1024)
    return True


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    LOG.info("capturing frames for ANNULUS domain (h_max=%g, seed=%d)", H_MAX, SEED)
    frames = capture_frames()
    LOG.info("captured %d frames after dedupe", len(frames))
    if not frames:
        LOG.error("no frames captured — aborting")
        return 1
    gif_path = OUT_DIR / "annulus_meshing.gif"
    mp4_path = OUT_DIR / "annulus_meshing.mp4"
    write_gif(frames, gif_path)
    write_mp4(frames, mp4_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
