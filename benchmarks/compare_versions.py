#!/usr/bin/env python3
"""Compare ADMESH algorithm-stage timings across code versions.

Derives the size-field parameters (hmin, hmax, g) from an *original* reference
mesh, then re-meshes a domain under each requested git ref, timing every
pipeline stage. Emits a markdown table with one column per version plus a
speedup column, and (optionally) a CHILmesh colormapped quality histogram per
version.

Each version is checked out into a throwaway git worktree and run as a
subprocess with ``PYTHONPATH`` pointed at it — so the *same* worker code times
whatever stage implementations that ref shipped. Pass ``current`` as a ref to
benchmark the working tree as-is (e.g. an untagged in-progress optimization).

Usage
-----
    python benchmarks/compare_versions.py \
        --mesh tests/fixtures/fort14/adcirc_examples/wnat_test.14 \
        --domain benchmarks/data/wnat_onur_boundary.json \
        --ref v0.2.1="v0.2.1 (original Python)" \
        --ref current="v0.5.0 (Numba-optimized Python)" \
        --niter 120 --hist

The first ``--ref`` is the baseline; the last is the speedup numerator's
denominator (speedup = baseline / latest).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
WORKER = pathlib.Path(__file__).resolve().parent / "_bench_worker.py"

# Stage display order + human labels.
STAGE_ORDER = [
    ("domain_load_sdf", "domain load + SDF build"),
    ("sdf_grid", "SDF grid eval (eval_sdf_grid)"),
    ("curvature", "curvature (apply_curvature)"),
    ("medial_axis", "medial axis (apply_medial_axis)"),
    ("grading_solve", "grading solve (solve_iter, g)"),
    ("build_h_total", "size-field build (subtotal)"),
    ("distmesh", "distmesh (point gen + relax)"),
    ("quality", "quality (mesh_quality)"),
]


def parse_fort14_geometry(path: str) -> tuple[np.ndarray, np.ndarray]:
    with open(path) as fh:
        fh.readline()
        ne, np_ = (int(x) for x in fh.readline().split()[:2])
        xy = np.empty((np_, 2))
        for i in range(np_):
            p = fh.readline().split()
            xy[i] = [float(p[1]), float(p[2])]
        tri = np.empty((ne, 3), dtype=np.int64)
        for i in range(ne):
            p = fh.readline().split()
            tri[i] = [int(p[2]), int(p[3]), int(p[4])]
    return xy, tri - 1


def derive_params(mesh_path: str) -> dict[str, float]:
    """Recover the size-field targets the original mesh was built to.

    hmin = the finest *real* element, i.e. the minimum edge length after
    dropping the bottom 0.1% as sliver/degenerate outliers. Using the 1st
    percentile (the previous rule) sat *above* the mesh's true resolution
    floor and under-resolved the coast/shelf, clipping the size field and
    piling distorted elements into the steep-gradient transition zone. The
    trimmed minimum reproduces the original element count instead.

    hmax = 99th edge-length percentile (coarsest interior, outliers trimmed).
    g    = 95th percentile of the per-edge local-size gradient
           |h_i - h_j| / L_ij (h = per-node mean edge length). The grading
           limit the original mesh actually uses; quality is insensitive to
           it here, so the derived value is kept.
    """
    xy, tri = parse_fort14_geometry(mesh_path)
    e = np.vstack([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
    e.sort(axis=1)
    e = np.unique(e, axis=0)
    d = xy[e[:, 0]] - xy[e[:, 1]]
    L = np.hypot(d[:, 0], d[:, 1])
    hnode = np.zeros(len(xy))
    cnt = np.zeros(len(xy))
    for k in range(2):
        np.add.at(hnode, e[:, k], L)
        np.add.at(cnt, e[:, k], 1)
    hnode /= np.maximum(cnt, 1)
    grad = np.abs(hnode[e[:, 0]] - hnode[e[:, 1]]) / L
    sliver_floor = np.percentile(L, 0.1)
    return {
        "hmin": float(L[L >= sliver_floor].min()),
        "hmax": float(np.percentile(L, 99)),
        "g": float(np.percentile(grad, 95)),
    }


def prepare_tree(ref: str, scratch: pathlib.Path) -> tuple[pathlib.Path, list[pathlib.Path]]:
    """Return (tree_root, cleanup_paths). ``current`` -> the live repo."""
    if ref == "current":
        return REPO, []
    tree = scratch / f"admesh_{ref.replace('/', '_')}"
    subprocess.run(["git", "worktree", "add", "--detach", str(tree), ref],
                   cwd=REPO, check=True, capture_output=True, text=True)
    return tree, [tree]


def run_worker(tree: pathlib.Path, domain: str, params: dict, niter: int,
               out: pathlib.Path, label: str) -> dict:
    cmd = [
        sys.executable, str(WORKER),
        "--domain", domain,
        "--hmin", str(params["hmin"]),
        "--hmax", str(params["hmax"]),
        "--g", str(params["g"]),
        "--niter", str(niter),
        "--out", str(out),
        "--label", label,
    ]
    env = {"PYTHONPATH": str(tree)}
    import os
    full_env = {**os.environ, **env}
    print(f"  running {label} (PYTHONPATH={tree}) ...", flush=True)
    subprocess.run(cmd, check=True, env=full_env)
    return json.loads(out.read_text())


def fmt(x: float) -> str:
    return f"{x:.3f}" if x < 10 else f"{x:.1f}"


def build_table(results: list[dict]) -> str:
    labels = [r["label"] for r in results]
    head = "| Algorithm step | " + " | ".join(labels) + " | speedup |"
    sep = "|" + "---|" * (len(labels) + 2)
    lines = [head, sep]
    base, last = results[0], results[-1]
    for key, disp in STAGE_ORDER:
        cells = [fmt(r["stages_sec"].get(key, 0.0)) for r in results]
        b = base["stages_sec"].get(key, 0.0)
        l = last["stages_sec"].get(key, 0.0)
        sp = f"{b / l:.1f}x" if l > 0 else "-"
        lines.append(f"| {disp} | " + " | ".join(cells) + f" | {sp} |")
    # totals
    tcells = [fmt(r["total_sec"]) for r in results]
    sp = f"{base['total_sec'] / last['total_sec']:.1f}x" if last["total_sec"] > 0 else "-"
    lines.append(f"| **TOTAL** | " + " | ".join(f"**{c}**" for c in tcells) + f" | **{sp}** |")
    # mesh stats footer
    lines.append("")
    lines.append("| | " + " | ".join(labels) + " |")
    lines.append("|---|" + "---|" * len(labels))
    lines.append("| nodes | " + " | ".join(str(r["n_nodes"]) for r in results) + " |")
    lines.append("| elements | " + " | ".join(str(r["n_elements"]) for r in results) + " |")
    lines.append("| distmesh iters | " + " | ".join(str(r["distmesh_iters"]) for r in results) + " |")
    lines.append("| Min. Elem Quality | " + " | ".join(f"{r['q_min']:.3f}" for r in results) + " |")
    lines.append("| Mean Elem Quality | " + " | ".join(f"{r['q_mean']:.3f}" for r in results) + " |")
    lines.append("| StDev Elem Quality | " + " | ".join(f"{r.get('q_std', float('nan')):.3f}" for r in results) + " |")
    return "\n".join(lines)


def make_histogram(results: list[dict], out_png: pathlib.Path) -> None:
    """One compact figure: quality map (top) + histogram (bottom) per version."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from chilmesh import CHILmesh

    n = len(results)
    fig, ax = plt.subplots(2, n, figsize=(8 * n, 11),
                           gridspec_kw={"height_ratios": [3, 1]}, squeeze=False)
    for j, res in enumerate(results):
        d = np.load(res["_meshnpz"])
        p, t = d["p"], d["t"].astype(int)
        pts = np.column_stack([p[:, 0], p[:, 1], np.zeros(len(p))])
        m = CHILmesh(connectivity=t, points=pts, compute_layers=False,
                     compute_adjacencies=True)
        q, _, _ = m.elem_quality()
        m.plot_quality(ax=ax[0, j])
        ax[0, j].set_title(f"{res['label']}\nn={m.n_elems}  "
                           f"min={q.min():.3f}  mean={q.mean():.3f}")
        m.plot_quality_histogram(bins=60, auto_norm=True, ax=ax[1, j])
        ax[1, j].set_title("quality distribution")
    fig.suptitle("Re-mesh quality — element skew (CHILmesh)", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_png, dpi=110)
    print(f"  [hist] {out_png}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mesh", required=True, help="original fort.14 mesh (param source)")
    ap.add_argument("--domain", required=True, help="domain boundary JSON to re-mesh")
    ap.add_argument("--ref", action="append", required=True, metavar="REF=LABEL",
                    help="git ref (or 'current') = column label; repeatable")
    ap.add_argument("--niter", type=int, default=120)
    ap.add_argument("--hist", action="store_true", help="CHILmesh quality histograms")
    ap.add_argument("--hmin", type=float, help="override derived hmin (e.g. to resolve sub-feature islands)")
    ap.add_argument("--hmax", type=float, help="override derived hmax")
    ap.add_argument("--g", type=float, help="override derived grading limit g")
    ap.add_argument("--out-md", default=str(REPO / "benchmarks" / "results" / "version_comparison.md"))
    args = ap.parse_args()

    refs = []
    for spec in args.ref:
        ref, _, label = spec.partition("=")
        refs.append((ref.strip(), (label.strip() or ref.strip())))

    params = derive_params(args.mesh)
    for k in ("hmin", "hmax", "g"):  # explicit overrides win over derivation
        v = getattr(args, k)
        if v is not None:
            params[k] = v
    print(f"Params from {pathlib.Path(args.mesh).name}: "
          f"hmin={params['hmin']:.4f} hmax={params['hmax']:.4f} g={params['g']:.3f}")

    domain_abs = str(pathlib.Path(args.domain).resolve())
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="admesh_bench_"))
    out_dir = REPO / "benchmarks" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    cleanups: list[pathlib.Path] = []
    try:
        for ref, label in refs:
            tree, cu = prepare_tree(ref, scratch)
            cleanups += cu
            out_json = scratch / f"{ref.replace('/', '_')}.json"
            res = run_worker(tree, domain_abs, params, args.niter, out_json, label)
            res["_meshnpz"] = str(out_json) + ".mesh.npz"
            results.append(res)
    finally:
        for tree in cleanups:
            subprocess.run(["git", "worktree", "remove", "--force", str(tree)],
                           cwd=REPO, capture_output=True, text=True)

    table = build_table(results)
    header = (
        f"# ADMESH version comparison — {pathlib.Path(args.domain).stem}\n\n"
        f"Params derived from `{pathlib.Path(args.mesh).name}`: "
        f"hmin={params['hmin']:.4f}, hmax={params['hmax']:.4f}, g={params['g']:.3f}. "
        f"Fixed niter={args.niter} (isolates per-call cost).\n\n"
    )
    pathlib.Path(args.out_md).write_text(header + table + "\n")
    print("\n" + table + "\n")
    print(f"[wrote] {args.out_md}")

    if args.hist:
        (REPO / "output").mkdir(parents=True, exist_ok=True)
        make_histogram(results, REPO / "output" / "wnat_quality_comparison.png")


if __name__ == "__main__":
    main()
