"""Benchmark the three ``medial_method`` options of ``triangulate``.

Runs ``triangulate(..., medial_method=m)`` for m in {grid, octree, vdt} on the
WNAT test mesh and on ENPAC, with identical settings for the three methods on
each domain, and writes ``benchmarks/medial_vdt.json`` and
``benchmarks/medial_vdt.md``. It then applies the default-change gate
mechanically and prints one line, ``VERDICT: flip`` or ``VERDICT: opt-in``.

Per row it records wall time, element count, min and mean element quality and
corner over-refinement.

Corner over-refinement
    A convex corner is a boundary vertex whose domain-side interior angle,
    measured between chords of length ``h_max``, is at most 135 degrees.
    Within radius ``r = 2 * h_max`` of those corners, the element density is
    ``N / sum(area)`` over the elements whose centroid lies in the radius. The
    ratio is that density divided by the median over all elements of
    ``1 / area`` (the median element density of the domain).

Gate (flip only if every line holds for each domain d in {WNAT, ENPAC} and each
baseline b in {grid, octree}; any miss, tie or failed row gives opt-in):
    1. corner_over(vdt, d) < corner_over(b, d)
    2. min_q(vdt, d)  >= 0.98 * min_q(b, d)
    3. mean_q(vdt, d) >= 0.98 * mean_q(b, d)
    4. |elements(vdt, d) / elements(b, d) - 1| <= 0.10
    5. time(vdt, d) <= 1.5 * time(octree, d)

The ENPAC fort.14 file is read from the path in the environment variable
``ADMESH_ENPAC_14``. When it is unset or missing, the ENPAC rows are recorded
as skipped and the verdict is ``opt-in``.

Usage (from the repository root)::

    ADMESH_ENPAC_14=/path/to/EasternPacific_ENPAC2003.14 python scripts/bench_medial.py
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
import warnings
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = REPO_ROOT / "benchmarks" / "medial_vdt.json"
OUT_MD = REPO_ROOT / "benchmarks" / "medial_vdt.md"
WNAT_REL = "tests/fixtures/fort14/adcirc_examples/wnat_test.14"
ENPAC_ENV = "ADMESH_ENPAC_14"

METHODS = ("grid", "octree", "vdt")
DOMAINS = ("WNAT", "ENPAC")

# One settings block per domain, shared by the three methods. Units are the
# domain's own (degrees of longitude and latitude for both meshes).
#
# h_max is much coarser than the full-resolution target of the default
# pipeline benchmark (1.5 / 111 degrees) so that the whole run fits in about
# 30 minutes: the octree method builds its tree with one signed-distance call
# per cell, which is the dominant cost on WNAT. The coarsening is the same for
# all three methods. max_iter caps the mesh-generator iterations for the same
# reason.
SETTINGS = {
    "WNAT": {"h_max": 0.5, "h_min": 0.1, "max_iter": 60, "seed": 0},
    "ENPAC": {"h_max": 0.3, "h_min": 0.06, "max_iter": 60, "seed": 0},
}
CORNER_ANGLE_DEG = 135.0
CORNER_RADIUS_FACTOR = 2.0


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------
# Domains
# --------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_wnat():
    import admesh
    from admesh.fort14 import read_fort14

    mesh = read_fort14(REPO_ROOT / WNAT_REL)
    domain = admesh.Domain.from_mesh(mesh)
    rings = [np.asarray(mesh.nodes[s.node_ids], dtype=float) for s in domain.bc_segments]
    return domain, rings, {"path": WNAT_REL}


def load_enpac():
    import admesh
    from admesh.fort14 import read_fort14

    raw = os.environ.get(ENPAC_ENV)
    if not raw:
        return None, None, {"skipped": f"environment variable {ENPAC_ENV} is not set"}
    path = Path(raw)
    if not path.is_file():
        return None, None, {"skipped": f"{ENPAC_ENV} does not point to a file"}
    domain = admesh.load_domain_from_fort14(str(path))
    mesh = read_fort14(path)
    # The loader uses the first closed land boundary as the outer ring.
    ring = None
    for seg in mesh.boundaries:
        if not seg.is_open:
            ring = np.asarray(mesh.nodes[seg.node_ids], dtype=float)
            break
    return domain, [ring], {"file": path.name, "env": ENPAC_ENV, "sha256": _sha256(path)}


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------


def _signed_area(ring: np.ndarray) -> float:
    x, y = ring[:, 0], ring[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def convex_corners(rings: list[np.ndarray], h_max: float) -> np.ndarray:
    """Convex boundary corners of the domain, as an (K, 2) array."""
    areas = [abs(_signed_area(r)) for r in rings]
    outer = int(np.argmax(areas))
    found: list[tuple[float, np.ndarray]] = []
    step = h_max / 2.0
    for idx, ring in enumerate(rings):
        pts = np.asarray(ring, dtype=float)
        if np.linalg.norm(pts[0] - pts[-1]) > 1e-12:
            pts = np.vstack([pts, pts[:1]])
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        arc = np.concatenate([[0.0], np.cumsum(seg)])
        total = arc[-1]
        n = int(total // step)
        if n < 8:
            continue
        s = np.linspace(0.0, total, n, endpoint=False)
        px = np.interp(s, arc, pts[:, 0])
        py = np.interp(s, arc, pts[:, 1])
        P = np.column_stack([px, py])
        ccw = _signed_area(pts[:-1]) > 0
        domain_left = ccw if idx == outer else not ccw
        a = np.roll(P, 2, axis=0) - P
        b = np.roll(P, -2, axis=0) - P
        na, nb = np.linalg.norm(a, axis=1), np.linalg.norm(b, axis=1)
        ok = (na > 0) & (nb > 0)
        cosang = np.zeros(n)
        cosang[ok] = np.einsum("ij,ij->i", a[ok], b[ok]) / (na[ok] * nb[ok])
        ang = np.degrees(np.arccos(np.clip(cosang, -1.0, 1.0)))
        # turn direction of travel P[k-2] -> P[k] -> P[k+2]
        cross = (-a[:, 0]) * b[:, 1] - (-a[:, 1]) * b[:, 0]
        convex = (cross > 0) if domain_left else (cross < 0)
        for k in np.nonzero(ok & convex & (ang <= CORNER_ANGLE_DEG))[0]:
            found.append((float(ang[k]), P[k]))
    found.sort(key=lambda t: t[0])
    accepted: list[np.ndarray] = []
    for _, p in found:
        if all(np.linalg.norm(p - q) > h_max for q in accepted):
            accepted.append(p)
    return np.array(accepted) if accepted else np.empty((0, 2))


def element_metrics(mesh, corners: np.ndarray, h_max: float) -> dict:
    n, e = mesh.nodes, mesh.elements
    v0, v1, v2 = n[e[:, 0]], n[e[:, 1]], n[e[:, 2]]
    area = 0.5 * np.abs(
        (v1[:, 0] - v0[:, 0]) * (v2[:, 1] - v0[:, 1])
        - (v1[:, 1] - v0[:, 1]) * (v2[:, 0] - v0[:, 0])
    )
    area = np.maximum(area, 1e-300)
    cent = (v0 + v1 + v2) / 3.0
    median_density = float(np.median(1.0 / area))
    corner_over = None
    n_near = 0
    if len(corners):
        dist, _ = cKDTree(corners).query(cent)
        near = dist <= CORNER_RADIUS_FACTOR * h_max
        n_near = int(near.sum())
        if n_near:
            corner_over = float((n_near / area[near].sum()) / median_density)
    return {
        "elements": int(len(e)),
        "min_q": float(np.min(mesh.quality)),
        "mean_q": float(np.mean(mesh.quality)),
        "corner_over": corner_over,
        "n_corners": int(len(corners)),
        "n_elements_near_corners": n_near,
    }


# --------------------------------------------------------------------------
# Runs and gate
# --------------------------------------------------------------------------


def run_row(domain_name: str, method: str, domain, corners) -> dict:
    import admesh

    cfg = SETTINGS[domain_name]
    row = {"domain": domain_name, "method": method, "status": "ok", **{
        k: None for k in ("time_s", "elements", "min_q", "mean_q", "corner_over")
    }}
    t0 = time.perf_counter()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mesh = admesh.triangulate(
                domain,
                h_max=cfg["h_max"],
                h_min=cfg["h_min"],
                seed=cfg["seed"],
                max_iter=cfg["max_iter"],
                medial_method=method,
                quality_gate=(0.0, 0.0),
            )
        row["time_s"] = time.perf_counter() - t0
        row.update(element_metrics(mesh, corners, cfg["h_max"]))
    except Exception as exc:  # noqa: BLE001 - recorded in the row
        row["time_s"] = time.perf_counter() - t0
        row["status"] = f"error: {type(exc).__name__}: {exc}"[:300]
    return row


def _lookup(rows, domain, method):
    for r in rows:
        if r["domain"] == domain and r["method"] == method:
            return r
    return None


def _usable(r) -> bool:
    return (
        r is not None
        and r["status"] == "ok"
        and r["corner_over"] is not None
        and r["elements"]
    )


def apply_gate(rows) -> tuple[str, dict]:
    gate: dict = {}
    flip = True
    for d in DOMAINS:
        gate[d] = {}
        v, o = _lookup(rows, d, "vdt"), _lookup(rows, d, "octree")
        for b in ("grid", "octree"):
            base = _lookup(rows, d, b)
            if not (_usable(v) and _usable(base) and _usable(o)):
                gate[d][b] = {"usable": False, "all": False}
                flip = False
                continue
            c = {
                "corner_over_lower": bool(v["corner_over"] < base["corner_over"]),
                "min_q_within_2pct": bool(v["min_q"] >= 0.98 * base["min_q"]),
                "mean_q_within_2pct": bool(v["mean_q"] >= 0.98 * base["mean_q"]),
                "elements_within_10pct": bool(
                    abs(v["elements"] / base["elements"] - 1.0) <= 0.10
                ),
                "time_within_1p5x_octree": bool(v["time_s"] <= 1.5 * o["time_s"]),
            }
            c["usable"] = True
            c["all"] = all(c[k] for k in list(c) if k not in ("usable",))
            gate[d][b] = c
            flip = flip and c["all"]
    return ("flip" if flip else "opt-in"), gate


def _fmt(x, nd=3):
    return "-" if x is None else f"{x:.{nd}f}"


def markdown(rows, gate, verdict, sources) -> str:
    out = [
        "# Medial method benchmark",
        "",
        "Generated by `scripts/bench_medial.py`. Each domain uses identical",
        "settings for the three methods.",
        "",
        "| domain | method | status | time (s) | elements | min_q | mean_q | corner over-refinement |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        out.append(
            f"| {r['domain']} | {r['method']} | {r['status'][:40]} | {_fmt(r['time_s'], 1)} | "
            f"{r['elements'] if r['elements'] is not None else '-'} | {_fmt(r['min_q'])} | "
            f"{_fmt(r['mean_q'])} | {_fmt(r['corner_over'], 2)} |"
        )
    out += ["", "## Settings", ""]
    for d in DOMAINS:
        out.append(f"- {d}: {json.dumps(SETTINGS[d])}")
    out += ["", "## Gate", ""]
    for d in DOMAINS:
        for b, c in gate[d].items():
            flags = ", ".join(f"{k}={v}" for k, v in c.items())
            out.append(f"- {d}, vdt vs {b}: {flags}")
    out += ["", f"Verdict: **{verdict}**", ""]
    return "\n".join(out)


def main() -> int:
    loaders = {"WNAT": load_wnat, "ENPAC": load_enpac}
    rows: list[dict] = []
    sources: dict = {}
    for name in DOMAINS:
        log(f"loading {name}")
        domain, rings, info = loaders[name]()
        sources[name] = info
        if domain is None:
            log(f"skip {name}: {info['skipped']}")
            for m in METHODS:
                rows.append({
                    "domain": name, "method": m, "status": f"skipped: {info['skipped']}",
                    "time_s": None, "elements": None, "min_q": None,
                    "mean_q": None, "corner_over": None,
                })
            continue
        corners = convex_corners(rings, SETTINGS[name]["h_max"])
        log(f"{name}: {len(corners)} convex corners")
        for m in METHODS:
            log(f"run {name} {m}")
            row = run_row(name, m, domain, corners)
            log(f"  -> {row['status']} t={_fmt(row['time_s'], 1)}s n={row['elements']}")
            rows.append(row)

    verdict, gate = apply_gate(rows)
    payload = {
        "description": "medial_method benchmark (grid, octree, vdt) with the default-change gate",
        "settings": SETTINGS,
        "corner_definition": {
            "max_interior_angle_deg": CORNER_ANGLE_DEG,
            "radius": f"{CORNER_RADIUS_FACTOR} * h_max",
        },
        "sources": sources,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "rows": rows,
        "gate": gate,
        "verdict": verdict,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n")
    OUT_MD.write_text(markdown(rows, gate, verdict, sources))
    print(f"VERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
