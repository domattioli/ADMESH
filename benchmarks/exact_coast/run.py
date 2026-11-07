"""Run round 1 of the exact-coast challenge.

    /Users/domattioli/Projects/MADMESHing/.venv-bench/bin/python benchmarks/exact_coast/run.py [domain ...]

Writes results/round1.csv and results/round1.md.
"""

from __future__ import annotations

import csv
import math
import os
import platform
import sys
import time
import traceback
from importlib import metadata
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import domains  # noqa: E402
import fields  # noqa: E402
import metrics  # noqa: E402
import tools  # noqa: E402

TOL = 0.05
MAX_BISECT = 12
TOOLS = ["admesh", "gmsh", "gmsh_opt", "triangle", "oceanmesh", "oceanmesh_pfix"]
COLS = [
    "domain", "tool", "status", "note", "s", "match_iters", "node_ratio_to_admesh",
    "nodes", "triangles", "seconds", "hausdorff", "vtx_kept_pct", "len_rel_err",
    "area_rel_err", "edge_err_med", "edge_err_p95", "sliver_rate", "q_min", "q_mean",
    "q_p5", "n_neg_area", "n_zero_area",
    "oc_q_min_raw", "oc_q_min_clean", "oc_faces_removed", "oc_bverts_removed",
    "oc_bad_raw", "oc_bad_raw_on_boundary", "oc_bad_clean", "oc_bad_clean_on_boundary",
    "oc_nodes_raw",
]


def match_nodes(run, rings, F1, H, target):
    """Find scale s so that node count is within TOL of target. Returns best result dict."""
    best = None
    lo = hi = None  # lo: s too small (too many nodes); hi: s too large (too few)
    s = 1.0
    for it in range(1, MAX_BISECT + 1):
        tools.LAST_DIAG.clear()
        nodes, tris, dt = run(rings, F1.scaled(s), H)
        n = len(nodes)
        err = abs(n / target - 1.0)
        if best is None or err < best["err"]:
            best = dict(s=s, nodes=nodes, tris=tris, dt=dt, err=err, iters=it,
                        diag=dict(tools.LAST_DIAG))
        if err <= TOL:
            break
        if n > target:
            lo = s if lo is None else max(lo, s)
        else:
            hi = s if hi is None else min(hi, s)
        s_new = s * math.sqrt(n / target)  # n ~ s^-2
        if lo is not None and hi is not None and not (lo < s_new < hi):
            s_new = math.sqrt(lo * hi)
        s = s_new
    best["iters"] = it
    best["matched"] = best["err"] <= TOL
    return best


def row_from(domain, tool, res, rings, F1, target):
    F = F1.scaled(res["s"])
    m = metrics.evaluate(res["nodes"], res["tris"], rings, F)
    r = dict(domain=domain, tool=tool, s=res["s"], match_iters=res["iters"],
             seconds=res["dt"], node_ratio_to_admesh=m["nodes"] / target)
    r.update(m)
    r.update(res.get("diag", {}))
    bad = m["n_neg_area"] > 0 or m["n_zero_area"] > 0
    notes = []
    if not res.get("matched", True):
        notes.append(f"node count not matched within {TOL:.0%} after {res['iters']} iters")
    if bad:
        notes.append("invalid: inverted/zero-area triangles")
    r["status"] = "invalid" if bad else ("ok" if not notes else "ok-unmatched")
    r["note"] = "; ".join(notes)
    return r


def fail_row(domain, tool, exc):
    return dict(domain=domain, tool=tool, status="FAIL",
                note=f"{type(exc).__name__}: {str(exc)[:200]}".replace("\n", " "))


def meta() -> dict:
    def v(p):
        try:
            return metadata.version(p)
        except Exception:
            return "?"

    import subprocess

    try:
        sysctl = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                                capture_output=True, text=True).stdout.strip()
    except Exception:
        sysctl = ""
    return {
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor() or "n/a",
        "cpu_brand": sysctl or "n/a",
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "oceanmesh": "git e7053b7 (installed dist-info 0+untagged.43.ge7053b7.dirty)", "admesh": v("admesh2D"), "gmsh": v("gmsh"), "triangle": v("triangle"),
        "shapely": v("shapely"), "numpy": v("numpy"), "scipy": v("scipy"),
        "seeds": "admesh seed=0; gmsh default (deterministic, Mesh.RandomFactor default); triangle deterministic",
        "threads": "gmsh General.NumThreads=1, Mesh.MaxNumThreads1D/2D=1",
    }


def fmt(x, spec):
    return "" if x is None or (isinstance(x, float) and math.isnan(x)) else format(x, spec)


def write_md(rows, md, path, total_s):
    head = ["domain", "tool", "status", "s", "nodes", "tris", "sec", "Hausd", "vtx kept %",
            "len err", "area err", "edge err med", "edge err p95", "sliver", "q min",
            "q mean", "q p5"]
    L = ["# Exact-coast challenge, round 1 (track A: matched node count)", ""]
    L += [f"- {k}: {v}" for k, v in md.items()]
    L += [f"- total runtime: {total_s:.1f} s", ""]
    L += ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        if r["status"] == "FAIL":
            L.append(f"| {r['domain']} | {r['tool']} | FAIL | " + " | ".join([r["note"]] + [""] * (len(head) - 4)) + " |")
            continue
        L.append("| " + " | ".join([
            r["domain"], r["tool"], r["status"], fmt(r["s"], ".3f"), str(r["nodes"]),
            str(r["triangles"]), fmt(r["seconds"], ".2f"), fmt(r["hausdorff"], ".2e"),
            fmt(r["vtx_kept_pct"], ".1f"), fmt(r["len_rel_err"], ".2e"),
            fmt(r["area_rel_err"], ".2e"), fmt(r["edge_err_med"], ".3f"),
            fmt(r["edge_err_p95"], ".3f"), fmt(r["sliver_rate"], ".4f"),
            fmt(r["q_min"], ".3f"), fmt(r["q_mean"], ".3f"), fmt(r["q_p5"], ".3f")]) + " |")
    notes = [f"- {r['domain']}/{r['tool']}: {r['note']}" for r in rows if r.get("note")]
    if notes:
        L += ["", "Notes:", *notes]
    path.write_text("\n".join(L) + "\n")


def main(only: list[str]) -> None:
    t_start = time.perf_counter()
    rows: list[dict] = []
    skipped = []
    for name, spec in domains.get_domains().items():
        if only and name not in only:
            continue
        dnote = ""
        if spec["rings"] is None:
            spec = domains.load_real(name, spec)
            if spec is None:
                skipped.append(name)
                continue
            dnote = spec.get("note", "")
        rings, H = spec["rings"], spec["H"]
        print(f"== {name} (H={H}) {dnote}", flush=True)
        fields.build_field(name, rings, H)
        F1 = fields.GridField.load(fields.FIELD_DIR / f"{name}.npz")

        # reference: ADMESH at s=1
        try:
            nodes, tris, dt = tools.run_admesh(rings, F1, H)
            ref = dict(s=1.0, nodes=nodes, tris=tris, dt=dt, iters=1, matched=True)
            target = len(nodes)
            r = row_from(name, "admesh", ref, rings, F1, target)
            r["note"] = "; ".join(x for x in [dnote, r["note"]] if x)
            rows.append(r)
            print(f"   admesh nodes={target} t={dt:.2f}s", flush=True)
        except Exception as e:
            traceback.print_exc()
            rows.append(fail_row(name, "admesh", e))
            for t in TOOLS[1:]:
                rows.append(fail_row(name, t, RuntimeError("no ADMESH reference node count")))
            continue

        gmsh_res = None
        for tool in ("gmsh", "triangle", "gmsh_opt", "oceanmesh", "oceanmesh_it100", "oceanmesh_it200", "oceanmesh_pfix", "oceanmesh_pfix_it200"):
            try:
                if tool == "gmsh_opt":
                    if gmsh_res is None:
                        raise RuntimeError("plain gmsh failed; no matched scale to reuse")
                    nodes, tris, dt = tools.run_gmsh(rings, F1.scaled(gmsh_res["s"]), H, optimize=True)
                    res = dict(gmsh_res, nodes=nodes, tris=tris, dt=dt, iters=0)
                    res["note_extra"] = "reuses gmsh matched s; Laplace2D x5 after generate (time includes it)"
                else:
                    res = match_nodes(tools.RUNNERS[tool], rings, F1, H, target)
                    if tool == "gmsh":
                        gmsh_res = res
                r = row_from(name, tool, res, rings, F1, target)
                if res.get("note_extra"):
                    r["note"] = "; ".join(x for x in [res["note_extra"], r["note"]] if x)
                rows.append(r)
                print(f"   {tool} s={r['s']:.3f} nodes={r['nodes']} ({r['status']}) t={r['seconds']:.2f}s", flush=True)
            except Exception as e:
                traceback.print_exc()
                rows.append(fail_row(name, tool, e))

    total = time.perf_counter() - t_start
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    with open(out / "round1.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in COLS})
    md = meta()
    if skipped:
        md["skipped_domains"] = ", ".join(skipped)
    md["match_rule"] = f"node count within {TOL:.0%} of ADMESH at s=1, <= {MAX_BISECT} iterations"
    md["total_runtime_s"] = f"{total:.1f}"
    (out / "round1_meta.txt").write_text("\n".join(f"{k}: {v}" for k, v in md.items()) + "\n")
    write_md(rows, md, out / "round1.md", total)
    print(f"done in {total:.1f}s")


if __name__ == "__main__":
    main(sys.argv[1:])
