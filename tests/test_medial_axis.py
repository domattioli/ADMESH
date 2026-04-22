"""Medial-axis distance field — clean-room P1 port.

Analytic references:

- ``unit_disk``: medial axis = {origin}; medial_distance(p) = |p| = r.
- ``annulus(inner=0.4, outer=1.0)``: medial axis = circle at
  r = 0.7; medial_distance(p) = |r - 0.7|.
"""

from __future__ import annotations

import numpy as np

from admesh import domains
from admesh.medial_axis import medial_distance_fmm


def test_medial_distance_unit_disk() -> None:
    """On the unit disk, medial distance ≈ r (distance to origin)."""
    dom = domains.UNIT_DISK
    delta = 0.02
    X, Y, med = medial_distance_fmm(dom.fd, dom.bbox, delta)
    r = np.hypot(X, Y)

    # Away from the boundary and origin, compare to analytic.
    mask = (r > 0.2) & (r < 0.8) & np.isfinite(med)
    err = np.abs(med[mask] - r[mask])
    assert err.max() < 2.5 * delta, f"err max {err.max():.3e} > 2.5·delta"


def test_medial_distance_annulus() -> None:
    """On annulus(0.4, 1.0), medial distance ≈ |r - 0.7|."""
    dom = domains.ANNULUS
    delta = 0.02
    X, Y, med = medial_distance_fmm(dom.fd, dom.bbox, delta)
    r = np.hypot(X, Y)
    analytic = np.abs(r - 0.7)

    # Interior annular ring, staying away from both boundaries.
    mask = (r > 0.5) & (r < 0.9) & np.isfinite(med)
    err = np.abs(med[mask] - analytic[mask])
    assert err.max() < 3.0 * delta, f"err max {err.max():.3e} > 3·delta"


def test_medial_distance_outside_is_nan() -> None:
    """Cells outside the domain are NaN."""
    dom = domains.UNIT_DISK
    delta = 0.05
    X, Y, med = medial_distance_fmm(dom.fd, dom.bbox, delta)
    r = np.hypot(X, Y)
    outside = r > 1.1
    assert np.isnan(med[outside]).all()


def test_medial_distance_annulus_medial_ring_has_zero_dist() -> None:
    """Cells near r=0.7 should have near-zero medial distance."""
    dom = domains.ANNULUS
    delta = 0.01
    X, Y, med = medial_distance_fmm(dom.fd, dom.bbox, delta)
    r = np.hypot(X, Y)
    near_medial = (r > 0.69) & (r < 0.71) & np.isfinite(med)
    assert near_medial.any()
    assert med[near_medial].max() < 5.0 * delta
