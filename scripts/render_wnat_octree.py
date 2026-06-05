"""WNAT-Onur octree demo + benchmark (spec 022).

Side-by-side comparison of the spec-022 pointer quadtree against a
uniform Cartesian background grid on the Western North Atlantic
(Onur 144-ring boundary, ~9 300 vertices, ~38° × 38° span).

Panels:
  - LEFT  — uniform grid at delta = h_min × 4 (the tractable baseline).
  - RIGHT — octree size-field leaves graded by 0.4 × |fd| (clamped to
            [h_min, h_max]), 2:1 balanced.

Timings:
  - Uniform grid build: meshgrid + per-point shapely-contains filter.
  - Octree build: build_octree (O(N log N) Samet pointer descent).

Usage: python scripts/render_wnat_octree.py
Output: output/wnat_octree.png  +  stdout timing table.
"""

from __future__ import annotations

import json
import pathlib
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import shapely  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402

from admesh._stages.octree_grid import build_octree  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
ONUR = REPO / "benchmarks" / "data" / "wnat_onur_boundary.json"
OUT = REPO / "output" / "wnat_octree.png"
H_MIN = 0.3   # degrees (~ 33 km at equator)
H_MAX = 4.0   # degrees (~ 440 km)
UNIFORM_DELTA = H_MIN   # uniform grid must match octree finest level — fair baseline


def load_onur_polygon() -> Polygon:
    """Build a single shapely Polygon (outer + 143 holes) from the JSON."""
    data = json.loads(ONUR.read_text())
    rings = data["rings"]
    outer = rings[0]
    holes = [r for r in rings[1:] if len(r) >= 3]
    return Polygon(outer, holes=holes), data["bbox"]


def make_sdf(poly: Polygon):
    """Return fd(p) where p is (N,2); negative inside, positive outside."""
    boundary = poly.boundary
    prepared_poly = shapely.prepare(poly)  # speeds up contains

    def fd(p):
        p = np.asarray(p, dtype=np.float64).reshape(-1, 2)
        pts = shapely.points(p[:, 0], p[:, 1])
        d = shapely.distance(pts, boundary)
        inside = shapely.contains(poly, pts)
        return np.where(inside, -d, d)

    _ = prepared_poly  # keep prepared cache live
    return fd


def time_uniform(bbox, fd) -> tuple[np.ndarray, float, int]:
    """Build a uniform delta grid; return interior centers, build time, total count."""
    xmin, ymin, xmax, ymax = bbox
    pad = H_MAX
    xs = np.arange(xmin - pad, xmax + pad, UNIFORM_DELTA)
    ys = np.arange(ymin - pad, ymax + pad, UNIFORM_DELTA)
    t0 = time.perf_counter()
    X, Y = np.meshgrid(xs, ys)
    p = np.c_[X.ravel(), Y.ravel()]
    d = fd(p)
    dt = time.perf_counter() - t0
    return p[d < 0], dt, len(p)


def time_octree(bbox, fd) -> tuple[object, float]:
    """Build the spec-022 octree; return grid + build time."""
    class _Dom:
        pass
    dom = _Dom()
    dom.fd = fd
    dom.bbox = tuple(bbox)
    oracle = lambda x, y: max(H_MIN, min(H_MAX, 0.4 * abs(fd(np.array([[x, y]]))[0])))  # noqa: E731
    t0 = time.perf_counter()
    g = build_octree(dom, h_min=H_MIN, h_max=H_MAX, size_oracle=oracle, balance=True)
    dt = time.perf_counter() - t0
    return g, dt


def plot_uniform(ax, interior_pts, n_total, bbox, t_build, outer_xy):
    ax.plot(outer_xy[:, 0], outer_xy[:, 1], color="black", lw=0.6)
    ax.scatter(interior_pts[:, 0], interior_pts[:, 1], s=1.2, c="#d62728", alpha=0.7)
    ax.set_aspect("equal")
    ax.set_xlim(bbox[0] - 0.5, bbox[2] + 0.5)
    ax.set_ylim(bbox[1] - 0.5, bbox[3] + 0.5)
    ax.set_title(
        f"WITHOUT octree (uniform Δ={UNIFORM_DELTA:.1f}°)\n"
        f"{n_total:,} grid pts → {len(interior_pts):,} interior  ·  build {t_build:.2f}s",
        fontsize=10,
    )


def plot_octree(ax, grid, bbox, t_build, outer_xy):
    from matplotlib.patches import Rectangle
    leaves = grid.leaves
    inside_centers = []
    for lf in leaves:
        x, y = lf.center
        s = lf.size
        col = "#2ca02c" if lf.D < 0 else "#cccccc"
        ax.add_patch(Rectangle((x - s / 2, y - s / 2), s, s,
                               linewidth=0.15, edgecolor="#444444",
                               facecolor=col, alpha=0.45))
        if lf.D < 0:
            inside_centers.append((x, y))
    inside_centers = np.array(inside_centers)
    ax.plot(outer_xy[:, 0], outer_xy[:, 1], color="black", lw=0.6)
    ax.set_aspect("equal")
    ax.set_xlim(bbox[0] - 0.5, bbox[2] + 0.5)
    ax.set_ylim(bbox[1] - 0.5, bbox[3] + 0.5)
    ax.set_title(
        f"WITH octree (spec 022, balance=2:1)\n"
        f"{len(leaves):,} leaves → {len(inside_centers):,} interior  ·  build {t_build:.2f}s",
        fontsize=10,
    )


def main():
    print(f"=== WNAT-Onur octree demo (spec 022) ===")
    print(f"  source: {ONUR.relative_to(REPO)}")
    print(f"  h_min={H_MIN}°  h_max={H_MAX}°  uniform Δ={UNIFORM_DELTA}°")
    print()

    poly, bbox = load_onur_polygon()
    outer_xy = np.array(poly.exterior.coords)
    print(f"  loaded: outer={len(outer_xy)} verts, holes={len(poly.interiors)}, "
          f"bbox span x={bbox[2]-bbox[0]:.1f}° y={bbox[3]-bbox[1]:.1f}°")

    fd = make_sdf(poly)

    print(f"\n[1/2] uniform grid …", end=" ", flush=True)
    uniform_pts, t_uniform, n_uniform = time_uniform(bbox, fd)
    print(f"{t_uniform:.2f}s  ({n_uniform:,} grid pts)")

    print(f"[2/2] octree build …", end=" ", flush=True)
    grid, t_octree = time_octree(bbox, fd)
    print(f"{t_octree:.2f}s  ({len(grid.leaves):,} leaves)")

    speedup = t_uniform / t_octree if t_octree > 0 else float("inf")
    leaves_inside = sum(1 for lf in grid.leaves if lf.D < 0)
    print()
    print("=== timing table ===")
    print(f"| method   | build time | total cells | interior cells |")
    print(f"|----------|-----------:|------------:|---------------:|")
    print(f"| uniform  | {t_uniform:8.2f}s | {n_uniform:>11,} | {len(uniform_pts):>14,} |")
    print(f"| octree   | {t_octree:8.2f}s | {len(grid.leaves):>11,} | {leaves_inside:>14,} |")
    print(f"  octree build-time speedup: {speedup:.2f}×")
    print(f"  octree cell-count reduction: {n_uniform / max(len(grid.leaves), 1):.1f}×")
    print()

    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    plot_uniform(axes[0], uniform_pts, n_uniform, bbox, t_uniform, outer_xy)
    plot_octree(axes[1], grid, bbox, t_octree, outer_xy)
    fig.suptitle(
        f"WNAT-Onur background grid · uniform vs spec-022 octree  "
        f"(h_min={H_MIN}°, h_max={H_MAX}°)",
        fontsize=12,
    )
    fig.tight_layout()
    OUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUT, dpi=140)
    plt.close(fig)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
