#!/usr/bin/env python3
"""Per-stage wall-clock harness for ADMESH pipeline (issue #145).

Monkeypatches stage entry-point callables with timing wrappers to isolate
wall-clock per-stage. MVP triangulate path (distmesh-only, no size-field stack)
will show distmesh2d + mesh_quality; full path (with build_h) invokes all 13
stages. Defensive patching: missing stages skipped silently.

Fixtures:
- square, lshape: tier-0 (in-package), h_max=0.1, runs=3
- wnat: real fixture, h_max=coarse, runs=1 (slow)
- tier1: JSON/TOML domains, skipped if absent

Usage:
    python scripts/bench_pipeline.py --runs 1 --fixtures square,lshape
    python scripts/bench_pipeline.py --runs 1 --json /tmp/bench.json
    python scripts/bench_pipeline.py --h0 0.2 --runs 1
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import pathlib
import subprocess
import sys
import time
from typing import Any

import numpy as np

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


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


@contextlib.contextmanager
def _stage_timer():
    """Context mgr for per-stage wall-clock accumulation.

    Monkeypatches stage callables (defensive: skip on missing).
    Restores all originals on exit. Yields dict[stage_label] → sec_accumulated.
    """
    import admesh._stages.routine as routine_mod
    import admesh._stages.quality as quality_mod
    import admesh.size_field as size_field_mod
    import admesh._stages.mesh_size as mesh_size_mod
    import admesh._stages.background_grid as bg_grid_mod
    import admesh._stages.distance as dist_mod
    import admesh._stages.curvature as curv_mod
    import admesh._stages.medial_axis as medial_mod
    import admesh._stages.bathymetry as bath_mod
    import admesh._stages.dominate_tide as tide_mod
    import admesh._stages.boundary as bnd_mod

    timings: dict[str, float] = {}
    originals: dict[tuple, Any] = {}

    # List of (module, attr_name, friendly_label)
    targets = [
        (routine_mod, "distmesh2d", "distmesh2d"),
        (routine_mod, "distmesh2d_admesh", "distmesh2d_admesh"),
        (quality_mod, "mesh_quality", "mesh_quality"),
        (size_field_mod, "compose_size_field", "size_field_compose"),
        (mesh_size_mod, "solve_iter", "mesh_size.solve_iter"),
        (mesh_size_mod, "build_h", "mesh_size.build_h"),
        (bg_grid_mod, "create_background_grid", "background_grid"),
        (dist_mod, "eval_sdf_grid", "distance.eval_sdf_grid"),
        (curv_mod, "apply_curvature", "curvature"),
        (medial_mod, "apply_medial_axis", "medial_axis"),
        (bath_mod, "apply_bathymetry", "bathymetry"),
        (tide_mod, "apply_tide", "dominate_tide"),
        (bnd_mod, "enforce_boundary_conditions", "boundary"),
    ]

    for module, attr_name, label in targets:
        if hasattr(module, attr_name):
            orig = getattr(module, attr_name)
            originals[(module, attr_name)] = orig
            timings[label] = 0.0

            def make_wrapper(fn, lbl):
                def wrapper(*args, **kwargs):
                    t0 = time.perf_counter()
                    try:
                        return fn(*args, **kwargs)
                    finally:
                        elapsed = time.perf_counter() - t0
                        timings[lbl] += elapsed
                return wrapper

            setattr(module, attr_name, make_wrapper(orig, label))

    try:
        yield timings
    finally:
        for (module, attr_name), orig in originals.items():
            setattr(module, attr_name, orig)


def _bench_fixture(
    name: str,
    domain: Any,
    h_max: float,
    runs: int,
) -> dict[str, Any]:
    """Benchmark one fixture: warm-up + measured runs.

    Returns {fixture_name, h_max, end_to_end_sec, n_nodes, n_elements, stages}.
    """
    import admesh

    result = {
        "fixture": name,
        "h_max": h_max,
        "end_to_end_sec": 0.0,
        "n_nodes": 0,
        "n_elements": 0,
        "stages": {},
    }

    # Warmup (non-fatal)
    print(f"  [{name}] Warmup...", end=" ", flush=True)
    try:
        with _stage_timer() as timings:
            t0 = time.perf_counter()
            mesh = admesh.triangulate(domain, h_max=h_max)
            e2e = time.perf_counter() - t0
        print(f"OK ({e2e:.2f}s)")
    except Exception as e:
        print(f"skip ({e})")

    # Measured runs
    print(f"  [{name}] {runs} run(s)...", end=" ", flush=True)
    medians: dict[str, list[float]] = {}
    e2e_times: list[float] = []

    for _ in range(runs):
        with _stage_timer() as timings:
            t0 = time.perf_counter()
            try:
                mesh = admesh.triangulate(domain, h_max=h_max)
            except Exception as e:
                print(f"\n    ✗ run failed: {e}")
                return result
            e2e = time.perf_counter() - t0

        e2e_times.append(e2e)
        for label, sec in timings.items():
            if label not in medians:
                medians[label] = []
            medians[label].append(sec)

    # Compute medians
    result["end_to_end_sec"] = float(np.median(e2e_times))
    result["n_nodes"] = mesh.n_nodes
    result["n_elements"] = mesh.n_elements

    for label, secs in medians.items():
        result["stages"][label] = float(np.median(secs))

    # "other" = unaccounted time
    measured_sum = sum(result["stages"].values())
    other = result["end_to_end_sec"] - measured_sum
    if other > 0:
        result["stages"]["other/unaccounted"] = other

    print(f"OK (median {result['end_to_end_sec']:.3f}s)")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ADMESH per-stage wall-clock harness (issue #145)"
    )
    parser.add_argument(
        "--h0",
        type=float,
        default=None,
        help="Override target h_max for all fixtures (default: per-fixture)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Measured iterations per fixture (default: 3; wnat auto→1)",
    )
    parser.add_argument(
        "--json",
        type=pathlib.Path,
        help="Write JSON record to PATH (omit to skip)",
    )
    parser.add_argument(
        "--fixtures",
        type=str,
        default="square,lshape,wnat",
        help="Comma-sep fixture names: square,lshape,tier1,wnat (default: all present)",
    )

    args = parser.parse_args()

    import admesh

    fixtures_requested = [f.strip() for f in args.fixtures.split(",")]

    # Tier-0 fixtures (always present)
    tier0 = {
        "square": (admesh.domains.UNIT_SQUARE, args.h0 or 0.1),
        "lshape": (admesh.domains.L_SHAPE, args.h0 or 0.1),
    }

    # WNAT fixture
    wnat_path = REPO_ROOT / "tests" / "fixtures" / "fort14" / "adcirc_examples" / "wnat_test.14"

    results = {
        "git_sha": _get_git_sha(),
        "env_hash": _get_env_hash(),
        "fixtures": {},
    }

    for fixture_name in fixtures_requested:
        fixture_name = fixture_name.strip()

        if fixture_name in tier0:
            domain, h_max = tier0[fixture_name]
            runs = args.runs
            if fixture_name == "wnat" and runs == 3:
                runs = 1
            fixture_result = _bench_fixture(fixture_name, domain, h_max, runs)
            results["fixtures"][fixture_name] = fixture_result

        elif fixture_name == "wnat":
            try:
                if not wnat_path.exists():
                    print(f"skip: wnat (file not found: {wnat_path})")
                    continue
                domain = admesh.load_domain_from_fort14(str(wnat_path))
                h_max = args.h0 or (1.5 / 111.0)
                runs = 1  # WNAT is slow
                fixture_result = _bench_fixture(fixture_name, domain, h_max, runs)
                results["fixtures"][fixture_name] = fixture_result
            except Exception as e:
                print(f"skip: wnat ({type(e).__name__}: {str(e)[:80]})")

        elif fixture_name == "tier1":
            # Search for any JSON/TOML domain files
            json_files = list((REPO_ROOT / "tests" / "fixtures").glob("**/*.json"))
            toml_files = list((REPO_ROOT / "tests" / "fixtures").glob("**/*.toml"))
            if not json_files and not toml_files:
                print("skip: tier1 (no JSON/TOML domain files found)")
                continue
            print(f"skip: tier1 (would scan {len(json_files)} JSON + {len(toml_files)} TOML; deferred)")

        else:
            print(f"skip: {fixture_name} (unknown fixture name)")

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    # Per-fixture table
    for fixture_name, fixture_data in results["fixtures"].items():
        print()
        print(f"Fixture: {fixture_name}")
        print(f"  h_max={fixture_data['h_max']:.6f}, nodes={fixture_data['n_nodes']}, elems={fixture_data['n_elements']}")
        print()
        print(f"  {'Stage':<30} {'Seconds':>12} {'% of total':>12}")
        print(f"  {'-' * 30} {'-' * 12} {'-' * 12}")

        stages = fixture_data["stages"]
        e2e = fixture_data["end_to_end_sec"]

        # Sort by time desc
        sorted_stages = sorted(stages.items(), key=lambda x: x[1], reverse=True)
        for label, sec in sorted_stages:
            pct = 100.0 * sec / e2e if e2e > 0 else 0.0
            print(f"  {label:<30} {sec:>12.6f} {pct:>11.1f}%")

        print(f"  {'-' * 30} {'-' * 12} {'-' * 12}")
        print(f"  {'TOTAL':<30} {e2e:>12.6f} {'100.0%':>11}")

    # JSON output
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2))
        print()
        print(f"✓ JSON saved: {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
