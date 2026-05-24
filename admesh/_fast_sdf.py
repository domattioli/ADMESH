"""Vectorized signed-distance function for polygon domains.

Replaces the per-point shapely ``distance``/``contains`` SDF in
``admesh.loaders`` with a Numba-parallel kernel: distance = minimum
point-to-segment distance over all boundary edges (outer + holes); sign =
even-odd ray cast over the same edges (negative inside the domain, positive
outside or inside a hole).

Falls back to a pure-NumPy implementation if Numba is unavailable.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

try:
    from numba import njit, prange

    _HAVE_NUMBA = True
except ImportError:  # pragma: no cover
    _HAVE_NUMBA = False


def _pack_edges(rings: list[np.ndarray]) -> np.ndarray:
    """Stack all ring edges into a contiguous (Nseg, 4) array [ax, ay, bx, by]."""
    segs = []
    for r in rings:
        r = np.asarray(r, dtype=np.float64)
        if len(r) < 2:
            continue
        a = r
        b = np.roll(r, -1, axis=0)
        segs.append(np.hstack([a, b]))
    if not segs:
        raise ValueError("rings produced no edges")
    return np.ascontiguousarray(np.vstack(segs))


def _sdf_numpy(px, py, ax, ay, bx, by):
    # distance: min over segments, chunked to bound memory
    n = px.shape[0]
    out = np.empty(n, dtype=np.float64)
    dx = bx - ax
    dy = by - ay
    seg_len2 = dx * dx + dy * dy
    seg_len2[seg_len2 == 0.0] = 1.0
    chunk = max(1, 4_000_000 // max(1, ax.shape[0]))
    for s in range(0, n, chunk):
        e = min(s + chunk, n)
        qx = px[s:e, None]
        qy = py[s:e, None]
        t = ((qx - ax) * dx + (qy - ay) * dy) / seg_len2
        np.clip(t, 0.0, 1.0, out=t)
        cx = ax + t * dx
        cy = ay + t * dy
        d = np.hypot(qx - cx, qy - cy)
        dmin = d.min(axis=1)
        # even-odd ray cast
        cond = (ay > qy) != (by > qy)
        xint = (bx - ax) * (qy - ay) / (by - ay + 1e-300) + ax
        crossings = (cond & (qx < xint)).sum(axis=1)
        inside = (crossings & 1).astype(bool)
        out[s:e] = np.where(inside, -dmin, dmin)
    return out


if _HAVE_NUMBA:

    @njit(parallel=True, fastmath=True, cache=True)
    def _sdf_numba(px, py, ax, ay, bx, by):  # pragma: no cover - compiled
        n = px.shape[0]
        m = ax.shape[0]
        out = np.empty(n, dtype=np.float64)
        for i in prange(n):
            qx = px[i]
            qy = py[i]
            dmin = 1e300
            crossings = 0
            for j in range(m):
                axj = ax[j]
                ayj = ay[j]
                bxj = bx[j]
                byj = by[j]
                ex = bxj - axj
                ey = byj - ayj
                seg2 = ex * ex + ey * ey
                if seg2 == 0.0:
                    t = 0.0
                else:
                    t = ((qx - axj) * ex + (qy - ayj) * ey) / seg2
                    if t < 0.0:
                        t = 0.0
                    elif t > 1.0:
                        t = 1.0
                cx = axj + t * ex
                cy = ayj + t * ey
                ddx = qx - cx
                ddy = qy - cy
                d = (ddx * ddx + ddy * ddy) ** 0.5
                if d < dmin:
                    dmin = d
                if (ayj > qy) != (byj > qy):
                    xint = (bxj - axj) * (qy - ayj) / (byj - ayj) + axj
                    if qx < xint:
                        crossings += 1
            out[i] = -dmin if (crossings & 1) else dmin
        return out


if _HAVE_NUMBA:

    @njit(parallel=True, fastmath=True, cache=True)
    def _dist_knn_numba(px, py, ax, ay, bx, by, cand):  # pragma: no cover
        # exact min point-segment distance over k candidate segments per point;
        # full even-odd ray cast over all segments for the sign.
        n = px.shape[0]
        m = ax.shape[0]
        k = cand.shape[1]
        out = np.empty(n, dtype=np.float64)
        for i in prange(n):
            qx = px[i]
            qy = py[i]
            dmin = 1e300
            for c in range(k):
                j = cand[i, c]
                axj = ax[j]
                ayj = ay[j]
                ex = bx[j] - axj
                ey = by[j] - ayj
                seg2 = ex * ex + ey * ey
                if seg2 == 0.0:
                    t = 0.0
                else:
                    t = ((qx - axj) * ex + (qy - ayj) * ey) / seg2
                    if t < 0.0:
                        t = 0.0
                    elif t > 1.0:
                        t = 1.0
                ddx = qx - (axj + t * ex)
                ddy = qy - (ayj + t * ey)
                d = (ddx * ddx + ddy * ddy) ** 0.5
                if d < dmin:
                    dmin = d
            crossings = 0
            for j in range(m):
                ayj = ay[j]
                byj = by[j]
                if (ayj > qy) != (byj > qy):
                    xint = (bx[j] - ax[j]) * (qy - ayj) / (byj - ayj) + ax[j]
                    if qx < xint:
                        crossings += 1
            out[i] = -dmin if (crossings & 1) else dmin
        return out


def fast_sdf(rings: list[np.ndarray], knn: int = 32) -> Callable[[np.ndarray], np.ndarray]:
    """Build a vectorized SDF closure over polygon rings (outer first, holes after).

    When SciPy + Numba are available and the boundary has many segments, the
    distance term is pruned with a cKDTree over segment midpoints: only the
    ``knn`` nearest segments per query point are tested exactly. The sign uses
    a full even-odd ray cast. Falls back to the brute kernel otherwise.
    """
    edges = _pack_edges(rings)
    ax = np.ascontiguousarray(edges[:, 0])
    ay = np.ascontiguousarray(edges[:, 1])
    bx = np.ascontiguousarray(edges[:, 2])
    by = np.ascontiguousarray(edges[:, 3])
    nseg = ax.shape[0]

    tree = None
    if _HAVE_NUMBA and nseg > 4 * knn:
        try:
            from scipy.spatial import cKDTree

            mid = np.column_stack([(ax + bx) * 0.5, (ay + by) * 0.5])
            tree = cKDTree(mid)
        except ImportError:
            tree = None

    def sdf(p: np.ndarray) -> np.ndarray:
        pts = np.asarray(p, dtype=np.float64)
        if pts.ndim == 1:
            pts = pts[None, :]
        px = np.ascontiguousarray(pts[:, 0])
        py = np.ascontiguousarray(pts[:, 1])
        if tree is not None:
            k = min(knn, nseg)
            _, cand = tree.query(pts, k=k)
            cand = np.ascontiguousarray(np.atleast_2d(cand).astype(np.int64))
            return _dist_knn_numba(px, py, ax, ay, bx, by, cand)
        if _HAVE_NUMBA:
            return _sdf_numba(px, py, ax, ay, bx, by)
        return _sdf_numpy(px, py, ax, ay, bx, by)

    return sdf
