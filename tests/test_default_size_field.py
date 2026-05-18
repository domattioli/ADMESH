"""Acceptance tests for issue #10: Default size-field stack structural validity.

Tier-0: polygon-constructed MVP domains — no regression.
Tier-1: wetting_and_drying_test.14 — real-world mesh, structural validity.
Tier-2: wnat_test.14 — real-world WNAT mesh, 60-second release gate.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

import admesh
from admesh import domains as _domains
from admesh.routine import triangulate as _routine_triangulate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mesh_area(mesh: admesh.Mesh) -> float:
    n, e = mesh.nodes, mesh.elements
    v0, v1, v2 = n[e[:, 0]], n[e[:, 1]], n[e[:, 2]]
    d12, d13 = v1 - v0, v2 - v0
    return float(np.sum(np.abs(d12[:, 0] * d13[:, 1] - d12[:, 1] * d13[:, 0]) / 2.0))


def _polygon_area(pts: np.ndarray) -> float:
    x, y = pts[:, 0], pts[:, 1]
    return float(abs(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)) / 2.0)


def _assert_structural_validity(mesh: admesh.Mesh, dom: admesh.Domain) -> None:
    """Assert mesh is structurally valid relative to domain."""
    assert mesh.n_nodes > 0, "mesh must be non-empty"
    assert mesh.n_elements > 0, "mesh must have elements"

    # No degenerate (negative-area) elements after fixmesh reorientation.
    n, e = mesh.nodes, mesh.elements
    v0, v1, v2 = n[e[:, 0]], n[e[:, 1]], n[e[:, 2]]
    d12, d13 = v1 - v0, v2 - v0
    areas = (d12[:, 0] * d13[:, 1] - d12[:, 1] * d13[:, 0]) / 2.0
    assert (areas >= 0).all(), "all elements must have non-negative signed area"

    # All nodes inside or within bbox_diag * 1e-2 of the domain boundary.
    diag = float(np.hypot(dom.bbox[2] - dom.bbox[0], dom.bbox[3] - dom.bbox[1]))
    tol = diag * 1e-2
    sdf_vals = dom.sdf(mesh.nodes)
    outside = sdf_vals > tol
    assert not outside.any(), (
        f"{outside.sum()} node(s) outside domain by more than {tol:.1f} units; "
        f"max overshoot={sdf_vals.max():.2f}"
    )


# ---------------------------------------------------------------------------
# Tier-0: polygon domains — no regression
# ---------------------------------------------------------------------------


class TestTier0PolygonDomains:
    """Polygon-constructed domains must still triangulate without regression."""

    @pytest.mark.parametrize("domain,name", [
        (_domains.UNIT_SQUARE, "UNIT_SQUARE"),
        (_domains.L_SHAPE, "L_SHAPE"),
    ])
    def test_polygon_domain_valid(self, domain: _domains.Domain, name: str) -> None:
        p, t = _routine_triangulate(domain, h0=0.1, seed=0, niter=200)
        assert len(p) > 0, f"{name}: mesh must be non-empty"
        assert len(t) > 0, f"{name}: mesh must have elements"
        # All centroids inside domain (sdf <= small tol).
        centroids = (p[t[:, 0]] + p[t[:, 1]] + p[t[:, 2]]) / 3.0
        sdf_vals = domain.fd(centroids)
        assert (sdf_vals <= 0.01).all(), f"{name}: centroids outside domain"


# ---------------------------------------------------------------------------
# Tier-1: wetting_and_drying_test.14 structural round-trip
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestTier1WettingAndDrying:
    """SC-T1: Domain.from_mesh(wnd) → triangulate() stays within domain."""

    FIXTURE = "tests/fixtures/fort14/adcirc_examples/wetting_and_drying_test.14"

    def test_tier1_wetting_and_drying_round_trip(self) -> None:
        src = admesh.read_fort14(self.FIXTURE)
        dom = admesh.Domain.from_mesh(src)

        mesh = admesh.triangulate(
            dom,
            h_min=200.0,
            h_max=2000.0,
            seed=0,
            max_iter=100,
            quality_gate=(0.0, 0.0),
        )

        _assert_structural_validity(mesh, dom)

        # Mesh area must cover ≥95% of the outer polygon area.
        outer_pts = src.nodes[dom.bc_segments[0].node_ids]
        domain_area = _polygon_area(outer_pts)
        fresh_area = _mesh_area(mesh)
        coverage = fresh_area / domain_area
        assert coverage >= 0.95, (
            f"Tier-1 mesh covers only {coverage:.1%} of domain area "
            f"(need ≥95%); domain_area={domain_area:.0f}, fresh_area={fresh_area:.0f}"
        )

    def test_tier1_bbox_matches_source(self) -> None:
        src = admesh.read_fort14(self.FIXTURE)
        dom = admesh.Domain.from_mesh(src)
        src_bbox = (
            float(src.nodes[:, 0].min()),
            float(src.nodes[:, 1].min()),
            float(src.nodes[:, 0].max()),
            float(src.nodes[:, 1].max()),
        )
        assert np.allclose(list(dom.bbox), list(src_bbox), rtol=1e-9), (
            f"bbox mismatch: dom={dom.bbox}, src={src_bbox}"
        )


# ---------------------------------------------------------------------------
# Tier-2: wnat_test.14 within 60-second wall-clock budget
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestTier2WNAT:
    """SC-T2 (0.1.0 release gate): WNAT triangulation within 60 s."""

    FIXTURE = "tests/fixtures/fort14/adcirc_examples/wnat_test.14"
    WALL_CLOCK_BUDGET_S = 60.0

    def test_tier2_wnat_release_gate(self) -> None:
        src = admesh.read_fort14(self.FIXTURE)
        dom = admesh.Domain.from_mesh(src)

        t0 = time.monotonic()
        mesh = admesh.triangulate(
            dom,
            h_min=0.5,
            h_max=3.0,
            seed=0,
            max_iter=100,
            quality_gate=(0.0, 0.0),
        )
        elapsed = time.monotonic() - t0

        _assert_structural_validity(mesh, dom)

        assert elapsed < self.WALL_CLOCK_BUDGET_S, (
            f"Tier-2 triangulation took {elapsed:.1f}s (budget={self.WALL_CLOCK_BUDGET_S}s)"
        )

    def test_tier2_wnat_bbox_coverage(self) -> None:
        src = admesh.read_fort14(self.FIXTURE)
        dom = admesh.Domain.from_mesh(src)

        assert dom.bbox[0] < -90, f"WNAT west boundary too far east: {dom.bbox[0]}"
        assert dom.bbox[2] > -70, f"WNAT east boundary too far west: {dom.bbox[2]}"

        mesh = admesh.triangulate(
            dom,
            h_min=0.5,
            h_max=3.0,
            seed=0,
            max_iter=100,
            quality_gate=(0.0, 0.0),
        )

        # All nodes within domain + pad tolerance.
        pad = 0.1
        assert mesh.nodes[:, 0].min() >= dom.bbox[0] - pad
        assert mesh.nodes[:, 0].max() <= dom.bbox[2] + pad
        assert mesh.nodes[:, 1].min() >= dom.bbox[1] - pad
        assert mesh.nodes[:, 1].max() <= dom.bbox[3] + pad
