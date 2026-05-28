#!/usr/bin/env python3
"""Real benchmark: measure Numba (Python) vs C++ on WNAT domain."""
import sys
import pathlib
import time
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import admesh
from admesh import domains

np.random.seed(0)

# Time Numba path on UNIT_DISK (smaller for quick turnaround)
domain = domains.UNIT_DISK

print("Benchmarking ADMESH stages on UNIT_DISK domain...")
print()

t_start = time.perf_counter()
try:
    mesh = admesh.triangulate(domain, h_max=0.05, backend="python")
    t_numba = time.perf_counter() - t_start
    n_nodes_py = mesh.nodes.shape[0]
    n_elems_py = mesh.elements.shape[0]
    mean_q_py = float(np.mean(mesh.quality)) if len(mesh.quality) > 0 else 0
    print(f"Python (Numba):  {t_numba:.3f}s  |  {n_nodes_py} nodes, {n_elems_py} elems, mean_q={mean_q_py:.3f}")
except Exception as e:
    print(f"Python failed: {e}")
    t_numba = None

# Try C++ path (may fail if bindings not ready; that's OK for this phase)
t_start = time.perf_counter()
try:
    mesh = admesh.triangulate(domain, h_max=0.05, backend="cpp")
    t_cpp = time.perf_counter() - t_start
    n_nodes_cpp = mesh.nodes.shape[0]
    n_elems_cpp = mesh.elements.shape[0]
    mean_q_cpp = float(np.mean(mesh.quality)) if len(mesh.quality) > 0 else 0
    print(f"C++ (native):    {t_cpp:.3f}s  |  {n_nodes_cpp} nodes, {n_elems_cpp} elems, mean_q={mean_q_cpp:.3f}")
except Exception as e:
    print(f"C++ unavailable (bindings deferred): {e}")
    t_cpp = None

print()
if t_numba and t_cpp:
    speedup = t_numba / t_cpp
    print(f"Speedup (Numba / C++): {speedup:.2f}×")
else:
    print("(C++ benchmark deferred to Phase 5 pybind11 integration)")
