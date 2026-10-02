"""Benchmark triangulate_batch wall time against a sequential loop.

Issue #99 P2 gate (``--wnat``): 8 Western North Atlantic meshes (about 95k
nodes each) must reach at least 4.0x speedup at ``n_jobs=8``. Measured
5.09x on a 10-core Mac (4 performance + 6 efficiency cores).

Without ``--wnat`` the script times small MVP domains and reports only. Each
spawned worker pays a fixed start-up cost (import of admesh and numba, about
0.5 s), so small meshes and small batches gain less: 8 meshes of about 6.9k
nodes measured 2.02x, 32 measured 3.81x.

Usage::

    PYTHONPATH=src python scripts/bench_batch.py --wnat          # gate, ~25 min
    PYTHONPATH=src python scripts/bench_batch.py [--h-max 0.02] [--n-domains 8]
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time

from pathlib import Path

import admesh
from admesh.domains import ALL as DOMAIN_REGISTRY

GATE_N_JOBS = 8
GATE_SPEEDUP = 4.0
WNAT = Path(__file__).resolve().parent.parent / "benchmarks/data/wnat_onur_boundary.json"
WNAT_KWARGS = {"h_max": 0.10, "h_min": 0.05, "max_iter": 120, "seed": 0,
               "quality_gate": (0.0, 0.0)}


def main() -> int:
    """Time sequential and pooled runs; with --wnat, return 1 if the P2 gate fails."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--h-max", type=float, default=0.02)
    parser.add_argument("--n-domains", type=int, default=8)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--wnat", action="store_true",
                        help="run the P2 gate: --n-domains WNAT meshes")
    args = parser.parse_args()

    if args.wnat:
        domains = [str(WNAT)] * args.n_domains
        kwargs = WNAT_KWARGS
    else:
        regs = list(DOMAIN_REGISTRY.values())
        domains = [regs[i % len(regs)] for i in range(args.n_domains)]
        kwargs = {"h_max": args.h_max, "max_iter": 200, "seed": 0,
                  "quality_gate": (0.0, 0.0)}

    def median_wall(fn) -> float:
        times = []
        for _ in range(args.repeats):
            t0 = time.perf_counter()
            fn()
            times.append(time.perf_counter() - t0)
        return statistics.median(times)

    # Warm the numba cache first; a cold serial baseline inflates speedup.
    seq = [admesh.triangulate(d, **kwargs) for d in domains]
    t_seq = median_wall(lambda: [admesh.triangulate(d, **kwargs) for d in domains])
    mean_nodes = sum(m.n_nodes for m in seq) / len(seq)

    print(f"{'WNAT' if args.wnat else 'MVP'}  h_max={kwargs['h_max']}  domains={args.n_domains}  mean nodes/mesh={mean_nodes:.0f}"
          f"  median of {args.repeats}")
    print(f"{'n_jobs':>6}  {'wall (s)':>8}  {'speedup':>7}")
    print(f"{1:>6}  {t_seq:>8.2f}  {1.0:>7.2f}")
    speedups = {}
    for n_jobs in (2, 4, 8):
        t_batch = median_wall(
            lambda n=n_jobs: admesh.triangulate_batch(domains, n_jobs=n, **kwargs)
        )
        speedups[n_jobs] = t_seq / t_batch
        print(f"{n_jobs:>6}  {t_batch:>8.2f}  {speedups[n_jobs]:>7.2f}")

    if not args.wnat:
        return 0
    ok = speedups[GATE_N_JOBS] >= GATE_SPEEDUP
    print(f"P2 gate (>= {GATE_SPEEDUP}x at n_jobs={GATE_N_JOBS}): {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
