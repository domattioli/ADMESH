"""Benchmark triangulate_batch wall time against a sequential loop.

Issue #99 P2 gate: 8 MVP domains at ``h_max=0.02`` (3k to 9k nodes per
mesh) must reach at least 2.5x speedup at ``n_jobs=8``. Each spawned worker pays a
fixed start-up cost (import of admesh and numba, about 0.5 s), so small
meshes run slower in a pool than in a loop.

Usage::

    PYTHONPATH=src python scripts/bench_batch.py [--h-max 0.02]
"""

from __future__ import annotations

import argparse
import sys
import time

import admesh
from admesh.domains import ALL as DOMAIN_REGISTRY

GATE_N_JOBS = 8
GATE_SPEEDUP = 2.5


def main() -> int:
    """Time sequential and pooled runs; return 1 if the P2 gate fails."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--h-max", type=float, default=0.02)
    args = parser.parse_args()

    regs = list(DOMAIN_REGISTRY.values())
    domains = [regs[i % len(regs)] for i in range(8)]
    kwargs = {"h_max": args.h_max, "max_iter": 200, "seed": 0, "quality_gate": (0.0, 0.0)}

    t0 = time.perf_counter()
    seq = [admesh.triangulate(d, **kwargs) for d in domains]
    t_seq = time.perf_counter() - t0
    mean_nodes = sum(m.n_nodes for m in seq) / len(seq)

    print(f"h_max={args.h_max}  mean nodes/mesh={mean_nodes:.0f}")
    print(f"{'n_jobs':>6}  {'wall (s)':>8}  {'speedup':>7}")
    print(f"{1:>6}  {t_seq:>8.2f}  {1.0:>7.2f}")
    speedups = {}
    for n_jobs in (2, 4, 8):
        t0 = time.perf_counter()
        admesh.triangulate_batch(domains, n_jobs=n_jobs, **kwargs)
        t_batch = time.perf_counter() - t0
        speedups[n_jobs] = t_seq / t_batch
        print(f"{n_jobs:>6}  {t_batch:>8.2f}  {speedups[n_jobs]:>7.2f}")

    ok = speedups[GATE_N_JOBS] >= GATE_SPEEDUP
    print(f"P2 gate (>= {GATE_SPEEDUP}x at n_jobs={GATE_N_JOBS}): {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
