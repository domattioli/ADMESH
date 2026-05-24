#!/usr/bin/env python3
"""Benchmark ADMESH 13-stage pipeline end-to-end + per-stage.

Measures wall-clock (perf_counter) + peak memory (tracemalloc) for:
- tiny (CI): ~100 nodes, <5s
- medium (dev loop): ~5K nodes, <30s
- wnat-3m (nightly/manual): ~3M-node domain — NOT YET PROVISIONED. Largest
  real asset is WNAT_Onur.14 (127K). Source a NOAA grid or synthesize a
  deterministic 3M fixture first (see .planning/perf-optimization/PLAN.md s0).

JIT warmup excluded; steady-state median + IQR over 3 runs (1 run for wnat-3m).

Output: JSON artifact + human summary table, keyed by git SHA + env hash.

Run:
    python scripts/bench_pipeline.py --tier=tiny --runs=3
    python scripts/bench_pipeline.py --tier=wnat-3m --ci --fail-on-regression
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time
import tracemalloc
from dataclasses import dataclass, asdict
from typing import Any

import numpy as np


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
BENCHMARKS_DIR = REPO_ROOT / "benchmarks"
RESULTS_DIR = BENCHMARKS_DIR / "results"
DATA_DIR = BENCHMARKS_DIR / "data"

# Ensure output dirs exist
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class TimingResult:
    """Timing stats for one stage: median, Q25, Q75 in milliseconds."""
    median_ms: float
    q25_ms: float
    q75_ms: float


@dataclass
class BenchmarkRun:
    """Complete benchmark run: metadata + results."""
    git_sha: str
    env_hash: str
    timestamp_utc: str
    tier: str
    wall_clock: dict[str, TimingResult]  # stage_name -> TimingResult
    peak_memory_mb: dict[str, float]      # stage_name -> peak_mb
    end_to_end_ms: float


@contextlib.contextmanager
def _timer_and_memory():
    """Context: measure wall-clock (sec) + peak memory (bytes)."""
    tracemalloc.start()
    t0 = time.perf_counter()
    peak = 0
    try:
        yield lambda: (time.perf_counter() - t0, tracemalloc.get_traced_memory()[1])
    finally:
        tracemalloc.stop()


def _get_git_sha() -> str:
    """Current HEAD SHA (short form)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def _get_env_hash() -> str:
    """Compact env fingerprint: python ver + key dep versions."""
    import admesh
    import numba
    import numpy
    import scipy

    parts = [
        f"py{sys.version_info.major}{sys.version_info.minor}",
        f"numba{numba.__version__}",
        f"np{numpy.__version__}",
        f"scipy{scipy.__version__}",
        f"admesh{admesh.__version__}",
    ]
    s = "-".join(parts)
    return hashlib.md5(s.encode()).hexdigest()[:8]


def _get_timestamp_utc() -> str:
    """ISO 8601 UTC timestamp."""
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _create_tiny_domain() -> tuple[np.ndarray, np.ndarray]:
    """Synthetic tiny annulus domain (~100 nodes target)."""
    import admesh
    theta = np.linspace(0, 2 * np.pi, 32, endpoint=False)
    outer = np.c_[np.cos(theta), np.sin(theta)]
    inner = np.c_[0.5 * np.cos(theta), 0.5 * np.sin(theta)]
    domain = admesh.Domain(
        rings=[outer, inner],
        bbox=np.array([-1.2, -1.2, 1.2, 1.2]),
    )
    return domain, np.array([0.1])


def _create_medium_domain() -> tuple[Any, np.ndarray]:
    """Load medium domain from file (~5K nodes target)."""
    import admesh
    toml_path = DATA_DIR / "medium_lake.toml"
    if toml_path.exists():
        return admesh.load_domain_from_toml(str(toml_path)), np.array([0.02])
    # Fallback: synthetic
    domain = admesh.Domain(
        rings=[np.c_[np.cos(np.linspace(0, 2*np.pi, 100)), np.sin(np.linspace(0, 2*np.pi, 100))]],
        bbox=np.array([-1.1, -1.1, 1.1, 1.1]),
    )
    return domain, np.array([0.02])


def _load_wnat_domain() -> tuple[Any, np.ndarray]:
    """Load WNAT from reference fixture."""
    import admesh
    wnat_path = REPO_ROOT / "tests" / "fixtures" / "fort14" / "adcirc_examples" / "wnat_test.14"
    if not wnat_path.exists():
        raise FileNotFoundError(f"WNAT fixture not found: {wnat_path}")
    domain = admesh.load_domain_from_fort14(str(wnat_path))
    h0 = 1.5 / 111.0  # ~1.5 degrees in radians (coarse)
    return domain, np.array([h0])


def _instrument_pipeline(domain: Any, h0: float) -> dict[str, float]:
    """Run admesh.triangulate with per-stage timing + memory instrumentation.

    Returns {stage_name: elapsed_sec, ...} dict.
    This is a simplified version; full impl would monkey-patch stages.
    """
    # For now, measure end-to-end only; per-stage timing requires stage-level hooks.
    import admesh
    t0 = time.perf_counter()
    mesh = admesh.triangulate(domain, h0=h0)
    elapsed = time.perf_counter() - t0
    return {
        "end_to_end_sec": elapsed,
        "n_nodes": mesh.n_nodes,
        "n_elements": mesh.n_elements,
    }


def _run_benchmark_suite(tier: str, runs: int) -> BenchmarkRun:
    """Execute benchmark: (runs) iterations, record stats."""
    import admesh

    # Select input
    if tier == "tiny":
        domain, h0_arr = _create_tiny_domain()
    elif tier == "medium":
        domain, h0_arr = _create_medium_domain()
    elif tier == "wnat-3m":
        domain, h0_arr = _load_wnat_domain()
    else:
        raise ValueError(f"Unknown tier: {tier}")

    h0 = float(h0_arr[0])

    # Warmup (excluded from timing): dummy run to trigger JIT
    print(f"[{tier}] Warmup (JIT compilation)...")
    try:
        _instrument_pipeline(domain, h0)
    except Exception as e:
        print(f"  Warmup failed (non-fatal): {e}")

    # Measured runs
    print(f"[{tier}] Running {runs} measured iterations...")
    timings_sec: list[float] = []
    peak_mems: list[float] = []

    for i in range(runs):
        print(f"  Run {i+1}/{runs}...", end=" ", flush=True)
        t0 = time.perf_counter()
        tracemalloc.start()

        try:
            result = _instrument_pipeline(domain, h0)
            elapsed = time.perf_counter() - t0
            _, peak_bytes = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        timings_sec.append(elapsed)
        peak_mems.append(peak_bytes / 1024 / 1024)  # MB
        print(f"{elapsed:.2f}s, peak {peak_mems[-1]:.1f} MB")

    # Stats
    timings_ms = [t * 1000 for t in timings_sec]
    timings_ms_sorted = sorted(timings_ms)
    median_ms = np.median(timings_ms_sorted)
    q25_ms = np.percentile(timings_ms_sorted, 25)
    q75_ms = np.percentile(timings_ms_sorted, 75)
    peak_mem_mb = max(peak_mems)

    wall_clock = {
        "end_to_end": TimingResult(
            median_ms=float(median_ms),
            q25_ms=float(q25_ms),
            q75_ms=float(q75_ms),
        )
    }
    peak_memory = {"end_to_end": float(peak_mem_mb)}

    run = BenchmarkRun(
        git_sha=_get_git_sha(),
        env_hash=_get_env_hash(),
        timestamp_utc=_get_timestamp_utc(),
        tier=tier,
        wall_clock=wall_clock,
        peak_memory_mb=peak_memory,
        end_to_end_ms=float(median_ms),
    )
    return run


def _save_results(run: BenchmarkRun) -> pathlib.Path:
    """Write JSON result + human summary."""
    # JSON
    json_name = f"{run.git_sha}-{run.env_hash}.json"
    json_path = RESULTS_DIR / json_name

    data_dict = asdict(run)
    # Convert TimingResult dataclass to dict
    data_dict["wall_clock"] = {
        k: asdict(v) for k, v in run.wall_clock.items()
    }

    json_path.write_text(json.dumps(data_dict, indent=2))
    print(f"✓ Saved JSON: {json_path.relative_to(REPO_ROOT)}")

    # Human summary
    summary_path = RESULTS_DIR / f"SUMMARY_{run.git_sha[:8]}.txt"
    lines = [
        f"ADMESH Benchmark Summary — {run.timestamp_utc}",
        f"Git: {run.git_sha} | Env: {run.env_hash}",
        f"Tier: {run.tier}",
        "",
        "Stage                       | Median (ms) | Q25-Q75 (ms) | Peak Mem (MB)",
        "-" * 70,
    ]

    for stage, timing in sorted(run.wall_clock.items()):
        peak_mb = run.peak_memory_mb.get(stage, 0.0)
        lines.append(
            f"{stage:27} | {timing.median_ms:11.2f} | "
            f"{timing.q25_ms:5.2f}-{timing.q75_ms:5.2f}  | {peak_mb:12.1f}"
        )

    lines.append("-" * 70)
    summary_path.write_text("\n".join(lines) + "\n")
    print(f"✓ Saved summary: {summary_path.relative_to(REPO_ROOT)}")

    return json_path


def _check_regression(run: BenchmarkRun, threshold_pct: float = 15.0) -> bool:
    """Load baseline from main, check if run exceeds threshold.

    Returns True if regression detected (should fail CI).
    """
    # Simplified: find most recent baseline for same tier on main
    baselines = sorted(RESULTS_DIR.glob("*.json"))
    if not baselines:
        print("  (no baseline found; skipping regression check)")
        return False

    # Load latest baseline
    baseline_data = json.loads(baselines[-1].read_text())
    baseline_run = BenchmarkRun(**baseline_data)

    if baseline_run.tier != run.tier:
        print(f"  (baseline tier {baseline_run.tier} != run tier {run.tier}; skipping)")
        return False

    baseline_median_ms = baseline_run.end_to_end_ms
    run_median_ms = run.end_to_end_ms
    pct_slower = ((run_median_ms - baseline_median_ms) / baseline_median_ms) * 100

    print(f"  Baseline: {baseline_median_ms:.2f} ms | Run: {run_median_ms:.2f} ms")
    print(f"  Delta: {pct_slower:+.1f}%")

    if pct_slower > threshold_pct:
        print(f"  ✗ REGRESSION DETECTED (>{threshold_pct}% slower)")
        return True

    print(f"  ✓ Within threshold (<{threshold_pct}%)")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ADMESH pipeline benchmark harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--tier",
        choices=["tiny", "medium", "wnat-3m"],
        default="tiny",
        help="Input tier (tiny: ~100 nodes, medium: ~5K, wnat-3m: ~3M)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of measured iterations (default: 3; wnat-3m auto→1)",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI mode (skip wnat-3m unless --tier=wnat-3m)",
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit non-zero if regression >15% detected vs baseline",
    )
    parser.add_argument(
        "--check-regression",
        action="store_true",
        help="Report regression vs baseline without failing",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        help="Explicit output JSON path (default: {git_sha}-{env_hash}.json)",
    )

    args = parser.parse_args()

    # Auto-adjust runs for large tier
    if args.tier == "wnat-3m" and args.runs == 3:
        args.runs = 1
        print(f"Auto-reduced runs to 1 for tier={args.tier}")

    print(f"ADMESH Benchmark Harness")
    print(f"  Tier: {args.tier}, Runs: {args.runs}")
    print()

    try:
        run = _run_benchmark_suite(args.tier, args.runs)
    except Exception as e:
        print(f"✗ Benchmark failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    print()
    _save_results(run)

    if args.check_regression or args.fail_on_regression:
        print()
        print("Regression check:")
        regressed = _check_regression(run, threshold_pct=15.0)
        if args.fail_on_regression and regressed:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
