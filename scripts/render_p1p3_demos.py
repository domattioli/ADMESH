"""Render P1 + P3 demonstration meshes — before/after the enrichments.

For each demo domain, produce a 2-up PNG comparing:
- **Before** — ``triangulate(Domain)`` with a uniform size function
  (the MVP M.4 path, which is what ``tests/output/mvp_*.png``
  currently shows).
- **After** — the same domain with a P1/P3 enrichment applied:
    - `unit_disk`: curvature-driven refinement via `build_h(curvature_scale=…)`
    - `annulus`: PTS-driven boundary refinement via the `triangulate(pts)` path
    - `notched_rectangle`: medial-axis LFS refinement via `build_h(medial_scale=…)`

Writes `tests/output/demo_<name>.png`. Metrics table is printed on
stdout so it can be pasted into the README / session report.

Run:
    python scripts/render_p1p3_demos.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from admesh import domains
from admesh.boundary import PTS, BoundaryType
from admesh.mesh_size import build_h
from admesh.quality import mesh_quality
from admesh.routine import triangulate

matplotlib.use("Agg")

OUTDIR = Path(__file__).resolve().parent.parent / "tests" / "output"
OUTDIR.mkdir(parents=True, exist_ok=True)


def _metrics(p, t):
    min_q, mean_q, _ = mesh_quality(p, t)
    return {"N": len(p), "T": len(t), "min_q": float(min_q), "mean_q": float(mean_q)}


def _draw(ax, p, t, *, title: str, node_bc=None) -> None:
    ax.triplot(p[:, 0], p[:, 1], t, lw=0.5, color="#1f77b4")
    if node_bc is not None:
        # Color nodes by BC label. -1 = interior, 0 = OPEN, 1 = WALL.
        interior = node_bc == -1
        wall = node_bc == int(BoundaryType.WALL)
        open_bc = node_bc == int(BoundaryType.OPEN)
        ax.plot(p[interior, 0], p[interior, 1], ".", ms=2, color="#999")
        ax.plot(p[wall, 0], p[wall, 1], ".", ms=4, color="#d62728")
        ax.plot(p[open_bc, 0], p[open_bc, 1], ".", ms=4, color="#2ca02c")
    else:
        ax.plot(p[:, 0], p[:, 1], ".", ms=2, color="#d62728")
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=10)
    ax.grid(True, alpha=0.2)


def demo_unit_disk_medial():
    """Before: uniform h0=0.05. After: medial-scaled build_h with h0
    matching the finest scale.

    The LFS (medial-distance) rule makes h smallest AT the medial axis
    (the origin) and grows outward. Setting ``h0 = medial_scale``
    ensures the initial lattice is dense enough that rejection
    keeps the full mesh in the coarsened regions, rather than
    emptying them out.
    """
    dom = domains.UNIT_DISK
    # Before: uniform with the same h0 — so "after" isn't unfairly dense.
    p0, t0 = triangulate(dom, h0=0.05, niter=200, seed=0)
    m_before = _metrics(p0, t0)

    fh = build_h(dom, base=0.25, medial_scale=0.05, grid_delta=0.03)
    p1, t1 = triangulate(dom, h0=0.05, fh=fh, niter=250, seed=0)
    m_after = _metrics(p1, t1)

    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    _draw(axes[0], p0, t0,
          title=f"Before — uniform h0=0.05  N={m_before['N']} mean_q={m_before['mean_q']:.3f}")
    _draw(axes[1], p1, t1,
          title=f"After — medial LFS  N={m_after['N']} mean_q={m_after['mean_q']:.3f}")
    fig.suptitle("unit_disk: medial-axis LFS refinement (fine at center, coarser toward boundary)", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUTDIR / "demo_unit_disk_medial.png", dpi=120)
    plt.close(fig)
    return m_before, m_after


def demo_annulus_pts():
    """Before: uniform Domain path. After: PTS path with per-ring BC."""
    dom = domains.ANNULUS
    # Before: same h0 as the "after" finest scale.
    p0, t0 = triangulate(dom, h0=0.04, niter=200, seed=0)
    m_before = _metrics(p0, t0)
    m_before["bc_labeled"] = 0

    # After: PTS path with outer=OPEN, inner=WALL. n_bnd ≈ perimeter /
    # boundary_scale so the pfix ring vertices spacing matches the
    # target h at the boundary (else distmesh forms slivers between
    # finer interior points and coarser pfix).
    boundary_scale = 0.04
    outer_perimeter = 2 * np.pi * 1.0
    n_bnd = int(round(outer_perimeter / boundary_scale))
    pts_auto = PTS.from_domain(dom, n_bnd=n_bnd)
    pts = PTS.from_polygons(
        pts_auto.rings[0], holes=[pts_auto.rings[1]],
        bc=[BoundaryType.OPEN, BoundaryType.WALL],
    )
    fh = build_h(
        dom, base=0.15, pts=pts,
        boundary_scale={int(BoundaryType.OPEN): boundary_scale,
                        int(BoundaryType.WALL): boundary_scale},
        grid_delta=0.02,
    )
    # MATLAB-port default niter=1000; the best-quality tracker in the
    # last 50 iters only works once the mesh has reached equilibrium.
    # Pass the analytic SDF when the caller has one — avoids the
    # polygon-SDF approximation artifacts.
    out = triangulate(pts, h0=0.04, fh=fh, seed=0, fd=dom.fd)
    m_after = _metrics(out.p, out.t)
    m_after["bc_labeled"] = int((out.node_bc >= 0).sum())

    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    _draw(axes[0], p0, t0,
          title=f"Before — Domain path, uniform  N={m_before['N']} mean_q={m_before['mean_q']:.3f}")
    _draw(axes[1], out.p, out.t, node_bc=out.node_bc,
          title=f"After — PTS path, labeled  N={m_after['N']} (labeled={m_after['bc_labeled']})")
    fig.suptitle("annulus: PTS path with per-ring BC tags (green=OPEN outer, red=WALL inner)", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUTDIR / "demo_annulus_pts.png", dpi=120)
    plt.close(fig)
    return m_before, m_after


def demo_notched_rect_medial():
    """Before: uniform. After: curvature + medial-axis composition.

    Mirrors MATLAB ``ADmeshRoutine.m`` lines 168 + 178 — CurvatureFunction
    then MedialAxisFunction, each ``min``-stacked onto h0. Curvature
    captures the convex/re-entrant corner singularities at the notch
    that medial-LFS alone misses (the AOF-detected medial axis doesn't
    extend into the wedge sectors directly under the notch corners).
    """
    dom = domains.NOTCHED_RECTANGLE
    # Before at the same h0 for apples-to-apples comparison.
    p0, t0 = triangulate(dom, h0=0.04, niter=200, seed=0)
    m_before = _metrics(p0, t0)

    fh = build_h(dom, base=0.12, curvature_scale=0.04, medial_scale=0.04, grid_delta=0.02)
    p1, t1 = triangulate(dom, h0=0.04, fh=fh, niter=250, seed=0)
    m_after = _metrics(p1, t1)

    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    _draw(axes[0], p0, t0,
          title=f"Before — uniform h0=0.04  N={m_before['N']} mean_q={m_before['mean_q']:.3f}")
    _draw(axes[1], p1, t1,
          title=f"After — curvature + medial LFS  N={m_after['N']} mean_q={m_after['mean_q']:.3f}")
    fig.suptitle("notched_rectangle: curvature + medial-axis composition (MATLAB K + R stages)", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUTDIR / "demo_notched_rectangle_medial.png", dpi=120)
    plt.close(fig)
    return m_before, m_after


def main() -> None:
    np.random.seed(0)

    print(f"Rendering P1/P3 demo meshes to {OUTDIR}\n")
    header = f"{'demo':<40} {'N (before)':>11} {'N (after)':>10} {'min_q (b)':>10} {'min_q (a)':>10} {'mean_q (b)':>11} {'mean_q (a)':>11}"
    print(header)
    print("-" * len(header))

    demos: list[tuple[str, Callable]] = [
        ("unit_disk: medial LFS", demo_unit_disk_medial),
        ("annulus: PTS path + labels", demo_annulus_pts),
        ("notched_rectangle: medial LFS", demo_notched_rect_medial),
    ]
    for name, fn in demos:
        b, a = fn()
        print(
            f"{name:<40} "
            f"{b['N']:>11} {a['N']:>10} "
            f"{b['min_q']:>10.3f} {a['min_q']:>10.3f} "
            f"{b['mean_q']:>11.3f} {a['mean_q']:>11.3f}"
        )
    print("\nDone.")


if __name__ == "__main__":
    main()
