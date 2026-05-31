"""Manim hero animation for the ADMESH README: Delaware Bay, three stages.

Renders the graded Delaware Bay mesh evolving through ADMESH's pipeline:

    1. Initialized   - rough, size-aware scatter inside the real Delaware
       Bay / River outline.
    2. Truss solver  - DistMesh force balance relaxes nodes toward
       elements sized by the graded size function h(x) (hmin..hmax, g).
    3. FEM smoothed  - Laplacian/FEM smoothing peaks element quality.

Triangles are colored by quality (red = poor, green = equilateral), so the
viewer literally watches the mesh go from red to green. Node motion is
interpolated continuously between precomputed keyframes via a ValueTracker,
so the camera sees smooth movement rather than hard cuts.

Data comes from ``delbay_stages.npz`` (see precompute_delbay_stages.py).

Render (from repo root, inside the manim venv):
    # MP4 (high quality, 30 fps)
    manim -qh --fps 30 scripts/hero/delbay_hero.py DelawareBayHero
    # GIF
    manim -qm --fps 24 --format gif scripts/hero/delbay_hero.py DelawareBayHero
"""
from __future__ import annotations

import pathlib

import numpy as np
from manim import (
    Scene, VGroup, VMobject, Polygon, Text, Line,
    ManimColor, config,
    FadeIn, FadeOut, ValueTracker, always_redraw,
    UL, DOWN, UP, LEFT, RIGHT, ORIGIN, rate_functions,
)

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "delbay_stages.npz"

# ADMESH palette: poor (magenta) -> mid (purple) -> good (cyan).
C_POOR = ManimColor("#e040fb")
C_MID = ManimColor("#7c4dff")
C_GOOD = ManimColor("#00e5ff")
C_COAST = ManimColor("#4aa3df")
C_BG = ManimColor("#0e1117")


def quality(pts, simp):
    a, b, c = pts[simp[:, 0]], pts[simp[:, 1]], pts[simp[:, 2]]
    ab = np.linalg.norm(b - a, axis=1)
    bc = np.linalg.norm(c - b, axis=1)
    ca = np.linalg.norm(a - c, axis=1)
    area = 0.5 * np.abs((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1])
                        - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1]))
    s = (ab + bc + ca) / 2
    rin = np.divide(area, s, out=np.zeros_like(area), where=s > 0)
    rout = np.divide(ab * bc * ca, 4 * area, out=np.ones_like(area), where=area > 0)
    q = np.divide(2 * rin, rout, out=np.zeros_like(area), where=rout > 0)
    return np.clip(q, 0, 1)


def edge_lengths(pts, simp):
    """All edge lengths (3 per triangle) in degrees."""
    a, b, c = pts[simp[:, 0]], pts[simp[:, 1]], pts[simp[:, 2]]
    ab = np.linalg.norm(b - a, axis=1)
    bc = np.linalg.norm(c - b, axis=1)
    ca = np.linalg.norm(a - c, axis=1)
    return np.concatenate([ab, bc, ca])


def quality_color(q: float) -> ManimColor:
    if q < 0.5:
        return ManimColor.interpolate(C_POOR, C_MID, q / 0.5)
    return ManimColor.interpolate(C_MID, C_GOOD, (q - 0.5) / 0.5)


class DelawareBayHero(Scene):
    def construct(self):
        self.camera.background_color = C_BG
        d = np.load(DATA)
        frames = d["frames"].astype(float)        # (T, N, 2)
        simp = d["simplices"]
        ring = d["ring"].astype(float)
        n_relax = int(d["n_relax_frames"])
        T = frames.shape[0]
        hmin, hmax, g = float(d["hmin"]), float(d["hmax"]), float(d["g"])

        # --- lon/lat -> scene coordinates -------------------------------
        allxy = frames.reshape(-1, 2)
        lo = allxy.min(axis=0)
        hi = allxy.max(axis=0)
        span = hi - lo
        target_h = 6.4
        scale = target_h / span[1]
        center = (lo + hi) / 2
        offset = np.array([-1.7, -0.15])  # shift left, room for the caption

        def to_scene(p2: np.ndarray) -> np.ndarray:
            xy = (p2 - center) * scale
            out = np.zeros((len(xy), 3))
            out[:, 0] = xy[:, 0] + offset[0]
            out[:, 1] = xy[:, 1] + offset[1]
            return out

        # --- coastline outline (static) ---------------------------------
        coast = Polygon(*to_scene(ring), color=C_COAST,
                        stroke_width=2.4, fill_opacity=0.0)
        coast.set_z_index(5)

        # --- mesh: build triangles once, update points + color each frame
        fidx = ValueTracker(0.0)

        def frame_positions(t: float) -> np.ndarray:
            t = float(np.clip(t, 0, T - 1))
            i0 = int(np.floor(t))
            i1 = min(i0 + 1, T - 1)
            a = t - i0
            return (1 - a) * frames[i0] + a * frames[i1]

        tris = VGroup()
        pts0 = frame_positions(0.0)
        scene_pts0 = to_scene(pts0)
        for s in simp:
            tri = Polygon(scene_pts0[s[0]], scene_pts0[s[1]], scene_pts0[s[2]],
                          stroke_width=0.6)
            tris.add(tri)
        tris.set_z_index(0)

        def update_mesh(group: VGroup):
            t = fidx.get_value()
            pts = frame_positions(t)
            q = quality(pts, simp)
            sp = to_scene(pts)
            for tri, s, qi in zip(group, simp, q):
                col = quality_color(float(qi))
                tri.set_points_as_corners(
                    [sp[s[0]], sp[s[1]], sp[s[2]], sp[s[0]]]
                )
                tri.set_fill(col, opacity=0.78)
                tri.set_stroke(C_BG, width=0.5, opacity=0.6)

        tris.add_updater(update_mesh)
        update_mesh(tris)

        # --- titles / captions ------------------------------------------
        # Title + subtitle: top-right corner.
        title = Text("ADMESH", font="sans-serif", weight="BOLD",
                     color="#e6edf3").scale(0.95)
        subtitle = Text("Delaware Bay  ·  graded unstructured mesh",
                        color="#9aa7b2").scale(0.34)
        subtitle.next_to(title, DOWN, buff=0.14)
        from manim import UR
        header = VGroup(title, subtitle).to_corner(UR, buff=0.45)
        header.set_z_index(10)

        # Right-hand caption panel (below title).
        cap_x = 4.55
        step_label = Text("", color="#e6edf3").scale(0.5)
        step_label.move_to([cap_x, 1.0, 0])
        step_label.set_z_index(10)

        DEG2KM = 111.0  # 1° ≈ 111 km at Delaware Bay (~39°N)

        # Live hmin/hmax readout (actual edge lengths converted to km).
        def hminmax_readout():
            t = fidx.get_value()
            el = edge_lengths(frame_positions(t), simp) * DEG2KM
            grp = VGroup(
                Text(f"hmin = {el.min():.1f} km", color="#9aa7b2").scale(0.30),
                Text(f"hmax = {el.max():.1f} km", color="#9aa7b2").scale(0.30),
                Text(f"g = {g:.2f}  (|∇h| limit)", color="#9aa7b2").scale(0.30),
            ).arrange(DOWN, aligned_edge=LEFT, buff=0.16)
            grp.move_to([cap_x, -0.55, 0])
            return grp
        hyper = always_redraw(hminmax_readout)
        hyper.set_z_index(10)

        def quality_readout():
            t = fidx.get_value()
            q = quality(frame_positions(t), simp)
            grp = VGroup(
                Text(f"mean q = {q.mean():.2f}",          color="#e6edf3").scale(0.38),
                Text(f"p5   q = {np.percentile(q,5):.2f}", color="#e6edf3").scale(0.38),
            ).arrange(DOWN, aligned_edge=LEFT, buff=0.14)
            grp.move_to([cap_x, 0.42, 0])
            return grp
        qreadout = always_redraw(quality_readout)
        qreadout.set_z_index(10)

        # Quality legend (red -> green bar).
        legend = VGroup()
        nseg = 24
        for k in range(nseg):
            qv = k / (nseg - 1)
            seg = Line([0, 0, 0], [0.13, 0, 0], stroke_width=8,
                       color=quality_color(qv))
            seg.move_to([cap_x - 0.9 + k * 0.075, -2.1, 0])
            legend.add(seg)
        leg_lbl = VGroup(
            Text("poor", color=C_POOR).scale(0.26).next_to(legend, LEFT, buff=0.12),
            Text("equilateral", color=C_GOOD).scale(0.26).next_to(legend, RIGHT, buff=0.12),  # noqa
        )
        legend_grp = VGroup(legend, leg_lbl).set_z_index(10)

        def set_step(n: int, label: str):
            new = Text(f"{n} · {label}", color="#e6edf3", weight="BOLD").scale(0.5)
            new.move_to([cap_x, 1.0, 0])
            return new

        # --- play -------------------------------------------------------
        self.add(coast, tris, header, hyper, qreadout, legend_grp)

        step_label = set_step(1, "Initialized")
        self.play(FadeIn(step_label), FadeIn(coast), run_time=0.8)
        self.wait(1.1)

        new_label = set_step(2, "Truss solver")
        self.play(FadeOut(step_label), FadeIn(new_label), run_time=0.5)
        step_label = new_label
        self.play(fidx.animate.set_value(n_relax - 1),
                  run_time=5.0, rate_func=rate_functions.ease_in_out_sine)
        self.wait(0.4)

        new_label = set_step(3, "Smoothed")
        self.play(FadeOut(step_label), FadeIn(new_label), run_time=0.5)
        step_label = new_label
        self.play(fidx.animate.set_value(T - 1),
                  run_time=2.6, rate_func=rate_functions.ease_in_out_sine)
        self.wait(1.6)
