"""Curvature-driven mesh-size contribution.

Faithful port of ``01_ADMESH_Library/04_Curvature_Function/CurvatureFunction.m``
@ ``19b2eb9`` (reference clone at ``/workspace/QuADMesh-MATLAB``).

For a signed distance function ``f``, the curvature of its level
sets is

    κ = ∇·(∇f / |∇f|)

which reduces to ``κ = Δf`` when ``|∇f| = 1`` (true SDF). The
MATLAB formula composes κ into a size-field contribution:

    h_curve(I) = (1 + κ·|D|) / ((K/π)·κ) − g·D,   I = {|D| ≤ 2·hmin}
    h_curve outside I is set to hmax
    h_curve = clip(h_curve, hmin, hmax)
    h0 = min(h_curve, h0)

The ``1/((K/π)·κ)`` term gives the target edge length for ``K``
elements per radian of arc at local curvature ``κ``. The ``|D|/(K/π)``
term lets the size grow linearly with distance from the boundary.
The ``−g·D`` term embeds the grading slope ``g`` directly in the
narrow band, so the downstream Eikonal solver
(``MeshSizeIterativeSolver.c`` → :func:`admesh.mesh_size.solve_iter`)
only needs to polish the boundary band — cells beyond the band
already satisfy ``|∇h| ≤ g`` by construction.

Reference for the κ formulation: Osher & Fedkiw, *Level Set Methods
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
    """Curvature of the level sets of a sampled SDF: ``κ = ∇·(∇D/|∇D|)``.

    Parameters
    ----------
    D : (LY, LX) ndarray
        Sampled signed distance function.
    delta : float
        Grid spacing (assumes square cells).
    grad_eps : float
        Threshold on ``|∇D|``; cells below this are masked ``NaN``.
    """
    D = np.asarray(D, dtype=float)
    gx, gy = grad_sdf(D, delta)
    mag = np.hypot(gx, gy)
    mask = mag < grad_eps

    with np.errstate(divide="ignore", invalid="ignore"):
        nx = np.where(mask, 0.0, gx / mag)
        ny = np.where(mask, 0.0, gy / mag)

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

    Returns ``(X, Y, kappa)`` with shape ``(LY, LX)``. Thin wrapper
    around :func:`eval_sdf_grid` + :func:`curvature_grid`.
    """
    X, Y, D = eval_sdf_grid(fd, bbox, delta)
    kappa = curvature_grid(D, delta, grad_eps=grad_eps)
    return X, Y, kappa


def apply_curvature(
    h0: NDArray[np.float64],
    D: NDArray[np.float64],
    delta: float,
    *,
    K: float,
    g: float,
    hmax: float,
    hmin: float,
) -> NDArray[np.float64]:
    """Port of MATLAB ``CurvatureFunction.m`` — compose κ-driven size reduction.

    Applies the MATLAB size-reduction formula in the narrow band
    ``|D| ≤ 2·hmin``, clamps to ``[hmin, hmax]``, then composes via
    elementwise ``min`` with the input ``h0``.

    Parameters
    ----------
    h0 : (LY, LX) ndarray
        Existing size-field initial condition. Not mutated.
    D : (LY, LX) ndarray
        Signed distance field.
    delta : float
        Grid spacing.
    K : float
        Target number of elements per radian at local curvature ``κ``.
    g : float
        Grading slope.
    hmax, hmin : float
        Size-field bounds.

    Returns
    -------
    h0_new : (LY, LX) ndarray
        ``min(h_curve, h0)`` per MATLAB line 71.
    """
    # Magnitude + normalized direction of ∇D.
    gx, gy = grad_sdf(D, delta)
    m = np.hypot(gx, gy)
    with np.errstate(divide="ignore", invalid="ignore"):
        nx = np.where(m > 0, gx / m, 0.0)
        ny = np.where(m > 0, gy / m, 0.0)

    # MATLAB: kappa = abs(divergence(X, Y, gradD.x./m, gradD.y./m))
    # Our ``grad_sdf`` is 4th-order central; MATLAB ``divergence`` is
    # 2nd-order central. Algorithmic substitution noted in PORTING_NOTES.
    dnx_dx, _ = grad_sdf(nx, delta)
    _, dny_dy = grad_sdf(ny, delta)
    kappa = np.abs(dnx_dx + dny_dy)

    # Narrow band: |D| <= 2*hmin (MATLAB line 53).
    I = np.abs(D) <= 2.0 * hmin

    # Default h_curve = hmax everywhere (MATLAB line 56).
    h_curve = np.full_like(D, hmax)

    # K / pi — elements per radian (MATLAB line 59).
    K_over_pi = K / np.pi

    # The formula (MATLAB line 64): avoid division by zero on flat
    # segments (κ ≈ 0 ⇒ 1/κ blows up; fall back to hmax there).
    kappa_I = kappa[I]
    D_I = D[I]
    safe = kappa_I > 1e-12
    h_band = np.full_like(kappa_I, hmax)
    with np.errstate(divide="ignore", invalid="ignore"):
        h_band[safe] = (
            np.abs(
                (1.0 + kappa_I[safe] * np.abs(D_I[safe]))
                / (K_over_pi * kappa_I[safe])
            )
            - g * D_I[safe]
        )
    h_curve[I] = h_band

    # Clamp (MATLAB lines 67-68).
    h_curve = np.clip(h_curve, hmin, hmax)

    # Compose (MATLAB line 71).
    return np.minimum(h_curve, h0)
