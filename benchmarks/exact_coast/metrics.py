"""Metrics for the exact-coast challenge.

All functions take plain arrays: ``nodes`` (n,2), ``tris`` (m,3) int, ``rings``
(list of open coordinate arrays, outer first) and ``h`` (callable (N,2)->(N,)).
"""

from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree
from shapely import STRtree
from shapely.geometry import LineString, MultiLineString, Polygon


def triangle_quality(nodes, tris):
    """q = (b+c-a)(c+a-b)(a+b-c)/(abc) = 2 r_in / r_out (1 equilateral, 0 degenerate).

    Same formula as admesh._stages.quality.mesh_quality, element="triangle"
    (port of MeshQuality.m @ 19b2eb9); degenerate triangles give 0.
    """
    p = np.asarray(nodes, float)
    t = np.asarray(tris, int)
    a = np.hypot(*(p[t[:, 1]] - p[t[:, 0]]).T)
    b = np.hypot(*(p[t[:, 2]] - p[t[:, 1]]).T)
    c = np.hypot(*(p[t[:, 0]] - p[t[:, 2]]).T)
    num = (b + c - a) * (c + a - b) * (a + b - c)
    den = a * b * c
    with np.errstate(divide="ignore", invalid="ignore"):
        q = np.where(den > 0, num / den, 0.0)
    return np.clip(np.nan_to_num(q), 0.0, 1.0)


def signed_areas(nodes, tris):
    p = np.asarray(nodes, float)
    t = np.asarray(tris, int)
    a, b, c = p[t[:, 0]], p[t[:, 1]], p[t[:, 2]]
    return 0.5 * ((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1])
                  - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0]))


def boundary_edges(tris):
    """Edges (i,j) used by exactly one triangle."""
    t = np.asarray(tris, int)
    e = np.vstack([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]])
    e = np.sort(e, axis=1)
    u, cnt = np.unique(e, axis=0, return_counts=True)
    return u[cnt == 1]


def ring_edges(rings):
    """Segments (k,2,2) of closed rings."""
    segs = []
    for r in rings:
        r = np.asarray(r, float)
        segs.append(np.stack([r, np.roll(r, -1, axis=0)], axis=1))
    return np.concatenate(segs)


def _mls(segs):
    return MultiLineString([LineString(s) for s in segs])


def hausdorff(nodes, bedges, rings, max_pts_per_geom=None):
    """Symmetric Hausdorff distance between mesh boundary edges and the input
    coast, via shapely.hausdorff_distance on MultiLineStrings (vertex-based,
    i.e. discrete; densify=0.5 adds a midpoint-ish refinement on each segment)."""
    import shapely

    a = _mls(np.asarray(nodes)[bedges])
    b = _mls(ring_edges(rings))
    return float(shapely.hausdorff_distance(a, b, densify=0.5))


def vertex_retention(nodes, rings):
    """Percent of input vertices that coincide with a mesh node (tol 1e-9*bbox diag)."""
    allp = np.vstack([np.asarray(r, float) for r in rings])
    uniq = np.unique(allp, axis=0)
    diag = float(np.hypot(*(uniq.max(0) - uniq.min(0))))
    d, _ = cKDTree(nodes).query(uniq)
    return 100.0 * float(np.mean(d <= 1e-9 * diag))


def length_area_errors(nodes, tris, bedges, rings):
    nodes = np.asarray(nodes, float)
    seg = nodes[bedges]
    Lm = float(np.hypot(*(seg[:, 1] - seg[:, 0]).T).sum())
    rs = ring_edges(rings)
    Li = float(np.hypot(*(rs[:, 1] - rs[:, 0]).T).sum())
    poly = Polygon(rings[0], [np.asarray(r) for r in rings[1:]])
    Am = float(np.abs(signed_areas(nodes, tris)).sum())
    return abs(Lm - Li) / Li, abs(Am - poly.area) / poly.area


def edge_length_error(nodes, bedges, h):
    """median and p95 of |L/h(mid) - 1| over boundary edges."""
    seg = np.asarray(nodes, float)[bedges]
    L = np.hypot(*(seg[:, 1] - seg[:, 0]).T)
    err = np.abs(L / h(seg.mean(axis=1)) - 1.0)
    return float(np.median(err)), float(np.percentile(err, 95))


def sliver_rate(nodes, tris, q, rings, h, qthr=0.3, k=2.0):
    """Share of ALL triangles with q < qthr whose centroid is within k*h(centroid)
    of the coast (distance to the closest input segment)."""
    cen = np.asarray(nodes, float)[np.asarray(tris, int)].mean(axis=1)
    bad = np.flatnonzero(q < qthr)
    if len(bad) == 0:
        return 0.0
    import shapely

    tree = STRtree([LineString(s) for s in ring_edges(rings)])
    pts = shapely.points(cen[bad])
    idx = tree.nearest(pts)
    d = shapely.distance(pts, np.asarray(tree.geometries)[idx])
    near = d <= k * h(cen[bad])
    return float(near.sum()) / len(q)


def evaluate(nodes, tris, rings, h):
    """All metrics in one dict.  ``h`` is the effective size field the tool was given."""
    nodes = np.asarray(nodes, float)
    tris = np.asarray(tris, int)
    out: dict = {"nodes": len(nodes), "triangles": len(tris)}
    sa = signed_areas(nodes, tris)
    diag = float(np.hypot(*(nodes.max(0) - nodes.min(0))))
    out["n_neg_area"] = int(min((sa < 0).sum(), (sa > 0).sum()))  # minority orientation
    out["n_zero_area"] = int((np.abs(sa) < 1e-14 * diag * diag).sum())
    q = triangle_quality(nodes, tris)
    out["q_min"] = float(q.min())
    out["q_mean"] = float(q.mean())
    out["q_p5"] = float(np.percentile(q, 5))
    be = boundary_edges(tris)
    out["hausdorff"] = hausdorff(nodes, be, rings)
    out["vtx_kept_pct"] = vertex_retention(nodes, rings)
    out["len_rel_err"], out["area_rel_err"] = length_area_errors(nodes, tris, be, rings)
    out["edge_err_med"], out["edge_err_p95"] = edge_length_error(nodes, be, h)
    out["sliver_rate"] = sliver_rate(nodes, tris, q, rings, h)
    return out
