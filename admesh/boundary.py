"""Boundary-condition enforcement and the PTS domain structure.

In ADMESH, a PTS is the polygonal representation of a
multiply-connected domain: an outer boundary ring, zero or more
inner boundary rings (holes), and a per-segment boundary-condition
tag. This module provides a minimum-viable :class:`PTS` dataclass,
a marching-squares constructor :meth:`PTS.from_domain` that samples
the zero-level set of a :class:`~admesh.domains.Domain`, and
:func:`enforce_boundary_conditions` which classifies a mesh node
set against the PTS.

**Clean-room implementation** — the MATLAB source
(``08_Enforce_Boundary_Conditions/{EnforceBoundaryConditions,
create_polygon_structure}.m`` in the upstream repo) is not
accessible in this session's environment. The MATLAB PTS has a
larger field set (hydraulic constraint sub-types, node attributes).
This port defines the minimum fields needed to drive P3 sizing and
the ADMESH-variant distmesh cleanup pass. Faithful-port backfill
is deferred — see ``docs/PORTING_NOTES.md`` entry dated 2026-04-23.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Sequence

import numpy as np
from numpy.typing import NDArray

from admesh.distance import eval_sdf_grid
from admesh.domains import Domain

Points = NDArray[np.float64]


class BoundaryType(IntEnum):
    """Minimum-viable ADMESH boundary-condition classes."""

    OPEN = 0
    """Outflow / prescribed elevation (MATLAB: open-ocean)."""
    WALL = 1
    """No-flux / reflective (MATLAB: no-normal-flow land)."""


@dataclass(frozen=True)
class PTS:
    """A multiply-connected polygonal domain with BC tags.

    Attributes
    ----------
    rings : list of ``(N_i, 2)`` arrays
        Boundary polygons. Ring ``0`` is the outer boundary
        (counter-clockwise). Rings ``1..`` are inner holes
        (clockwise by convention).
    bc_type : list of ``(N_i,)`` int arrays
        Per-vertex BC tag (drawn from :class:`BoundaryType`). The
        tag on vertex ``k`` is interpreted as the type of the
        *segment starting at vertex k* (closing at vertex ``k+1``
        mod ``N_i``).
    attributes : dict
        Opaque passthrough for caller-owned data (e.g. bathymetry
        samples per segment).
    """

    rings: list[Points]
    bc_type: list[NDArray[np.int64]]
    attributes: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.rings) != len(self.bc_type):
            raise ValueError(
                f"rings ({len(self.rings)}) and bc_type ({len(self.bc_type)}) length mismatch"
            )
        for r, b in zip(self.rings, self.bc_type):
            if r.ndim != 2 or r.shape[1] != 2:
                raise ValueError(f"ring must be (N, 2); got {r.shape}")
            if b.shape != (len(r),):
                raise ValueError(f"bc_type shape {b.shape} != ({len(r)},)")

    @property
    def n_rings(self) -> int:
        return len(self.rings)

    @property
    def n_vertices(self) -> int:
        return sum(len(r) for r in self.rings)

    # ------------------------------------------------------------------ ctors

    @classmethod
    def from_polygons(
        cls,
        outer: Points,
        holes: Sequence[Points] = (),
        *,
        bc: BoundaryType | Sequence[BoundaryType] = BoundaryType.WALL,
    ) -> "PTS":
        """Build a PTS from explicit polygon rings.

        ``bc`` is either a single :class:`BoundaryType` applied to
        every segment in every ring, or a sequence of length
        ``1 + len(holes)`` assigning a single type to each ring.
        """
        rings = [np.asarray(outer, dtype=float)] + [np.asarray(h, dtype=float) for h in holes]
        if isinstance(bc, BoundaryType):
            tags = [np.full(len(r), int(bc), dtype=np.int64) for r in rings]
        else:
            bc_seq = list(bc)
            if len(bc_seq) != len(rings):
                raise ValueError(f"bc sequence length {len(bc_seq)} != rings {len(rings)}")
            tags = [np.full(len(r), int(b), dtype=np.int64) for r, b in zip(rings, bc_seq)]
        return cls(rings=rings, bc_type=tags)

    @classmethod
    def from_domain(
        cls,
        domain: Domain,
        *,
        n_bnd: int = 64,
        grid_delta: float | None = None,
        bc: BoundaryType = BoundaryType.WALL,
    ) -> "PTS":
        """Sample the zero-level set of ``domain.fd`` into a PTS.

        Uses marching-squares on a grid evaluation of ``domain.fd``
        to extract boundary segments, chains them into closed rings
        by endpoint-matching, then resamples each ring by arc-length
        to ``n_bnd`` vertices. The largest ring by perimeter is
        treated as the outer boundary; any remaining rings are holes.
        """
        xmin, ymin, xmax, ymax = domain.bbox
        diag = np.hypot(xmax - xmin, ymax - ymin)
        delta = float(grid_delta) if grid_delta is not None else diag / 200.0
        # Pad the sampling bbox outward by a few cells so the actual
        # zero-level set is strictly interior to the grid — avoids
        # fencepost loss of boundary sign-change cells when delta
        # doesn't evenly divide (xmax - xmin).
        pad = 3.0 * delta
        sampled_bbox = (xmin - pad, ymin - pad, xmax + pad, ymax + pad)
        X, Y, D = eval_sdf_grid(domain.fd, sampled_bbox, delta)
        segs = _marching_squares(X, Y, D)
        rings = _chain_segments(segs)
        if not rings:
            raise RuntimeError("marching squares produced no closed rings")
        # Largest-perimeter ring is the outer boundary.
        rings.sort(key=_ring_perimeter, reverse=True)
        # Resample each ring to n_bnd vertices.
        rings = [_resample_by_arclength(r, n_bnd) for r in rings]
        # Orient outer CCW, holes CW (standard convention).
        if _signed_area(rings[0]) < 0:
            rings[0] = rings[0][::-1]
        for i in range(1, len(rings)):
            if _signed_area(rings[i]) > 0:
                rings[i] = rings[i][::-1]
        tags = [np.full(len(r), int(bc), dtype=np.int64) for r in rings]
        return cls(rings=rings, bc_type=tags)


# ---------------------------------------------------------------- BC enforce


def enforce_boundary_conditions(
    pts: PTS, p: Points, *, tol: float = 1e-2
) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    """Classify each mesh node against the PTS.

    For each point in ``p``, compute the nearest PTS segment and
    return its ``(ring_id, BoundaryType)`` if the perpendicular
    distance is below ``tol``; otherwise ``(-1, -1)``.

    Returns
    -------
    ring_id : (N,) int64
        Ring index containing the nearest segment, or ``-1`` for
        interior.
    bc : (N,) int64
        :class:`BoundaryType` value, or ``-1`` for interior.
    """
    p = np.asarray(p, dtype=float).reshape(-1, 2)
    N = len(p)
    best_dist = np.full(N, np.inf)
    ring_id = np.full(N, -1, dtype=np.int64)
    bc = np.full(N, -1, dtype=np.int64)

    for ri, (ring, tags) in enumerate(zip(pts.rings, pts.bc_type)):
        M = len(ring)
        for si in range(M):
            a = ring[si]
            b = ring[(si + 1) % M]
            d, _ = _point_segment_distance(p, a, b)
            closer = d < best_dist
            best_dist = np.where(closer, d, best_dist)
            ring_id = np.where(closer, ri, ring_id)
            bc = np.where(closer, int(tags[si]), bc)

    # Mask out interior nodes (distance above tol).
    interior = best_dist > tol
    ring_id[interior] = -1
    bc[interior] = -1
    return ring_id, bc


# --------------------------------------------------------------- geometry ops


def _point_segment_distance(
    p: Points, a: NDArray[np.float64], b: NDArray[np.float64]
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Perpendicular distance from each point in ``p`` to segment ``ab``.

    Returns ``(distance, t)`` where ``t ∈ [0, 1]`` is the projection
    parameter clamped to the segment.
    """
    ab = b - a
    denom = float(ab @ ab)
    if denom < 1e-30:
        d = np.linalg.norm(p - a, axis=1)
        return d, np.zeros(len(p))
    t = np.clip(((p - a) @ ab) / denom, 0.0, 1.0)
    proj = a + t[:, None] * ab
    d = np.linalg.norm(p - proj, axis=1)
    return d, t


def _marching_squares(
    X: NDArray[np.float64], Y: NDArray[np.float64], D: NDArray[np.float64]
) -> list[tuple[Points, Points]]:
    """Clean-room marching squares on a scalar grid.

    Extracts zero-level contour segments of ``D`` on the grid
    defined by ``(X, Y)``. Treats D == 0 as slightly positive
    (outside) to keep topology deterministic on grid-aligned edges.

    Returns a list of ``(a, b)`` segment endpoint pairs (each a
    ``(2,)`` array).
    """
    LY, LX = D.shape
    # Shift exact zeros by a tiny epsilon so no cell corner is on
    # the isoline — avoids the ambiguous cases 5 and 10.
    D = np.where(D == 0, 1e-12, D)
    segs: list[tuple[Points, Points]] = []

    for j in range(LY - 1):
        for i in range(LX - 1):
            # Corners: 0=bl, 1=br, 2=tr, 3=tl
            v = (D[j, i], D[j, i + 1], D[j + 1, i + 1], D[j + 1, i])
            px = (X[j, i], X[j, i + 1], X[j + 1, i + 1], X[j + 1, i])
            py = (Y[j, i], Y[j, i + 1], Y[j + 1, i + 1], Y[j + 1, i])
            code = (int(v[0] < 0) | (int(v[1] < 0) << 1)
                    | (int(v[2] < 0) << 2) | (int(v[3] < 0) << 3))
            if code in (0, 15):
                continue

            def interp(ea: int, eb: int) -> np.ndarray:
                va, vb = v[ea], v[eb]
                t = va / (va - vb)
                return np.array([px[ea] + t * (px[eb] - px[ea]),
                                 py[ea] + t * (py[eb] - py[ea])])

            # Edges: 0=bottom (0-1), 1=right (1-2), 2=top (2-3), 3=left (3-0)
            edge_endpoints = {0: (0, 1), 1: (1, 2), 2: (2, 3), 3: (3, 0)}
            edges_by_code = {
                1:  [(3, 0)], 2: [(0, 1)], 3: [(3, 1)], 4: [(1, 2)],
                5:  [(3, 2), (1, 0)], 6: [(0, 2)], 7: [(3, 2)],
                8:  [(2, 3)], 9: [(2, 0)], 10: [(2, 1), (0, 3)],
                11: [(2, 1)], 12: [(1, 3)], 13: [(1, 0)], 14: [(0, 3)],
            }
            for ea, eb in edges_by_code[code]:
                a = interp(*edge_endpoints[ea])
                b = interp(*edge_endpoints[eb])
                segs.append((a, b))
    return segs


def _chain_segments(
    segs: list[tuple[Points, Points]], *, tol: float = 1e-8
) -> list[Points]:
    """Join segments into closed polygonal rings by endpoint matching."""
    if not segs:
        return []
    # Index each endpoint by a rounded key.
    def key(pt: np.ndarray) -> tuple[int, int]:
        return (int(round(pt[0] / tol)), int(round(pt[1] / tol)))

    # Build adjacency: endpoint-key → list of (seg_index, which_end).
    adj: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for idx, (a, b) in enumerate(segs):
        adj.setdefault(key(a), []).append((idx, 0))
        adj.setdefault(key(b), []).append((idx, 1))

    used = [False] * len(segs)
    rings: list[Points] = []
    for start_idx in range(len(segs)):
        if used[start_idx]:
            continue
        used[start_idx] = True
        a, b = segs[start_idx]
        ring = [a, b]
        last_end = b
        # Walk forward.
        while True:
            k = key(last_end)
            next_found = False
            for idx, end in adj.get(k, []):
                if used[idx]:
                    continue
                used[idx] = True
                sa, sb = segs[idx]
                next_pt = sb if end == 0 else sa
                ring.append(next_pt)
                last_end = next_pt
                next_found = True
                break
            if not next_found:
                break
            if key(last_end) == key(ring[0]):
                # Closed ring.
                break
        if key(last_end) == key(ring[0]) and len(ring) >= 3:
            rings.append(np.asarray(ring[:-1]))
    return rings


def _resample_by_arclength(ring: Points, n: int) -> Points:
    """Resample a closed polygonal ring at ``n`` uniformly arc-spaced points."""
    closed = np.vstack([ring, ring[:1]])
    seg_len = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg_len)])
    total = cum[-1]
    if total == 0:
        return ring[:n]
    targets = np.linspace(0.0, total, n, endpoint=False)
    ix = np.searchsorted(cum, targets, side="right") - 1
    ix = np.clip(ix, 0, len(closed) - 2)
    t = (targets - cum[ix]) / np.where(seg_len[ix] > 0, seg_len[ix], 1.0)
    return closed[ix] + t[:, None] * (closed[ix + 1] - closed[ix])


def _ring_perimeter(ring: Points) -> float:
    closed = np.vstack([ring, ring[:1]])
    return float(np.sum(np.linalg.norm(np.diff(closed, axis=0), axis=1)))


def _signed_area(ring: Points) -> float:
    """Shoelace signed area; positive = CCW."""
    x, y = ring[:, 0], ring[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))
