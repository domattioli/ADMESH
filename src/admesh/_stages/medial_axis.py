"""Medial-axis-driven mesh-size contribution.

Faithful port of ``01_ADMESH_Library/05_Medial_Axis/MedialAxisFunction.m``
+ helpers @ ``19b2eb9`` (reference clone at ``/workspace/QuADMesh-MATLAB``).

Pipeline (MATLAB ``MedialAxisFunction.m``):

1. Average Outward Flux (AOF) — for each interior cell, sum the 8
   unit-vector ⋅ ∇D dot products from 8 surrounding neighbors; divide
   by 8. Medial axis = cells with ``AOF > 0.15``.
2. Restrict to interior (``D ≤ 0``).
3. Morphological skeletonize (MATLAB ``bwmorph(MA, 'skel', inf)``).
   The skeletonize is Zhang-Suen iterative thinning — a scipy
   substitution for MATLAB's Lantuéjoul iteration. Equivalent
   1-pixel skeleton up to boundary-order symmetry. See PORTING_NOTES.
4. Remove isolated pixels (MATLAB ``bwmorph(MA, 'clean', inf)``) —
   pixels with zero 8-connected neighbors.
5. ``MAD = distance_transform_edt(~MA) * delta`` — distance to
   medial axis (MATLAB uses ``bwdist`` × grid spacing).
6. ``LFS = |D| + |MAD|``; ``h_lfs = LFS / R``, clamped to
   ``[hmin, hmax]``; ``h0 = min(h_lfs, h0)``.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import distance_transform_edt

from admesh._stages.distance import eval_sdf_grid, grad_sdf

Points = NDArray[np.float64]
SDF = Callable[[Points], NDArray[np.float64]]

_AOF_THRESHOLD = 0.15
"""MATLAB MedialAxisFunction.m line 47."""


def _average_outward_flux(
    gx: NDArray[np.float64],
    gy: NDArray[np.float64],
    delta: float,
) -> NDArray[np.float64]:
    """Port of the 8-neighbor AOF computation in MATLAB lines 53-76.

    For each interior cell ``(j, i)`` we sum ``û · ∇D(neighbor)``
    over 8 neighbor directions (4 cardinal + 4 diagonal), where
    ``û`` is the unit vector from cell center to neighbor. Result is
    divided by 8. Cells that "look outward" (gradient points away
    from the cell — i.e. cell is on the medial axis) give AOF > 0.

    Simplified vectorization of MATLAB's explicit 6-term sum per
    axis (the MATLAB source writes out inner_productx from 3
    left/right and 3 vertical-tilted directions per side — the
    6 terms per axis cover the 8 compass directions with each
    diagonal counted twice via its x and y projection). We
    reproduce the exact same sum.
    """
    LY, LX = gx.shape
    # Unit-direction contributions to the sum, pre-computed.
    # MATLAB terms (inner_productx at interior cell [j,i]):
    #   +  (X[j,i-1]-X[j,i]) / sqrt((dx)^2 + dy^2)  · gradD.x[j,i-1]
    #     (left-down diagonal pointing left)
    #   +  (X[j,i+1]-X[j,i]) / sqrt(dx^2 + dy^2)    · gradD.x[j,i+1]
    #     (right-up diagonal pointing right)
    #   +  (X[j,i+1]-X[j,i]) / sqrt(dx^2)           · gradD.x[j,i+1]
    #     (cardinal right)
    #   +  (X[j,i+1]-X[j,i]) / sqrt(dx^2 + dy^2)    · gradD.x[j,i+1]
    #     (right-down diagonal pointing right)
    #   +  (X[j,i-1]-X[j,i]) / sqrt(dx^2 + dy^2)    · gradD.x[j,i-1]
    #     (left-up diagonal pointing left)
    #   +  (X[j,i-1]-X[j,i]) / sqrt(dx^2)           · gradD.x[j,i-1]
    #     (cardinal left)
    #
    # On a uniform grid with delta=dx=dy:
    #   (X[j,i+1]-X[j,i])/sqrt(2*delta^2) = +delta/(delta*sqrt(2)) = +1/sqrt(2)
    #   (X[j,i+1]-X[j,i])/sqrt(delta^2)   = +1
    # The 6 terms per axis reduce to 3 coefficients per neighbor
    # column (left/right) — two diagonals and one cardinal.
    inv_sq2 = 1.0 / np.sqrt(2.0)

    left_coef_x  = -1.0 - 2.0 * inv_sq2   # 2 diagonals + 1 cardinal left
    right_coef_x = +1.0 + 2.0 * inv_sq2   # 2 diagonals + 1 cardinal right
    down_coef_y  = -1.0 - 2.0 * inv_sq2
    up_coef_y    = +1.0 + 2.0 * inv_sq2

    aof = np.zeros_like(gx)
    j = slice(1, LY - 1)
    i = slice(1, LX - 1)
    aof[j, i] = (
        left_coef_x * gx[j, 0:LX - 2]     # gx at left neighbor
        + right_coef_x * gx[j, 2:LX]      # gx at right neighbor
        + down_coef_y * gy[0:LY - 2, i]   # gy at top-row-neighbor (j-1)
        + up_coef_y * gy[2:LY, i]         # gy at bottom-row-neighbor (j+1)
    ) / 8.0
    return aof


def _skeletonize_zhang_suen(mask: NDArray[np.bool_]) -> NDArray[np.bool_]:
    """Iterative morphological skeletonization (Zhang-Suen 1984, vectorized).

    MATLAB ``bwmorph(MA, 'skel', inf)`` uses Lantuéjoul's iteration;
    Zhang-Suen produces an equivalent 1-pixel skeleton with the same
    preservation semantics. Algorithmic substitution flagged in
    ``docs/PORTING_NOTES.md``.
    """
    img = mask.astype(np.uint8).copy()
    LY, LX = img.shape

    def _step(img, sub_iter: int) -> tuple[np.ndarray, bool]:
        """One Zhang-Suen sub-iteration, fully vectorized.

        sub_iter=1: delete (p2*p4*p6==0) and (p4*p6*p8==0)
        sub_iter=2: delete (p2*p4*p8==0) and (p2*p6*p8==0)
        """
        # Pad to keep interior-only operations at the same shape.
        a = img
        p2 = a[:-2, 1:-1]   # N
        p3 = a[:-2, 2:]     # NE
        p4 = a[1:-1, 2:]    # E
        p5 = a[2:, 2:]      # SE
        p6 = a[2:, 1:-1]    # S
        p7 = a[2:, :-2]     # SW
        p8 = a[1:-1, :-2]   # W
        p9 = a[:-2, :-2]    # NW
        B = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
        # A = # of 0→1 transitions in (p2,p3,p4,p5,p6,p7,p8,p9,p2)
        seq = np.stack([p2, p3, p4, p5, p6, p7, p8, p9], axis=-1)
        seq_next = np.roll(seq, -1, axis=-1)
        A = np.sum((seq == 0) & (seq_next == 1), axis=-1)
        cond_B = (B >= 2) & (B <= 6)
        cond_A = A == 1
        if sub_iter == 1:
            cond_c = (p2 * p4 * p6) == 0
            cond_d = (p4 * p6 * p8) == 0
        else:
            cond_c = (p2 * p4 * p8) == 0
            cond_d = (p2 * p6 * p8) == 0
        is_one = a[1:-1, 1:-1] == 1
        remove = is_one & cond_B & cond_A & cond_c & cond_d
        if not remove.any():
            return img, False
        new = img.copy()
        new[1:-1, 1:-1][remove] = 0
        return new, True

    while True:
        img, c1 = _step(img, 1)
        img, c2 = _step(img, 2)
        if not (c1 or c2):
            break
    return img.astype(bool)


def _remove_isolated(mask: NDArray[np.bool_]) -> NDArray[np.bool_]:
    """Drop pixels with zero 8-connected neighbors.

    Port of MATLAB ``bwmorph(MA, 'clean', inf)``.
    """
    from scipy.signal import convolve2d
    k = np.ones((3, 3), dtype=int)
    k[1, 1] = 0
    neigh = convolve2d(mask.astype(int), k, mode="same", boundary="fill", fillvalue=0)
    return mask & (neigh > 0)


def medial_axis_mask(
    D: NDArray[np.float64],
    delta: float,
) -> NDArray[np.bool_]:
    """Port of MATLAB MedialAxisFunction.m lines 45-83: AOF + skeletonize.

    Returns a boolean mask of medial-axis cells inside the domain
    (``D ≤ 0``). The mask is 1-pixel-thin and isolated pixels are
    removed.
    """
    gx, gy = grad_sdf(D, delta)
    aof = _average_outward_flux(gx, gy, delta)
    ma = aof > _AOF_THRESHOLD
    ma = ma & (D <= 0)
    if not ma.any():
        return ma
    ma = _skeletonize_zhang_suen(ma)
    ma = _remove_isolated(ma)
    return ma


def apply_medial_axis(
    h0: NDArray[np.float64],
    D: NDArray[np.float64],
    delta: float,
    *,
    R: float,
    hmax: float,
    hmin: float,
) -> NDArray[np.float64]:
    """Port of MATLAB ``MedialAxisFunction.m`` — compose LFS-driven size.

    Parameters
    ----------
    h0 : (LY, LX) ndarray — existing size-field initial condition.
    D : (LY, LX) ndarray — signed distance field.
    delta : float — grid spacing.
    R : float — desired number of elements per local-feature-size unit.
    hmax, hmin : float — size bounds.

    Returns
    -------
    h0_new : (LY, LX) ndarray — ``min(h_lfs, h0)``.
    """
    ma = medial_axis_mask(D, delta)
    if not ma.any():
        # Fallback to distance-from-boundary only.
        MAD = np.full_like(D, hmax)
    else:
        # MATLAB: MAD = double(bwdist(MA)) * abs(Y(1) - Y(2))
        MAD = distance_transform_edt(~ma) * delta
    LFS = np.abs(D) + np.abs(MAD)
    h_lfs = LFS / R
    h_lfs = np.clip(h_lfs, hmin, hmax)
    return np.minimum(h_lfs, h0)


def medial_distance_fmm(
    fd: SDF,
    bbox: tuple[float, float, float, float],
    delta: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Distance-to-medial-axis field on a rectangular grid.

    Convenience wrapper: ``(X, Y, MAD)`` where ``MAD`` is NaN outside
    the domain (``fd(p) > 0``). Kept for backward compatibility with
    session-2 tests; the primary port entry is :func:`apply_medial_axis`.
    """
    X, Y, D = eval_sdf_grid(fd, bbox, delta)
    inside = D <= 0.0
    if not inside.any():
        return X, Y, np.full_like(D, np.nan)
    ma = medial_axis_mask(D, delta)
    if not ma.any():
        # Fallback: use the interior cell farthest from the boundary.
        Dabs = distance_transform_edt(inside) * delta
        idx = np.unravel_index(np.argmax(Dabs), Dabs.shape)
        ma = np.zeros_like(inside)
        ma[idx] = True
    med_dist = distance_transform_edt(~ma) * delta
    med_dist = med_dist.astype(float)
    med_dist[~inside] = np.nan
    return X, Y, med_dist
