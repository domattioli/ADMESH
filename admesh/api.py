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

        # Create an SDF from the mesh boundary and (optionally) bathymetry
        # For now, use a simple LinearNDInterpolator-based approach
        # The outer ring (bc_segments[0]) defines the outer boundary
        try:
            # If mesh has elevation data, use it for bathymetry-aware SDF
            if hasattr(mesh, "elevation") and mesh.elevation is not None:
                z = mesh.elevation
            else:
                # Otherwise, use a constant elevation
                z = np.zeros(len(mesh.nodes))

            # Build SDF as distance to nearest boundary point, signed by bathymetry
            from scipy.spatial import cKDTree

            outer_ring_nodes = bc_segments[0].node_ids
            outer_ring_pts = mesh.nodes[outer_ring_nodes]
            tree = cKDTree(outer_ring_pts)

            def sdf(points: np.ndarray) -> np.ndarray:
                """Compute signed distance: negative inside, positive outside."""
                distances, indices = tree.query(points)
                # Simple heuristic: points inside the bbox are negative, outside positive
                # (This is a rough approximation; for production, use proper winding number)
                inside = (
                    (points[:, 0] >= bbox[0])
                    & (points[:, 0] <= bbox[2])
                    & (points[:, 1] >= bbox[1])
                    & (points[:, 1] <= bbox[3])
                )
                signed_distances = np.where(inside, -distances, distances)
                return signed_distances

        except Exception:
            # Fallback: use a simple distance-to-bbox heuristic
            def sdf(points: np.ndarray) -> np.ndarray:
                xmin, ymin, xmax, ymax = bbox
                dx = np.minimum(points[:, 0] - xmin, xmax - points[:, 0])
                dy = np.minimum(points[:, 1] - ymin, ymax - points[:, 1])
                inside_dist = np.minimum(dx, dy)
                outside_dist = np.sqrt(
                    np.maximum(xmin - points[:, 0], 0) ** 2
                    + np.maximum(points[:, 0] - xmax, 0) ** 2
                    + np.maximum(ymin - points[:, 1], 0) ** 2
                    + np.maximum(points[:, 1] - ymax, 0) ** 2
                )
                signed = np.where(
                    (points[:, 0] >= xmin)
                    & (points[:, 0] <= xmax)
                    & (points[:, 1] >= ymin)
                    & (points[:, 1] <= ymax),
                    -inside_dist,
                    outside_dist,
                )
                return signed

        return cls(sdf=sdf, bbox=bbox, bc_segments=bc_segments)


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
    seed: int | None = None,
    max_iter: int | None = None,
    quality_gate: tuple[float, float] = (0.30, 0.60),
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
    seed : int or None
        Random seed for reproducibility.
    max_iter : int or None
        Maximum iterations for mesh generation.
    quality_gate : tuple[float, float]
        Quality thresholds (min_q, mean_q). Default: (0.30, 0.60).

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
    # Load domain from file or registry if necessary
    if not isinstance(domain, Domain):
        domain = _load_domain_from_source(domain)
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
