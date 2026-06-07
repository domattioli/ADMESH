#!/usr/bin/env python3
"""Benchmark: ADMESH Python (faithful port) vs Rust port — same domain, same h0.

For each real-world mesh in ADMESH-Domains/registry_data/meshes/*.14:
  1. Read mesh, extract outer boundary as a polygon.
  2. Build SDF (point-in-polygon + boundary distance) via shapely.
  3. Regenerate mesh with admesh.distmesh.distmesh2d (Python) and
     admesh_rs.distmesh2d_rs (Rust). Same h0, same seed, same niter.
  4. Record wall-clock, node count, mean quality.

Usage:
    python scripts/bench_vs_python.py [--limit N] [--niter 50] [--n-target 2000]

Outputs CSV at admesh-rs/bench-results.csv + summary table.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent  # /home/user/ADMESH
DOMAINS = ROOT.parent / "ADMESH-Domains" / "registry_data" / "meshes"

sys.path.insert(0, str(ROOT))


def read_fort14_nodes(path: Path) -> np.ndarray:
    """Lenient fort.14 node-only reader. Handles tri/quad/mixed.

    Format: line 1 = title; line 2 = "NE NN"; next NN lines = "id x y z".
    """
    with path.open() as f:
        f.readline()  # title
        ne_nn = f.readline().split()
        ne, nn = int(ne_nn[0]), int(ne_nn[1])
        xs = np.empty((nn, 2), dtype=np.float64)
        for i in range(nn):
            parts = f.readline().split()
            xs[i, 0] = float(parts[1])
            xs[i, 1] = float(parts[2])
    return xs


def read_fort14_boundary(path: Path) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """Extract outer boundary via convex hull of all nodes."""
    from scipy.spatial import ConvexHull
    xy = read_fort14_nodes(path)
    bbox = (float(xy[:, 0].min()), float(xy[:, 1].min()),
            float(xy[:, 0].max()), float(xy[:, 1].max()))
    hull = ConvexHull(xy)
    boundary = xy[hull.vertices]
    return boundary, bbox


def build_sdf_from_polygon(boundary_xy: np.ndarray):
    """Return (sdf_fn, bbox) — negative inside polygon, positive outside."""
    from shapely.geometry import Polygon, Point
    import shapely
    poly = Polygon(boundary_xy)
    if not poly.is_valid:
        poly = poly.buffer(0)
    shapely.prepare(poly)
    coast = poly.exterior
    shapely.prepare(coast)

    def sdf(pts: np.ndarray) -> np.ndarray:
        sp = shapely.points(pts[:, 0], pts[:, 1])
        inside = shapely.contains(poly, sp)
        dist = shapely.distance(sp, coast)
        return np.where(inside, -dist, dist)

    return sdf, poly.bounds


def bench_one(path: Path, niter: int, n_target: int) -> dict:
    boundary, _ = read_fort14_boundary(path)
    sdf, bounds = build_sdf_from_polygon(boundary)
    xmin, ymin, xmax, ymax = bounds
    diag = ((xmax - xmin) ** 2 + (ymax - ymin) ** 2) ** 0.5

    # Pick h0 so initial-lattice point count ≈ 2 × n_target (rejection halves it).
    # Lattice density = 2 / (h0² · sqrt(3)); we want lattice ≈ 2·n_target inside
    # poly with area A ≈ (bbox area) × fill_factor. Approximate fill = 0.6.
    poly_area = (xmax - xmin) * (ymax - ymin) * 0.6
    h0 = (poly_area / (n_target * (3 ** 0.5) / 2)) ** 0.5
    h0 = max(h0, diag / 200)  # cap minimum

    bbox4 = (xmin - 0.02 * diag, ymin - 0.02 * diag,
             xmax + 0.02 * diag, ymax + 0.02 * diag)

    result = {
        "mesh": path.name,
        "h0": h0,
        "diag": diag,
        "py_time_s": None,
        "py_nodes": None,
        "py_elems": None,
        "py_mean_q": None,
        "rs_time_s": None,
        "rs_nodes": None,
        "rs_elems": None,
        "rs_mean_q": None,
        "speedup": None,
    }

    # ── Python ─────────────────────────────────────────────────────────
    from admesh._stages.distmesh import distmesh2d as py_distmesh2d
    from admesh._stages.quality import mesh_quality as py_quality
    try:
        t0 = time.perf_counter()
        p_py, t_py = py_distmesh2d(
            fd=sdf, fh=None, h0=h0, bbox=bbox4, pfix=None,
            niter=niter, seed=42,
        )
        py_dt = time.perf_counter() - t0
        if len(p_py) >= 3 and len(t_py):
            min_q, mean_q, _ = py_quality(p_py, t_py)
        else:
            mean_q = 0.0
        result.update({
            "py_time_s": round(py_dt, 4),
            "py_nodes": len(p_py),
            "py_elems": len(t_py),
            "py_mean_q": round(float(mean_q), 4),
        })
    except Exception as e:
        result["py_time_s"] = f"ERR: {type(e).__name__}"

    # ── Rust ───────────────────────────────────────────────────────────
    import admesh_rs
    try:
        t0 = time.perf_counter()
        p_rs, t_rs = admesh_rs.distmesh2d_rs(
            sdf, None, h0, bbox4, None,
            1e-3, 0.1, 1.2, 0.2, 1e-3, niter, 42,
        )
        rs_dt = time.perf_counter() - t0
        if len(p_rs) >= 3 and len(t_rs):
            min_q, mean_q, _ = admesh_rs.mesh_quality_rs(
                p_rs.astype(np.float64), t_rs.astype(np.int64))
        else:
            mean_q = 0.0
        result.update({
            "rs_time_s": round(rs_dt, 4),
            "rs_nodes": len(p_rs),
            "rs_elems": len(t_rs),
            "rs_mean_q": round(float(mean_q), 4),
        })
    except Exception as e:
        result["rs_time_s"] = f"ERR: {type(e).__name__}: {str(e)[:60]}"

    if isinstance(result["py_time_s"], float) and isinstance(result["rs_time_s"], float):
        if result["rs_time_s"] > 0:
            result["speedup"] = round(result["py_time_s"] / result["rs_time_s"], 2)

    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="benchmark only first N meshes (sorted by size)")
    ap.add_argument("--niter", type=int, default=50,
                    help="distmesh iterations per run (default 50 — short)")
    ap.add_argument("--n-target", type=int, default=2000,
                    help="target node count (default 2000)")
    args = ap.parse_args()

    meshes = sorted(DOMAINS.glob("*.14"), key=lambda p: p.stat().st_size)
    if args.limit:
        meshes = meshes[: args.limit]
    print(f"Benchmarking {len(meshes)} meshes (niter={args.niter}, target ≈{args.n_target} nodes)")
    print("-" * 110)
    print(f"{'mesh':45s} {'h0':>10s} {'py_s':>8s} {'rs_s':>8s} {'speedup':>8s} "
          f"{'py_n':>7s} {'rs_n':>7s} {'py_q':>6s} {'rs_q':>6s}")
    print("-" * 110)

    results = []
    for m in meshes:
        r = bench_one(m, args.niter, args.n_target)
        results.append(r)
        print(f"{m.name:45s} {r['h0']:>10.4g} "
              f"{str(r['py_time_s']):>8s} {str(r['rs_time_s']):>8s} "
              f"{str(r['speedup']):>8s} "
              f"{str(r['py_nodes']):>7s} {str(r['rs_nodes']):>7s} "
              f"{str(r['py_mean_q']):>6s} {str(r['rs_mean_q']):>6s}")

    out = ROOT / "admesh-rs" / "bench-results.csv"
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"\nWrote: {out}")

    # Summary
    speedups = [r["speedup"] for r in results if isinstance(r["speedup"], float)]
    if speedups:
        print(f"\nGeo-mean speedup (Rust vs Python): {np.exp(np.mean(np.log(speedups))):.2f}x "
              f"(n={len(speedups)}, min={min(speedups):.2f}, max={max(speedups):.2f})")


if __name__ == "__main__":
    main()
