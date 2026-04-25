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

    def equals(self, other: "Mesh", *, atol: float = 1e-10, rtol: float = 0.0) -> bool:
        """Tolerance-aware equality check for round-trip tests.

        Implementation lands in T022.
        """
        raise NotImplementedError("Mesh.equals — implemented in T022")

    def __repr__(self) -> str:
        raise NotImplementedError("Mesh.__repr__ — implemented in T022")

    def __str__(self) -> str:
        raise NotImplementedError("Mesh.__str__ — implemented in T022")


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
# Free functions (skeletons — implementations land in T020 / T021).
# ---------------------------------------------------------------------------


def domain_from_polygon(
    rings: list[np.ndarray],
    *,
    pfix: np.ndarray | None = None,
    bc_segments: tuple[BoundarySegment, ...] = (),
) -> Domain:
    """Build a :class:`Domain` from a list of polygon rings.

    Implementation lands in T020.
    """
    raise NotImplementedError("domain_from_polygon — implemented in T020")


def domain_from_sdf(
    sdf: Callable[[np.ndarray], np.ndarray],
    bbox: tuple[float, float, float, float],
    *,
    pfix: np.ndarray | None = None,
    pts: np.ndarray | None = None,
    bc_segments: tuple[BoundarySegment, ...] = (),
) -> Domain:
    """Build a :class:`Domain` from an explicit SDF callable.

    Implementation lands in T020.
    """
    raise NotImplementedError("domain_from_sdf — implemented in T020")


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
    """Generate a triangular mesh on the given domain.

    Implementation lands in T021.
    """
    raise NotImplementedError("triangulate — implemented in T021")
