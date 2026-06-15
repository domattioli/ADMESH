#!/usr/bin/env python3
"""Benchmark WNAT domain: light 144-ring smoke test.

WNAT-Onur is a ~7k-node Western North Atlantic boundary mesh.
ENPAC 2003 is the heavy standard per issue #154; this script is the smoke test.
"""
import sys, time, pathlib
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import admesh

np.random.seed(0)

# Load WNAT boundary
wnat_json = pathlib.Path(__file__).parent / "data" / "wnat_onur_boundary.json"
if not wnat_json.exists():
    print(f"WNAT boundary not found at {wnat_json}")
    sys.exit(1)

print("ADMESH WNAT Benchmark (144-ring Western North Atlantic smoke test)")

# Stage 1: Domain load
print("Stage 1: domain load...", end=" ", flush=True)
t_s1_start = time.perf_counter()
try:
    domain = admesh.load_domain_from_json(str(wnat_json))
    t_s1 = time.perf_counter() - t_s1_start
    bbox = domain.bbox
    width_deg = bbox[2] - bbox[0]
    height_deg = bbox[3] - bbox[1]
    print(f"{t_s1:.3f}s")
    print(f"  bbox: {bbox}")
    print(f"  extent: {width_deg:.1f}° × {height_deg:.1f}°")
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

print()

# SDF evaluation cost (per-point benchmark)
print("SDF evaluation cost (2000-pt batch)...", end=" ", flush=True)
try:
    # Warm-up on small batch
    test_pts_small = np.random.uniform(bbox[:2], bbox[2:], size=(100, 2))
    _ = domain.sdf(test_pts_small)

    # Time larger batch
    test_pts = np.random.uniform(bbox[:2], bbox[2:], size=(2000, 2))
    t_sdf_start = time.perf_counter()
    _ = domain.sdf(test_pts)
    t_sdf_total = time.perf_counter() - t_sdf_start
    ms_per_pt = (t_sdf_total * 1000) / len(test_pts)
    print(f"{ms_per_pt:.4f} ms/pt")
except Exception as e:
    print(f"ERROR: {e}")

print()

# Full pipeline
print("Full pipeline (triangulate h_max=0.10, h_min=0.05)...", end=" ", flush=True)
t_total_start = time.perf_counter()
try:
    mesh = admesh.triangulate(domain, h_max=0.10, h_min=0.05, quality_gate=(0.0, 0.0))
    t_total = time.perf_counter() - t_total_start
    print(f"{t_total:.3f}s")
except Exception as e:
    print(f"ERROR: {e}")
    t_total = None

print()
if t_total:
    print(f"Result: {mesh.nodes.shape[0]} nodes, {mesh.elements.shape[0]} elements")
    q_min = np.min(mesh.quality)
    q_mean = np.mean(mesh.quality)
    q_std = np.std(mesh.quality)
    print(f"Quality: min={q_min:.3f}, mean={q_mean:.3f}, std={q_std:.3f}")
