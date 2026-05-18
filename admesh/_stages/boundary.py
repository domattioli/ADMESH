"""Boundary-condition enforcement and the PTS domain structure.

In ADMESH, a PTS is the polygonal representation of a
multiply-connected domain: an outer boundary ring, zero or more
inner boundary rings (holes), a per-segment boundary-condition
tag, and an optional list of additional :class:`BCSegment`
constraints (open-ocean / internal + external barrier lines).

This module provides:

- :class:`PTS` — container, constructed either from explicit
  polygons (``PTS.from_polygons``) or from a :class:`~admesh.
  domains.Domain` via marching-squares contour extraction
  (``PTS.from_domain``).
- :class:`BCSegment` — a single MATLAB ``PTS.BC(k)`` entry:
  an integer BC code (ADCIRC convention) + a polyline.
- :func:`create_polygon_structure` — **faithful port** of
  ``08_Enforce_Boundary_Conditions/create_polygon_structure.m``;
  builds a width-``√3/2·L`` rectangle around each edge plus an
  end-cap circle.
- :func:`enforce_boundary_conditions` — **faithful port** of
  ``08_Enforce_Boundary_Conditions/EnforceBoundaryConditions.m``;
  operates on an h-field on a rectangular grid, clipping to
  ``[hmin, hmax]``, setting ``hmax`` outside the domain, enforcing
  open-ocean ``IB`` indices to ``hmax``, and enforcing external /
  internal barrier band sizes per MATLAB.
- :func:`classify_nodes_against_pts` — utility (previously called
  ``enforce_boundary_conditions`` in the session-3 clean-room
  pass); classifies mesh nodes against the nearest PTS segment,
  returning ``(ring_id, bc_type)`` tags.

**Port status** — ``PTS``/``BoundaryType`` and the marching-squares
constructor remain clean-room (they have no direct MATLAB
counterpart — MATLAB assumes the caller hands it a PTS struct from
the GUI). The BC enforcement functions that *do* have MATLAB
sources (``EnforceBoundaryConditions.m``,
``create_polygon_structure.m``) are now faithful ports — see
``docs/PORTING_NOTES.md`` entry dated 2026-04-24.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Sequence

import numpy as np
from numpy.typing import NDArray

from admesh._stages.distance import eval_sdf_grid
from admesh._stages.domains import Domain
from admesh._stages.in_polygon import in_polygon

Points = NDArray[np.float64]


class BoundaryType(IntEnum):
    """Minimum-viable ADMESH boundary-condition classes (ring-vertex tags)."""

    OPEN = 0
    """Outflow / prescribed elevation (MATLAB: open-ocean)."""
    WALL = 1
    """No-flux / reflective (MATLAB: no-normal-flow land)."""


# ADCIRC BC codes handled by ``EnforceBoundaryConditions.m`` (line 95, 144).
# The integer values are the ADCIRC ``IBTYPE`` convention carried through the
# MATLAB PTS struct: open-ocean = -1, external barriers in {3, 13, 23},
# internal barriers in {4, 5, 24, 25}. Our port reproduces the same triage.
BC_OPEN_OCEAN = -1
BC_EXTERNAL_BARRIER = (3, 13, 23)
BC_INTERNAL_BARRIER = (4, 5, 24, 25)


@dataclass
class BCSegment:
    """A single MATLAB ``PTS.BC(k)`` constraint: BC code + polyline.

    Faithful mirror of the MATLAB struct-array entry. ``num`` is the
    ADCIRC ``IBTYPE`` integer; ``points`` is an ``(N, 2)`` polyline.

    Port of the ``PTS.BC(k)`` sub-struct referenced throughout
    ``08_Enforce_Boundary_Conditions/*.m``.
    """

    num: int
    points: NDArray[np.float64]


@dataclass(frozen=True)
class PolygonStructure:
    """Output of :func:`create_polygon_structure`.

    Mirrors the MATLAB ``POLY`` struct fields returned by
    ``create_polygon_structure.m``:

    - ``L`` — ``(N,)`` edge lengths.
    - ``x``, ``y`` — ``(N, 5)`` rectangular polygon vertices per
      edge (closed: last column equals first).
    - ``circ_x``, ``circ_y`` — ``(N, 500)`` end-cap circle at
      ``(x1, y1)`` of each edge.
    """

    L: NDArray[np.float64]
    x: NDArray[np.float64]
    y: NDArray[np.float64]
    circ_x: NDArray[np.float64]
    circ_y: NDArray[np.float64]


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
    BC : list of :class:`BCSegment`
        Faithful mirror of MATLAB ``PTS.BC`` — additional per-segment
        constraints (open-ocean polyline, external/internal barriers).
        Empty list means no constraints are layered on top of ``rings``;
        matches MATLAB ``isempty(PTS.BC)`` semantics at
        ``EnforceBoundaryConditions.m`` line 42.
    attributes : dict
        Opaque passthrough for caller-owned data (e.g. bathymetry
        samples per segment).
    """

    rings: list[Points]
    bc_type: list[NDArray[np.int64]]
    BC: list[BCSegment] = field(default_factory=list)
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
        BC: Sequence[BCSegment] = (),
    ) -> "PTS":
        """Build a PTS from explicit polygon rings.

        ``bc`` is either a single :class:`BoundaryType` applied to
        every segment in every ring, or a sequence of length
        ``1 + len(holes)`` assigning a single type to each ring.
        ``BC`` is an optional sequence of :class:`BCSegment` entries
        layered on top — mirrors MATLAB ``PTS.BC``.
        """
        rings = [np.asarray(outer, dtype=float)] + [np.asarray(h, dtype=float) for h in holes]
        if isinstance(bc, BoundaryType):
            tags = [np.full(len(r), int(bc), dtype=np.int64) for r in rings]
        else:
            bc_seq = list(bc)
            if len(bc_seq) != len(rings):
                raise ValueError(f"bc sequence length {len(bc_seq)} != rings {len(rings)}")
            tags = [np.full(len(r), int(b), dtype=np.int64) for r, b in zip(rings, bc_seq)]
        return cls(rings=rings, bc_type=tags, BC=list(BC))

    @classmethod
    def from_domain(
        cls,
        domain: Domain,
        *,
        n_bnd: int = 64,
        grid_delta: float | None = None,
        bc: BoundaryType = BoundaryType.WALL,
        BC: Sequence[BCSegment] = (),
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
        pad = 3.0 * delta
        sampled_bbox = (xmin - pad, ymin - pad, xmax + pad, ymax + pad)
        X, Y, D = eval_sdf_grid(domain.fd, sampled_bbox, delta)
        segs = _marching_squares(X, Y, D)
        rings = _chain_segments(segs)
        if not rings:
            raise RuntimeError("marching squares produced no closed rings")
        rings.sort(key=_ring_perimeter, reverse=True)
        rings = [_resample_by_arclength(r, n_bnd) for r in rings]
        if _signed_area(rings[0]) < 0:
            rings[0] = rings[0][::-1]
        for i in range(1, len(rings)):
            if _signed_area(rings[i]) > 0:
                rings[i] = rings[i][::-1]
        tags = [np.full(len(r), int(bc), dtype=np.int64) for r in rings]
        return cls(rings=rings, bc_type=tags, BC=list(BC))


# ---------------------------------------------------------------- faithful port


def create_polygon_structure(
    points: NDArray[np.float64],
    delta: float | None = None,
) -> PolygonStructure:
    """Rectangular polygon + end-cap circle around each edge in ``points``.

    Port of ``01_ADMESH_Library/08_Enforce_Boundary_Conditions/
    create_polygon_structure.m`` @ ``19b2eb9``.

    For an ``(N+1, 2)`` polyline ``points``, returns a
    :class:`PolygonStructure` with one rectangle + one end-cap circle
    per edge. The rectangle has width ``2·d`` perpendicular to the
    edge and length equal to the edge. The circle is centered on the
    edge's first endpoint with radius ``d``.

    The half-width ``d`` is:

    - ``√3/2 · delta`` if ``delta`` is supplied (MATLAB line 33);
    - ``√3/2 · L_i`` (per-edge scaling) otherwise (line 63).

    Parameters
    ----------
    points : (M, 2) ndarray
        Polyline vertices. Edges are between consecutive rows, so
        ``N = M - 1`` edges total.
    delta : float or None
        Grid spacing; if given, ``d`` is uniform across all edges.
        If ``None``, ``d`` scales with each edge's length — used by
        the MATLAB barrier-enforcement path where ``POLY.L`` is the
        per-edge target h.

    Returns
    -------
    poly : PolygonStructure
    """
    pts = np.asarray(points, dtype=float)
    if pts.ndim != 2 or pts.shape[1] != 2:
        raise ValueError(f"points must be (M, 2); got {pts.shape}")
    N = pts.shape[0] - 1
    if N <= 0:
        raise ValueError("points must contain at least 2 rows")

    # MATLAB lines 52-53: vectorized edge endpoints.
    x1, y1 = pts[:-1, 0], pts[:-1, 1]
    x2, y2 = pts[1:, 0], pts[1:, 1]

    # MATLAB lines 58-62: edge vectors, length, outward normal.
    # Note the MATLAB sign convention: ``dx = x1 - x2`` (reverse), so
    # ``nx = dy/L``, ``ny = -dx/L`` gives a left-handed normal relative
    # to the forward edge direction. We preserve the sign exactly so
    # rectangles match MATLAB vertex order.
    dx = x1 - x2
    dy = y1 - y2
    L = np.hypot(dx, dy)
    nx = dy / L
    ny = -dx / L

    # MATLAB line 63: d is scalar delta*√3/2 if caller supplied delta,
    # else per-edge √3/2·L.
    sqrt3_2 = np.sqrt(3.0) / 2.0
    if delta is None:
        d = sqrt3_2 * L
    else:
        d = np.full(N, sqrt3_2 * float(delta))

    # MATLAB lines 68-69: rectangle corner construction.
    # Columns: (x1 + n·d, x1 - n·d, x2 - n·d, x2 + n·d, x1 + n·d).
    x = np.column_stack([
        x1 + nx * d,
        x1 - nx * d,
        x2 - nx * d,
        x2 + nx * d,
        x1 + nx * d,
    ])
    y = np.column_stack([
        y1 + ny * d,
        y1 - ny * d,
        y2 - ny * d,
        y2 + ny * d,
        y1 + ny * d,
    ])

    # MATLAB lines 70, 73-74: end-cap circle at (x1, y1) with radius d.
    t = np.linspace(0.0, 2.0 * np.pi, 500)
    circ_x = d[:, None] * np.cos(t)[None, :] + x1[:, None]
    circ_y = d[:, None] * np.sin(t)[None, :] + y1[:, None]

    return PolygonStructure(L=L, x=x, y=y, circ_x=circ_x, circ_y=circ_y)


def enforce_boundary_conditions(
    h_ic: NDArray[np.float64],
    X: NDArray[np.float64],
    Y: NDArray[np.float64],
    D: NDArray[np.float64],
    IB: NDArray[np.bool_] | NDArray[np.intp] | None,
    pts: PTS,
    hmax: float,
    hmin: float,
) -> NDArray[np.float64]:
    """Enforce h-field boundary conditions on a rectangular grid.

    Port of ``01_ADMESH_Library/08_Enforce_Boundary_Conditions/
    EnforceBoundaryConditions.m`` @ ``19b2eb9``.

    Modifies ``h_ic`` (a copy — the input is not mutated) to:

    1. Clip to ``[hmin, hmax]`` (MATLAB lines 35-36).
    2. Set ``hmax`` where ``D > hmin`` (MATLAB line 37) — far exterior
       cells. MATLAB sign convention is ``D < 0`` interior.
    3. Set ``hmax`` on open-ocean indices ``IB`` (line 47).
    4. For each external-barrier segment (``BC.num in {3, 13, 23}``):
       build a per-edge polygon structure via
       :func:`create_polygon_structure`, then on grid cells within
       ``|D| ≤ L_i`` that lie inside the i-th rectangle or end-cap,
       set ``h_ic = L_i`` (lines 94-136).
    5. Same for internal-barrier segments (``BC.num in {4, 5, 24, 25}``,
       lines 142-183).

    Parameters
    ----------
    h_ic : (LY, LX) ndarray
        Initial h field; will be clipped + enforced per above.
    X, Y : (LY, LX) ndarrays
        Grid coordinates (``meshgrid(xs, ys, indexing='xy')``).
    D : (LY, LX) ndarray
        Signed distance function; ``D < 0`` interior (MATLAB
        convention, see ``SignedDistanceFunction.m`` line 129).
    IB : (LY, LX) bool ndarray, flat int indices, or None
        Grid cells nearest to open-ocean boundary. If ``None`` or
        empty, the open-ocean enforcement is skipped. A boolean mask
        is interpreted elementwise; integer arrays are treated as
        C-order flat indices into ``h_ic`` (matching MATLAB linear
        indexing semantics).
    pts : PTS
        Boundary structure; ``pts.BC`` drives the barrier
        enforcement. If ``pts.BC`` is empty, the function returns
        after the clip + ``D > hmin`` + ``IB`` steps (MATLAB line 42).
    hmax, hmin : float

    Returns
    -------
    h_out : (LY, LX) ndarray
        Enforced h-field (new array).
    """
    h = np.asarray(h_ic, dtype=np.float64).copy()
    X = np.asarray(X, dtype=np.float64)
    Y = np.asarray(Y, dtype=np.float64)
    D = np.asarray(D, dtype=np.float64)
    if h.shape != D.shape or h.shape != X.shape or h.shape != Y.shape:
        raise ValueError("h_ic, X, Y, D must share shape")

    # MATLAB lines 35-37: clip + far-exterior = hmax.
    np.clip(h, hmin, hmax, out=h)
    h[D > hmin] = hmax

    # MATLAB line 42: no BC constraints → early return.
    if not pts.BC:
        return h

    # MATLAB line 47: open-ocean indices → hmax.
    if IB is not None:
        _apply_mask_or_indices(h, IB, hmax)

    # MATLAB lines 94-136: external barriers.
    for bc_seg in pts.BC:
        if bc_seg.num in BC_EXTERNAL_BARRIER:
            _enforce_barrier_band(h, X, Y, D, bc_seg.points)

    # MATLAB lines 142-183: internal barriers.
    for bc_seg in pts.BC:
        if bc_seg.num in BC_INTERNAL_BARRIER:
            _enforce_barrier_band(h, X, Y, D, bc_seg.points)

    return h


def _apply_mask_or_indices(
    h: NDArray[np.float64],
    mask_or_idx: NDArray[np.bool_] | NDArray[np.intp],
    value: float,
) -> None:
    """Set ``h`` to ``value`` at ``mask_or_idx``.

    Supports three callers:
    - Boolean mask with same shape as ``h``: elementwise assignment.
    - 1-D integer array: treated as C-order flat indices (matches
      MATLAB ``h(IB) = hmax`` when ``IB`` is a linear index vector).
    - Empty array / None: no-op.
    """
    arr = np.asarray(mask_or_idx)
    if arr.size == 0:
        return
    if arr.dtype == bool:
        h[arr] = value
    else:
        flat = h.ravel()
        flat[arr.astype(np.intp).ravel()] = value
        h[...] = flat.reshape(h.shape)


def _enforce_barrier_band(
    h: NDArray[np.float64],
    X: NDArray[np.float64],
    Y: NDArray[np.float64],
    D: NDArray[np.float64],
    barrier_points: NDArray[np.float64],
) -> None:
    """Set ``h = POLY.L(i)`` inside each per-edge rectangle + end-cap.

    Helper for MATLAB lines 94-136 (external) and 142-183 (internal)
    — both paths are structurally identical, only the BC-code triage
    differs. For each edge ``i`` in ``barrier_points``:

    1. Build ``POLY = create_polygon_structure(barrier_points)``.
    2. Restrict to grid cells with ``|D| <= POLY.L[i]`` (MATLAB line
       112, 161: ``ind = find(abs(D) <= POLY.L(i))``).
    3. Among those, find cells inside the rectangle or the end-cap
       circle (MATLAB ``PointInPolygon`` calls at lines 115, 123,
       164, 171); set their ``h`` to ``POLY.L[i]``.
    """
    poly = create_polygon_structure(barrier_points)
    X_flat = X.ravel()
    Y_flat = Y.ravel()
    abs_D_flat = np.abs(D).ravel()
    h_flat = h.ravel()

    for i in range(len(poly.L)):
        Li = float(poly.L[i])
        # MATLAB line 112: ind = find(abs(D) <= POLY.L(i)).
        band = abs_D_flat <= Li
        if not band.any():
            continue
        band_idx = np.nonzero(band)[0]
        Xq = X_flat[band_idx]
        Yq = Y_flat[band_idx]
        # MATLAB line 115: PointInPolygon on the rectangle.
        rect_in, _ = in_polygon(Xq, Yq, poly.x[i, :], poly.y[i, :])
        h_flat[band_idx[rect_in]] = Li
        # MATLAB line 123: PointInPolygon on the end-cap circle.
        circ_in, _ = in_polygon(Xq, Yq, poly.circ_x[i, :], poly.circ_y[i, :])
        h_flat[band_idx[circ_in]] = Li

    h[...] = h_flat.reshape(h.shape)


# --------------------------------------------------------- node classification


def classify_nodes_against_pts(
    pts: PTS, p: Points, *, tol: float = 1e-2
) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    """Classify each mesh node against the PTS rings.

    For each point in ``p``, compute the nearest PTS segment (drawn
    from ``pts.rings``) and return its ``(ring_id, BoundaryType)`` if
    the perpendicular distance is below ``tol``; otherwise
    ``(-1, -1)``.

    This is a clean-room utility for use by distmesh + routine code;
    it has no MATLAB counterpart (MATLAB uses ADCIRC-style per-
    segment BC codes; this is a ring-vertex tag-aware classifier).

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

    interior = best_dist > tol
    ring_id[interior] = -1
    bc[interior] = -1
    return ring_id, bc


# --------------------------------------------------------------- geometry ops


def _point_segment_distance(
    p: Points, a: NDArray[np.float64], b: NDArray[np.float64]
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Perpendicular distance from each point in ``p`` to segment ``ab``."""
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
    """Clean-room marching squares on a scalar grid."""
    LY, LX = D.shape
    D = np.where(D == 0, 1e-12, D)
    segs: list[tuple[Points, Points]] = []

    for j in range(LY - 1):
        for i in range(LX - 1):
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
    def key(pt: np.ndarray) -> tuple[int, int]:
        return (int(round(pt[0] / tol)), int(round(pt[1] / tol)))

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
