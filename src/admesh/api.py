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

    def to_msh(self, path: "str | os.PathLike[str] | TextIO") -> None:
        """Serialize this mesh to Gmsh ASCII v2.2 (``admesh.gmsh.write_msh``)."""
        from admesh.gmsh import write_msh

        write_msh(self, path)

    def plot(self, ax=None, **kwargs):
        """Draw the mesh wireframe via chilmesh.

        Delegates to ``admesh.viz.plot_mesh`` → ``chilmesh.CHILmesh.plot``.

        Raises
        ------
        ImportError
            If chilmesh is not installed. Install with
            ``pip install admesh2D[viz]``.
        """
        from admesh.viz import plot_mesh

        return plot_mesh(self, ax=ax, **kwargs)

    def plot_quality(self, ax=None, cmap="cool", **kwargs):
        """Colormap elements by shape quality via chilmesh.

        Delegates to ``admesh.viz.plot_mesh_quality`` →
        ``chilmesh.CHILmesh.plot_quality``.

        Raises
        ------
        ImportError
            If chilmesh is not installed. Install with
            ``pip install admesh2D[viz]``.
        """
        from admesh.viz import plot_mesh_quality

        return plot_mesh_quality(self, ax=ax, cmap=cmap, **kwargs)

    def plot_layers(self, ax=None, cmap="viridis", **kwargs):
        """Color mesh elements by onion-peel layer via chilmesh.

        Delegates to ``admesh.viz.plot_mesh_layers`` →
        ``chilmesh.CHILmesh.plot_layer``.

        Raises
        ------
        ImportError
            If chilmesh is not installed. Install with
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
    bathymetry
        Optional callable for bathymetric elevation sampling;
        used by the default size-field stack.
    """

    sdf: Callable[[np.ndarray], np.ndarray]
    bbox: tuple[float, float, float, float]
    pfix: np.ndarray | None = None
    pts: np.ndarray | None = None
    bc_segments: tuple[BoundarySegment, ...] = ()
    bathymetry: Callable[[np.ndarray], np.ndarray] | None = field(default=None, compare=False)

    @classmethod
    def from_mesh(cls, mesh: "Mesh") -> "Domain":
        """Recover a multiply-connected domain from a mesh.

        Extracts the boundary rings from the mesh, identifies the outer ring
        (by signed area), and constructs a Domain suitable for re-triangulation.

        Parameters
        ----------
        mesh : Mesh
            Source mesh with nodes and elements.

        Returns
        -------
        Domain
            Domain with SDF derived from mesh boundary and interior bathymetry
            (if available), and bc_segments recovered from the mesh boundary.
        """
        from scipy.interpolate import LinearNDInterpolator

        # Extract boundary segments (rings) from the mesh
        bc_segments = _derive_boundary_segments(mesh.elements, mesh.nodes)
        if not bc_segments:
            raise ValueError("Mesh has no boundary (is it fully 2D connected?)")

        # Compute domain bbox from all nodes
        bbox = (
            float(mesh.nodes[:, 0].min()),
            float(mesh.nodes[:, 1].min()),
            float(mesh.nodes[:, 0].max()),
            float(mesh.nodes[:, 1].max()),
        )

        # Build SDF using:
        #  1. Dense-sampled boundary polyline for accurate distance (fixes #38 gradient spikes)
        #  2. in_polygon winding test for correct sign — enabled by the junction-aware ring
        #     walk in _derive_boundary_segments which now produces closed rings even for
        #     real-world ADCIRC meshes with pinch-point boundary nodes.
        from scipy.spatial import cKDTree
        from admesh._stages.in_polygon import in_polygon as _in_polygon

        outer_ring_nodes = bc_segments[0].node_ids
        outer_ring_pts = mesh.nodes[outer_ring_nodes]
        hole_rings_pts = [mesh.nodes[seg.node_ids] for seg in bc_segments[1:]]

        diag = float(np.hypot(bbox[2] - bbox[0], bbox[3] - bbox[1]))
        h_samp = max(diag / 500, 1e-8)

        def _dense_sample_ring(ring_pts: np.ndarray, h: float) -> np.ndarray:
            segs = []
            n = len(ring_pts)
            for i in range(n):
                a = ring_pts[i]
                b = ring_pts[(i + 1) % n]
                seg_len = float(np.linalg.norm(b - a))
                n_samp = max(2, int(np.ceil(seg_len / h)))
                ts = np.linspace(0.0, 1.0, n_samp)[:-1]
                segs.append(a + ts[:, None] * (b - a))
            return np.vstack(segs) if segs else ring_pts

        dense_parts = [_dense_sample_ring(outer_ring_pts, h_samp)]
        for hr in hole_rings_pts:
            dense_parts.append(_dense_sample_ring(hr, h_samp))
        tree = cKDTree(np.vstack(dense_parts))

        def sdf(points: np.ndarray) -> np.ndarray:
            distances, _ = tree.query(points)
            in_outer, _ = _in_polygon(
                points[:, 0], points[:, 1],
                outer_ring_pts[:, 0], outer_ring_pts[:, 1],
            )
            in_hole = np.zeros(len(points), dtype=bool)
            for hr in hole_rings_pts:
                ih, _ = _in_polygon(
                    points[:, 0], points[:, 1],
                    hr[:, 0], hr[:, 1],
                )
                in_hole |= ih
            inside = in_outer & ~in_hole
            return np.where(inside, -distances, distances)

        if getattr(mesh, "bathymetry", None) is not None:
            from scipy.interpolate import NearestNDInterpolator
            bathy_interp = NearestNDInterpolator(
                mesh.nodes,
                mesh.bathymetry,
                rescale=False,
            )
        else:
            bathy_interp = None

        return cls(sdf=sdf, bbox=bbox, bc_segments=bc_segments, bathymetry=bathy_interp)


# ---------------------------------------------------------------------------
# Boundary seeding helper (issue #2).
# ---------------------------------------------------------------------------


def _seed_boundary_1d(
    pts: np.ndarray,
    fh: "Callable[[np.ndarray], np.ndarray] | None",
    h0: float,
) -> np.ndarray:
    """Sample a closed boundary polygon at adaptive spacing.

    For each edge ``pts[i] -> pts[(i+1) % n]``, inserts intermediate points
    at spacing ``fh(midpoint)`` (or ``h0`` when ``fh`` is None).  The
    interior samples become extra ``pfix`` entries so that short boundary
    segments — e.g. the notch walls in ``NOTCHED_RECTANGLE`` — are seeded
    with enough nodes even when the 2-D lattice is coarse.

    Endpoints are excluded from the returned array (they should already be
    in ``domain.pfix``).
    """
    seeds: list[np.ndarray] = []
    n = len(pts)
    for i in range(n):
        p0 = pts[i]
        p1 = pts[(i + 1) % n]
        edge_vec = p1 - p0
        edge_len = float(np.linalg.norm(edge_vec))
        if edge_len < 1e-14:
            continue
        midpoint = (p0 + p1) / 2.0
        h_edge = float(fh(midpoint[None, :])[0]) if fh is not None else h0
        h_edge = max(h_edge, h0 * 0.1)
        n_interior = max(int(np.floor(edge_len / h_edge)) - 1, 0)
        if n_interior > 0:
            ts = np.linspace(0.0, 1.0, n_interior + 2)[1:-1]
            seeds.append(p0[None, :] + ts[:, None] * edge_vec[None, :])
    return np.vstack(seeds) if seeds else np.empty((0, 2), dtype=np.float64)


# ---------------------------------------------------------------------------
# Boundary derivation helper.
# ---------------------------------------------------------------------------


def _ring_area(ring: list[int], nodes: np.ndarray) -> float:
    """Compute signed area of a ring using the shoelace formula.

    Parameters
    ----------
    ring : list[int]
        Ordered node indices forming a closed boundary.
    nodes : (N, 2) ndarray
        Mesh node coordinates.

    Returns
    -------
    float
        Absolute signed area of the polygon. Larger values indicate larger rings.
        Used to distinguish outer rings (larger area) from holes (smaller areas).
    """
    if len(ring) < 3:
        return 0.0
    pts = nodes[ring]
    x = pts[:, 0]
    y = pts[:, 1]
    # Shoelace formula: A = 0.5 * |sum(x_i * y_{i+1} - x_{i+1} * y_i)|
    signed_area = 0.5 * abs(np.sum(x[:-1] * y[1:] - x[1:] * y[:-1]) + x[-1] * y[0] - x[0] * y[-1])
    return float(signed_area)


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

    # Build a directed-edge adjacency restricted to boundary edges.
    # Use a list per node so junction nodes (where ≥2 boundary rings
    # share a vertex, e.g. where open-ocean meets land boundary in ADCIRC
    # meshes) don't silently overwrite each other.
    next_nodes: dict[int, list[int]] = {}
    for u, vs in directed.items():
        for v in vs:
            key = (u, v) if u < v else (v, u)
            if key in boundary_edges:
                next_nodes.setdefault(u, []).append(v)

    def _pick_next(cur: int, prev: int | None, candidates: list[int]) -> int | None:
        """At junction nodes pick the successor that turns most left.

        For non-junction nodes (len==1) just returns the single candidate.
        For junctions, uses the signed angle of the turn prev→cur→cand to
        select the leftmost (counter-clockwise) continuation, keeping each
        ring consistently oriented.
        """
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        if prev is None:
            return candidates[0]
        p_prev = nodes[prev]
        p_cur = nodes[cur]
        v_in = p_cur - p_prev
        best, best_angle = None, float("inf")
        for c in candidates:
            v_out = nodes[c] - p_cur
            angle = float(np.arctan2(
                v_in[0] * v_out[1] - v_in[1] * v_out[0],
                v_in[0] * v_out[0] + v_in[1] * v_out[1],
            ))
            if angle < best_angle:
                best_angle, best = angle, c
        return best

    # Walk rings, tracking both visited nodes and used directed edges so a
    # shared junction node doesn't block a second ring from starting there.
    used_edges: set[tuple[int, int]] = set()
    visited: set[int] = set()
    rings: list[list[int]] = []
    for start in sorted(next_nodes):
        # Try each outgoing edge from start as a potential ring entry.
        for first_step in list(next_nodes.get(start, [])):
            if (start, first_step) in used_edges:
                continue
            ring = [start]
            prev, cur = start, first_step
            used_edges.add((start, first_step))
            guard = len(next_nodes) + 2
            while cur != start and guard > 0:
                ring.append(cur)
                candidates = [
                    v for v in next_nodes.get(cur, [])
                    if (cur, v) not in used_edges
                ]
                nxt = _pick_next(cur, prev, candidates)
                if nxt is None:
                    break
                used_edges.add((cur, nxt))
                prev, cur = cur, nxt
                guard -= 1
            if cur == start and len(ring) >= 3:
                rings.append(ring)
                visited.update(ring)

    # Order rings by signed area, largest first — the outer ring of a
    # multiply-connected polygon always has the largest area, independent of
    # node sampling. This fixes issue #11 where internal coastlines with more
    # nodes than the outer ocean ring were incorrectly identified as the outer.
    rings.sort(key=lambda ring: _ring_area(ring, nodes), reverse=True)
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


def _load_domain_from_source(source: str | "os.PathLike[str]") -> Domain:
    """Load domain from file or registry.

    Parameters
    ----------
    source : str or os.PathLike
        File path or mesh_id string (from ADMESH-Domains registry).

    Returns
    -------
    Domain
        Loaded domain ready for triangulation.
    """
    import os
    from pathlib import Path

    source_str = str(source)
    is_path = (
        isinstance(source, os.PathLike)
        or ("/" in source_str or "\\" in source_str)
        or any(source_str.endswith(ext) for ext in [".toml", ".json", ".14", ".grd"])
    )

    if not is_path:
        # Try registry first
        try:
            from admesh.registry import load_domain_from_registry
            return load_domain_from_registry(source_str)
        except ImportError:
            pass

    # Load as file
    from admesh.loaders import (
        load_domain_from_fort14,
        load_domain_from_json,
        load_domain_from_toml,
    )

    path = Path(source)
    if not path.exists():
        raise ValueError(f"Domain file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".toml":
        return load_domain_from_toml(path)
    elif suffix in [".14", ".grd"]:
        return load_domain_from_fort14(path)
    elif suffix == ".json":
        return load_domain_from_json(path)
    else:
        raise ValueError(
            f"Unknown domain file format: {suffix}. Supported: .toml, .14, .grd, .json"
        )


def triangulate(
    domain: Domain | str | "os.PathLike[str]",
    *,
    h_max: float | None = None,
    h_min: float | None = None,
    size_field: Callable[[np.ndarray], np.ndarray] | None = None,
    user_contribs: tuple[Callable[[np.ndarray], np.ndarray], ...] = (),
    combine: Callable[[list[np.ndarray]], np.ndarray] = np.minimum.reduce,
    background: str = "uniform",
    seed: int | None = None,
    max_iter: int | None = None,
    initial_points: "np.ndarray | None" = None,
    # Advisory default, NOT a binding invariant (CONSTITUTION Article V.5, #140):
    # (0.30, 0.60) is an MVP port-sanity smoke floor, caller-overridable. Mesh
    # quality is hyperparameter-driven (h_min/h_max/g); aggressive ratios
    # legitimately lower min quality. Pass (0.0, 0.0) to disable the gate.
    quality_gate: tuple[float, float] = (0.30, 0.60),
    ttol: float | None = None,
    dptol: float | None = None,
) -> Mesh:
    """Generate a triangular mesh on ``domain``.

    Parameters
    ----------
    domain : Domain, str, or os.PathLike
        Domain object, file path (TOML/JSON/fort.14), or mesh_id string
        (from ADMESH-Domains registry if installed).
    h_max : float or None
        Target maximum edge length. If None, defaults to bbox_diagonal / 20.
    h_min : float or None
        Minimum edge length for size field composition.
    size_field : callable or None
        Pre-composed size field function.
    user_contribs : tuple of callables
        User-defined size field contributions.
    combine : callable
        Function to combine multiple size fields (default: np.minimum.reduce).
    background : str
        Background grid strategy: 'uniform' (default) or 'octree' (adaptive
        octree-backed size field from spec-029).
    seed : int or None
        Random seed for reproducibility.
    max_iter : int or None
        Maximum iterations for mesh generation.
    quality_gate : tuple[float, float]
        Advisory (min_q, mean_q) smoke thresholds. Default: (0.30, 0.60) —
        an MVP port-sanity floor, NOT a binding quality invariant
        (CONSTITUTION Article V.5). Quality is driven by h_min/h_max/g;
        pass (0.0, 0.0) to disable the gate when knobs lower min quality.
    ttol : float or None
        Relative displacement threshold for Delaunay rebuild. Default: 0.27.
    dptol : float or None
        Interior node movement tolerance for convergence. Default: 2e-3.

    Returns
    -------
    Mesh
        Triangulated mesh with quality metrics and boundaries.

    Raises
    ------
    ValueError
        If domain source cannot be resolved or quality gates fail.
    ImportError
        If registry lookup is attempted without admesh-domains installed.

    Adapts the v1 :class:`Domain` onto the faithful-port driver
    :func:`admesh.routine.triangulate` without modifying it (Constitution
    Principle I). Returns a :class:`Mesh` with per-element quality
    populated and boundaries derived from the triangulation.
    """
    # Lazy imports — keeps `import admesh` cheap and avoids a hard
    # dependency cycle with the faithful-port modules at import time.
    from admesh._stages.domains import Domain as _PortDomain
    from admesh._stages.quality import mesh_quality
    from admesh._stages.routine import triangulate as _routine_triangulate

    # Load domain from file or registry if it's a string; adapt if it's a port Domain.
    api_domain = None  # Track whether we have an api.Domain (may have bc_segments)
    if isinstance(domain, _PortDomain):
        # Input is already a faithful-port Domain; use it directly.
        port_domain = domain
        bbox = domain.bbox
        h0_default = max(_bbox_diag(bbox) / 20.0, 1e-6)
        h0 = float(h_max) if h_max is not None else h0_default
        pfix = np.asarray(domain.fixed_points, dtype=np.float64) if domain.fixed_points is not None else np.empty((0, 2), dtype=np.float64)
    else:
        # Input should be an api.Domain or a file/registry path
        if not isinstance(domain, Domain):
            domain = _load_domain_from_source(domain)

        api_domain = domain  # Track the api.Domain for bc_segments access later
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
    if ttol is not None:
        opts["ttol"] = float(ttol)
    if dptol is not None:
        opts["dptol"] = float(dptol)
    if initial_points is not None:
        opts["initial_points"] = np.asarray(initial_points, dtype=np.float64)

    # Resolve the size field. Cases:
    #
    #   1. Caller passed a pre-composed `size_field=`. They've already
    #      done their own composition; we use it as-is. If they ALSO
    #      passed `user_contribs=` we warn — those would be ignored
    #      otherwise, which silently violates the contract.
    #   2. Caller passed `user_contribs=`. Wrap them via
    #      `compose_size_field` with `size_field` (if any) as the sole
    #      Phase-1 builtin. Default combiner is `np.minimum.reduce`.
    #   3. Caller passed h_min or h_max but no user_contribs — auto-create
    #      a uniform clamping size field so the bounds are not silently ignored.
    #   4. Neither — uniform sizing falls through (`fh=None`).
    if size_field is not None and user_contribs:
        warnings.warn(
            "triangulate: both `size_field` and `user_contribs` were "
            "supplied; ignoring `user_contribs` (the pre-composed "
            "`size_field` already encodes its own composition).",
            UserWarning,
            stacklevel=2,
        )
        fh = size_field
    elif user_contribs or h_min is not None or h_max is not None:
        from admesh.size_field import compose_size_field

        # Build Phase-1 builtins: include size_field if provided
        builtins_phase1 = (size_field,) if size_field is not None else ()

        # Build Phase-2 user contributions
        user_phase2 = tuple(user_contribs)

        # If h_min/h_max specified without other size fields, create a bounded field.
        # NOTE (#65 / spec 025 Step 3 DEFERRED): wiring build_h() here as the
        # unconditional default degrades MVP convex-domain min_q 0.30 -> 0.22
        # (curvature+medial size-gradient -> low-quality distmesh transition
        # tris), violating the constitutional MVP quality gate + spec 025
        # AC-005/AC-006. Deferred pending operator decision (make conditional on
        # domain features / tune scales / revise gate). Steps 1+2 (Domain.bathymetry
        # + from_mesh extraction) shipped — additive, no behavior change.
        if not builtins_phase1 and not user_phase2:
            # Create a clamping size field directly to avoid warning noise.
            def _clamped_uniform(pts):
                pts_arr = np.asarray(pts, dtype=np.float64)
                n = pts_arr.shape[0]
                # Return uniform field, already clamped to [h_min, h_max]
                result = np.full(n, h_max if h_max is not None else h_min or 1.0, dtype=np.float64)
                if h_min is not None and h_max is not None:
                    result[:] = h_max  # Use h_max as the target (conservative for refinement)
                return result
            user_phase2 = (_clamped_uniform,)

        fh = compose_size_field(
            builtins=builtins_phase1,
            user_contribs=user_phase2,
            combine=combine,
            hmin=h_min,
            hmax=h_max,
        )
    elif size_field is None and (h_min is not None or h_max is not None):
        # Fix #37: h_min/h_max were silently ignored when no user_contribs
        # provided. Auto-compose a uniform field that clamps to [h_min, h_max].
        from admesh.size_field import compose_size_field

        _h_max_val = h_max if h_max is not None else h0
        _uniform = lambda pts: np.full(len(pts), _h_max_val, dtype=float)  # noqa: E731
        fh = compose_size_field(
            builtins=(_uniform,),
            user_contribs=(),
            combine=combine,
            hmin=h_min,
            hmax=h_max,
        )
    else:
        fh = size_field  # may still be None — uniform sizing

    if background == "octree":
        from admesh.octree import octree_size_field
        _bbox = port_domain.bbox
        _hmax_o = float(h_max) if h_max is not None else h0
        _hmin_o = float(h_min) if h_min is not None else _hmax_o / 100.0
        _base = fh if fh is not None else (
            lambda pts: np.full(len(np.atleast_2d(pts)), _hmax_o, dtype=float))
        class _BBoxShim:
            bbox = _bbox
        fh = octree_size_field(_BBoxShim, _base, h_min=_hmin_o, h_max=_hmax_o)
    elif background != "uniform":
        raise ValueError(f"triangulate: background must be 'uniform' or 'octree', got {background!r}")

    # Issue #2: if the domain carries explicit boundary vertices (pts), seed
    # intermediate points along each edge so short boundary segments get
    # adequate coverage even when the 2-D lattice is coarse.
    # Use getattr because admesh.domains.Domain (MVP class) lacks `pts`.
    _pts = getattr(domain, "pts", None)
    domain_pts = _pts if _pts is not None else getattr(domain, "boundary_polygon", None)
    if domain_pts is not None:
        boundary_seeds = _seed_boundary_1d(
            np.asarray(domain_pts, dtype=np.float64), fh, h0
        )
        if boundary_seeds.size:
            pfix = (
                np.vstack([pfix, boundary_seeds]) if pfix.size else boundary_seeds
            )
            # _PortDomain uses `fd`; api.Domain uses `sdf` — handle both.
            _sdf = getattr(domain, "sdf", None) or getattr(domain, "fd", None)
            port_domain = _PortDomain(
                name="api_v1",
                fd=_sdf,
                bbox=domain.bbox,
                fixed_points=pfix,
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
    if api_domain and api_domain.bc_segments:
        boundaries = tuple(api_domain.bc_segments)
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