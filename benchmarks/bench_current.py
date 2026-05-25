#!/usr/bin/env python3
"""Benchmark current Python/Numba implementation."""
import sys, time, pathlib
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import admesh
from admesh import domains

np.random.seed(0)

domains_to_bench = [
    ("UNIT_DISK", domains.UNIT_DISK),
    ("NOTCHED_RECTANGLE", domains.NOTCHED_RECTANGLE),
]

print("Current ADMESH (Python/Numba) Benchmark")
print()
print("| Domain | Time (s) | Nodes | Elements | Mean Quality |")
print("|---|---|---|---|---|")

for name, domain in domains_to_bench:
    t_start = time.perf_counter()
    try:
        mesh = admesh.triangulate(domain, h_max=0.1, h_min=0.01)
        t_elapsed = time.perf_counter() - t_start
        n_nodes = mesh.nodes.shape[0]
        n_elems = mesh.elements.shape[0]
        mean_q = float(np.mean(mesh.quality)) if len(mesh.quality) > 0 else 0
        print(f"| {name} | {t_elapsed:.3f} | {n_nodes} | {n_elems} | {mean_q:.3f} |")
    except Exception as e:
        print(f"| {name} | ERROR: {e} | — | — | — |")

print()
print("*Note: C++ native measurements deferred to Phase 5 (pybind11 integration).*")
print("*Estimated 1.5× speedup per spec 019 SC-003.*")
