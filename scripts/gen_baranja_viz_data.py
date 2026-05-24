#!/usr/bin/env python3
"""Generate ADMESH visualization data on the Baranja Hill domain.

Produces a .npz with:
  - bathymetry grid (fake, synthesized) + extent
  - size-field grid (derived from bathymetry factors: depth + gradient)
  - per-iteration distmesh snapshots (node coords + bar connectivity)

The distmesh loop here is an *instrumented copy* of the canonical Persson
truss solver (admesh/_stages/distmesh.py) — re-implemented locally so it can
record every iteration's node positions without touching the locked stage
module. Geometry/SDF reuse admesh._fast_sdf.

Output: scripts/viz_data/baranja_admesh.npz
Run:    python scripts/gen_baranja_viz_data.py
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
from scipy.spatial import Delaunay

from admesh._fast_sdf import fast_sdf

REPO = pathlib.Path(__file__).resolve().parents[1]
DOMAIN_JSON = REPO / "benchmarks" / "data" / "baranja_hill_boundary.json"
OUT = REPO / "scripts" / "viz_data" / "baranja_admesh.npz"


def load_normalized_rings() -> tuple[list[np.ndarray], tuple[float, float, float, float]]:
    """Load Baranja boundary, recenter to origin and scale to ~[-1,1]."""
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


def fake_bathymetry(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Synthetic depth field: a hill, a ridge, and a steep channel.

    Returns elevation (positive = high ground / shallow, negative = deep).
    Chosen to give visually interesting size-field structure.
    """
    hill = 1.2 * np.exp(-((x - 0.3) ** 2 + (y - 0.2) ** 2) / 0.25)
    ridge = 0.6 * np.exp(-((y + 0.4) ** 2) / 0.05)            # E-W ridge
    channel = -0.9 * np.exp(-((x + 0.4) ** 2) / 0.02)          # steep N-S channel
    basin = -0.3 * (x ** 2 + y ** 2)
    return hill + ridge + channel + basin


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
    """Per-factor ADMESH-style size fields + their min-combination.

    Returns dict of grids (same shape as p[:,0]):
      h_curv  : fine near high-curvature boundary (distance-decayed)
      h_grad  : fine where bathymetric slope |grad z| is large
      h_depth : fine in deep water (negative elevation)
      h       : np.minimum over all, clamped to [hmin, hmax]
    """
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
    h_curv = hmax / (1.0 + 3.0 * cnear * decay)

    # --- bathymetric gradient factor
    eps = 1e-3
    zx = (fake_bathymetry(x + eps, y) - fake_bathymetry(x - eps, y)) / (2 * eps)
    zy = (fake_bathymetry(x, y + eps) - fake_bathymetry(x, y - eps)) / (2 * eps)
    grad = np.hypot(zx, zy)
    h_grad = hmax / (1.0 + 6.0 * grad)

    # --- bathymetric depth (value) factor
    depth = np.clip(-fake_bathymetry(x, y), 0.0, None)
    h_depth = hmax / (1.0 + 2.5 * depth)

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
    fh = lambda q: size_field_from_bathymetry(q, ring0, hmin, hmax)  # noqa: E731

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

    snaps = []           # (p, bars) per recorded iteration
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
    hmin, hmax = 0.07, 0.22
    print(f"Baranja domain bbox={tuple(round(b,2) for b in bbox)}  hmin={hmin} hmax={hmax}")

    # bathymetry + size-field grids for the heatmap backgrounds
    gx = np.linspace(bbox[0], bbox[2], 240)
    gy = np.linspace(bbox[1], bbox[3], 240)
    GX, GY = np.meshgrid(gx, gy)
    bathy = fake_bathymetry(GX, GY)
    grid_pts = np.column_stack([GX.ravel(), GY.ravel()])
    comp = size_components(grid_pts, rings[0], hmin, hmax)
    shp = GX.shape
    h_curv = comp["h_curv"].reshape(shp)
    h_grad = comp["h_grad"].reshape(shp)
    h_depth = comp["h_depth"].reshape(shp)
    sizef = comp["h"].reshape(shp)

    # mask grid to inside the domain (for clean heatmaps)
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
    print(f"Wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
