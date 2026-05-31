#!/usr/bin/env python3
"""Native-SDF benchmark: Python distmesh+raster vs Rust distmesh+raster (native).

Same boundary corpus. SDF rasterised once; Python path runs scipy
interpolator callback per SDF eval; Rust native path runs interp in Rust
(zero Python callback during inner loop).
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
DOMAINS = ROOT.parent / "ADMESH-Domains" / "registry_data" / "meshes"
sys.path.insert(0, str(ROOT))


def read_fort14_nodes(path):
    with path.open() as f:
        f.readline()
        ne_nn = f.readline().split()
        nn = int(ne_nn[1])
        xs = np.empty((nn, 2), dtype=np.float64)
        for i in range(nn):
            parts = f.readline().split()
            xs[i, 0] = float(parts[1]); xs[i, 1] = float(parts[2])
    return xs


def rasterise_sdf(boundary, bbox, res=300):
    import scipy.ndimage
    from shapely.geometry import Polygon
    import shapely
    xmin, ymin, xmax, ymax = bbox
    xs = np.linspace(xmin, xmax, res)
    ys = np.linspace(ymin, ymax, res)
    XX, YY = np.meshgrid(xs, ys)
    flat = np.column_stack([XX.ravel(), YY.ravel()])
    poly = Polygon(boundary)
    if not poly.is_valid:
        poly = poly.buffer(0)
    shapely.prepare(poly)
    sp = shapely.points(flat[:, 0], flat[:, 1])
    inside = shapely.contains(poly, sp).reshape(XX.shape)
    dx = (xmax-xmin)/(res-1); dy = (ymax-ymin)/(res-1)
    cell = (dx+dy)/2
    dt_in = scipy.ndimage.distance_transform_edt(inside) * cell
    dt_out = scipy.ndimage.distance_transform_edt(~inside) * cell
    return xs, ys, (dt_out - dt_in)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--niter", type=int, default=25)
    ap.add_argument("--n-target", type=int, default=2000)
    args = ap.parse_args()

    from scipy.spatial import ConvexHull
    import scipy.interpolate
    from admesh._stages.distmesh import distmesh2d as py_distmesh
    from admesh._stages.quality import mesh_quality as py_q
    import admesh_rs

    meshes = sorted(DOMAINS.glob("*.14"), key=lambda p: p.stat().st_size)
    if args.limit:
        meshes = meshes[:args.limit]

    print(f"Native-SDF bench: {len(meshes)} meshes, niter={args.niter}")
    print("-"*110)
    print(f"{'mesh':45s} {'h0':>10s} {'py_s':>8s} {'rs_s':>8s} {'speedup':>8s} "
          f"{'py_n':>7s} {'rs_n':>7s} {'py_q':>6s} {'rs_q':>6s}")
    print("-"*110)

    results = []
    for path in meshes:
        try:
            xy = read_fort14_nodes(path)
            hull = ConvexHull(xy)
            boundary = xy[hull.vertices]
            bbox = (float(xy[:,0].min()), float(xy[:,1].min()),
                    float(xy[:,0].max()), float(xy[:,1].max()))
            diag = ((bbox[2]-bbox[0])**2 + (bbox[3]-bbox[1])**2)**0.5
            poly_area = (bbox[2]-bbox[0])*(bbox[3]-bbox[1]) * 0.6
            h0 = (poly_area / (args.n_target * (3**0.5)/2)) ** 0.5
            h0 = max(h0, diag/200)
            bbox4 = (bbox[0]-0.02*diag, bbox[1]-0.02*diag,
                     bbox[2]+0.02*diag, bbox[3]+0.02*diag)

            xs_g, ys_g, sdf_g = rasterise_sdf(boundary, bbox4)
            interp = scipy.interpolate.RegularGridInterpolator(
                (ys_g, xs_g), sdf_g, method='linear',
                bounds_error=False, fill_value=1.0)
            def py_sdf(pts):
                return interp((pts[:,1], pts[:,0]))

            # Python path
            t0 = time.perf_counter()
            p_py, t_py = py_distmesh(
                fd=py_sdf, fh=None, h0=h0, bbox=bbox4, pfix=None,
                niter=args.niter, seed=42)
            py_dt = time.perf_counter()-t0
            _, mean_q, _ = py_q(p_py, t_py) if len(t_py) else (0,0,[])

            # Rust native path (raster grid passed in; no Python SDF callback)
            t0 = time.perf_counter()
            p_rs, t_rs = admesh_rs.distmesh2d_native_rs(
                xs_g.astype(np.float64), ys_g.astype(np.float64),
                sdf_g.astype(np.float64),
                h0, bbox4, None,
                1e-3, 0.1, 1.2, 0.2, 1e-3, args.niter, 42)
            rs_dt = time.perf_counter()-t0
            _, rs_mean_q, _ = admesh_rs.mesh_quality_rs(
                p_rs.astype(np.float64), t_rs.astype(np.int64))

            speedup = py_dt/rs_dt if rs_dt > 0 else None
            print(f"{path.name:45s} {h0:>10.4g} {py_dt:>8.4f} {rs_dt:>8.4f} "
                  f"{speedup:>8.2f} {len(p_py):>7d} {len(p_rs):>7d} "
                  f"{mean_q:>6.4f} {rs_mean_q:>6.4f}")
            results.append({
                "mesh": path.name, "h0": h0,
                "py_time_s": py_dt, "rs_time_s": rs_dt,
                "py_nodes": len(p_py), "rs_nodes": len(p_rs),
                "py_mean_q": float(mean_q), "rs_mean_q": float(rs_mean_q),
                "speedup": speedup})
        except Exception as e:
            print(f"{path.name:45s} ERR: {type(e).__name__}: {str(e)[:60]}")

    out = ROOT / "admesh-rs" / "bench-native-sdf-results.csv"
    if results:
        with out.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=results[0].keys())
            w.writeheader(); w.writerows(results)
        print(f"\nWrote: {out}")
        sp = [r["speedup"] for r in results if r["speedup"]]
        if sp:
            print(f"Geo-mean native-SDF speedup: {np.exp(np.mean(np.log(sp))):.2f}x "
                  f"(n={len(sp)}, min={min(sp):.2f}, max={max(sp):.2f})")


if __name__ == "__main__":
    main()
