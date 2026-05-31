#!/usr/bin/env python3
"""Generate truss-solver animation frames for the GitHub Pages demo (#118).

Runs the canonical DistMesh driver (:func:`admesh._stages.distmesh.distmesh2d`)
on a handful of analytic signed-distance domains, capturing one keyframe per
Delaunay retriangulation via the ``on_iter`` callback. Frames are written as
compact JSON to ``docs/demo/data/<domain>.json`` for client-side playback.

This is Phase-1 of spec-023: no Pyodide, no in-browser Python — the page just
replays pre-baked frames on a Canvas2D renderer.

Usage
-----
    python scripts/gen_demo_frames.py

Output
------
    docs/demo/data/circle.json
    docs/demo/data/rectangle.json
    docs/demo/data/annulus.json
    docs/demo/data/manifest.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from admesh._stages.distmesh import distmesh2d
from admesh._stages.quality import mesh_quality

OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "demo" / "data"

# Cap stored frames so the JSON stays small and playback stays smooth.
MAX_FRAMES = 60
# Round coordinates to keep payload tight (3 decimals is sub-pixel at render).
COORD_DP = 3


# --- signed-distance primitives (Persson & Strang conventions) -------------

def _dcircle(p, cx, cy, r):
    return np.sqrt((p[:, 0] - cx) ** 2 + (p[:, 1] - cy) ** 2) - r


def _drectangle(p, x1, x2, y1, y2):
    # Negative inside; matches distmesh drectangle.m.
    d1 = y1 - p[:, 1]
    d2 = -y2 + p[:, 1]
    d3 = x1 - p[:, 0]
    d4 = -x2 + p[:, 0]
    d5 = np.sqrt(d1 ** 2 + d3 ** 2)
    d6 = np.sqrt(d1 ** 2 + d4 ** 2)
    d7 = np.sqrt(d2 ** 2 + d3 ** 2)
    d8 = np.sqrt(d2 ** 2 + d4 ** 2)
    d = -np.minimum.reduce([-d1, -d2, -d3, -d4])
    ix = (d1 > 0) & (d3 > 0)
    d[ix] = d5[ix]
    ix = (d1 > 0) & (d4 > 0)
    d[ix] = d6[ix]
    ix = (d2 > 0) & (d3 > 0)
    d[ix] = d7[ix]
    ix = (d2 > 0) & (d4 > 0)
    d[ix] = d8[ix]
    return d


def _ddiff(a, b):
    return np.maximum(a, -b)


# --- demo domain definitions -----------------------------------------------

def _domain_circle():
    fd = lambda p: _dcircle(p, 0.0, 0.0, 1.0)  # noqa: E731
    return dict(
        key="circle",
        title="Unit disk — uniform size field",
        fd=fd,
        fh=None,
        h0=0.12,
        bbox=(-1.0, -1.0, 1.0, 1.0),
    )


def _domain_rectangle():
    fd = lambda p: _drectangle(p, -1.0, 1.0, -0.6, 0.6)  # noqa: E731
    return dict(
        key="rectangle",
        title="Rectangle — uniform size field",
        fd=fd,
        fh=None,
        h0=0.1,
        bbox=(-1.0, -0.6, 1.0, 0.6),
    )


def _domain_annulus():
    fd = lambda p: _ddiff(_dcircle(p, 0, 0, 1.0), _dcircle(p, 0, 0, 0.4))  # noqa: E731
    # Graded: finer near the inner hole.
    def fh(p):
        return 0.06 + 0.30 * (np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2) - 0.4)
    return dict(
        key="annulus",
        title="Annulus — size field refined toward inner ring",
        fd=fd,
        fh=fh,
        h0=0.06,
        bbox=(-1.0, -1.0, 1.0, 1.0),
    )


DOMAINS = [_domain_circle, _domain_rectangle, _domain_annulus]


def _serialize_frame(k: int, p: np.ndarray, t: np.ndarray) -> dict:
    if len(t):
        q_min, q_mean, _ = mesh_quality(p, t)
    else:
        q_min, q_mean = 0.0, 0.0
    return {
        "iter": int(k),
        "p": np.round(p, COORD_DP).tolist(),
        "t": t.astype(int).tolist(),
        "q_min": round(float(q_min), 4),
        "q_mean": round(float(q_mean), 4),
    }


def _decimate(frames: list[dict], cap: int) -> list[dict]:
    """Keep the first frame, the last frame, and an even sample between."""
    if len(frames) <= cap:
        return frames
    idx = np.linspace(0, len(frames) - 1, cap).round().astype(int)
    idx = sorted(set(idx.tolist()))
    return [frames[i] for i in idx]


def run_domain(spec: dict) -> dict:
    frames: list[dict] = []

    def collector(k, p, t):
        frames.append(_serialize_frame(k, p, t))

    p, t = distmesh2d(
        fd=spec["fd"],
        fh=spec["fh"],
        h0=spec["h0"],
        bbox=spec["bbox"],
        seed=0,
        on_iter=collector,
    )
    # Append the final cleaned mesh as the closing frame.
    frames.append(_serialize_frame(-1, p, t))
    frames = _decimate(frames, MAX_FRAMES)

    # Topology dedupe: ``t`` only changes at a Delaunay retriangulation, so
    # store it only when it differs from the previous frame; ``None`` means
    # "reuse the previous frame's triangulation". Cuts payload ~90%.
    prev_t = None
    for fr in frames:
        if fr["t"] == prev_t:
            fr["t"] = None
        else:
            prev_t = fr["t"]

    q_min, q_mean, _ = mesh_quality(p, t)
    return {
        "key": spec["key"],
        "title": spec["title"],
        "h0": spec["h0"],
        "bbox": list(spec["bbox"]),
        "n_nodes": int(len(p)),
        "n_elements": int(len(t)),
        "q_min": round(float(q_min), 4),
        "q_mean": round(float(q_mean), 4),
        "frames": frames,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    for factory in DOMAINS:
        spec = factory()
        print(f"[gen] {spec['key']} … ", end="", flush=True)
        data = run_domain(spec)
        out = OUT_DIR / f"{spec['key']}.json"
        out.write_text(json.dumps(data, separators=(",", ":")))
        manifest.append({
            "key": data["key"],
            "title": data["title"],
            "n_frames": len(data["frames"]),
            "n_nodes": data["n_nodes"],
            "n_elements": data["n_elements"],
            "q_min": data["q_min"],
            "q_mean": data["q_mean"],
        })
        print(
            f"{len(data['frames'])} frames, {data['n_nodes']} nodes, "
            f"q_min={data['q_min']}, q_mean={data['q_mean']} → {out.name}"
        )
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[gen] wrote manifest.json with {len(manifest)} domains")


if __name__ == "__main__":
    main()
