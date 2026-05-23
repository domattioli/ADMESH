#!/usr/bin/env python3
"""Full-pipeline benchmark: Python / Rust / C++ × {distmesh, smooth, quality}.

For each real-world ADMESH-Domains mesh:
  1. Extract boundary (convex hull) → rasterised SDF.
  2. distmesh stage: Python admesh, Rust admesh-rs (native), C++ admesh-cpp.
  3. CHILmesh angle-based smoother (Python only — same impl, different input).
  4. Element quality: Python admesh, Rust admesh-rs.

Reports per-stage timings + speedups + final quality.

Note on "size" column: file size of source .14 (informational only — regen
runs at fixed `h0` chosen for `n_target≈2000` regardless of source mesh size).
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
DOMAINS = ROOT.parent / "ADMESH-Domains" / "registry_data" / "meshes"
CPP_BIN = ROOT / "admesh-cpp" / "distmesh"
CPP_CHILMESH_BIN = ROOT / "admesh-cpp" / "chilmesh"
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


def run_cpp(xs, ys, sdf_g, h0, bbox, niter, seed=42):
    """Drive admesh-cpp via stdin protocol."""
    nx, ny = len(xs), len(ys)
    lines = [
        f"{niter} {h0} {bbox[0]} {bbox[1]} {bbox[2]} {bbox[3]} {nx} {ny} {seed}",
        " ".join(f"{v:.10g}" for v in xs),
        " ".join(f"{v:.10g}" for v in ys),
    ]
    for j in range(ny):
        lines.append(" ".join(f"{v:.10g}" for v in sdf_g[j]))
    payload = "\n".join(lines) + "\n"
    try:
        result = subprocess.run(
            [str(CPP_BIN)], input=payload, capture_output=True,
            text=True, timeout=60)
        if result.returncode != 0:
            return None
        parts = result.stdout.split()
        return {
            "time_s": float(parts[0]),
            "n_nodes": int(parts[1]),
            "n_elems": int(parts[2]),
            "mean_q": float(parts[3]),
        }
    except Exception as e:
        return {"error": str(e)[:60]}


def run_cpp_chilmesh(nodes, elems, n_iter=20, omega=0.5):
    """Drive admesh-cpp/chilmesh via stdin protocol."""
    if not CPP_CHILMESH_BIN.exists():
        return {"error": "chilmesh binary not found"}
    n_nodes = len(nodes)
    n_elems_c = len(elems)
    lines = [f"{n_nodes} {n_elems_c} {n_iter} {omega}"]
    for xy in nodes:
        lines.append(f"{float(xy[0]):.10g} {float(xy[1]):.10g}")
    for tri in elems:
        lines.append(f"{int(tri[0])} {int(tri[1])} {int(tri[2])}")
    payload = "\n".join(lines) + "\n"
    try:
        result = subprocess.run(
            [str(CPP_CHILMESH_BIN)], input=payload, capture_output=True,
            text=True, timeout=120)
        if result.returncode != 0:
            return {"error": result.stderr[:80]}
        parts = result.stdout.split()
        return {
            "smooth_time_s": float(parts[0]),
            "quality_time_s": float(parts[1]),
            "n_nodes": int(parts[2]),
            "n_elems": int(parts[3]),
            "mean_q": float(parts[4]),
            "min_q": float(parts[5]),
        }
    except Exception as e:
        return {"error": str(e)[:80]}


def chilmesh_smooth_and_quality(nodes, elems, n_iter=20):
    """Run CHILmesh angle-based smoother + quality."""
    try:
        import chilmesh
        # CHILmesh API: connectivity = (N_elem, 3) int, points = (N_node, 2|3) float.
        # 1-based indexing internally per MATLAB origin; convert.
        pts = np.asarray(nodes, dtype=float)
        if pts.shape[1] == 2:
            pts = np.column_stack([pts, np.zeros(len(pts))])
        conn = np.asarray(elems, dtype=int)  # CHILmesh uses 0-based
        m = chilmesh.CHILmesh(connectivity=conn, points=pts, compute_layers=True)
        t0 = time.perf_counter()
        m.angle_based_smoother(n_iter=n_iter, omega=0.5)
        smooth_dt = time.perf_counter() - t0

        t0 = time.perf_counter()
        q, *_ = m.elem_quality(quality_type='skew')
        quality_dt = time.perf_counter() - t0
        return {
            "smooth_time_s": smooth_dt,
            "smooth_iters": n_iter,
            "quality_time_s": quality_dt,
            "mean_q": float(np.mean(q)) if len(q) else 0.0,
            "min_q": float(np.min(q)) if len(q) else 0.0,
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:80]}"}


def bench_one(path, niter, n_target):
    from scipy.spatial import ConvexHull
    import scipy.interpolate
    from admesh._stages.distmesh import distmesh2d as py_distmesh
    from admesh._stages.quality import mesh_quality as py_q
    import admesh_rs

    xy = read_fort14_nodes(path)
    hull = ConvexHull(xy)
    boundary = xy[hull.vertices]
    bbox = (float(xy[:, 0].min()), float(xy[:, 1].min()),
            float(xy[:, 0].max()), float(xy[:, 1].max()))
    diag = ((bbox[2]-bbox[0])**2 + (bbox[3]-bbox[1])**2)**0.5
    poly_area = (bbox[2]-bbox[0])*(bbox[3]-bbox[1]) * 0.6
    h0 = (poly_area / (n_target * (3**0.5)/2)) ** 0.5
    h0 = max(h0, diag/200)
    bbox4 = (bbox[0]-0.02*diag, bbox[1]-0.02*diag,
             bbox[2]+0.02*diag, bbox[3]+0.02*diag)

    xs_g, ys_g, sdf_g = rasterise_sdf(boundary, bbox4)
    interp = scipy.interpolate.RegularGridInterpolator(
        (ys_g, xs_g), sdf_g, method='linear',
        bounds_error=False, fill_value=1.0)
    def py_sdf(pts):
        return interp((pts[:, 1], pts[:, 0]))

    result = {
        "mesh": path.name,
        "file_size_mb": round(path.stat().st_size / (1024*1024), 2),
        "h0": h0,
    }

    # ── Python distmesh ────────────────────────────────────────────────
    t0 = time.perf_counter()
    p_py, t_py = py_distmesh(
        fd=py_sdf, fh=None, h0=h0, bbox=bbox4, pfix=None,
        niter=niter, seed=42)
    py_dt = time.perf_counter() - t0
    py_min_q, py_mean_q, _ = py_q(p_py, t_py) if len(t_py) else (0,0,[])

    # ── Rust distmesh (native SDF) ─────────────────────────────────────
    t0 = time.perf_counter()
    p_rs, t_rs = admesh_rs.distmesh2d_native_rs(
        xs_g.astype(np.float64), ys_g.astype(np.float64),
        sdf_g.astype(np.float64),
        h0, bbox4, None,
        1e-3, 0.1, 1.2, 0.2, 1e-3, niter, 42)
    rs_dt = time.perf_counter() - t0
    _, rs_mean_q, _ = admesh_rs.mesh_quality_rs(
        p_rs.astype(np.float64), t_rs.astype(np.int64))

    # ── C++ distmesh (delaunator + OpenMP SDF) ─────────────────────────
    cpp = run_cpp(xs_g, ys_g, sdf_g, h0, bbox4, niter)

    result.update({
        "py_distmesh_s": round(py_dt, 4),
        "rs_distmesh_s": round(rs_dt, 4),
        "cpp_distmesh_s": round(cpp["time_s"], 4) if cpp and "time_s" in cpp else None,
        "py_nodes": len(p_py),
        "rs_nodes": len(p_rs),
        "cpp_nodes": cpp["n_nodes"] if cpp and "n_nodes" in cpp else None,
        "py_mean_q": round(float(py_mean_q), 4),
        "rs_mean_q": round(float(rs_mean_q), 4),
        "cpp_mean_q": round(cpp["mean_q"], 4) if cpp and "mean_q" in cpp else None,
        "rs_vs_py": round(py_dt / rs_dt, 2) if rs_dt > 0 else None,
        "cpp_vs_py": round(py_dt / cpp["time_s"], 2) if cpp and cpp.get("time_s",0) > 0 else None,
    })

    # ── CHILmesh smooth + quality (Python) ─────────────────────────────
    smooth = chilmesh_smooth_and_quality(p_rs, t_rs, n_iter=20)
    if "error" not in smooth:
        result.update({
            "chil_smooth_s": round(smooth["smooth_time_s"], 4),
            "chil_quality_s": round(smooth["quality_time_s"], 4),
            "chil_mean_q": round(smooth["mean_q"], 4),
            "chil_min_q": round(smooth["min_q"], 4),
        })
    else:
        result["chil_err"] = smooth["error"]

    # ── C++ chilmesh smooth + quality ──────────────────────────────────
    cpp_chil = run_cpp_chilmesh(p_rs, t_rs, n_iter=20, omega=0.5)
    if "error" not in cpp_chil:
        result.update({
            "cpp_chil_smooth_s": round(cpp_chil["smooth_time_s"], 4),
            "cpp_chil_quality_s": round(cpp_chil["quality_time_s"], 4),
            "cpp_chil_mean_q": round(cpp_chil["mean_q"], 4),
            "cpp_chil_min_q": round(cpp_chil["min_q"], 4),
        })
    else:
        result["cpp_chil_err"] = cpp_chil["error"]

    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--largest", type=int, default=None,
                    help="bench only N largest meshes by file size")
    ap.add_argument("--niter", type=int, default=25)
    ap.add_argument("--n-target", type=int, default=2000)
    args = ap.parse_args()

    if not CPP_BIN.exists():
        print(f"ERROR: C++ distmesh not built. Run: cd admesh-cpp && g++ -std=c++17 -O3 distmesh.cpp -o distmesh")
        return 1
    if not CPP_CHILMESH_BIN.exists():
        print(f"ERROR: C++ chilmesh not built. Run: cd admesh-cpp && g++ -std=c++17 -O3 -march=native chilmesh.cpp -o chilmesh")

    meshes = sorted(DOMAINS.glob("*.14"), key=lambda p: p.stat().st_size)
    if args.largest:
        meshes = meshes[-args.largest:]
    if args.limit:
        meshes = meshes[:args.limit]

    print(f"Pipeline bench: {len(meshes)} meshes, niter={args.niter}, n_target={args.n_target}")
    print("=" * 150)
    hdr = (f"{'mesh':35s} {'fileMB':>7s} {'py_s':>7s} {'rs_s':>7s} {'cpp_s':>7s} "
           f"{'rs/py':>6s} {'cpp/py':>7s} "
           f"{'py_chil_s':>10s} {'cpp_chil_s':>11s} {'chil_sp':>8s} "
           f"{'py_q':>6s} {'rs_q':>6s} {'cpp_q':>6s} "
           f"{'pychil_q':>9s} {'cppchil_q':>10s}")
    print(hdr)
    print("-" * 150)

    results = []
    for path in meshes:
        try:
            r = bench_one(path, args.niter, args.n_target)
            results.append(r)
            py_chil_s = r.get('chil_smooth_s', '?')
            cpp_chil_s = r.get('cpp_chil_smooth_s', '?')
            chil_sp = (round(r['chil_smooth_s'] / r['cpp_chil_smooth_s'], 1)
                       if r.get('chil_smooth_s') and r.get('cpp_chil_smooth_s') else '?')
            print(f"{path.name:35s} {r['file_size_mb']:>7.2f} "
                  f"{r['py_distmesh_s']:>7.3f} {r['rs_distmesh_s']:>7.3f} "
                  f"{str(r.get('cpp_distmesh_s','?')):>7s} "
                  f"{str(r.get('rs_vs_py','?')):>6s} {str(r.get('cpp_vs_py','?')):>7s} "
                  f"{str(py_chil_s):>10s} {str(cpp_chil_s):>11s} {str(chil_sp):>8s} "
                  f"{r['py_mean_q']:>6.3f} {r['rs_mean_q']:>6.3f} "
                  f"{str(r.get('cpp_mean_q','?')):>6s} "
                  f"{str(r.get('chil_mean_q','?')):>9s} "
                  f"{str(r.get('cpp_chil_mean_q','?')):>10s}")
        except Exception as e:
            print(f"{path.name:35s} ERR: {type(e).__name__}: {str(e)[:80]}")

    out = ROOT / "admesh-rs" / "bench-pipeline-results.csv"
    if results:
        all_keys = sorted({k for r in results for k in r.keys()})
        with out.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=all_keys)
            w.writeheader()
            w.writerows(results)
        print(f"\nWrote: {out}")

        sps_rs = [r["rs_vs_py"] for r in results if r.get("rs_vs_py")]
        sps_cpp = [r["cpp_vs_py"] for r in results if r.get("cpp_vs_py")]
        if sps_rs:
            print(f"distmesh geo-mean speedup: Rust {np.exp(np.mean(np.log(sps_rs))):.2f}× "
                  f"| C++ {np.exp(np.mean(np.log(sps_cpp))):.2f}×" if sps_cpp else
                  f"distmesh geo-mean speedup: Rust {np.exp(np.mean(np.log(sps_rs))):.2f}×")


if __name__ == "__main__":
    main()
