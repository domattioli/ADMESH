#!/usr/bin/env python3
"""Benchmark WNAT domain: real Numba measurement + C++ projection."""
import sys, time, pathlib, json
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import admesh
from admesh._stages import mesh_size as mesh_size_stage

np.random.seed(0)

# Load WNAT domain
wnat_json = pathlib.Path(__file__).parent / "data" / "wnat_onur_boundary.json"
if not wnat_json.exists():
    print(f"WNAT domain not found at {wnat_json}")
    print("Falling back to MVP domains...")
    sys.exit(1)

with open(wnat_json) as f:
    wnat_data = json.load(f)

domain = admesh.Domain(
    vertices=np.array(wnat_data["vertices"]),
    boundaries=tuple(
        admesh.BoundarySegment(
            node_indices=np.array(b["node_indices"], dtype=np.int64),
            bc_type=b.get("bc_type", 0)
        )
        for b in wnat_data.get("boundaries", [])
    ),
    bathymetry=np.array(wnat_data.get("bathymetry")) if wnat_data.get("bathymetry") else None
)

print("ADMESH WNAT Benchmark (144-ring Western North Atlantic)")
print(f"Domain: {domain.vertices.shape[0]} boundary vertices")
print()

# Time WNAT triangulation
h_min, h_max, g = 0.05, 0.10, 0.10

print(f"Parameters: h_min={h_min}, h_max={h_max}, g={g}")
print()

# Stage 1: Domain load + SDF build
print("Stage 1: domain load + SDF build...", end=" ", flush=True)
t_s1_start = time.perf_counter()
try:
    from admesh._stages.distance import build_sdf
    sdf = build_sdf(domain)
    t_s1 = time.perf_counter() - t_s1_start
    print(f"{t_s1:.3f}s")
except Exception as e:
    print(f"ERROR: {e}")
    t_s1 = None

# Stage 2: SDF grid eval (expensive)
print("Stage 2: SDF grid eval...", end=" ", flush=True)
t_s2_start = time.perf_counter()
try:
    h0 = 0.02
    from admesh._stages.distance import eval_sdf_grid
    grid, hgrid = eval_sdf_grid(domain, sdf, h0)
    t_s2 = time.perf_counter() - t_s2_start
    print(f"{t_s2:.3f}s")
except Exception as e:
    print(f"ERROR: {e}")
    t_s2 = None

# Full pipeline
print("Full pipeline (triangulate)...", end=" ", flush=True)
t_total_start = time.perf_counter()
try:
    mesh = admesh.triangulate(domain, h_max=h_max, h_min=h_min)
    t_total = time.perf_counter() - t_total_start
    print(f"{t_total:.3f}s")
except Exception as e:
    print(f"ERROR: {e}")
    t_total = None

print()
if t_total:
    print(f"Result: {mesh.nodes.shape[0]} nodes, {mesh.elements.shape[0]} elements")
    print(f"Quality: min={np.min(mesh.quality):.3f}, mean={np.mean(mesh.quality):.3f}, std={np.std(mesh.quality):.3f}")
    print()

    # Project C++ at 1.5× speedup
    t_cpp = t_total / 1.5
    print("| Measurement | Numba (measured) | C++ (projected 1.5×) |")
    print("|---|---|---|")
    print(f"| Total time | {t_total:.3f}s | {t_cpp:.3f}s |")
    print(f"| Speedup | 1.0× | 1.50× |")
    print()
    if t_s1:
        print(f"Stage 1 (domain + SDF build): {t_s1:.3f}s")
    if t_s2:
        print(f"Stage 2 (SDF grid eval): {t_s2:.3f}s")
