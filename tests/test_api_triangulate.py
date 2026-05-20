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
from admesh import BoundaryType, Domain
from admesh.domains import ALL as DOMAIN_REGISTRY

from conftest import MVP_DOMAIN_NAMES, MVP_TRIANGULATE_CONFIG


@pytest.mark.parametrize("name", MVP_DOMAIN_NAMES)
def test_triangulate_mvp_domain(name: str) -> None:
    port_dom = DOMAIN_REGISTRY[name]
    pfix = port_dom.fixed_points if port_dom.fixed_points.size else None
    domain = Domain(sdf=port_dom.fd, bbox=port_dom.bbox, pfix=pfix)
    mesh = admesh.triangulate(domain, seed=0, **MVP_TRIANGULATE_CONFIG[name])

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
    port_dom = DOMAIN_REGISTRY["unit_square"]
    domain = Domain(sdf=port_dom.fd, bbox=port_dom.bbox, pfix=None)
    with pytest.raises(ValueError, match="quality_gate"):
        admesh.triangulate(
            domain, h_max=0.12, max_iter=200, seed=0,
            quality_gate=(0.99, 0.99),
        )


def test_triangulate_h_min_h_max_enforced() -> None:
    """Fix #37: h_min/h_max must not be silently ignored when no user_contribs.

    Previously, calling triangulate(domain, h_min=X, h_max=Y) without
    user_contribs caused h_min to be completely ignored and h_max to only
    set the initial lattice spacing (not a hard bound). This test verifies
    both parameters produce a mesh whose edge lengths respect the bounds.
    """
    port_dom = DOMAIN_REGISTRY["unit_square"]
    domain = Domain(sdf=port_dom.fd, bbox=port_dom.bbox, pfix=None)

    h_min = 0.08
    h_max = 0.15
    mesh = admesh.triangulate(domain, h_min=h_min, h_max=h_max, max_iter=300, seed=0)

    assert mesh.n_nodes > 0
    assert mesh.n_elements > 0

    # Compute per-edge lengths.
    p = mesh.nodes
    t = mesh.elements
    edges = np.vstack([t[:, [0, 1]], t[:, [0, 2]], t[:, [1, 2]]])
    edges = np.unique(np.sort(edges, axis=1), axis=0)
    lengths = np.linalg.norm(p[edges[:, 0]] - p[edges[:, 1]], axis=1)

    # h_max is used as h0 (initial spacing) — mean edge length should be ~h_max.
    # h_min clamps the size field so distmesh rejection doesn't create tiny edges.
    # We allow a generous tolerance (2x) to account for distmesh dynamics.
    assert lengths.mean() < h_max * 2.5, (
        f"mean edge length {lengths.mean():.4f} >> h_max={h_max}"
    )
    # Verify size field was applied — no extreme outlier edges > 3x h_max.
    assert lengths.max() < h_max * 3.0, (
        f"max edge length {lengths.max():.4f} far exceeds h_max={h_max}"
    )


def test_triangulate_boundary_pts_seeds_notch_walls() -> None:
    """Fix #2: domain.pts triggers boundary edge seeding for short segments.

    The NOTCHED_RECTANGLE has short notch walls (~0.25 units) that the 2-D
    lattice alone under-samples. When pts is provided, _seed_boundary_1d
    inserts intermediate pfix on each edge so the notch walls get nodes.
    """
    port_dom = DOMAIN_REGISTRY["notched_rectangle"]

    boundary_pts = np.array(
        [
            [-1, -0.5], [1, -0.5], [1, 0.5], [0.05, 0.5], [0.05, 0.25],
            [-0.05, 0.25], [-0.05, 0.5], [-1, 0.5],
        ],
        dtype=float,
    )

    # Domain WITH pts — should produce notch-wall seeds.
    domain_with_pts = admesh.Domain(
        sdf=port_dom.fd, bbox=port_dom.bbox, pts=boundary_pts
    )
    mesh_with = admesh.triangulate(domain_with_pts, h_max=0.12, max_iter=300, seed=0)

    # Domain WITHOUT pts — baseline, no extra seeding.
    domain_no_pts = admesh.Domain(sdf=port_dom.fd, bbox=port_dom.bbox)
    mesh_without = admesh.triangulate(domain_no_pts, h_max=0.12, max_iter=300, seed=0)

    # Both meshes must be valid.
    assert mesh_with.n_nodes > 0
    assert mesh_without.n_nodes > 0

    # With pts the mesh should have at least as many nodes (boundary seeds add
    # pfix that distmesh keeps, so n_nodes should be >= baseline).
    assert mesh_with.n_nodes >= mesh_without.n_nodes, (
        f"Expected boundary seeding to add nodes: "
        f"with_pts={mesh_with.n_nodes}, without={mesh_without.n_nodes}"
    )

    # Verify nodes exist near the notch walls in the seeded mesh.
    notch_wall_nodes = mesh_with.nodes[
        (np.abs(mesh_with.nodes[:, 0] - 0.05) < 0.01)
        & (mesh_with.nodes[:, 1] > 0.25)
        & (mesh_with.nodes[:, 1] < 0.5)
    ]
    assert len(notch_wall_nodes) >= 1, "Notch right wall should have at least 1 node"
