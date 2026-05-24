#!/usr/bin/env python3
"""Manim animation: ADMESH mesh generation on the Baranja Hill domain.

Storyboard
----------
1. Domain boundary appears.
2. Fake bathymetry heatmap fades in (synthetic hill / ridge / channel).
3. Crossfade to the size-field heatmap derived from bathymetry factors
   (fine cells where slopes are steep or water is deep).
4. Initial point cloud drops in; Delaunay truss connects them.
5. The truss relaxes — nodes and edges interpolate toward force balance,
   edge set rebuilding at each re-triangulation.
6. Final equilibrium mesh holds.

Data comes from scripts/gen_baranja_viz_data.py (run that first).

Render:
    python scripts/gen_baranja_viz_data.py
    manim -ql scripts/manim_admesh_baranja.py AdmeshBaranja
"""

from __future__ import annotations

import pathlib

import numpy as np
from manim import (
    Scene, ImageMobject, Polygon, Dot, VGroup, Text, Line,
    FadeIn, FadeOut, Create, ValueTracker, always_redraw,
    config, WHITE, YELLOW, BLACK,
)

DATA = pathlib.Path(__file__).resolve().parent / "viz_data" / "baranja_admesh.npz"

# scene framing
SCALE = 3.0          # data units -> manim units
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
    """Map normalized [0,1] -> RGB (deep blue -> cyan -> green -> brown -> white)."""
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
    """Size field: fine (small h, v low) = hot magenta; coarse = dark teal."""
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


def _heatmap_rgba(field: np.ndarray, inside: np.ndarray, cmap) -> np.ndarray:
    """Build an RGBA uint8 image (origin top-left) from a scalar field."""
    f = field.astype(np.float64)
    lo, hi = np.percentile(f[inside], [2, 98])
    n = np.clip((f - lo) / (hi - lo + 1e-12), 0, 1)
    rgb = cmap(n)
    rgba = np.zeros(field.shape + (4,), dtype=np.uint8)
    rgba[..., :3] = (rgb * 255).astype(np.uint8)
    rgba[..., 3] = np.where(inside, 235, 0).astype(np.uint8)
    return np.flipud(rgba)  # manim image origin top-left


class AdmeshBaranja(Scene):
    def construct(self):
        d = np.load(DATA)
        bbox = d["bbox"]
        ring = d["ring"]
        n_snaps = int(d["n_snaps"])
        snaps = [(d[f"p{i}"], d[f"b{i}"]) for i in range(n_snaps)]

        # extent of the heatmap images in scene units
        w = (bbox[2] - bbox[0]) * SCALE
        h = (bbox[3] - bbox[1]) * SCALE

        def heat(field, cmap):
            img = ImageMobject(_heatmap_rgba(d[field], d["inside"], cmap))
            img.height = h
            img.width = w
            return img

        bathy_img = heat("bathy", _cmap_terrain)
        boundary = Polygon(*to_scene(ring, bbox), color=WHITE, stroke_width=2.5)

        title = Text("ADMESH — bathymetry-driven meshing", font_size=30).to_edge(np.array([0, 1, 0]))
        self._cap = Text("Baranja Hill domain", font_size=22).to_edge(np.array([0, -1, 0]))

        # 1. boundary
        self.play(Create(boundary), FadeIn(title), FadeIn(self._cap))
        self.wait(0.5)

        # 2. bathymetry context
        self.play(FadeIn(bathy_img))
        self.bring_to_front(boundary)
        self._caption("Fake bathymetry: hill, ridge, steep channel")
        self.wait(1.5)
        self.play(FadeOut(bathy_img))

        # 3. size-function components, revealed incrementally
        label = Text("", font_size=24).to_corner(np.array([-1, 1, 0]))
        self.add(label)
        components = [
            ("h_curv",  "Component 1/3 — boundary curvature"),
            ("h_grad",  "Component 2/3 — bathymetric slope |∇z|"),
            ("h_depth", "Component 3/3 — water depth"),
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
            self.wait(1.6)

        # 4. combined size function = min of components
        size_img = heat("sizef", _cmap_size)
        self._set_label(label, "min-combined")
        self._caption("Computed size function = min(curvature, slope, depth)")
        self.play(FadeOut(cur_img), FadeIn(size_img))
        self.bring_to_front(boundary)
        self.wait(2.0)
        self.play(FadeOut(size_img), FadeOut(label))
        bathy_img.set_opacity(0.30)
        self.add(bathy_img)
        self.bring_to_front(boundary)

        # 4. initial truss
        p0 = to_scene(snaps[0][0], bbox)
        nodes = VGroup(*[Dot(pt, radius=NODE_R, color=YELLOW) for pt in p0])
        self._caption("Initial Delaunay truss")
        self.play(FadeIn(nodes, lag_ratio=0.002, run_time=1.2))

        # 5. relaxation via a tracker that interpolates node positions
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

        self._caption("Truss relaxation — force balance moves nodes")
        self.play(tracker.animate.set_value(n_snaps - 1), run_time=9.0, rate_func=lambda x: x)
        self.wait(0.5)

        # 6. final
        self._caption(f"Equilibrium mesh — {len(snaps[-1][0])} nodes")
        self.wait(2.0)

    def _caption(self, text):
        new = Text(text, font_size=22).to_edge(np.array([0, -1, 0]))
        self.play(FadeOut(self._cap), FadeIn(new), run_time=0.4)
        self._cap = new

    def _set_label(self, label, text):
        label.become(Text(text, font_size=24, color=YELLOW).to_corner(np.array([-1, 1, 0])))
