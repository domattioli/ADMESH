#!/usr/bin/env python3
"""Generate truss-solver animation frames for the GitHub Pages demo (#118).

Runs the canonical DistMesh driver (:func:`admesh._stages.distmesh.distmesh2d`)
on three graded domains, capturing one keyframe per Delaunay retriangulation
via the ``on_iter`` callback. Frames are written as compact JSON to
``docs/demo/data/<domain>.json`` for client-side playback.

Phase-1 of spec-023: no Pyodide, no in-browser Python — the page replays
pre-baked frames on a Canvas2D renderer.

Usage
-----
    python scripts/gen_demo_frames.py

Output
------
    docs/demo/data/l_shape.json
    docs/demo/data/seamount.json
    docs/demo/data/annulus.json
    docs/demo/data/manifest.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from admesh._stages.distmesh import distmesh2d
from admesh._stages.domains import _sdf_l_shape
from admesh._stages.quality import mesh_quality
from admesh._fast_sdf import fast_sdf

OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "demo" / "data"
BENCHMARKS_DIR = Path(__file__).resolve().parent.parent / "benchmarks" / "data"

MAX_FRAMES = 60
COORD_DP = 3


def _dcircle(p, cx, cy, r):
    return np.sqrt((p[:, 0] - cx) ** 2 + (p[:, 1] - cy) ** 2) - r


def _ddiff(a, b):
    return np.maximum(a, -b)


def _cross_shelf_bathymetry(x, y):
    """Synthetic cross-shelf + seamount bathymetry (normalized coords)."""
    z_shelf = -50.0 * (x + 1.0)
    seamount = 4.0 * np.exp(-((x + 0.8) ** 2 + y ** 2) / 0.08)
    return z_shelf + seamount


# --- demo domain definitions -----------------------------------------------

def _domain_l_shape():
    """L-shape with graded fh refining near the re-entrant corner at (0, 0)."""
    def fh(p):
        d = np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2)
        return np.clip(0.05 + 0.22 * np.tanh(d / 0.35), 0.05, 0.24)

    pfix = np.array([[-1., -1.], [1., -1.], [1., 0.], [0., 0.], [0., 1.], [-1., 1.]])
    return dict(
        key="l_shape",
        title="L-shape — refined at re-entrant corner",
        fd=_sdf_l_shape,
        fh=fh,
        h0=0.05,
        bbox=(-1.0, -1.0, 1.0, 1.0),
        pfix=pfix,
    )


def _domain_seamount():
    """Coastal notch domain with bathymetry-graded size field."""
    d = json.load(open(BENCHMARKS_DIR / "notch_seamount_domain.json"))
    rings = [np.array(r) for r in d["rings"]]
    bbox = tuple(d["bbox"])
    fd = fast_sdf(rings)

    def fh(p):
        z = _cross_shelf_bathymetry(p[:, 0], p[:, 1])
        depth = np.clip(-z, 0.0, None)
        return np.clip(0.07 + 0.22 * (depth / 100.0), 0.07, 0.27)

    return dict(
        key="seamount",
        title="Seamount — bathymetry-graded coastal mesh",
        fd=fd,
        fh=fh,
        h0=0.07,
        bbox=bbox,
    )


def _domain_annulus():
    """Annulus with fh refined toward the inner hole."""
    fd = lambda p: _ddiff(_dcircle(p, 0, 0, 1.0), _dcircle(p, 0, 0, 0.4))  # noqa: E731

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


DOMAINS = [_domain_l_shape, _domain_seamount, _domain_annulus]


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
    """Keep first, last, and an even sample in between."""
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
        pfix=spec.get("pfix"),
        seed=0,
        on_iter=collector,
    )
    frames.append(_serialize_frame(-1, p, t))
    frames = _decimate(frames, MAX_FRAMES)

    # Topology dedupe: store t only when topology changes; None = reuse prev.
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
