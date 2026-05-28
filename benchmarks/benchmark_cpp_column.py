#!/usr/bin/env python3
"""Quick benchmark: show Numba timings + hypothetical C++ column (1.5x speedup)."""
import sys
import pathlib
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import admesh
from admesh import domains
from admesh._stages import mesh_size as mesh_size_stage

np.random.seed(0)

# MVP domain timings (hypothetical)
# These are scaled-down estimates for demo. Full WNAT would be larger.
timings = {
    "unit_disk": {"domain_load_sdf": 0.001, "sdf_grid": 0.01, "curvature": 0.001,
                  "medial_axis": 0.05, "grading_solve": 0.001, "build_h_total": 0.062,
                  "distmesh": 0.5, "quality": 0.001},
}

print("# C++ Rewrite Benchmark (Hypothetical)")
print()
print("| Stage | Numba (baseline) | C++ (projected 1.5×) |")
print("|---|---|---|")

total_numba = 0
total_cpp = 0

for stage, t_numba in timings["unit_disk"].items():
    t_cpp = t_numba / 1.5
    total_numba += t_numba
    total_cpp += t_cpp
    print(f"| {stage} | {t_numba:.3f}s | {t_cpp:.3f}s |")

print(f"| **TOTAL** | **{total_numba:.3f}s** | **{total_cpp:.3f}s** |")
print()
print("**Speedup**: 1.5×")
print()
print("Note: This is a hypothesis based on the spec's target. Real timings will be")
print("measured during Phase 4-5 parity testing (T039/T040).")
