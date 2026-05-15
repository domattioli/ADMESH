"""Tests for admesh.routine — triangulate() and _seed_boundary_1d().

Issue #2: 1D boundary seeding for polygonal Domain path.
"""

from __future__ import annotations

import numpy as np
import pytest

from admesh.domains import ANNULUS, L_SHAPE, NOTCHED_RECTANGLE, UNIT_DISK, UNIT_SQUARE
from admesh.routine import _seed_boundary_1d, triangulate


# ---------------------------------------------------------------------------
# _seed_boundary_1d unit tests
# ---------------------------------------------------------------------------

class TestSeedBoundary1D:
    def test_uniform_square_edge_count(self):
        """A 2x1 rectangle at h0=0.5 -> 1 interior seed per 1-unit edge, 3 per 2-unit edge."""
        poly = np.array([[-1, 0], [1, 0], [1, 1], [-1, 1]], dtype=float)
        seeds = _seed_boundary_1d(poly, fh=None, h0=0.5)
        # Bottom edge len=2 -> n_segs=4 -> 3 interior pts
        # Right edge len=1 -> n_segs=2 -> 1 interior pt
        # Top edge len=2  -> n_segs=4 -> 3 interior pts
        # Left edge len=1 -> n_segs=2 -> 1 interior pt
        assert seeds.shape == (8, 2)

    def test_zero_length_edge_skipped(self):
        poly = np.array([[0, 0], [0, 0], [1, 0], [1, 1]], dtype=float)
        seeds = _seed_boundary_1d(poly, fh=None, h0=0.5)
        assert seeds.ndim == 2
        assert seeds.shape[1] == 2

    def test_edge_shorter_than_h0_produces_no_seeds(self):
        poly = np.array([[0, 0], [0.1, 0], [0.05, 0.087]], dtype=float)
        seeds = _seed_boundary_1d(poly, fh=None, h0=0.2)
        assert len(seeds) == 0

    def test_non_uniform_fh_gives_more_seeds_in_fine_region(self):
        """Edges near origin get local_h=0.03; far edges get local_h=0.1."""
        poly = np.array([
            [-0.5,  0.0], [0.5,  0.0],
            [ 0.5,  1.0], [-0.5, 1.0],
        ], dtype=float)

        def graded_fh(p):
            return np.where(np.abs(p[:, 1]) < 0.1, 0.03, 0.1)

        seeds = _seed_boundary_1d(poly, fh=graded_fh, h0=0.03)
        fine_seeds = seeds[np.abs(seeds[:, 1]) < 0.01]
        coarse_seeds = seeds[np.abs(seeds[:, 1] - 1.0) < 0.01]
        assert len(fine_seeds) > len(coarse_seeds)

    def test_fh_nan_falls_back_to_h0(self):
        poly = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=float)

        def bad_fh(p):
            return np.full(len(p), np.nan)

        seeds = _seed_boundary_1d(poly, fh=bad_fh, h0=0.25)
        assert seeds.shape[1] == 2

    def test_returns_float64(self):
        poly = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=float)
        seeds = _seed_boundary_1d(poly, fh=None, h0=0.4)
        assert seeds.dtype == np.float64


# ---------------------------------------------------------------------------
# triangulate() integration tests — notch wall coverage (issue #2)
# ---------------------------------------------------------------------------

class TestNotchedRectangleBoundaryCoverage:
    """Verify that 1D seeding guarantees adequate notch-wall node coverage."""

    @pytest.fixture(scope="class")
    def mesh(self):
        p, t = triangulate(NOTCHED_RECTANGLE, h0=0.05, seed=0, niter=300)
        return p, t

    def test_right_notch_wall_coverage(self, mesh):
        p, _ = mesh
        right_wall = np.sum((np.abs(p[:, 0] - 0.05) < 1e-3) & (p[:, 1] >= 0.24))
        assert right_wall >= 4, f"Right notch wall has only {right_wall} nodes (need >=4)"

    def test_left_notch_wall_coverage(self, mesh):
        p, _ = mesh
        left_wall = np.sum((np.abs(p[:, 0] + 0.05) < 1e-3) & (p[:, 1] >= 0.24))
        assert left_wall >= 4, f"Left notch wall has only {left_wall} nodes (need >=4)"

    def test_notch_floor_coverage(self, mesh):
        p, _ = mesh
        floor = np.sum((np.abs(p[:, 1] - 0.25) < 1e-3) & (np.abs(p[:, 0]) < 0.06))
        assert floor >= 1, f"Notch floor has only {floor} nodes (need >=1)"

    def test_mesh_is_valid(self, mesh):
        p, t = mesh
        assert p.shape[1] == 2
        assert t.shape[1] == 3
        assert len(p) > 0
        assert len(t) > 0


class TestSeedBoundary1DWithNonUniformFhOnNotch:
    """US2: graded fh produces finer seeds on notch walls than uniform h0."""

    def test_graded_fh_denser_near_notch(self):
        def fine_near_notch(p):
            near = np.abs(p[:, 0]) < 0.1
            return np.where(near, 0.02, 0.07)

        seeds_graded = _seed_boundary_1d(
            NOTCHED_RECTANGLE.boundary_polygon, fh=fine_near_notch, h0=0.02
        )
        seeds_uniform = _seed_boundary_1d(
            NOTCHED_RECTANGLE.boundary_polygon, fh=None, h0=0.05
        )
        assert len(seeds_graded) > len(seeds_uniform)


# ---------------------------------------------------------------------------
# Regression: other canonical domains unaffected (US3)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("domain", [UNIT_SQUARE, L_SHAPE, UNIT_DISK, ANNULUS])
def test_non_notched_domains_have_no_boundary_polygon(domain):
    assert domain.boundary_polygon is None


@pytest.mark.parametrize("domain,h0", [
    (UNIT_SQUARE, 0.2),
    (L_SHAPE, 0.2),
    (UNIT_DISK, 0.2),
    (ANNULUS, 0.2),
])
def test_triangulate_non_notched_domains_produces_valid_mesh(domain, h0):
    p, t = triangulate(domain, h0=h0, seed=0, niter=200)
    assert p.shape[1] == 2
    assert t.shape[1] == 3
    assert len(p) > 0
    assert len(t) > 0
