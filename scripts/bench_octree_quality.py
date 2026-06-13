"""Octree vs uniform background — end-to-end quality + parity benchmark (spec-029 P3).

Research instrumentation. Compares `triangulate(background="uniform")` vs
`triangulate(background="octree")` on meshable registry/MVP domains:
wall-clock, node count, min_q / mean_q, structural validity. Plus a graded
multiscale case and an octree size-field fidelity (SC-005) check.

Run: .venv/bin/python scripts/bench_octree_quality.py
"""
from __future__ import annotations
import time, sys
import numpy as np
import admesh
from admesh import domains as D


def structural_valid(mesh) -> tuple[bool, str]:
    """Positive-area tris (consistent orientation), no NaN nodes."""
    p = np.asarray(mesh.nodes, float)
    t = np.asarray(mesh.elements, int)
    if np.isnan(p).any():
        return False, "NaN nodes"
    if len(t) == 0:
        return False, "no elements"
    a = p[t[:, 0]]; b = p[t[:, 1]]; c = p[t[:, 2]]
    area2 = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
    if np.any(np.abs(area2) < 1e-14):
        return False, f"{int(np.sum(np.abs(area2) < 1e-14))} zero-area tris"
    # consistent sign (all CW or all CCW) — watertight, non-folded
    if not (np.all(area2 > 0) or np.all(area2 < 0)):
        return False, "mixed-orientation tris (fold)"
    return True, "ok"


def one(domain, name, h_max, h_min, contribs=()):
    row = {"domain": name}
    for bg in ("uniform", "octree"):
        try:
            t0 = time.perf_counter()
            m = admesh.triangulate(domain, h_max=h_max, h_min=h_min,
                                   user_contribs=contribs, background=bg,
                                   seed=0, quality_gate=(0.0, 0.0))
            dt = time.perf_counter() - t0
            ok, why = structural_valid(m)
            q = np.asarray(m.quality, float)
            row[bg] = dict(n=len(m.nodes), e=len(m.elements), t=dt,
                           min_q=float(q.min()), mean_q=float(q.mean()),
                           valid=ok, why=why)
        except Exception as ex:
            row[bg] = dict(err=f"{type(ex).__name__}: {ex}")
    return row


def fmt(r):
    d = r["domain"]
    for bg in ("uniform", "octree"):
        v = r[bg]
        if "err" in v:
            print(f"  {d:18} {bg:8} ERR {v['err'][:70]}")
        else:
            print(f"  {d:18} {bg:8} {v['n']:5}n {v['e']:5}e {v['t']:6.2f}s "
                  f"min_q={v['min_q']:.3f} mean_q={v['mean_q']:.3f} "
                  f"valid={'Y' if v['valid'] else 'N('+v['why']+')'}")


def main():
    print("=== P3a: MVP/registry domains, uniform vs octree background ===")
    cases = [
        (D.UNIT_SQUARE, "UNIT_SQUARE", 0.1, 0.02),
        (D.L_SHAPE, "L_SHAPE", 0.1, 0.02),
        (D.ANNULUS, "ANNULUS", 0.1, 0.02),
        (D.UNIT_DISK, "UNIT_DISK", 0.1, 0.02),
        (D.NOTCHED_RECTANGLE, "NOTCHED_RECT", 0.1, 0.02),
    ]
    rows = []
    for dom, name, hmx, hmn in cases:
        r = one(dom, name, hmx, hmn)
        rows.append(r); fmt(r)

    print("\n=== P3b: graded multiscale size field (radial fine-center) ===")
    # fine near center, coarse at edges — the case octree exists for
    def radial(pts):
        pts = np.atleast_2d(np.asarray(pts, float))
        rr = np.hypot(pts[:, 0], pts[:, 1])
        return 0.015 + 0.12 * rr   # 0.015 at center -> ~0.1 at edge
    r = one(D.UNIT_DISK, "DISK_graded", 0.12, 0.015, contribs=(radial,))
    rows.append(r); fmt(r)

    print("\n=== P3c: octree size-field fidelity (SC-005-style) ===")
    # octree fh should represent the sampled oracle to < 5% of h_max
    from admesh.octree import octree_size_field
    h_min, h_max = 0.015, 0.12
    class Shim:
        bbox = (-1.0, -1.0, 1.0, 1.0)
    base = lambda p: np.clip(radial(p), h_min, h_max)
    fh_lim = octree_size_field(Shim, base, h_min=h_min, h_max=h_max, gradient_limit=True)
    fh_raw = octree_size_field(Shim, base, h_min=h_min, h_max=h_max, gradient_limit=False)
    gx, gy = np.meshgrid(np.linspace(-0.95, 0.95, 80), np.linspace(-0.95, 0.95, 80))
    P = np.column_stack([gx.ravel(), gy.ravel()])
    truth = base(P)
    err_raw = np.max(np.abs(fh_raw(P) - truth)) / h_max
    err_lim = np.max(np.abs(fh_lim(P) - truth)) / h_max
    print(f"  octree(no-limit) vs oracle: max|dh|/h_max = {err_raw:.4f}  (SC-005 gate < 0.05: {'PASS' if err_raw<0.05 else 'FAIL'})")
    print(f"  octree(gradient-limited) vs oracle: max|dh|/h_max = {err_lim:.4f}  (expected larger; limiter smooths by design)")

    # summary verdict
    print("\n=== VERDICT ===")
    all_valid = all(("err" not in r["octree"]) and r["octree"].get("valid", False) for r in rows)
    print(f"  octree structural validity all rows: {'PASS' if all_valid else 'FAIL'}")
    print(f"  SC-005 fidelity (no-limit): {'PASS' if err_raw < 0.05 else 'FAIL'}")
    return 0 if (all_valid and err_raw < 0.05) else 1


if __name__ == "__main__":
    sys.exit(main())
