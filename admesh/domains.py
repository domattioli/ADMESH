"""Test-domain registry for the MVP triangulation goal.

Each domain is a signed distance function (SDF) ``fd(p) -> d``:
``d < 0`` inside, ``d > 0`` outside, ``d = 0`` on the boundary.
Callers pass ``p`` as an ``(N, 2)`` array of (x, y) points.

These are NOT a port — they're new infrastructure for the Python MVP.
The 5 domains mirror the MVP acceptance set declared in
``PROJECT_PLAN.md``:

- ``unit_square``       — axis-aligned square, trivial sanity
- ``l_shape``           — non-convex re-entrant corner
- ``unit_disk``         — smooth curved boundary
- ``annulus``           — doubly-connected topology
- ``notched_rectangle`` — tight pinch / keyhole stress test
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from numpy.typing import ArrayLike, NDArray

Points = NDArray[np.float64]
SDF = Callable[[Points], NDArray[np.float64]]


@dataclass(frozen=True)
class Domain:
    """A 2D domain described by a signed distance function."""

    name: str
    fd: SDF
    bbox: tuple[float, float, float, float]
    """(xmin, ymin, xmax, ymax) — loose axis-aligned bounding box."""
    fixed_points: NDArray[np.float64] = field(
        default_factory=lambda: np.empty((0, 2), dtype=float)
    )
    """Points pinned into the mesh (e.g. reentrant corners)."""

    def __call__(self, p: ArrayLike) -> NDArray[np.float64]:
        p = np.asarray(p, dtype=float)
        if p.ndim == 1:
            p = p[None, :]
        return self.fd(p)


def _sdf_unit_square(p: Points) -> NDArray[np.float64]:
    return np.maximum(np.abs(p[:, 0]), np.abs(p[:, 1])) - 0.5


def _sdf_unit_disk(p: Points) -> NDArray[np.float64]:
    return np.hypot(p[:, 0], p[:, 1]) - 1.0


def _sdf_annulus(p: Points, inner: float = 0.4, outer: float = 1.0) -> NDArray[np.float64]:
    r = np.hypot(p[:, 0], p[:, 1])
    return np.maximum(r - outer, inner - r)


def _sdf_l_shape(p: Points) -> NDArray[np.float64]:
    """L = [-1, 1]^2 minus the open top-right quadrant (0, 1] x (0, 1]."""
    d_outer = np.maximum(np.abs(p[:, 0]), np.abs(p[:, 1])) - 1.0
    # d_notch < 0 iff the point is strictly in the top-right quadrant.
    d_notch = np.maximum(-p[:, 0], -p[:, 1])
    return np.maximum(d_outer, -d_notch)


def _sdf_notched_rectangle(
    p: Points,
    outer_half: tuple[float, float] = (1.0, 0.5),
    notch_half: tuple[float, float] = (0.05, 0.25),
) -> NDArray[np.float64]:
    """Rectangle minus a thin vertical notch centered on the top edge.

    Creates a tight pinch; stress test for the pipeline.
    """
    ox, oy = outer_half
    nx, ny = notch_half
    d_rect = np.maximum(np.abs(p[:, 0]) - ox, np.abs(p[:, 1]) - oy)
    d_notch = np.maximum(np.abs(p[:, 0]) - nx, np.abs(p[:, 1] - oy) - ny)
    return np.maximum(d_rect, -d_notch)


UNIT_SQUARE = Domain(
    name="unit_square",
    fd=_sdf_unit_square,
    bbox=(-0.5, -0.5, 0.5, 0.5),
    fixed_points=np.array(
        [[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]], dtype=float
    ),
)

L_SHAPE = Domain(
    name="l_shape",
    fd=_sdf_l_shape,
    bbox=(-1.0, -1.0, 1.0, 1.0),
    fixed_points=np.array(
        [[-1, -1], [1, -1], [1, 0], [0, 0], [0, 1], [-1, 1]], dtype=float
    ),
)

UNIT_DISK = Domain(
    name="unit_disk",
    fd=_sdf_unit_disk,
    bbox=(-1.0, -1.0, 1.0, 1.0),
)

ANNULUS = Domain(
    name="annulus",
    fd=_sdf_annulus,
    bbox=(-1.0, -1.0, 1.0, 1.0),
)

NOTCHED_RECTANGLE = Domain(
    name="notched_rectangle",
    fd=_sdf_notched_rectangle,
    bbox=(-1.0, -0.5, 1.0, 0.5),
    fixed_points=np.array(
        [
            [-1, -0.5], [1, -0.5], [1, 0.5], [0.05, 0.5], [0.05, 0.0],
            [-0.05, 0.0], [-0.05, 0.5], [-1, 0.5],
        ],
        dtype=float,
    ),
)


ALL: dict[str, Domain] = {
    d.name: d
    for d in (UNIT_SQUARE, L_SHAPE, UNIT_DISK, ANNULUS, NOTCHED_RECTANGLE)
}
