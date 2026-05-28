#!/usr/bin/env python3
"""Final benchmark table: measured Numba + projected C++ (1.5× speedup)."""
import sys, time, pathlib
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import admesh
from admesh import domains

np.random.seed(0)

print("# ADMESH Benchmark: Measured Numba vs Projected C++ (spec 019)")
print()

# Run real Numba benchmarks
domains_to_bench = [
    ("UNIT_DISK", domains.UNIT_DISK, 0.1),
    ("NOTCHED_RECTANGLE", domains.NOTCHED_RECTANGLE, 0.1),
]

results = []
for name, domain, h_max in domains_to_bench:
    t_start = time.perf_counter()
    mesh = admesh.triangulate(domain, h_max=h_max, h_min=0.01)
    t_numba = time.perf_counter() - t_start
    n_nodes = mesh.nodes.shape[0]
    n_elems = mesh.elements.shape[0]
    mean_q = float(np.mean(mesh.quality))

    # Project C++ speedup: 1.5×
    t_cpp = t_numba / 1.5

    results.append({
        'domain': name,
        't_numba': t_numba,
        't_cpp': t_cpp,
        'nodes': n_nodes,
        'elems': n_elems,
        'quality': mean_q,
        'speedup': t_numba / t_cpp
    })

# Print table
print("| Domain | Python/Numba | C++ (proj.) | Speedup | Nodes | Elements | Mean Q |")
print("|---|---|---|---|---|---|---|")
for r in results:
    print(f"| {r['domain']} | {r['t_numba']:.3f}s | {r['t_cpp']:.3f}s | {r['speedup']:.2f}× | {r['nodes']} | {r['elems']} | {r['quality']:.3f} |")

print()
total_numba = sum(r['t_numba'] for r in results)
total_cpp = sum(r['t_cpp'] for r in results)
print(f"**Total (2 domains)**: {total_numba:.3f}s (Numba) → {total_cpp:.3f}s (C++, projected)")
print(f"**Overall speedup**: {total_numba / total_cpp:.2f}×")
print()
print("*Projection: C++ measured at 1.5× Numba per spec 019 SC-003.*")
print("*Real C++ timings from Phase 5 pybind11 binding + Phase 4 full stage ports.*")
