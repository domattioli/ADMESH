"""Tests for ``domain_from_polygon`` and ``domain_from_sdf`` (T013)."""

from __future__ import annotations

import numpy as np
import pytest

import admesh
from admesh import Domain


def test_domain_from_polygon_sdf_signs():
    ring = np.array(
        [[-1.0, -1.0], [1.0, -1.0], [1.0, 1.0], [-1.0, 1.0]], dtype=float
    )
    domain = admesh.domain_from_polygon([ring])
    assert isinstance(domain, Domain)
    assert domain.bbox == (-1.0, -1.0, 1.0, 1.0)
    inside = domain.sdf(np.array([[0.0, 0.0]]))
    outside = domain.sdf(np.array([[2.0, 2.0]]))
    on_edge = domain.sdf(np.array([[1.0, 0.0]]))
    assert inside[0] < 0
    assert outside[0] > 0
    assert abs(on_edge[0]) < 1e-9


def test_domain_from_polygon_with_hole():
    outer = np.array(
        [[-2.0, -2.0], [2.0, -2.0], [2.0, 2.0], [-2.0, 2.0]], dtype=float
    )
    hole = np.array(
        [[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]], dtype=float
    )
    domain = admesh.domain_from_polygon([outer, hole])
    # Annulus topology: origin is in the hole → outside.
    assert domain.sdf(np.array([[0.0, 0.0]]))[0] > 0
    # Between the hole and outer ring → inside.
    assert domain.sdf(np.array([[1.0, 0.0]]))[0] < 0


def test_domain_from_sdf_passthrough():
    def my_sdf(p: np.ndarray) -> np.ndarray:
        return np.hypot(p[:, 0], p[:, 1]) - 1.0

    domain = admesh.domain_from_sdf(my_sdf, bbox=(-1.0, -1.0, 1.0, 1.0))
    assert domain.sdf is my_sdf
    assert domain.bbox == (-1.0, -1.0, 1.0, 1.0)


def test_domain_from_polygon_rejects_empty_rings():
    with pytest.raises(ValueError, match="non-empty"):
        admesh.domain_from_polygon([])


def test_domain_from_polygon_rejects_wrong_shape():
    with pytest.raises(ValueError, match=r"\(M, 2\)"):
        admesh.domain_from_polygon([np.array([0.0, 1.0, 2.0])])


def test_domain_from_sdf_rejects_short_bbox():
    with pytest.raises(ValueError, match="bbox"):
        admesh.domain_from_sdf(lambda p: p[:, 0], bbox=(0.0, 1.0))  # type: ignore[arg-type]
