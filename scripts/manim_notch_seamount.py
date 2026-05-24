#!/usr/bin/env python3
"""Manim animation: ADMESH mesh generation on Coastal Notch + Seamount domain.

5-Act Storyboard:
1. Domain boundary appears + notch corner labeled
2. Three size-field factors (curvature, slope, depth) fade in sequence
3. Combined size function (min-stack) revealed
4. Mesh relaxation: nodes compress into size-field valleys
5. Final mesh with quality colormap + statistics

Render: python scripts/gen_notch_seamount_data.py
        manim -ql scripts/manim_notch_seamount.py NotchSeamount
"""

from __future__ import annotations

import pathlib
import numpy as np
from manim import (
    Scene, ImageMobject, Polygon, Dot, VGroup, Text, Line,
    FadeIn, FadeOut, Create, ValueTracker, always_redraw,
    config, WHITE, YELLOW, BLACK, GRAY,
)

DATA = pathlib.Path(__file__).resolve().parent / "viz_data" / "notch_seamount_admesh.npz"

# Scene framing
SCALE = 3.0
EDGE_W = 1.2
NODE_R = 0.018


def to_scene(pts: np.ndarray, bbox) -> np.ndarray:
    """Map data coords to centered manim coords (z=0)."""
    cx = 0.5 * (bbox[0] + bbox[2])
    cy = 0.5 * (bbox[1] + bbox[3])
    out = np.empty((len(pts), 3))
    out[:, 0] = (pts[:, 0] - cx) * SCALE
    out[:, 1] = (pts[:, 1] - cy) * SCALE
    out[:, 2] = 0.0
    return out


def _cmap_terrain(v: np.ndarray) -> np.ndarray:
    """Bathymetry colormap: deep blue → cyan → green → brown → white."""
    stops = np.array([
        [0.05, 0.05, 0.35],
        [0.10, 0.45, 0.75],
        [0.30, 0.70, 0.55],
        [0.75, 0.70, 0.35],
        [0.55, 0.35, 0.20],
        [0.95, 0.95, 0.92],
    ])
    xs = np.linspace(0, 1, len(stops))
    rgb = np.empty(v.shape + (3,))
    for c in range(3):
        rgb[..., c] = np.interp(v, xs, stops[:, c])
    return rgb


def _cmap_size(v: np.ndarray) -> np.ndarray:
    """Size field colormap: hot magenta (fine) → dark teal (coarse)."""
    stops = np.array([
        [0.95, 0.15, 0.55],   # fine
        [0.95, 0.65, 0.25],
        [0.30, 0.75, 0.70],
        [0.10, 0.25, 0.35],   # coarse
    ])
    xs = np.linspace(0, 1, len(stops))
    rgb = np.empty(v.shape + (3,))
    for c in range(3):
        rgb[..., c] = np.interp(v, xs, stops[:, c])
    return rgb


def _cmap_quality(v: np.ndarray) -> np.ndarray:
    """Quality aspect ratio: green (isotropic) → red (skewed)."""
    rgb = np.empty(v.shape + (3,))
    # v ∈ [0,1]: 0=isotropic (green), 1=skewed (red)
    rgb[..., 0] = v       # red increases with skewness
    rgb[..., 1] = 1.0 - v # green decreases
    rgb[..., 2] = 0.2
    return rgb


def _heatmap_rgba(field: np.ndarray, inside: np.ndarray, cmap) -> np.ndarray:
    """Build RGBA uint8 image (origin top-left)."""
    f = field.astype(np.float64)
    lo, hi = np.percentile(f[inside], [2, 98])
    n = np.clip((f - lo) / (hi - lo + 1e-12), 0, 1)
    rgb = cmap(n)
    rgba = np.zeros(field.shape + (4,), dtype=np.uint8)
    rgba[..., :3] = (rgb * 255).astype(np.uint8)
    rgba[..., 3] = np.where(inside, 235, 0).astype(np.uint8)
    return np.flipud(rgba)


class NotchSeamount(Scene):
    def construct(self):
        d = np.load(DATA)
        bbox = d["bbox"]
        ring = d["ring"]
        n_snaps = int(d["n_snaps"])
        snaps = [(d[f"p{i}"], d[f"b{i}"]) for i in range(n_snaps)]

        # extent of heatmap images in scene units
        w = (bbox[2] - bbox[0]) * SCALE
        h = (bbox[3] - bbox[1]) * SCALE

        def heat(field, cmap):
            img = ImageMobject(_heatmap_rgba(d[field], d["inside"], cmap))
            img.height = h
            img.width = w
            return img

        bathy_img = heat("bathy", _cmap_terrain)
        boundary = Polygon(*to_scene(ring, bbox), color=WHITE, stroke_width=2.5)

        title = Text("ADMESH — adaptive mesh on Coastal Notch + Seamount", font_size=28).to_edge(np.array([0, 1, 0]))
        self._cap = Text("Domain with boundary curvature", font_size=20).to_edge(np.array([0, -1, 0]))

        # Act I: Boundary
        self.play(Create(boundary), FadeIn(title), FadeIn(self._cap))
        self.wait(1.0)

        # Act II: Size-field factors (3 heatmaps, 2 sec each)
        self.play(FadeIn(bathy_img))
        self.bring_to_front(boundary)
        self._caption("Bathymetry context: cross-shelf profile + seamount bump")
        self.wait(1.5)
        self.play(FadeOut(bathy_img))

        label = Text("", font_size=22).to_corner(np.array([-1, 1, 0]))
        self.add(label)
        components = [
            ("h_curv", "Factor 1/3 — boundary curvature (notch corner → fine)"),
            ("h_grad", "Factor 2/3 — bathymetric slope (seamount flank → fine)"),
            ("h_depth", "Factor 3/3 — water depth (deep zones → fine)"),
        ]
        cur_img = None
        for field, text in components:
            img = heat(field, _cmap_size)
            self._set_label(label, text.split("—")[1].strip())
            self._caption(text)
            if cur_img is None:
                self.play(FadeIn(img))
            else:
                self.play(FadeOut(cur_img), FadeIn(img))
            self.bring_to_front(boundary)
            cur_img = img
            self.wait(2.0)

        # Act III: Combined size function
        size_img = heat("sizef", _cmap_size)
        self._set_label(label, "min-combined size field")
        self._caption("Computed target: h = min(curvature, slope, depth)")
        self.play(FadeOut(cur_img), FadeIn(size_img))
        self.bring_to_front(boundary)
        self.wait(1.5)
        self.play(FadeOut(size_img), FadeOut(label))
        bathy_img.set_opacity(0.15)
        self.add(bathy_img)
        self.bring_to_front(boundary)

        # Act IV: Initial truss + relaxation
        p0 = to_scene(snaps[0][0], bbox)
        nodes = VGroup(*[Dot(pt, radius=NODE_R, color=YELLOW) for pt in p0])
        self._caption("Initial lattice: nodes placed at uniform spacing")
        self.play(FadeIn(nodes, lag_ratio=0.001, run_time=1.0))
        self.wait(0.5)

        tracker = ValueTracker(0.0)
        scene_pts = [to_scene(s[0], bbox) for s in snaps]

        def truss_redraw():
            t = tracker.get_value()
            i = int(np.floor(t))
            j = min(i + 1, n_snaps - 1)
            frac = t - i
            P = scene_pts[i] * (1 - frac) + scene_pts[j] * frac
            bars = snaps[i][1]
            grp = VGroup()
            for a, b in bars:
                grp.add(Line(P[a], P[b], stroke_width=EDGE_W, color="#56b6ff"))
            return grp

        truss = always_redraw(truss_redraw)
        self.add(truss)
        self.bring_to_front(nodes)

        def nodes_redraw():
            t = tracker.get_value()
            i = int(np.floor(t))
            j = min(i + 1, n_snaps - 1)
            frac = t - i
            P = scene_pts[i] * (1 - frac) + scene_pts[j] * frac
            return VGroup(*[Dot(pt, radius=NODE_R, color=YELLOW) for pt in P])

        live_nodes = always_redraw(nodes_redraw)
        self.remove(nodes)
        self.add(live_nodes)

        self._caption("Force balance relaxation: nodes compress into size-field valleys")
        self.play(tracker.animate.set_value(n_snaps - 1), run_time=4.0, rate_func=lambda x: x)
        self.wait(0.5)

        # Act V: Final mesh quality
        self._caption(f"Equilibrium mesh: {len(snaps[-1][0])} nodes, refined at notch + seamount")
        self.wait(2.0)

    def _caption(self, text):
        new = Text(text, font_size=20).to_edge(np.array([0, -1, 0]))
        self.play(FadeOut(self._cap), FadeIn(new), run_time=0.3)
        self._cap = new

    def _set_label(self, label, text):
        label.become(Text(text, font_size=22, color=YELLOW).to_corner(np.array([-1, 1, 0])))
