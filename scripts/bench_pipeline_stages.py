"""Profile admesh.triangulate() default size-field pipeline.

Measures per-stage wall-clock overhead via cProfile aggregating tottime by stage.
Addresses ADMESH issues #8 (perf), #99 (parallelization), #203 (roadmap priority).

Run: python scripts/bench_pipeline_stages.py [--quick]
"""
from __future__ import annotations

import argparse
import cProfile
import os
import pstats
import time
from io import StringIO

import admesh
from admesh._stages import domains as D


def bucket_by_stage(profiler: cProfile.Profile) -> dict[str, float]:
    """Aggregate pstats tottime by stage bucket."""
    buckets = {
        "size-field-build": 0.0,
        "eikonal-solver": 0.0,
        "medial-axis": 0.0,
        "sdf-eval": 0.0,
        "distmesh": 0.0,
        "background-grid": 0.0,
        "quality": 0.0,
        "other": 0.0,
    }

    stats = pstats.Stats(profiler, stream=StringIO())
    for (filename, lineno, funcname), data in stats.stats.items():
        tottime = data[2]
        basename = os.path.basename(filename)

        if basename in {"size_field.py", "curvature.py", "bathymetry.py", "dominate_tide.py"}:
            buckets["size-field-build"] += tottime
        elif basename == "mesh_size.py" and funcname == "build_h":
            buckets["size-field-build"] += tottime
        elif basename == "mesh_size.py" and funcname in {"solve_iter", "_solve_iter_nb", "_solve_iter_py"}:
            buckets["eikonal-solver"] += tottime
        elif basename == "medial_axis.py":
            buckets["medial-axis"] += tottime
        elif basename in {"distance.py", "in_polygon.py"}:
            buckets["sdf-eval"] += tottime
        elif basename == "distmesh.py":
            buckets["distmesh"] += tottime
        elif basename in {"background_grid.py", "octree.py"}:
            buckets["background-grid"] += tottime
        elif basename == "quality.py":
            buckets["quality"] += tottime
        else:
            buckets["other"] += tottime

    return buckets


def bench_size_field_stack(fort14_path: str) -> None:
    """Profile the full size-field stack (curvature+medial+bathymetry) on a
    real coastal fort.14 domain.

    The default triangulate() path does NOT compose this stack (deferred per
    issue #65), so it never shows in the default pipeline benchmark. This mode
    profiles build_h() directly to measure the stack's own cost on real geometry.
    """
    import numpy as np
    from admesh.fort14 import read_fort14
    from admesh.api import Domain
    from admesh._stages.domains import Domain as PortDomain
    from admesh._stages.mesh_size import build_h

    if not os.path.exists(fort14_path):
        print(f"size-field-stack: SKIP (fixture not found: {fort14_path})")
        return

    mesh = read_fort14(fort14_path)
    dom = Domain.from_mesh(mesh)
    bx = dom.bbox
    diag = ((bx[2] - bx[0]) ** 2 + (bx[3] - bx[1]) ** 2) ** 0.5
    h_max = diag / 40.0
    h_min = h_max / 20.0
    pd = PortDomain(name="coastal", fd=dom.sdf, bbox=dom.bbox,
                    fixed_points=np.empty((0, 2)))

    # Warm up (JIT / interpolant caches) so the reported run is steady-state.
    build_h(pd, base=h_max, curvature_scale=0.25, medial_scale=h_min,
            bathymetry=dom.bathymetry, bathy_scale=0.5, hmin=h_min, hmax=h_max)

    start = time.perf_counter()
    profiler = cProfile.Profile()
    profiler.enable()
    build_h(pd, base=h_max, curvature_scale=0.25, medial_scale=h_min,
            bathymetry=dom.bathymetry, bathy_scale=0.5, hmin=h_min, hmax=h_max)
    profiler.disable()
    elapsed = time.perf_counter() - start

    n_nodes = mesh.nodes.shape[0]
    buckets = bucket_by_stage(profiler)
    total = sum(buckets.values())
    print(f"size-field-stack ({os.path.basename(fort14_path)}): "
          f"{n_nodes} nodes, {elapsed:.4f}s build_h wall-clock "
          f"(h_min={h_min:.4f} h_max={h_max:.4f})")
    for name, t in sorted(buckets.items(), key=lambda x: -x[1]):
        if t > 0:
            pct = 100 * t / total if total > 0 else 0
            print(f"  {name:20s} {t:8.4f}s {pct:6.1f}%")
    print(f"  {'sum':20s} {total:8.4f}s")
    print()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="Run only coarse configs (3 domains)")
    parser.add_argument("--size-field", action="store_true",
                        help="Profile the size-field stack on the WNAT coastal fixture instead")
    args = parser.parse_args()

    if args.size_field:
        bench_size_field_stack(
            "tests/fixtures/fort14/adcirc_examples/wnat_test.14"
        )
        return

    configs = [
        ("L_SHAPE_coarse", D.L_SHAPE, 0.03, 0.12),
        ("L_SHAPE_fine", D.L_SHAPE, 0.012, 0.05),
        ("UNIT_SQUARE_coarse", D.UNIT_SQUARE, 0.03, 0.12),
        ("UNIT_SQUARE_fine", D.UNIT_SQUARE, 0.012, 0.05),
        ("ANNULUS_coarse", D.ANNULUS, 0.03, 0.12),
        ("ANNULUS_fine", D.ANNULUS, 0.012, 0.05),
    ]

    if args.quick:
        configs = configs[::2]

    # Warm up Numba JIT once
    try:
        admesh.triangulate(D.L_SHAPE, h_min=0.03, h_max=0.12, quality_gate=(0.0, 0.0), seed=0)
    except Exception:
        pass

    for label, domain, h_min, h_max in configs:
        start = time.perf_counter()
        try:
            profiler = cProfile.Profile()
            profiler.enable()
            mesh = admesh.triangulate(domain, h_min=h_min, h_max=h_max, quality_gate=(0.0, 0.0), seed=0)
            profiler.disable()
            elapsed = time.perf_counter() - start

            n_nodes, n_elems = mesh.nodes.shape[0], mesh.elements.shape[0]
            buckets = bucket_by_stage(profiler)
            total_profiled = sum(buckets.values())

            print(f"{label}: {n_nodes:4d} nodes, {n_elems:4d} elems, {elapsed:.4f}s wall-clock")
            for name, t in sorted(buckets.items(), key=lambda x: -x[1]):
                pct = 100 * t / total_profiled if total_profiled > 0 else 0
                print(f"  {name:20s} {t:8.4f}s {pct:6.1f}%")
            print(f"  {'sum':20s} {total_profiled:8.4f}s")
            print()

        except Exception as e:
            print(f"{label}: ERROR {type(e).__name__}: {e}\n")


if __name__ == "__main__":
    main()
