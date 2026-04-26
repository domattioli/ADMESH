"""Public Pythonic API for admesh2D v1.

Defined by ``specs/001-pythonize-and-fort14-integration/`` —
``data-model.md`` (entity shapes), ``contracts/python-api.md`` (public
signatures), ``quickstart.md`` (idealized usage).

This module is **strictly additive** to the faithful-port surface in
``admesh/<stage>.py``. Constitution Principle I — no edits to the 13
faithful-port stage modules are made by this layer; it only adapts
their inputs and outputs.
"""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

import numpy as np

from admesh.boundary_types import BoundaryType

if TYPE_CHECKING:
    from typing import TextIO

__all__ = [
    "BoundarySegment",
    "Mesh",
    "Domain",
    "triangulate",
    "domain_from_polygon",
    "domain_from_sdf",
]


@dataclass(frozen=True, slots=True)
class BoundarySegment:
    """A single boundary segment of a :class:`Mesh`.

    Attributes
    ----------
    node_ids
        Shape ``(N,)``, dtype ``int64``. **0-based** node indices in
        declaration order. Conversion to/from the 1-based fort.14
        convention is handled at the I/O boundary by ``admesh.fort14``.
    bc_type
        Either a :class:`BoundaryType` member (named ADCIRC code) or a
        plain ``int`` (unmapped code preserved for round-trip).
    is_open
        ``True`` iff this segment lives in the fort.14 *open* boundary
        block. Tracked separately from ``bc_type`` so uncommon ADCIRC
        codes that may appear in either block round-trip faithfully.
    """

    node_ids: np.ndarray
    bc_type: BoundaryType | int
    is_open: bool

    def __post_init__(self) -> None:
        ids = self.node_ids
        if not isinstance(ids, np.ndarray):
            raise TypeError(
                f"BoundarySegment.node_ids must be a numpy.ndarray, got {type(ids).__name__}"
            )
        if ids.ndim != 1:
            raise ValueError(
                f"BoundarySegment.node_ids must be 1-D, got ndim={ids.ndim}"
            )
        if ids.dtype != np.int64:
            raise ValueError(
                f"BoundarySegment.node_ids must be int64, got dtype={ids.dtype}"
            )
        if ids.size > 0 and ids.min() < 0:
            raise ValueError(
                "BoundarySegment.node_ids contains negative indices "
                "(must be 0-based and non-negative)"
            )


@dataclass(frozen=True, slots=True)
class Mesh:
    """Triangular mesh with optional bathymetry and per-element quality.

    See ``specs/001-pythonize-and-fort14-integration/data-model.md``.
    Coordinates are 0-based and bathymetry follows the elevation
    (positive-up) convention. The fort.14 reader/writer apply the
    1-based ↔ 0-based and elevation ↔ depth conversions strictly at the
    I/O boundary.
    """

    nodes: np.ndarray
    elements: np.ndarray
    boundaries: tuple[BoundarySegment, ...] = ()
    bathymetry: np.ndarray | None = None
    quality: np.ndarray | None = None
    title: str = ""

    @property
    def n_nodes(self) -> int:
        return int(self.nodes.shape[0])

    @property
    def n_elements(self) -> int:
        return int(self.elements.shape[0])

    @property
    def n_boundaries(self) -> int:
        return len(self.boundaries)

    def to_fort14(self, path: "str | os.PathLike[str] | TextIO") -> None:
        """Serialize this mesh to ADCIRC v55 fort.14.

        Implementation lands in T024 (``admesh.fort14.write_fort14``).
        """
        from admesh.fort14 import write_fort14

        write_fort14(self, path)

    def plot(self, ax=None, **kwargs):
        """Draw the mesh using matplotlib.

        Implementation lands in T028 (``admesh.viz.plot_mesh``).

        Raises
        ------
        ImportError
            If matplotlib is not installed. Install with
            ``pip install admesh2D[viz]``.
        """
        from admesh.viz import plot_mesh

        return plot_mesh(self, ax=ax, **kwargs)

    def plot_layers(self, ax=None, cmap="viridis", **kwargs):
        """Draw mesh layers (onion-peel BFS from boundary) with colors.

        Raises
        ------
        ImportError
            If matplotlib is not installed. Install with
            ``pip install admesh2D[viz]``.
        """
        from admesh.viz import plot_mesh_layers

        return plot_mesh_layers(self, ax=ax, cmap=cmap, **kwargs)

    def equals(self, other: "Mesh", *, atol: float = 1e-10, rtol: float = 0.0) -> bool:
        """Tolerance-aware equality check for round-trip tests.

        Connectivity (``elements``, per-segment BC labels and node ids)
        is compared exactly; coordinates and bathymetry use
        ``np.allclose`` with the supplied tolerances. ``quality`` is
        ignored — it's a derived attribute and the round-trip path
        does not preserve it.
        """
        if not isinstance(other, Mesh):
            return NotImplemented  # type: ignore[return-value]
        if self.nodes.shape != other.nodes.shape:
            return False
        if self.elements.shape != other.elements.shape:
            return False
        if not np.array_equal(self.elements, other.elements):
            return False
        if not np.allclose(self.nodes, other.nodes, atol=atol, rtol=rtol):
            return False
        if (self.bathymetry is None) != (other.bathymetry is None):
            return False
        if self.bathymetry is not None and other.bathymetry is not None:
            if self.bathymetry.shape != other.bathymetry.shape:
                return False
            if not np.allclose(
                self.bathymetry, other.bathymetry, atol=atol, rtol=rtol
            ):
                return False
        if len(self.boundaries) != len(other.boundaries):
            return False
        for a, b in zip(self.boundaries, other.boundaries):
            if a.is_open != b.is_open:
                return False
            if int(a.bc_type) != int(b.bc_type):
                return False
            if not np.array_equal(a.node_ids, b.node_ids):
                return False
        return True

    def __repr__(self) -> str:
        if self.quality is not None and self.quality.size > 0:
            min_q = float(self.quality.min())
            mean_q = float(self.quality.mean())
            q_part = f", min_q={min_q:.2f}, mean_q={mean_q:.2f}"
        else:
            q_part = ""
        return (
            f"Mesh(n_nodes={self.n_nodes}, n_elements={self.n_elements}"
            f"{q_part}, n_boundaries={self.n_boundaries})"
        )

    def __str__(self) -> str:
        lines = ["Mesh"]
        lines.append(f"  nodes:      {self.n_nodes} × 2 (float64)")
        lines.append(f"  elements:   {self.n_elements} × 3 (int64)")
        if self.quality is not None and self.quality.size > 0:
            qmin = float(self.quality.min())
            qmean = float(self.quality.mean())
            qmax = float(self.quality.max())
            lines.append(
                f"  quality:    min={qmin:.2f}, mean={qmean:.2f}, max={qmax:.2f}"
            )
        else:
            lines.append("  quality:    not computed")
        if self.boundaries:
            lines.append(f"  boundaries: {self.n_boundaries} segments")
            for i, seg in enumerate(self.boundaries):
                if isinstance(seg.bc_type, BoundaryType):
                    label = seg.bc_type.name
                else:
                    label = f"code={int(seg.bc_type)}"
                lines.append(
                    f"    [{i}] {label:<13} ({seg.node_ids.size} nodes)"
                )
        else:
            lines.append("  boundaries: none")
        if self.bathymetry is None:
            lines.append("  bathymetry: not set")
        else:
            lines.append(
                f"  bathymetry: {self.bathymetry.size} samples (float64)"
            )
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class Domain:
    """Geometric description for :func:`triangulate`.

    Attributes
    ----------
    sdf
        Signed-distance function: ``(N, 2) -> (N,)``. Negative inside,
        positive outside, zero on the boundary.
    bbox
        ``(xmin, ymin, xmax, ymax)`` extent (matches Shapely / matplotlib
        convention).
    pfix
        Optional ``(K, 2)`` array of fixed points the triangulator must
        keep.
    pts
        Optional ``(P, 2)`` array of boundary discretization points
        (used by stages that take an explicit polyline input).
    bc_segments
        Optional pre-labeled boundary metadata that flows through to
        the output mesh.
    """

    sdf: Callable[[np.ndarray], np.ndarray]
    bbox: tuple[float, float, float, float]
    pfix: np.ndarray | None = None
    pts: np.ndarray | None = None
    bc_segments: tuple[BoundarySegment, ...] = ()


# ---------------------------------------------------------------------------
# Domain builders (T020).
# ---------------------------------------------------------------------------


def _shapely_sdf(rings: list[np.ndarray]) -> Callable[[np.ndarray], np.ndarray]:
    """Construct an SDF from a list of rings using Shapely.

    Outer ring first, holes following. The returned callable accepts an
    ``(N, 2)`` array of query points and returns ``(N,)`` signed
    distances: negative inside, positive outside, zero on the boundary.
    """
    from shapely.geometry import Polygon, Point  # noqa: F401  (Point used below)
    from shapely.prepared import prep
    from shapely import distance as shp_distance, points as shp_points

    if not rings:
        raise ValueError("rings must contain at least one outer ring")

    outer = np.asarray(rings[0], dtype=np.float64)
    holes = [np.asarray(r, dtype=np.float64) for r in rings[1:]]
    polygon = Polygon(outer, holes=holes if holes else None)
    boundary = polygon.boundary
    prepared = prep(polygon)

    def sdf(p: np.ndarray) -> np.ndarray:
        pts = np.asarray(p, dtype=np.float64)
        if pts.ndim == 1:
            pts = pts[None, :]
        sp = shp_points(pts[:, 0], pts[:, 1])
        d = shp_distance(sp, boundary)
        # Inside: negative. Use prepared.contains for vectorized membership.
        inside = np.array([prepared.contains(g) for g in sp])
        return np.where(inside, -d, d).astype(np.float64)

    return sdf


def domain_from_polygon(
    rings: list[np.ndarray],
    *,
    pfix: np.ndarray | None = None,
    bc_segments: tuple[BoundarySegment, ...] = (),
) -> Domain:
    """Build a :class:`Domain` from a list of polygon rings.

    Outer ring first, then any holes. Each ring is an ``(M, 2)`` float
    array of ``(x, y)`` vertices. The SDF is built via Shapely; the
    bbox is derived from the outer-ring extent.
    """
    if not rings:
        raise ValueError("domain_from_polygon: rings must be non-empty")
    outer = np.asarray(rings[0], dtype=np.float64)
    if outer.ndim != 2 or outer.shape[1] != 2:
        raise ValueError(
            f"domain_from_polygon: outer ring must have shape (M, 2), got {outer.shape}"
        )
    xmin = float(outer[:, 0].min())
    ymin = float(outer[:, 1].min())
    xmax = float(outer[:, 0].max())
    ymax = float(outer[:, 1].max())
    return Domain(
        sdf=_shapely_sdf(rings),
        bbox=(xmin, ymin, xmax, ymax),
        pfix=pfix,
        pts=None,
        bc_segments=bc_segments,
    )


def domain_from_sdf(
    sdf: Callable[[np.ndarray], np.ndarray],
    bbox: tuple[float, float, float, float],
    *,
    pfix: np.ndarray | None = None,
    pts: np.ndarray | None = None,
    bc_segments: tuple[BoundarySegment, ...] = (),
) -> Domain:
    """Build a :class:`Domain` from an explicit SDF callable + bbox."""
    if len(bbox) != 4:
        raise ValueError(
            f"domain_from_sdf: bbox must be (xmin, ymin, xmax, ymax); got {bbox}"
        )
    return Domain(
        sdf=sdf,
        bbox=tuple(float(x) for x in bbox),  # type: ignore[arg-type]
        pfix=pfix,
        pts=pts,
        bc_segments=bc_segments,
    )


# ---------------------------------------------------------------------------
# Boundary derivation helper.
# ---------------------------------------------------------------------------


def _derive_boundary_segments(
    elements: np.ndarray,
    nodes: np.ndarray,
    *,
    default_bc: BoundaryType = BoundaryType.MAINLAND,
) -> tuple[BoundarySegment, ...]:
    """Walk boundary edges of a triangulation and assemble into rings.

    A boundary edge is one that appears in exactly one triangle. This
    function chains adjacent boundary edges into closed rings, then wraps
    each ring as a :class:`BoundarySegment` with the supplied default BC
    type (caller can relabel afterward).
    """
    # Collect undirected edges with multiplicity.
    edges: dict[tuple[int, int], int] = {}
    directed: dict[tuple[int, int], list[int]] = {}
    for tri in elements:
        a, b, c = int(tri[0]), int(tri[1]), int(tri[2])
        for u, v in ((a, b), (b, c), (c, a)):
            key = (u, v) if u < v else (v, u)
            edges[key] = edges.get(key, 0) + 1
            directed.setdefault(u, []).append(v)
    boundary_edges = {k for k, count in edges.items() if count == 1}
    if not boundary_edges:
        return ()

    # Build a directed-edge map restricted to boundary edges using the
    # directed traversals we collected above. For each boundary undirected
    # edge {u,v}, we want the *one* triangle's directed edge u→v that
    # actually appeared (so the ring is consistently oriented).
    next_node: dict[int, int] = {}
    for u, vs in directed.items():
        for v in vs:
            key = (u, v) if u < v else (v, u)
            if key in boundary_edges:
                next_node[u] = v

    # Walk rings.
    visited: set[int] = set()
    rings: list[list[int]] = []
    for start in next_node:
        if start in visited:
            continue
        if start not in next_node:
            continue
        ring = [start]
        visited.add(start)
        cur = next_node[start]
        guard = len(next_node) + 2
        while cur != start and guard > 0:
            ring.append(cur)
            visited.add(cur)
            if cur not in next_node:
                break
            cur = next_node[cur]
            guard -= 1
        if len(ring) >= 3:
            rings.append(ring)

    # Order rings by length, longest first — gives the outer ring index 0
    # for typical doubly-connected shapes.
    rings.sort(key=len, reverse=True)
    return tuple(
        BoundarySegment(
            node_ids=np.asarray(ring, dtype=np.int64),
            bc_type=default_bc,
            is_open=False,
        )
        for ring in rings
    )


# ---------------------------------------------------------------------------
# Pipeline (T021).
# ---------------------------------------------------------------------------


def _bbox_diag(bbox: tuple[float, float, float, float]) -> float:
    xmin, ymin, xmax, ymax = bbox
    return float(np.hypot(xmax - xmin, ymax - ymin))


def triangulate(
    domain: Domain,
    *,
    h_max: float | None = None,
    h_min: float | None = None,
    size_field: Callable[[np.ndarray], np.ndarray] | None = None,
    user_contribs: tuple[Callable[[np.ndarray], np.ndarray], ...] = (),
    combine: Callable[[list[np.ndarray]], np.ndarray] = np.minimum.reduce,
    seed: int | None = None,
    max_iter: int | None = None,
    quality_gate: tuple[float, float] = (0.30, 0.60),
) -> Mesh:
    """Generate a triangular mesh on ``domain``.

    Adapts the v1 :class:`Domain` onto the faithful-port driver
    :func:`admesh.routine.triangulate` without modifying it (Constitution
    Principle I). Returns a :class:`Mesh` with per-element quality
    populated and boundaries derived from the triangulation.
    """
    # Lazy imports — keeps `import admesh` cheap and avoids a hard
    # dependency cycle with the faithful-port modules at import time.
    from admesh.domains import Domain as _PortDomain
    from admesh.quality import mesh_quality
    from admesh.routine import triangulate as _routine_triangulate

    # Resolve h0 from h_max, falling back to a fraction of the bbox diagonal.
    if h_max is None:
        h0 = max(_bbox_diag(domain.bbox) / 20.0, 1e-6)
    else:
        h0 = float(h_max)

    # Adapter: the faithful-port `Domain` carries the SDF + fixed points.
    pfix = domain.pfix
    if pfix is None:
        pfix = np.empty((0, 2), dtype=np.float64)
    pfix = np.asarray(pfix, dtype=np.float64)
    port_domain = _PortDomain(
        name="api_v1",
        fd=domain.sdf,
        bbox=domain.bbox,
        fixed_points=pfix,
    )

    # Build kwargs for the driver. seed / niter only forwarded when the
    # caller supplied them — let the routine apply its own defaults.
    opts: dict[str, object] = {}
    if seed is not None:
        opts["seed"] = int(seed)
    if max_iter is not None:
        opts["niter"] = int(max_iter)

    # Resolve the size field. Three cases:
    #
    #   1. Caller passed a pre-composed `size_field=`. They've already
    #      done their own composition; we use it as-is. If they ALSO
    #      passed `user_contribs=` we warn — those would be ignored
    #      otherwise, which silently violates the contract.
    #   2. Caller passed `user_contribs=`. Wrap them via
    #      `compose_size_field` with `size_field` (if any) as the sole
    #      Phase-1 builtin. Default combiner is `np.minimum.reduce`.
    #   3. Neither — uniform sizing falls through (`fh=None`).
    if size_field is not None and user_contribs:
        warnings.warn(
            "triangulate: both `size_field` and `user_contribs` were "
            "supplied; ignoring `user_contribs` (the pre-composed "
            "`size_field` already encodes its own composition).",
            UserWarning,
            stacklevel=2,
        )
        fh = size_field
    elif user_contribs:
        from admesh.size_field import compose_size_field

        builtins_phase1 = (size_field,) if size_field is not None else ()
        fh = compose_size_field(
            builtins=builtins_phase1,
            user_contribs=tuple(user_contribs),
            combine=combine,
            hmin=h_min,
            hmax=h_max,
        )
    else:
        fh = size_field  # may still be None — uniform sizing

    p, t = _routine_triangulate(port_domain, h0=h0, fh=fh, **opts)
    nodes = np.asarray(p, dtype=np.float64)
    elements = np.asarray(t, dtype=np.int64)

    min_q, mean_q, q_per = mesh_quality(nodes, elements)
    gate_min, gate_mean = quality_gate
    if min_q < gate_min:
        raise ValueError(
            f"triangulate: min_q {min_q:.3f} < quality_gate[0] {gate_min:.2f}"
        )
    if mean_q < gate_mean:
        raise ValueError(
            f"triangulate: mean_q {mean_q:.3f} < quality_gate[1] {gate_mean:.2f}"
        )

    # Derive boundary segments. If the caller pre-declared bc_segments
    # on the Domain, pass them through verbatim — they're the user's
    # contract about the output. Otherwise default-label every closed
    # boundary ring as MAINLAND.
    if domain.bc_segments:
        boundaries = tuple(domain.bc_segments)
    else:
        boundaries = _derive_boundary_segments(elements, nodes)

    return Mesh(
        nodes=nodes,
        elements=elements,
        boundaries=boundaries,
        bathymetry=None,
        quality=np.asarray(q_per, dtype=np.float64),
        title="",
    )
