"""1D DistMesh relaxation of boundary node spacing (API layer).

This module is **not** a MATLAB port and is not part of the locked
``_stages/`` set.  It adds an optional pre-pass for
:func:`admesh.triangulate` (``boundary="fixed"``): each closed boundary ring
is discretized with a one-dimensional Persson-Strang force relaxation along
its arc length, so that boundary node spacing follows the size field ``fh``
before the 2D solver starts.  The relaxed nodes are then held fixed by the
2D solver, which avoids the slivers that appear when free interior nodes
are snapped onto the boundary next to pinned nodes.

Algorithm (per ring)
--------------------
* Arc-length parameter ``s`` on ``[0, L)``, periodic.  ``h(s) = fh(xy(s))``.
* Pinned nodes: original polygon vertices whose turning angle exceeds
  ``corner_angle_deg``, plus user-supplied fixed points lying on the ring.
* Force on bar ``[s_i, s_{i+1}]`` of length ``l``: ``l0 = Fscale * h_mid *
  sum(l) / sum(h_mid)`` and ``F = max(l0 - l, 0)``.  A node receives ``+F``
  from its left bar and ``-F`` from its right bar; pinned nodes receive zero.
* Update ``s += deltat * F`` (``deltat = 0.2``), clamped so order is preserved
  and no node crosses a neighbour (pinned nodes included).
* Every sweep splits bars longer than ``1.5 h_mid`` and deletes a non-pinned
  endpoint of bars shorter than ``0.5 h_mid``.
* Stops when ``max(step / h) < tol`` with no topology change, or after
  ``max_iter`` sweeps.

Nodes are mapped from ``s`` back to ``xy`` along the input polyline, so they
lie exactly on it.
"""

from __future__ import annotations

from typing import Callable, Sequence

import numpy as np

__all__ = ["relax_ring", "relax_rings", "ring_arclength"]

_SizeFn = "Callable[[np.ndarray], np.ndarray] | None"

FSCALE = 1.2
DELTAT = 0.2


def _clean_ring(ring: np.ndarray) -> np.ndarray:
    """Drop a repeated closing vertex and zero-length edges."""
    r = np.asarray(ring, dtype=np.float64).reshape(-1, 2)
    if len(r) > 1 and np.allclose(r[0], r[-1], rtol=0.0, atol=1e-14):
        r = r[:-1]
    keep = [0]
    for i in range(1, len(r)):
        if np.linalg.norm(r[i] - r[keep[-1]]) > 1e-14:
            keep.append(i)
    r = r[keep]
    if len(r) > 1 and np.linalg.norm(r[0] - r[-1]) <= 1e-14:
        r = r[:-1]
    if len(r) < 3:
        raise ValueError("relax_ring: ring needs at least 3 distinct vertices")
    return r


class _Ring:
    """Closed polyline with arc-length <-> xy maps."""

    def __init__(self, verts: np.ndarray):
        self.v = verts
        closed = np.vstack([verts, verts[:1]])
        self.closed = closed
        seg = np.linalg.norm(np.diff(closed, axis=0), axis=1)
        self.cum = np.concatenate([[0.0], np.cumsum(seg)])
        self.L = float(self.cum[-1])

    def xy(self, s: np.ndarray) -> np.ndarray:
        s = np.mod(np.asarray(s, dtype=np.float64), self.L)
        return np.column_stack(
            [np.interp(s, self.cum, self.closed[:, 0]),
             np.interp(s, self.cum, self.closed[:, 1])]
        )

    def project(self, pts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return (arc length, distance) of the closest ring point per pt."""
        pts = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
        a = self.closed[:-1]
        d = self.closed[1:] - a
        dd = (d ** 2).sum(axis=1)
        w = pts[:, None, :] - a[None, :, :]
        t = np.clip((w * d[None]).sum(axis=2) / dd[None], 0.0, 1.0)
        q = a[None] + t[..., None] * d[None]
        dist = np.linalg.norm(pts[:, None, :] - q, axis=2)
        k = dist.argmin(axis=1)
        idx = np.arange(len(pts))
        s = self.cum[k] + t[idx, k] * np.sqrt(dd[k])
        return s, dist[idx, k]


def _h_of(fh, xy: np.ndarray, h0: float) -> np.ndarray:
    if fh is None:
        return np.full(len(xy), h0, dtype=np.float64)
    h = np.asarray(fh(xy), dtype=np.float64).reshape(-1)
    if h.size == 1:
        h = np.full(len(xy), float(h[0]))
    bad = ~np.isfinite(h)
    if bad.any():
        h = np.where(bad, h0, h)
    return np.maximum(h, 0.1 * h0)


def ring_arclength(ring: np.ndarray, xy: np.ndarray) -> np.ndarray:
    """Arc length (from ``ring[0]``) of the point on ``ring`` nearest each ``xy``.

    Helper for plotting bar length against arc length.
    """
    return _Ring(_clean_ring(ring)).project(xy)[0]


def relax_ring(
    ring: np.ndarray,
    fh: "Callable[[np.ndarray], np.ndarray] | None",
    h0: float,
    *,
    corner_angle_deg: float = 20.0,
    pinned_points: "np.ndarray | None" = None,
    record_history: bool = False,
    max_iter: int = 200,
    tol: float = 1e-3,
    init: str = "seeded",
    rng_seed: "int | None" = None,
):
    """Distribute nodes along one closed ring with a 1D DistMesh relaxation.

    API-layer routine, not a MATLAB port.

    Parameters
    ----------
    ring : (M, 2) array
        Closed polygon vertices (closing vertex optional).
    fh : callable or None
        Size field ``(N, 2) -> (N,)``; ``None`` means uniform ``h0``.
    h0 : float
        Fallback and floor size (values are floored at ``0.1 * h0``).
    corner_angle_deg : float
        Vertices with turning angle above this are pinned.
    pinned_points : (K, 2) array or None
        Extra fixed points; those within ``1e-8 * L`` of the ring are pinned.
    record_history : bool
        If True also return a list of per-iteration ``(N, 2)`` snapshots
        (index 0 is the initial seeding).
    max_iter, tol : int, float
        Sweep limit and convergence threshold on ``max(step / h)``.
    init : {"seeded", "random"}
        ``"seeded"`` starts from per-edge even seeds (near-converged).
        ``"random"`` keeps pinned nodes and scatters the free ones uniformly
        along the ring; ``rng_seed`` makes it reproducible.

    Returns
    -------
    xy : (N, 2) array
        Node coordinates in ring order, starting at a pinned node, lying on the
        input polyline.  With ``record_history=True`` returns ``(xy, history)``.
    """
    verts = _clean_ring(ring)
    R = _Ring(verts)
    L = R.L
    n = len(verts)

    # Corner detection (turning angle at each vertex).
    e_in = verts - np.roll(verts, 1, axis=0)
    e_out = np.roll(verts, -1, axis=0) - verts
    ang = np.arctan2(
        e_in[:, 0] * e_out[:, 1] - e_in[:, 1] * e_out[:, 0],
        (e_in * e_out).sum(axis=1),
    )
    is_corner = np.abs(np.degrees(ang)) > corner_angle_deg

    # Initial seeds: every vertex plus per-edge interior points at ~h.
    s_list: list[float] = []
    pin_list: list[bool] = []
    for i in range(n):
        s0, s1 = R.cum[i], R.cum[i + 1]
        mid = R.xy(np.array([(s0 + s1) / 2.0]))
        h_e = float(_h_of(fh, mid, h0)[0])
        nseg = max(int(round((s1 - s0) / h_e)), 1)
        s_list.append(s0)
        pin_list.append(bool(is_corner[i]))
        for k in range(1, nseg):
            s_list.append(s0 + (s1 - s0) * k / nseg)
            pin_list.append(False)

    s = np.array(s_list)
    pin = np.array(pin_list, dtype=bool)

    # User pins lying on the ring.
    if pinned_points is not None and len(np.atleast_2d(pinned_points)):
        ps, pd = R.project(np.atleast_2d(pinned_points))
        for sv, dv in zip(ps, pd):
            if dv > 1e-8 * max(L, 1.0):
                continue
            j = int(np.argmin(np.abs(s - sv)))
            if abs(s[j] - sv) < 1e-12 * L:
                pin[j] = True
            else:
                s = np.append(s, sv)
                pin = np.append(pin, True)
        o = np.argsort(s)
        s, pin = s[o], pin[o]

    # Optional random start: keep pinned nodes, scatter the free ones
    # uniformly along the ring (same count). Used for demos/stress tests.
    if init == "random":
        rng = np.random.default_rng(rng_seed)
        n_free = int((~pin).sum())
        s = np.concatenate([s[pin], rng.uniform(0.0, L, n_free)])
        pin = np.concatenate([np.ones(int(pin.sum()), bool), np.zeros(n_free, bool)])
        o = np.argsort(s, kind="stable")
        s, pin = s[o], pin[o]
    elif init != "seeded":
        raise ValueError(f"relax_ring: init must be 'seeded' or 'random', got {init!r}")

    if not pin.any():
        pin[0] = True  # anchor so the ring has a fixed start node

    # Rotate so node 0 is pinned; u in [0, L) measured from s_origin.
    k0 = int(np.argmax(pin))
    s_origin = s[k0]
    u = np.mod(s - s_origin, L)
    o = np.argsort(u)
    u, pin = u[o], pin[o]

    def to_xy(uu: np.ndarray) -> np.ndarray:
        return R.xy(uu + s_origin)

    history: list[np.ndarray] = [to_xy(u)] if record_history else []

    for _ in range(int(max_iter)):
        u_ext = np.append(u, L)
        l = np.diff(u_ext)
        mid = 0.5 * (u_ext[:-1] + u_ext[1:])
        hm = _h_of(fh, to_xy(mid), h0)
        l0 = FSCALE * hm * l.sum() / hm.sum()
        F = np.maximum(l0 - l, 0.0)
        Fn = np.roll(F, 1) - F  # +left bar, -right bar
        Fn[pin] = 0.0
        du = DELTAT * Fn
        gap_r = l
        gap_l = np.roll(l, 1)
        du = np.clip(du, -0.45 * gap_l, 0.45 * gap_r)
        du[pin] = 0.0
        u = u + du
        hn = np.maximum(0.5 * (hm + np.roll(hm, 1)), 1e-300)
        step = float(np.max(np.abs(du) / hn)) if len(du) else 0.0

        # Topology sweep: split long bars, delete one end of short bars.
        u_ext = np.append(u, L)
        l = np.diff(u_ext)
        mid = 0.5 * (u_ext[:-1] + u_ext[1:])
        hm = _h_of(fh, to_xy(mid), h0)
        split = l > 1.5 * hm
        drop = np.zeros(len(u), dtype=bool)
        for i in np.where((l < 0.5 * hm) & ~split)[0]:
            j = (i + 1) % len(u)
            if drop[i] or drop[j] or split[i]:
                continue
            if not pin[j]:
                drop[j] = True
            elif not pin[i]:
                drop[i] = True
        changed = bool(split.any() or drop.any())
        if changed:
            new_u = mid[split]
            keep = ~drop
            u = np.concatenate([u[keep], new_u])
            pin = np.concatenate([pin[keep], np.zeros(len(new_u), dtype=bool)])
            o = np.argsort(u, kind="stable")
            u, pin = u[o], pin[o]

        if record_history:
            history.append(to_xy(u))
        if step < tol and not changed:
            break

    xy = to_xy(u)
    return (xy, history) if record_history else xy


def relax_rings(
    rings: Sequence[np.ndarray],
    fh: "Callable[[np.ndarray], np.ndarray] | None",
    h0: float,
    *,
    corner_angle_deg: float = 20.0,
    pinned_points: "np.ndarray | None" = None,
    record_history: bool = False,
    max_iter: int = 200,
    tol: float = 1e-3,
):
    """Relax every ring (outer boundary first, then holes).

    API-layer routine, not a MATLAB port.  Returns a list of ``(N_k, 2)``
    arrays, or ``(list, list_of_histories)`` when ``record_history`` is True.
    """
    out, hist = [], []
    for r in rings:
        res = relax_ring(
            r, fh, h0,
            corner_angle_deg=corner_angle_deg,
            pinned_points=pinned_points,
            record_history=record_history,
            max_iter=max_iter, tol=tol,
        )
        if record_history:
            out.append(res[0])
            hist.append(res[1])
        else:
            out.append(res)
    return (out, hist) if record_history else out
