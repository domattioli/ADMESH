"""Curvature field of a 2D signed distance function.

For a signed distance function ``f``, the curvature of its level
sets is

    κ = ∇·(∇f / |∇f|)

For a distance function, ``|∇f| = 1`` almost everywhere, so this
reduces to ``κ = Δf`` (the Laplacian) except near the medial axis
where ``f`` loses smoothness.

**Clean-room implementation** — the MATLAB source
(``04_Curvature_Function/CurvatureFunction.m`` in the upstream
repo) is not accessible in this session's environment. This module
implements the textbook formula above with a 4th-order
finite-difference Laplacian on a rectangular grid, then masks cells
where ``|∇f|`` is small (medial-axis singularities). A faithful
port against the MATLAB source is deferred — see
``docs/PORTING_NOTES.md`` entry dated 2026-04-22.

Reference for the formulation: Osher & Fedkiw, *Level Set Methods
and Dynamic Implicit Surfaces* (Springer, 2003), §1.4.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
from numpy.typing import NDArray

from admesh.distance import eval_sdf_grid, grad_sdf

Points = NDArray[np.float64]
SDF = Callable[[Points], NDArray[np.float64]]

_GRAD_EPS = 1e-3
"""``|∇f|`` threshold below which κ is masked (NaN)."""


def curvature_grid(
    D: NDArray[np.float64],
    delta: float,
    grad_eps: float = _GRAD_EPS,
) -> NDArray[np.float64]:
    """Curvature of the level sets of a sampled SDF.

    Parameters
    ----------
    D : (LY, LX) ndarray
        Sampled signed distance function.
    delta : float
        Grid spacing (assumes square cells).
    grad_eps : float
        Threshold on ``|∇D|``; cells below this are masked ``NaN``.

    Returns
    -------
    kappa : (LY, LX) ndarray
        ``κ = ∇·(∇D / |∇D|)``, with ``NaN`` where ``|∇D| < grad_eps``.

    Notes
    -----
    For a *true* signed-distance function (``|∇D| ≡ 1``) the formula
    collapses to ``κ = ΔD``. We compute the full divergence form
    anyway because numerical SDFs drift from unit-gradient near the
    medial axis and at corners.
    """
    D = np.asarray(D, dtype=float)
    gx, gy = grad_sdf(D, delta)
    mag = np.hypot(gx, gy)
    mask = mag < grad_eps

    with np.errstate(divide="ignore", invalid="ignore"):
        nx = np.where(mask, 0.0, gx / mag)
        ny = np.where(mask, 0.0, gy / mag)

    # Divergence of (nx, ny) via the same 4th-order gradient utility.
    dnx_dx, _ = grad_sdf(nx, delta)
    _, dny_dy = grad_sdf(ny, delta)
    kappa = dnx_dx + dny_dy
    kappa[mask] = np.nan
    return kappa


def curvature_function(
    fd: SDF,
    bbox: tuple[float, float, float, float],
    delta: float,
    grad_eps: float = _GRAD_EPS,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Evaluate level-set curvature of an analytic SDF on a grid.

    Returns ``(X, Y, kappa)`` with shape ``(LY, LX)``.
    """
    X, Y, D = eval_sdf_grid(fd, bbox, delta)
    kappa = curvature_grid(D, delta, grad_eps=grad_eps)
    return X, Y, kappa
