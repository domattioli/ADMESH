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
    paired_node_ids
        Optional ``(N,)`` int64 array of paired node ids (0-based)
        for ADCIRC paired-edge BC types (IBTYPE 4, 14, 24, 25). When
        not ``None``, ``len(paired_node_ids) == len(node_ids)``. See
        ``specs/002-size-field-defaults/contracts/fort14-paired-edge.md``.
    barrier_data
        Optional ``(N, K)`` float64 array carrying per-record crest /
        coefficient columns for IBTYPE 3 / 4 / 13 / 24 / 25 barrier
        records. Column meaning is IBTYPE-specific; see the data-model
        of spec 002. ``barrier_data.shape[0] == len(node_ids)`` when
        not ``None``.
    """

    node_ids: np.ndarray
    bc_type: BoundaryType | int
    is_open: bool
    paired_node_ids: np.ndarray | None = None
    barrier_data: np.ndarray | None = None

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
        if self.paired_node_ids is not None:
            pids = self.paired_node_ids
            if not isinstance(pids, np.ndarray):
                raise TypeError(
                    "BoundarySegment.paired_node_ids must be a numpy.ndarray, "
                    f"got {type(pids).__name__}"
                )
            if pids.ndim != 1:
                raise ValueError(
                    "BoundarySegment.paired_node_ids must be 1-D, "
                    f"got ndim={pids.ndim}"
                )
            if pids.dtype != np.int64:
                raise ValueError(
                    "BoundarySegment.paired_node_ids must be int64, "
                    f"got dtype={pids.dtype}"
                )
            if pids.size != ids.size:
                raise ValueError(
                    "BoundarySegment.paired_node_ids length "
                    f"({pids.size}) must match node_ids length ({ids.size})"
                )
            if pids.size > 0 and pids.min() < 0:
                raise ValueError(
                    "BoundarySegment.paired_node_ids contains negative "
                    "indices (must be 0-based and non-negative)"
                )
        if self.barrier_data is not None:
            bd = self.barrier_data
            if not isinstance(bd, np.ndarray):
                raise TypeError(
                    "BoundarySegment.barrier_data must be a numpy.ndarray, "
                    f"got {type(bd).__name__}"
                )
            if bd.ndim != 2:
                raise ValueError(
                    "BoundarySegment.barrier_data must be 2-D (N, K), "
                    f"got ndim={bd.ndim}"
                )
            if bd.dtype != np.float64:
                raise ValueError(
                    "BoundarySegment.barrier_data must be float64, "
                    f"got dtype={bd.dtype}"
                )
            if bd.shape[0] != ids.size:
                raise ValueError(
                    f"BoundarySegment.barrier_data row count ({bd.shape[0]}) "
                    f"must match node_ids length ({ids.size})"
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
            # Spec 002: paired-edge + barrier data preserved on round-trip.
            if (a.paired_node_ids is None) != (b.paired_node_ids is None):
                return False
            if a.paired_node_ids is not None and b.paired_node_ids is not None:
                if not np.array_equal(a.paired_node_ids, b.paired_node_ids):
                    return False
            if (a.barrier_data is None) != (b.barrier_data is None):
                return False
            if a.barrier_data is not None and b.barrier_data is not None:
                if a.barrier_data.shape != b.barrier_data.shape:
                    return False
                if not np.allclose(
                    a.barrier_data, b.barrier_data, atol=atol, rtol=rtol
                ):
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
    bathymetry
        Optional callable ``(X, Y) -> Z`` returning depth (or elevation)
        samples on arbitrary-shape input arrays. When set, the default
        size-field stack activates the bathymetry-driven refinement
        stage. See spec 002 ``data-model.md``.
    tide_period
        Optional float (seconds, > 0). When set, the default size-field
        stack activates the tide-wavelength stage. If ``bathymetry`` is
        ``None`` while ``tide_period`` is set, ``triangulate`` emits a
        ``UserWarning`` and falls back to a constant default depth.
    polygons
        Optional tuple of Shapely ``Polygon`` objects describing the
        domain rings (outer first, holes following). Populated by
        :func:`domain_from_polygon` and :meth:`Domain.from_mesh` so the
        structural-validity test gate can compare triangle edges
        against input boundary edges.
    """

    sdf: Callable[[np.ndarray], np.ndarray]
    bbox: tuple[float, float, float, float]
    pfix: np.ndarray | None = None
    pts: np.ndarray | None = None
    bc_segments: tuple[BoundarySegment, ...] = ()
    bathymetry: Callable[[np.ndarray, np.ndarray], np.ndarray] | None = None
    tide_period: float | None = None
    polygons: tuple | None = None

    def __post_init__(self) -> None:
        if self.tide_period is not None:
            tp = float(self.tide_period)
            if not (tp > 0.0):
                raise ValueError(
                    "Domain.tide_period must be positive (seconds); "
                    f"got {self.tide_period!r}"
                )
        if self.bathymetry is not None and not callable(self.bathymetry):
            raise TypeError(
                "Domain.bathymetry must be callable (X, Y) -> Z or None; "
                f"got {type(self.bathymetry).__name__}"
            )

    @classmethod
    def from_mesh(
        cls,
        mesh: "Mesh",
        *,
        tide_period: float | None = None,
        bbox_pad: float = 0.0,
    ) -> "Domain":
        """Build a :class:`Domain` from an existing triangulated :class:`Mesh`.

        Closes the round-trip story: ``Domain → triangulate → Mesh →
        Domain.from_mesh → Domain``. Useful for re-meshing an ADCIRC
        ``fort.14`` file at a different resolution.

        - Outer + island rings are recovered from the mesh's element
          topology (boundary edges = edges in exactly one triangle).
          Internal weir / barrier records are NOT topologically
          embedded; they are not transferred to the new mesh.
        - When ``mesh.bathymetry`` is set, ``Domain.bathymetry`` is a
          ``LinearNDInterpolator`` over ``(mesh.nodes, mesh.bathymetry)``.
          Returns ``NaN`` outside the convex hull; the bathymetry stage
          calls ``inpaint_nans`` to handle that.

        Parameters
        ----------
        mesh : Mesh
        tide_period : float or None
            Optional tidal period (seconds) to attach to the returned
            ``Domain``; not derived from the mesh.
        bbox_pad : float
            Padding added to each side of the recovered bbox. Default 0.

        Raises
        ------
        ValueError
            If the mesh has zero boundary edges (no element topology).
        """
        from shapely.geometry import Polygon

        if mesh.n_elements == 0:
            raise ValueError(
                "Domain.from_mesh: mesh has no elements"
            )

        rings_segs = _derive_boundary_segments(mesh.elements, mesh.nodes)
        if not rings_segs:
            raise ValueError(
                "Domain.from_mesh: no boundary edges found in element topology"
            )

        rings_xy = [mesh.nodes[seg.node_ids] for seg in rings_segs]
        outer = rings_xy[0]
        holes = rings_xy[1:]
        polygon = Polygon(outer, holes=holes if holes else None)

        sdf = _shapely_sdf(rings_xy)
        xmin = float(outer[:, 0].min()) - bbox_pad
        ymin = float(outer[:, 1].min()) - bbox_pad
        xmax = float(outer[:, 0].max()) + bbox_pad
        ymax = float(outer[:, 1].max()) + bbox_pad

        # Bathymetry interpolant via LinearNDInterpolator.
        bathy_callable = None
        if mesh.bathymetry is not None:
            from scipy.interpolate import LinearNDInterpolator

            interp = LinearNDInterpolator(
                np.asarray(mesh.nodes, dtype=np.float64),
                np.asarray(mesh.bathymetry, dtype=np.float64),
                fill_value=np.nan,
            )

            def bathy_callable(X, Y, _interp=interp):
                X = np.asarray(X, dtype=np.float64)
                Y = np.asarray(Y, dtype=np.float64)
                pts = np.column_stack([X.ravel(), Y.ravel()])
                Z = _interp(pts)
                return Z.reshape(X.shape)

        return cls(
            sdf=sdf,
            bbox=(xmin, ymin, xmax, ymax),
            pfix=None,
            pts=None,
            bc_segments=(),
            bathymetry=bathy_callable,
            tide_period=tide_period,
            polygons=(polygon,),
        )


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
    bathymetry: Callable[[np.ndarray, np.ndarray], np.ndarray] | None = None,
    tide_period: float | None = None,
) -> Domain:
    """Build a :class:`Domain` from a list of polygon rings.

    Outer ring first, then any holes. Each ring is an ``(M, 2)`` float
    array of ``(x, y)`` vertices. The SDF is built via Shapely; the
    bbox is derived from the outer-ring extent.

    ``bathymetry`` and ``tide_period`` (spec 002) feed the default
    size-field stack — see :func:`triangulate`.
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

    # Build the canonical Shapely polygon once (for the structural-validity
    # test gate) — same input the SDF builder uses internally.
    from shapely.geometry import Polygon as _ShapelyPolygon

    holes_xy = [np.asarray(r, dtype=np.float64) for r in rings[1:]]
    polygon = _ShapelyPolygon(
        np.asarray(rings[0], dtype=np.float64),
        holes=holes_xy if holes_xy else None,
    )

    return Domain(
        sdf=_shapely_sdf(rings),
        bbox=(xmin, ymin, xmax, ymax),
        pfix=pfix,
        pts=None,
        bc_segments=bc_segments,
        bathymetry=bathymetry,
        tide_period=tide_period,
        polygons=(polygon,),
    )


def domain_from_sdf(
    sdf: Callable[[np.ndarray], np.ndarray],
    bbox: tuple[float, float, float, float],
    *,
    pfix: np.ndarray | None = None,
    pts: np.ndarray | None = None,
    bc_segments: tuple[BoundarySegment, ...] = (),
    bathymetry: Callable[[np.ndarray, np.ndarray], np.ndarray] | None = None,
    tide_period: float | None = None,
) -> Domain:
    """Build a :class:`Domain` from an explicit SDF callable + bbox.

    ``bathymetry`` and ``tide_period`` (spec 002) feed the default
    size-field stack — see :func:`triangulate`.
    """
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
        bathymetry=bathymetry,
        tide_period=tide_period,
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


def _build_default_size_field(
    domain: Domain,
    *,
    h_min: float,
    h_max: float,
    h_target: float | None,
    enable_curvature: bool,
    enable_medial_axis: bool,
    default_depth: float,
    tide_elements_per_wavelength: float,
) -> Callable[[np.ndarray], np.ndarray]:
    """Compose the spec-002 default Phase-1 size-field callable.

    Maps the public-API kwargs to ``admesh.mesh_size.build_h(...)``
    parameters per
    ``specs/002-size-field-defaults/contracts/python-api-default-stack.md``.
    The faithful-port composer is **not modified** — Constitution
    Principle I; this function only adapts inputs.

    Returns a uniform-``h`` callable when the dynamic range is too
    small (``h_max / h_min < 2``) or every stage is disabled.
    """
    base = float(h_target) if h_target is not None else float(h_max)
    h_min_f = float(h_min)
    h_max_f = float(h_max)

    # Determine which stages would actually contribute.
    bathy = domain.bathymetry
    tide = domain.tide_period
    fallback_used = False
    if tide is not None and bathy is None:
        # Spec FR-013 / clarification 3: warn-and-run with a constant
        # default depth instead of silently skipping the tide stage.
        warnings.warn(
            "tide_period set but Domain.bathymetry is None; "
            f"using constant default_depth={default_depth!r}",
            UserWarning,
            stacklevel=3,
        )

        def _const_bathy(X, Y, _d=float(default_depth)):
            X = np.asarray(X, dtype=np.float64)
            return np.full(X.shape, _d, dtype=np.float64)

        bathy = _const_bathy
        fallback_used = True

    want_curv = bool(enable_curvature)
    want_med = bool(enable_medial_axis)
    want_bathy = bathy is not None
    want_tide = tide is not None and bathy is not None
    any_stage = want_curv or want_med or want_bathy or want_tide

    # Short-circuit: degenerate dynamic range or all stages off → uniform.
    if not any_stage or (h_min_f > 0 and h_max_f / h_min_f < 2.0):
        uniform = float(base)

        def _fh_uniform(p, _u=uniform):
            p = np.asarray(p, dtype=np.float64).reshape(-1, 2)
            return np.full(len(p), _u, dtype=np.float64)

        return _fh_uniform

    # Adapt the public Domain onto the port-domain shape build_h expects.
    from admesh.domains import Domain as _PortDomain

    pfix = domain.pfix
    if pfix is None:
        pfix = np.empty((0, 2), dtype=np.float64)
    pfix = np.asarray(pfix, dtype=np.float64)
    port_domain = _PortDomain(
        name="api_v1_default_stack",
        fd=domain.sdf,
        bbox=domain.bbox,
        fixed_points=pfix,
    )

    from admesh.mesh_size import build_h

    fh = build_h(
        port_domain,
        base=base,
        curvature_scale=h_min_f if want_curv else None,
        medial_scale=h_min_f if want_med else None,
        bathymetry=bathy,
        bathy_scale=1.0 if want_bathy else None,
        tide_period=float(tide) if tide is not None else None,
        tide_scale=(
            float(tide_elements_per_wavelength) if want_tide else None
        ),
        hmin=h_min_f,
        hmax=h_max_f,
    )
    # Annotate the callable for optional introspection in tests.
    try:
        fh.__admesh_default_stack__ = {  # type: ignore[attr-defined]
            "enable_curvature": want_curv,
            "enable_medial_axis": want_med,
            "enable_bathymetry": want_bathy,
            "enable_tide": want_tide,
            "fallback_default_depth": fallback_used,
        }
    except (AttributeError, TypeError):
        pass
    return fh


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
    # --- New kwargs (spec 002) ---
    h_target: float | None = None,
    enable_curvature: bool = True,
    enable_medial_axis: bool = True,
    default_depth: float = 1.0,
    tide_elements_per_wavelength: float = 100.0,
) -> Mesh:
    """Generate a triangular mesh on ``domain``.

    Adapts the v1 :class:`Domain` onto the faithful-port driver
    :func:`admesh.routine.triangulate` without modifying it (Constitution
    Principle I). Returns a :class:`Mesh` with per-element quality
    populated and boundaries derived from the triangulation.

    Spec 002 introduces a default size-field stack: when neither
    ``size_field=`` nor ``user_contribs=`` is supplied, the function
    composes curvature + medial-axis (always-on) plus bathymetry +
    tide (auto-enabled from ``Domain.bathymetry`` /
    ``Domain.tide_period``) via :func:`admesh.mesh_size.build_h`. See
    ``specs/002-size-field-defaults/contracts/python-api-default-stack.md``
    for the public-knob → MATLAB-internal mapping.

    New keyword arguments (spec 002):

    h_target
        Target edge length where no size-reducing stage contributes.
        Defaults to ``h_max`` when ``None``.
    enable_curvature, enable_medial_axis
        Boolean toggles for the always-on stages of the default stack.
        Defaults ``True``. Set ``False`` to bypass that stage entirely.
    default_depth
        Constant depth (metres) used when ``Domain.tide_period`` is set
        but ``Domain.bathymetry`` is ``None``. A ``UserWarning`` fires.
    tide_elements_per_wavelength
        Forwarded as ``tide_scale`` to the dominant-tide stage. Default
        100.0 elements per wavelength.
    """
    # Lazy imports — keeps `import admesh` cheap and avoids a hard
    # dependency cycle with the faithful-port modules at import time.
    from admesh.domains import Domain as _PortDomain
    from admesh.quality import mesh_quality
    from admesh.routine import triangulate as _routine_triangulate

    # Resolve h0 from h_max, falling back to a fraction of the bbox diagonal.
    if h_max is None:
        h0 = max(_bbox_diag(domain.bbox) / 20.0, 1e-6)
        h_max_eff = h0
    else:
        h0 = float(h_max)
        h_max_eff = float(h_max)

    # Default h_min if not supplied — used by the default size-field
    # stack to set per-stage clipping. Mirrors `build_h(...)`'s own
    # `hmin = base / 8.0` fallback so the public default matches the
    # composer's internal default.
    h_min_eff = float(h_min) if h_min is not None else h_max_eff / 8.0

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

    # Resolve the size field. Four cases:
    #
    #   1. Both supplied: warn (spec-001 behaviour) and use size_field.
    #   2. size_field= alone: spec-001 bypass. Default stack does NOT run.
    #   3. user_contribs= alone (spec 002 change): build the default
    #      stack as the Phase-1 builtin, then compose user_contribs on
    #      top via `compose_size_field`.
    #   4. Neither (spec 002 change): build and use the default stack.
    user_contribs_tuple = tuple(user_contribs) if user_contribs else ()
    if size_field is not None and user_contribs_tuple:
        warnings.warn(
            "triangulate: both `size_field` and `user_contribs` were "
            "supplied; ignoring `user_contribs` (the pre-composed "
            "`size_field` already encodes its own composition).",
            UserWarning,
            stacklevel=2,
        )
        fh = size_field
    elif size_field is not None:
        fh = size_field
    elif user_contribs_tuple:
        from admesh.size_field import compose_size_field

        default_fh = _build_default_size_field(
            domain,
            h_min=h_min_eff,
            h_max=h_max_eff,
            h_target=h_target,
            enable_curvature=enable_curvature,
            enable_medial_axis=enable_medial_axis,
            default_depth=default_depth,
            tide_elements_per_wavelength=tide_elements_per_wavelength,
        )
        fh = compose_size_field(
            builtins=(default_fh,),
            user_contribs=user_contribs_tuple,
            combine=combine,
            hmin=h_min,
            hmax=h_max,
        )
    else:
        fh = _build_default_size_field(
            domain,
            h_min=h_min_eff,
            h_max=h_max_eff,
            h_target=h_target,
            enable_curvature=enable_curvature,
            enable_medial_axis=enable_medial_axis,
            default_depth=default_depth,
            tide_elements_per_wavelength=tide_elements_per_wavelength,
        )

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
