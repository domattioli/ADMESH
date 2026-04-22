"""Medial-axis distance on a rasterized 2D domain.

The medial axis of a domain ``Ω`` is the set of interior points
equidistant to two or more boundary points. For mesh-size grading
we need the *distance to the medial axis* at every interior cell —
it falls to zero on the skeleton and grows toward the boundary.

**Clean-room implementation** — the MATLAB source
(``05_Medial_Axis/{MedialAxisFunction,TriMedialAxisFunction,
medial_distance_FMM,heap}.m`` in the upstream repo) is not
accessible in this session's environment. This module uses SciPy's
Euclidean distance transform (`scipy.ndimage.distance_transform_edt`,
which solves the Eikonal equation with unit speed — equivalent to
the MATLAB FMM in the limit of fine grids). A faithful port
against MATLAB's heap-based FMM is deferred — see
``docs/PORTING_NOTES.md`` entry dated 2026-04-22.

Algorithm:

1. Rasterize the domain to a binary mask (``fd(p) < 0`` inside).
2. ``D_edt = distance_transform_edt(mask) * delta`` — L2 distance
   from each interior cell to the nearest boundary cell.
3. Medial-axis detection: cells where ``|∇D_edt| < 1 - ε``. True
   distance functions satisfy ``|∇D| = 1`` a.e., so the gradient
   drops below 1 precisely on the skeleton.
4. ``medial_dist = distance_transform_edt(~medial) * delta`` —
   L2 distance from each cell to the nearest medial-axis cell.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import distance_transform_edt

from admesh.distance import eval_sdf_grid

Points = NDArray[np.float64]
SDF = Callable[[Points], NDArray[np.float64]]

_GRAD_MEDIAL = 0.85
"""``|∇D_edt|`` threshold; cells below this are tagged medial-axis."""

_EDT_BUFFER = 1.5
"""Min ``D_edt / delta`` for a cell to be medial (keeps boundary-adjacent
cells out of the detection, where ``np.gradient`` one-sided differences
against outside-domain zeros produce spuriously small gradient magnitudes)."""


def _detect_medial(D_edt: NDArray[np.float64], delta: float) -> NDArray[np.bool_]:
    """Return a boolean mask of cells on the medial axis.

    A cell is medial iff (a) ``|∇D_edt| < _GRAD_MEDIAL`` and (b) it's
    strictly interior by at least ``_EDT_BUFFER * delta`` — true distance
    functions satisfy ``|∇D| = 1`` a.e. in the interior; the gradient
    threshold catches the skeleton. The buffer guards against the
    boundary staircase artifacts of the EDT rasterization.
    """
    gy, gx = np.gradient(D_edt, delta, delta)
    grad_mag = np.hypot(gx, gy)
    return (grad_mag < _GRAD_MEDIAL) & (D_edt > _EDT_BUFFER * delta)


def medial_distance_fmm(
    fd: SDF,
    bbox: tuple[float, float, float, float],
    delta: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Distance-to-medial-axis field on a rectangular grid.

    Returns ``(X, Y, med_dist)`` with shape ``(LY, LX)``.
    ``med_dist`` is ``NaN`` outside the domain (``fd(p) > 0``).
    """
    X, Y, D = eval_sdf_grid(fd, bbox, delta)
    inside = D < 0.0

    if not inside.any():
        return X, Y, np.full_like(D, np.nan)

    # EDT from the boundary into the interior.
    D_edt = distance_transform_edt(inside) * delta

    medial = _detect_medial(D_edt, delta) & inside

    # Pathological case: no medial-axis detected (e.g. grid too coarse
    # relative to h0). Fall back to the max-D cell as the "medial point".
    if not medial.any():
        idx = np.unravel_index(np.argmax(D_edt * inside), D_edt.shape)
        medial = np.zeros_like(inside)
        medial[idx] = True

    med_dist = distance_transform_edt(~medial) * delta
    med_dist = med_dist.astype(float)
    med_dist[~inside] = np.nan
    return X, Y, med_dist
