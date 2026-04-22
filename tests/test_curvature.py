"""Curvature field — clean-room P1 port, analytic-reference tests.

Reference (signed-distance sign convention: d<0 inside):

- ``unit_disk`` (``d = r - 1``): the level sets are concentric
  circles of radius ``1 + d``. Normal points outward (∇d = r̂), so
  ``κ = ∇·r̂ = 1/r``.
- ``annulus`` (inner radius a, outer radius b,
  ``d = max(r - b, a - r)``): outside the outer ring and inside
  the inner ring, the normal flips sign, but *inside* the annular
  region ∇d points toward the *nearer* boundary. On the outer
  half (r > (a+b)/2), ``d = r - b`` so ``κ = 1/r``. On the inner
  half (r < (a+b)/2), ``d = a - r`` so ``∇d = -r̂`` and
  ``κ = ∇·(-r̂) = -1/r``.
"""

from __future__ import annotations

import numpy as np

from admesh import domains
from admesh.curvature import curvature_function


def _interior_mask(D: np.ndarray, pad: float = 0.05) -> np.ndarray:
    """Return cells strictly inside the domain, away from boundaries
    and medial-axis-like regions (where ``D`` is small-magnitude)."""
    return D < -pad


def test_curvature_unit_disk_converges() -> None:
    """κ = 1/r on the unit disk. Check coarse-grid bound + convergence."""
    dom = domains.UNIT_DISK

    errs = []
    deltas = [0.05, 0.025]
    for delta in deltas:
        X, Y, kappa = curvature_function(dom.fd, dom.bbox, delta)
        # Evaluate analytic κ on the interior (avoid the origin medial).
        r = np.hypot(X, Y)
        _, _, D = _eval_with(dom, delta)
        mask = _interior_mask(D, pad=0.2) & (r > 0.3) & np.isfinite(kappa)
        analytic = 1.0 / r
        err = np.max(np.abs(kappa[mask] - analytic[mask]))
        errs.append(err)

    # Coarse-grid absolute bound.
    assert errs[0] < 5e-2, f"coarse err {errs[0]:.3e} exceeds 5e-2"
    # Refining the grid reduces error (convergence check — not a rate,
    # just monotonic for finite domains where the stencil is valid).
    assert errs[1] < errs[0], f"no refinement gain: {errs}"


def test_curvature_annulus_sign_flip() -> None:
    """Inner half of the annulus has ``κ = -1/r``; outer half ``+1/r``."""
    dom = domains.ANNULUS
    delta = 0.02
    X, Y, kappa = curvature_function(dom.fd, dom.bbox, delta)
    r = np.hypot(X, Y)

    # Bands away from both the boundary layer and the medial ring
    # at r=(0.4+1.0)/2=0.7. Use 0.5..0.6 and 0.8..0.9.
    inner_band = (r > 0.50) & (r < 0.60) & np.isfinite(kappa)
    outer_band = (r > 0.80) & (r < 0.90) & np.isfinite(kappa)

    # Inner half: κ should track -1/r (negative).
    err_inner = np.max(np.abs(kappa[inner_band] - (-1.0 / r[inner_band])))
    # Outer half: κ should track +1/r (positive).
    err_outer = np.max(np.abs(kappa[outer_band] - (1.0 / r[outer_band])))

    assert err_inner < 1e-1, f"inner-half κ err {err_inner:.3e}"
    assert err_outer < 1e-1, f"outer-half κ err {err_outer:.3e}"


def test_curvature_handles_kinked_sdf() -> None:
    """The unit-square SDF ``max(|x|,|y|) - 0.5`` has kinks along
    the diagonals (``|x| = |y|``) where ∇d flips direction.
    Verify the solver runs, the far-from-kink regions hit κ≈0
    (flat level sets on each face), and no crashes happen."""
    dom = domains.UNIT_SQUARE
    delta = 0.02
    X, Y, kappa = curvature_function(dom.fd, dom.bbox, delta)

    # Axis strip well inside the domain, away from diagonals: |y| < 0.1,
    # 0.2 < |x| < 0.35 (level sets are vertical lines → κ = 0).
    strip = (np.abs(Y) < 0.1) & (np.abs(X) > 0.2) & (np.abs(X) < 0.35)
    strip = strip & np.isfinite(kappa)
    assert strip.any(), "no finite-κ cells in the test strip"
    assert np.max(np.abs(kappa[strip])) < 2.0, (
        f"flat-face κ should be ~0, got max={np.max(np.abs(kappa[strip])):.2e}"
    )


def _eval_with(dom, delta: float):
    """Re-sample the SDF at the same grid curvature uses."""
    from admesh.distance import eval_sdf_grid
    return eval_sdf_grid(dom.fd, dom.bbox, delta)
