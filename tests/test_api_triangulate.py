"""End-to-end :func:`admesh.triangulate` on the 5 MVP domains (T010).

For each canonical domain, assert: the call produces a non-empty
:class:`Mesh` whose quality clears the constitutional gate
(``min_q ≥ 0.30``, ``mean_q ≥ 0.60``) and whose boundary list contains
at least one segment labelled with a ``BoundaryType``.
"""

from __future__ import annotations

import numpy as np
import pytest

import admesh
from admesh import BoundaryType
from admesh.domains import ALL as DOMAIN_REGISTRY


_MVP = {
    "unit_square":       {"h_max": 0.12, "max_iter": 200},
    "l_shape":           {"h_max": 0.15, "max_iter": 200},
    "unit_disk":         {"h_max": 0.15, "max_iter": 200},
    "annulus":           {"h_max": 0.12, "max_iter": 200},
    "notched_rectangle": {"h_max": 0.08, "max_iter": 200},
}


@pytest.mark.parametrize("name", list(_MVP))
def test_triangulate_mvp_domain(name: str) -> None:
    port_dom = DOMAIN_REGISTRY[name]
    pfix = port_dom.fixed_points if port_dom.fixed_points.size else None
    domain = admesh.domain_from_sdf(
        sdf=port_dom.fd, bbox=port_dom.bbox, pfix=pfix
    )
    mesh = admesh.triangulate(domain, seed=0, **_MVP[name])

    assert mesh.n_nodes > 0
    assert mesh.n_elements > 0
    assert mesh.quality is not None
    assert float(mesh.quality.min()) >= 0.30, f"{name}: min_q below gate"
    assert float(mesh.quality.mean()) >= 0.60, f"{name}: mean_q below gate"
    assert mesh.n_boundaries >= 1
    # At least one segment carries a named BC type (default MAINLAND).
    named = [s for s in mesh.boundaries if isinstance(s.bc_type, BoundaryType)]
    assert named, f"{name}: no segment carries a BoundaryType label"
    assert any(
        s.bc_type in (BoundaryType.OPEN, BoundaryType.MAINLAND)
        for s in named
    )


def test_triangulate_quality_gate_failure_raises() -> None:
    """Quality gate enforcement: an impossible gate must raise ValueError."""
    ring = np.array(
        [[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]], dtype=float
    )
    domain = admesh.domain_from_polygon([ring])
    with pytest.raises(ValueError, match="quality_gate"):
        admesh.triangulate(
            domain, h_max=0.12, max_iter=200, seed=0,
            quality_gate=(0.99, 0.99),
        )
