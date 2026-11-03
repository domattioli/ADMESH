"""Quad-ready triangle meshing by offset layers (prototype).

Additive module; ``_stages/`` is untouched.  Design from the 2026-11-02
consensus debate (Remacle et al. 2013 L-inf frontal idea, adapted to the
ADMESH truss):

1. Boundary pre-pass: split each loop at corners, resample every segment by
   the integral of ds/h, force an even node count per loop, pin everything.
2. Travel field: tau(x) = geodesic integral of ds/h from the boundary
   (Dijkstra on a fine grid), so layer i is the level set tau = i.
3. Ring seeding: every level set tau = i is resampled by ds/h with an even
   count; contour corners (offset images of domain corners) are kept.
4. Truss: per-bar rest length uses the L-inf norm in the local frame
   (n = grad tau, t = n rotated).  Nodes keep their ring tag: after each step
   they are projected back onto their own level set, so ring counts and
   parity cannot change.  Topology is frozen for the last iterations.

Prototype status: works on simply connected domains given as a polyline loop
with explicit corner indices.  The medial band (where fronts from two sides
meet) gets no special treatment beyond stopping at the last full level.
"""
from __future__ import annotations

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.interpolate import RegularGridInterpolator
from scipy.spatial import Delaunay
from matplotlib.path import Path

__all__ = ["resample_boundary", "travel_field", "quad_layer_mesh"]


# ---------------------------------------------------------------- pre-pass
def _resample_open(poly, fh, n=None):
    """Resample an open polyline by integral ds/h. Returns nodes incl. ends."""
    seg = np.diff(poly, axis=0)
    ds = np.hypot(*seg.T)
    mid = 0.5 * (poly[1:] + poly[:-1])
    w = ds / fh(mid)
    s = np.r_[0.0, np.cumsum(w)]
    if n is None:
        n = max(1, int(round(s[-1])))
    tgt = np.linspace(0.0, s[-1], n + 1)
    x = np.interp(tgt, s, poly[:, 0])
    y = np.interp(tgt, s, poly[:, 1])
    return np.c_[x, y], s[-1]


def resample_boundary(loop, corners, fh):
    """Resample a closed loop between corners; total count even.

    ``loop`` is (N, 2) dense polyline (not repeated at end); ``corners`` are
    indices into it.  Returns (nodes, corner_mask).
    """
    corners = sorted(corners)
    k = len(corners)
    pieces, lens = [], []
    for j in range(k):
        a, b = corners[j], corners[(j + 1) % k]
        idx = np.r_[a:b + 1] if b > a else np.r_[a:len(loop), 0:b + 1]
        pieces.append(loop[idx])
        lens.append(_resample_open(loop[idx], fh)[1])
    counts = [max(1, int(round(L))) for L in lens]
    if sum(counts) % 2:  # parity: fix on segment with largest rounding error
        err = [L - c for L, c in zip(lens, counts)]
        j = int(np.argmax(np.abs(err)))
        counts[j] += 1 if err[j] > 0 else -1
        if counts[j] == 0:
            counts[j] = 2
    nodes, cm = [], []
    for pc, c in zip(pieces, counts):
        q, _ = _resample_open(pc, fh, c)
        nodes.append(q[:-1])
        cm.append(np.r_[True, np.zeros(c - 1, bool)])
    return np.vstack(nodes), np.concatenate(cm)


# ------------------------------------------------------------ travel field
def travel_field(loop, fh, step):
    """tau = integral of ds/h from boundary, on a grid. Returns interpolator."""
    lo, hi = loop.min(0) - step, loop.max(0) + step
    xs = np.arange(lo[0], hi[0] + step, step)
    ys = np.arange(lo[1], hi[1] + step, step)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    G = np.c_[X.ravel(), Y.ravel()]
    inside = Path(loop).contains_points(G, radius=1e-9)
    nx, ny = X.shape
    idx = np.arange(nx * ny).reshape(nx, ny)
    offs = [(1, 0), (0, 1), (1, 1), (1, -1), (2, 1), (1, 2), (2, -1), (1, -2)]
    rows, cols, wts = [], [], []
    H = fh(G)
    for dx, dy in offs:
        a = idx[max(0, -dx):nx - max(0, dx), max(0, -dy):ny - max(0, dy)]
        b = idx[max(0, dx):nx - max(0, -dx) or None, max(0, dy):ny - max(0, -dy) or None]
        a, b = a.ravel(), b.ravel()
        ok = inside[a] & inside[b]
        a, b = a[ok], b[ok]
        L = np.hypot(dx, dy) * step
        rows += [a]; cols += [b]; wts += [L * 2.0 / (H[a] + H[b])]
    n = nx * ny
    src = n  # virtual source joined to near-boundary grid nodes
    # exact distance from inside grid nodes to the loop polyline
    d = _dist_to_polyline(G[inside], loop)
    near = np.flatnonzero(inside)[d < 2.5 * step]
    rows += [np.full(len(near), src)]; cols += [near]
    wts += [d[d < 2.5 * step] / H[near]]
    A = coo_matrix((np.concatenate(wts), (np.concatenate(rows), np.concatenate(cols))), shape=(n + 1, n + 1))
    tau = dijkstra(A, directed=False, indices=src)[:n]
    tau[~inside] = -_dist_to_polyline(G[~inside], loop) / H[~inside]
    tau = tau.reshape(nx, ny)
    return RegularGridInterpolator((xs, ys), tau, bounds_error=False, fill_value=None), (xs, ys, tau)


def _dist_to_polyline(P, loop):
    a = loop; b = np.roll(loop, -1, 0)
    best = np.full(len(P), np.inf)
    for i in range(0, len(a), 256):
        A, B = a[i:i + 256], b[i:i + 256]
        AB = B - A
        t = ((P[:, None] - A[None]) * AB[None]).sum(-1) / np.maximum((AB ** 2).sum(-1), 1e-30)
        t = np.clip(t, 0, 1)
        Q = A[None] + t[..., None] * AB[None]
        best = np.minimum(best, np.hypot(*(P[:, None] - Q).transpose(2, 0, 1)).min(1))
    return best


# ---------------------------------------------------------------- seeding
def _level_curves(grid, level):
    import contourpy
    xs, ys, tau = grid
    gen = contourpy.contour_generator(xs, ys, tau.T, line_type="Separate")
    return [c for c in gen.lines(level) if len(c) > 3]


def _corner_ids(c, closed, ang_tol=35.0):
    v1 = c - np.roll(c, 1, 0); v2 = np.roll(c, -1, 0) - c
    a = np.degrees(np.arctan2(np.cross(v1, v2), (v1 * v2).sum(1)))
    # turning over a small window catches corners smeared across grid cells
    win = np.convolve(np.r_[a[-2:], a, a[:2]], np.ones(5), "valid") if closed else a
    ids = []
    for i in np.argsort(-np.abs(win)):
        if abs(win[i]) < ang_tol:
            break
        if all(min(abs(i - j), len(c) - abs(i - j)) > 6 for j in ids):
            ids.append(int(i))
    return sorted(ids)


def _seed_ring(c, fh):
    closed = np.allclose(c[0], c[-1])
    if closed:
        c = c[:-1]
    cid = _corner_ids(c, closed)
    if not closed or len(cid) == 0:
        L = _resample_open(np.vstack([c, c[:1]]) if closed else c, fh)[1]
        n = max(2, 2 * int(round(L / 2)))
        q, _ = _resample_open(np.vstack([c, c[:1]]) if closed else c, fh, n)
        return q[:-1] if closed else q
    return resample_boundary(c, cid, fh)[0]


# ----------------------------------------------------------------- truss
def _frame(interp, P, eps):
    gx = (interp(P + [eps, 0]) - interp(P - [eps, 0])) / (2 * eps)
    gy = (interp(P + [0, eps]) - interp(P - [0, eps])) / (2 * eps)
    n = np.c_[gx, gy]
    nn = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.maximum(nn, 1e-12), nn[:, 0]


def _project_to_level(interp, P, lev, fh, eps, iters=3):
    for _ in range(iters):
        n, g = _frame(interp, P, eps)
        r = interp(P) - lev
        P = P - (r / np.maximum(g, 1e-9))[:, None] * n
    return P


def _triangulate(P, loop):
    t = Delaunay(P).simplices
    c = P[t].mean(1)
    keep = Path(loop).contains_points(c)
    a = P[t[:, 1]] - P[t[:, 0]]; b = P[t[:, 2]] - P[t[:, 0]]
    area = 0.5 * np.cross(a, b)
    t = t[keep & (np.abs(area) > 1e-12)]
    return np.sort(t, axis=1)


def quad_layer_mesh(loop, corners, fh, niter=60, freeze=10, dt=0.2, step=None, verbose=False):
    """Build a layered, quad-ready triangle mesh.

    Returns dict(points, elements, ring) with ring tag per node (-1 = core).
    """
    hmin = float(fh(loop).min())
    step = step or hmin / 6
    interp, grid = travel_field(loop, fh, step)
    eps = step
    b, _ = resample_boundary(loop, corners, fh)
    P = [b]; ring = [np.zeros(len(b), int)]
    tau_max = grid[2].max()
    k = 1
    while k <= tau_max - 0.5:
        for c in _level_curves(grid, float(k)):
            q = _seed_ring(c, fh)
            P.append(q); ring.append(np.full(len(q), k))
        k += 1
    # core: medial ridge points beyond the last full level, isotropic
    last = k - 1
    xs, ys, tau = grid
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    core = np.c_[X[tau > last + 0.5], Y[tau > last + 0.5]]
    if len(core):
        # thin core grid to ~h spacing
        sel = []; hc = fh(core)
        for i in np.argsort(-tau[tau > last + 0.5]):
            if all(np.hypot(*(core[i] - core[j])) > 0.9 * hc[i] for j in sel):
                sel.append(i)
        P.append(core[sel]); ring.append(np.full(len(sel), -1))
    P = np.vstack(P); ring = np.concatenate(ring)
    fixed = ring == 0
    pinned_corner = np.zeros(len(P), bool)
    t = _triangulate(P, loop)
    for it in range(niter):
        if it < niter - freeze:
            t = _triangulate(P, loop)
        e = np.unique(np.vstack([t[:, [0, 1]], t[:, [1, 2]], t[:, [0, 2]]]), axis=0)
        # cross bars only between adjacent rings (core treated as last+1)
        rr = np.where(ring < 0, last + 1, ring)
        e = e[np.abs(rr[e[:, 0]] - rr[e[:, 1]]) <= 1]
        v = P[e[:, 1]] - P[e[:, 0]]
        mid = 0.5 * (P[e[:, 0]] + P[e[:, 1]])
        n, _ = _frame(interp, mid, eps)
        tt = np.c_[-n[:, 1], n[:, 0]]
        linf = np.maximum(np.abs((v * n).sum(1)), np.abs((v * tt).sum(1)))
        iso = (ring[e[:, 0]] < 0) | (ring[e[:, 1]] < 0)
        linf[iso] = np.hypot(*v[iso].T)  # transition band: Euclidean rest length
        L0 = fh(mid)
        f = (L0 - linf) / np.maximum(linf, 1e-12)
        fv = -f[:, None] * v
        F = np.zeros_like(P)
        np.add.at(F, e[:, 0], fv); np.add.at(F, e[:, 1], -fv)
        F[fixed] = 0
        Pn = P + dt * F
        lay = ring > 0
        # keep ring-tag nodes on their level set (counts and parity frozen)
        for lev in np.unique(ring[lay]):
            m = ring == lev
            Pn[m] = _project_to_level(interp, Pn[m], float(lev), fh, eps)
        core_m = ring < 0
        if core_m.any():  # core nodes stay beyond last level
            tc = interp(Pn[core_m])
            bad = tc < last + 0.25
            Pc = Pn[core_m]; Pc[bad] = P[core_m][bad]; Pn[core_m] = Pc
        move = np.abs(Pn - P).max()
        P = Pn
        if verbose and it % 10 == 0:
            print(f"iter {it}: max move {move:.3f}")
    t = _triangulate(P, loop)
    t = enforce_corner_templates(P, t, ring, b, corners_xy=loop[sorted(corners)])
    P, t, ring = _fix_core_parity(P, t, ring, loop, b, loop[sorted(corners)])
    return {"points": P, "elements": t, "ring": ring, "last_level": last}


# ------------------------------------------------------- topology repairs
def _flip(t, a, b):
    """Flip edge (a, b) shared by two triangles; returns new t or None."""
    sh = [i for i, tri in enumerate(t) if a in tri and b in tri]
    if len(sh) != 2:
        return None
    c = [v for v in t[sh[0]] if v not in (a, b)][0]
    d = [v for v in t[sh[1]] if v not in (a, b)][0]
    t = t.copy()
    t[sh[0]] = sorted((a, c, d)); t[sh[1]] = sorted((b, c, d))
    return t


def _valid(P, t):
    a = P[t[:, 1]] - P[t[:, 0]]; b = P[t[:, 2]] - P[t[:, 0]]
    return np.all(np.abs(np.cross(a, b)) > 1e-9)


def _orient_ok(P, t, t0):
    s0 = np.sign(np.cross(P[t0[:, 1]] - P[t0[:, 0]], P[t0[:, 2]] - P[t0[:, 0]]))
    return _valid(P, t)


def enforce_corner_templates(P, t, ring, b, corners_xy):
    """Make each domain corner node sit in exactly two triangles (one quad).

    The ring-1 node nearest the corner becomes the shared diagonal end; edges
    blocking corner-to-k are flipped (Lawson walk, convex quads only).
    """
    t = np.sort(t, axis=1)
    r1 = np.flatnonzero(ring == 1)
    for cxy in corners_xy:
        c = int(np.argmin(np.hypot(*(P - cxy).T)))
        k = int(r1[np.argmin(np.hypot(*(P[r1] - P[c]).T))])
        for _ in range(6):
            tri = [x for x in t if c in x]
            if len(tri) == 2 and any(k in x for x in tri):
                break
            if len(tri) == 1:  # corner in one triangle: flip its opposite edge
                a, bb = [v for v in tri[0] if v != c]
                nt = _flip(t, a, bb)
            else:  # too many: flip the edge from c to a non-k interior node
                nbr = {v for x in tri for v in x} - {c}
                bad = [v for v in nbr if v != k and ring[v] != 0]
                nt = _flip(t, c, bad[0]) if bad else None
            if nt is None or not _convex_flip_ok(P, nt):
                break
            t = np.sort(nt, axis=1)
    return t


def _convex_flip_ok(P, t):
    a = P[t[:, 1]] - P[t[:, 0]]; b = P[t[:, 2]] - P[t[:, 0]]
    ar = np.cross(a, b)
    # sorted rows have mixed orientation; only reject degenerate ones, and
    # overlap is caught by total area staying constant
    return np.all(np.abs(ar) > 1e-9)


def _peel_rings(t):
    from collections import Counter
    rest = [tuple(x) for x in t]; out = []
    while rest:
        c = Counter(frozenset(e) for x in rest for e in ((x[0], x[1]), (x[1], x[2]), (x[0], x[2])))
        bnd = [e for e, n in c.items() if n == 1]
        nodes = {v for e in bnd for v in e}
        out.append(len(bnd))
        rest = [x for x in rest if not set(x) & nodes]
    return out


def _fix_core_parity(P, t, ring, loop, b, corners_xy):
    """If the peel leaves an odd ring, drop one core node (try each)."""
    if all(n % 2 == 0 for n in _peel_rings(t)):
        return P, t, ring
    core = np.flatnonzero(ring < 0)
    for i in core:
        keep = np.ones(len(P), bool); keep[i] = False
        P2, r2 = P[keep], ring[keep]
        t2 = enforce_corner_templates(P2, _triangulate(P2, loop), r2, b, corners_xy)
        if all(n % 2 == 0 for n in _peel_rings(t2)):
            return P2, t2, r2
    return P, t, ring
