#!/usr/bin/env python3
"""Generate ADMESH visualization data on Coastal Notch + Seamount domain.

Produces a .npz with:
  - domain boundary + extent
  - bathymetry grid (cross-shelf profile + seamount bump)
  - size-field grid (derived from curvature + slope + depth factors)
  - per-iteration distmesh snapshots (node coords + bar connectivity)

Bathymetry:
  - Cross-shelf: z(x) = 0 (coast) → -20 (shelf edge) → -100 (deep)
  - Seamount: +4 m Gaussian bump (400 m radius) in notch interior

Output: scripts/viz_data/notch_seamount_admesh.npz
Run:    python scripts/gen_notch_seamount_data.py
"""

from __future__ import annotations

import json
import pathlib
import numpy as np
from scipy.spatial import Delaunay

from admesh._fast_sdf import fast_sdf

REPO = pathlib.Path(__file__).resolve().parents[1]
DOMAIN_JSON = REPO / "benchmarks" / "data" / "notch_seamount_domain.json"
OUT = REPO / "scripts" / "viz_data" / "notch_seamount_admesh.npz"


def load_normalized_rings() -> tuple[list[np.ndarray], tuple[float, float, float, float]]:
    """Load notch domain, recenter to origin and scale to ~[-1,1]."""
    d = json.loads(DOMAIN_JSON.read_text())
    rings = [np.asarray(r, dtype=np.float64) for r in d["rings"]]
    allpts = np.vstack(rings)
    cx, cy = allpts[:, 0].mean(), allpts[:, 1].mean()
    span = max(np.ptp(allpts[:, 0]), np.ptp(allpts[:, 1]))
    scale = 2.0 / span
    rings = [np.column_stack([(r[:, 0] - cx) * scale, (r[:, 1] - cy) * scale]) for r in rings]
    alln = np.vstack(rings)
    bbox = (alln[:, 0].min(), alln[:, 1].min(), alln[:, 0].max(), alln[:, 1].max())
    return rings, bbox


def cross_shelf_bathymetry(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Synthetic bathymetry: cross-shelf profile + seamount bump.

    Cross-shelf: z(x) = 0 (coast, x=-1) → -20 (shelf, x=0) → -100 (deep, x=1)
    Seamount: +4 m Gaussian in notch interior (x ≈ -0.8, y ≈ 0)

    Returns elevation (positive = shallow, negative = deep).
    """
    # Cross-shelf profile: linear interpolation
    # Map x ∈ [-1, 1] → z ∈ [0, -100]
    z_shelf = -50.0 * (x + 1.0)  # Linear from 0 at x=-1 to -100 at x=1

    # Seamount: Gaussian bump at notch interior
    seamount = 4.0 * np.exp(-((x + 0.8) ** 2 + y ** 2) / 0.08)

    return z_shelf + seamount


def _ring_curvature(ring: np.ndarray) -> np.ndarray:
    """Discrete curvature magnitude at each ring vertex (turning angle / length)."""
    prev = np.roll(ring, 1, axis=0)
    nxt = np.roll(ring, -1, axis=0)
    v1 = ring - prev
    v2 = nxt - ring
    a1 = np.arctan2(v1[:, 1], v1[:, 0])
    a2 = np.arctan2(v2[:, 1], v2[:, 0])
    dang = np.abs(np.arctan2(np.sin(a2 - a1), np.cos(a2 - a1)))
    seg = 0.5 * (np.hypot(v1[:, 0], v1[:, 1]) + np.hypot(v2[:, 0], v2[:, 1]))
    return dang / (seg + 1e-9)


def size_components(p: np.ndarray, ring: np.ndarray, hmin: float, hmax: float) -> dict:
    """Per-factor ADMESH-style size fields + their min-combination."""
    x, y = p[:, 0], p[:, 1]

    # --- curvature factor: nearest boundary vertex curvature, decayed by distance
    curv = _ring_curvature(ring)
    dx = x[:, None] - ring[None, :, 0]
    dy = y[:, None] - ring[None, :, 1]
    dist2 = dx * dx + dy * dy
    nearest = np.argmin(dist2, axis=1)
    dmin = np.sqrt(dist2[np.arange(len(p)), nearest])
    cnear = curv[nearest]
    decay = np.exp(-(dmin / 0.30) ** 2)
    h_curv = hmax / (1.0 + 1.5 * cnear * decay)

    # --- bathymetric gradient factor
    eps = 1e-3
    zx = (cross_shelf_bathymetry(x + eps, y) - cross_shelf_bathymetry(x - eps, y)) / (2 * eps)
    zy = (cross_shelf_bathymetry(x, y + eps) - cross_shelf_bathymetry(x, y - eps)) / (2 * eps)
    grad = np.hypot(zx, zy)
    h_grad = hmax / (1.0 + 3.0 * grad)

    # --- bathymetric depth (value) factor
    depth = np.clip(-cross_shelf_bathymetry(x, y), 0.0, None)
    h_depth = hmax / (1.0 + 1.5 * depth)

    h = np.clip(np.minimum.reduce([h_curv, h_grad, h_depth]), hmin, hmax)
    return {
        "h_curv": np.clip(h_curv, hmin, hmax),
        "h_grad": np.clip(h_grad, hmin, hmax),
        "h_depth": np.clip(h_depth, hmin, hmax),
        "h": h,
    }


def size_field_from_bathymetry(p: np.ndarray, ring: np.ndarray, hmin: float, hmax: float) -> np.ndarray:
    return size_components(p, ring, hmin, hmax)["h"]


def instrumented_distmesh(rings, bbox, hmin, hmax, *, niter=120, seed=0):
    """Canonical Persson truss solver, recording node coords each iteration."""
    fd = fast_sdf(rings)
    ring0 = rings[0]
    fh = lambda q: size_field_from_bathymetry(q, ring0, hmin, hmax)

    h0 = hmin
    geps = 1e-3 * h0
    deps = np.sqrt(np.finfo(float).eps) * h0
    ttol, Fscale, deltat = 0.1, 1.2, 0.2
    rng = np.random.default_rng(seed)

    # initial lattice + rejection
    xmin, ymin, xmax, ymax = bbox
    xs = np.arange(xmin, xmax + 0.5 * h0, h0)
    ys = np.arange(ymin, ymax + 0.5 * h0, h0 * np.sqrt(3) / 2)
    X, Y = np.meshgrid(xs, ys, indexing="xy")
    X[1::2, :] += h0 / 2.0
    p = np.column_stack([X.ravel(), Y.ravel()])
    p = p[fd(p) < geps]
    r = fh(p)
    p = p[rng.random(len(p)) < (r.min() / r) ** 2]

    snaps = []
    pold = np.full_like(p, np.inf)
    bars = np.empty((0, 2), dtype=np.int64)

    for _k in range(niter):
        if np.sqrt(((p - pold) ** 2).sum(axis=1)).max() / h0 > ttol:
            pold = p.copy()
            t = Delaunay(p).simplices
            cent = (p[t[:, 0]] + p[t[:, 1]] + p[t[:, 2]]) / 3.0
            t = t[fd(cent) < -geps]
            e = np.vstack([t[:, [0, 1]], t[:, [0, 2]], t[:, [1, 2]]])
            e = np.sort(e, axis=1)
            bars = np.unique(e, axis=0)
        if bars.size == 0:
            break

        bv = p[bars[:, 0]] - p[bars[:, 1]]
        L = np.hypot(bv[:, 0], bv[:, 1])
        hb = fh((p[bars[:, 0]] + p[bars[:, 1]]) / 2.0)
        L0 = hb * Fscale * np.sqrt((L ** 2).sum() / (hb ** 2).sum())
        F = np.maximum(L0 - L, 0.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            Fv = np.where(L[:, None] > 0, (F / L)[:, None] * bv, 0.0)
        Ft = np.zeros_like(p)
        np.add.at(Ft, bars[:, 0], Fv)
        np.add.at(Ft, bars[:, 1], -Fv)
        p = p + deltat * Ft

        d = fd(p)
        outside = d > 0
        if outside.any():
            po = p[outside]
            do = d[outside]
            dx = (fd(po + [deps, 0.0]) - do) / deps
            dy = (fd(po + [0.0, deps]) - do) / deps
            den = dx * dx + dy * dy
            den[den == 0] = 1.0
            p[outside] = po - np.column_stack([do * dx / den, do * dy / den])

        snaps.append((p.copy(), bars.copy()))

    return snaps


def main():
    rings, bbox = load_normalized_rings()
    hmin, hmax = 0.06, 0.20
    print(f"Notch+Seamount bbox={tuple(round(b, 2) for b in bbox)}  hmin={hmin} hmax={hmax}")

    # bathymetry + size-field grids for heatmaps
    gx = np.linspace(bbox[0], bbox[2], 240)
    gy = np.linspace(bbox[1], bbox[3], 240)
    GX, GY = np.meshgrid(gx, gy)
    bathy = cross_shelf_bathymetry(GX, GY)
    grid_pts = np.column_stack([GX.ravel(), GY.ravel()])
    comp = size_components(grid_pts, rings[0], hmin, hmax)
    shp = GX.shape
    h_curv = comp["h_curv"].reshape(shp)
    h_grad = comp["h_grad"].reshape(shp)
    h_depth = comp["h_depth"].reshape(shp)
    sizef = comp["h"].reshape(shp)

    # mask grid to inside domain
    fd = fast_sdf(rings)
    inside = (fd(grid_pts) < 0).reshape(GX.shape)

    print("Running instrumented distmesh...")
    snaps = instrumented_distmesh(rings, bbox, hmin, hmax)
    print(f"Captured {len(snaps)} iterations; final {len(snaps[-1][0])} nodes")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        OUT,
        ring=rings[0],
        bbox=np.array(bbox),
        bathy=bathy,
        h_curv=h_curv,
        h_grad=h_grad,
        h_depth=h_depth,
        sizef=sizef,
        inside=inside,
        n_snaps=len(snaps),
        **{f"p{i}": s[0] for i, s in enumerate(snaps)},
        **{f"b{i}": s[1] for i, s in enumerate(snaps)},
    )
    print(f"✓ Wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
