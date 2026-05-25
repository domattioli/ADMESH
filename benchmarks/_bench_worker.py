#!/usr/bin/env python3
"""Per-version ADMESH stage-timing worker (version-agnostic).

Run with ``PYTHONPATH`` pointed at the admesh tree to benchmark. Times each
algorithm step on a polygon domain and writes a JSON result. Driver
(:mod:`compare_versions`) derives hmin/hmax/g from the original mesh and passes
them in so every version uses identical sizing targets.

Not meant to be run directly — see ``benchmarks/compare_versions.py``.
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", required=True, help="domain boundary JSON")
    ap.add_argument("--hmin", type=float, required=True)
    ap.add_argument("--hmax", type=float, required=True)
    ap.add_argument("--g", type=float, required=True)
    ap.add_argument("--niter", type=int, default=120)
    ap.add_argument("--out", required=True, help="output JSON path")
    ap.add_argument("--label", required=True)
    a = ap.parse_args()

    import admesh
    from admesh._stages import curvature as _curvature
    from admesh._stages import distance as _distance
    from admesh._stages import medial_axis as _medial
    from admesh._stages import mesh_size as _ms
    from admesh._stages import quality as _quality
    from admesh._stages.distmesh import distmesh2d

    T: dict[str, float] = {}

    def _wrap(mod, name, key):
        orig = getattr(mod, name)

        def w(*args, **kw):
            t0 = time.perf_counter()
            r = orig(*args, **kw)
            T[key] = T.get(key, 0.0) + (time.perf_counter() - t0)
            return r

        setattr(mod, name, w)

    # Patch stage fns so build_h's internal calls are timed individually.
    _wrap(_distance, "eval_sdf_grid", "sdf_grid")
    _wrap(_curvature, "apply_curvature", "curvature")
    _wrap(_medial, "apply_medial_axis", "medial_axis")
    _wrap(_ms, "solve_iter", "grading_solve")

    # Stage 0: domain load + SDF construction (shapely vs numba fast_sdf).
    t0 = time.perf_counter()
    dom = admesh.load_domain_from_json(a.domain)
    T["domain_load_sdf"] = time.perf_counter() - t0

    class _D:  # shim: build_h wants .fd / .bbox
        fd = staticmethod(dom.sdf)
        bbox = dom.bbox

    # Stages 1-5: size field (SDF grid + curvature + medial + grading + interp).
    t0 = time.perf_counter()
    fh = _ms.build_h(
        _D, base=a.hmax, hmin=a.hmin, hmax=a.hmax, g=a.g,
        curvature_scale=a.hmin, medial_scale=a.hmin,
    )
    T["build_h_total"] = time.perf_counter() - t0
    T["interpolant"] = max(
        T["build_h_total"]
        - sum(T.get(k, 0.0) for k in ("sdf_grid", "curvature", "medial_axis", "grading_solve")),
        0.0,
    )

    # Stage 6: distmesh (point generation + force relaxation).
    pfix = dom.pfix if getattr(dom, "pfix", None) is not None else None
    t0 = time.perf_counter()
    out = distmesh2d(fd=dom.sdf, fh=fh, h0=a.hmin, bbox=dom.bbox,
                     pfix=pfix, niter=a.niter, return_diagnostics=True)
    T["distmesh"] = time.perf_counter() - t0
    if len(out) == 3:
        p, t, diag = out
        n_iter = len(diag)
    else:
        p, t = out
        n_iter = None

    # Stage 7: quality.
    t0 = time.perf_counter()
    qmin, qmean, q = _quality.mesh_quality(p, t)
    T["quality"] = time.perf_counter() - t0

    # Apply quality gate (same as admesh.triangulate default).
    # Benchmark bypasses the production size-field stack (spec-002), so must enforce this gate explicitly.
    gate_min, gate_mean = 0.30, 0.60
    if qmin < gate_min:
        raise ValueError(
            f"Mesh quality {qmin:.3f} below gate min {gate_min:.2f} — "
            f"benchmark domain/params invalid for timing"
        )
    if qmean < gate_mean:
        raise ValueError(
            f"Mesh mean quality {qmean:.3f} below gate mean {gate_mean:.2f} — "
            f"benchmark domain/params invalid for timing"
        )

    res = {
        "label": a.label,
        "params": {"hmin": a.hmin, "hmax": a.hmax, "g": a.g, "niter": a.niter},
        "n_nodes": int(len(p)),
        "n_elements": int(len(t)),
        "distmesh_iters": n_iter,
        "q_min": float(qmin),
        "q_mean": float(qmean),
        "q_std": float(np.std(q)),
        "stages_sec": T,
        "total_sec": T["domain_load_sdf"] + T["build_h_total"] + T["distmesh"] + T["quality"],
    }
    np.savez_compressed(a.out + ".mesh.npz", p=p, t=np.asarray(t), q=q)
    with open(a.out, "w") as f:
        json.dump(res, f, indent=2)
    print(f"[{a.label}] nodes={res['n_nodes']} elems={res['n_elements']} "
          f"iters={n_iter} total={res['total_sec']:.2f}s")


if __name__ == "__main__":
    main()
