"""Test fast_sdf pruned NumPy fallback for bit-identical output vs brute-force."""

from __future__ import annotations

import json
import numpy as np
import pytest

import admesh
from admesh._fast_sdf import _sdf_numpy, _sdf_numpy_pruned, _build_prune


@pytest.fixture
def wnat_rings():
    """Load rings from web/examples/wnat.json."""
    with open("web/examples/wnat.json") as f:
        data = json.load(f)
    return [np.array(ring, dtype=np.float64) for ring in data["rings"]]


@pytest.fixture
def synthetic_rings():
    """Build synthetic domain: jagged outer ring + 2 holes."""
    np.random.seed(42)
    # Outer ring: 300-vertex jagged ring with random radius
    theta = np.linspace(0, 2 * np.pi, 300, endpoint=False)
    r = 1.0 + 0.3 * np.random.randn(300)
    outer = np.column_stack([r * np.cos(theta), r * np.sin(theta)])

    # Hole 1: small circle at (0.3, 0.3)
    theta_h1 = np.linspace(0, 2 * np.pi, 50, endpoint=False)
    hole1 = np.column_stack([
        0.3 + 0.15 * np.cos(theta_h1),
        0.3 + 0.15 * np.sin(theta_h1)
    ])

    # Hole 2: small circle at (-0.4, -0.2)
    theta_h2 = np.linspace(0, 2 * np.pi, 60, endpoint=False)
    hole2 = np.column_stack([
        -0.4 + 0.12 * np.cos(theta_h2),
        -0.2 + 0.12 * np.sin(theta_h2)
    ])

    return [outer, hole1, hole2]


def _pack_edges_for_test(rings):
    """Pack ring edges into (ax, ay, bx, by) arrays."""
    ax, ay, bx, by = [], [], [], []
    for r in rings:
        r = np.asarray(r, dtype=np.float64)
        if len(r) < 2:
            continue
        a = r
        b = np.roll(r, -1, axis=0)
        ax.extend(a[:, 0])
        ay.extend(a[:, 1])
        bx.extend(b[:, 0])
        by.extend(b[:, 1])
    return (
        np.array(ax, dtype=np.float64),
        np.array(ay, dtype=np.float64),
        np.array(bx, dtype=np.float64),
        np.array(by, dtype=np.float64),
    )


class TestSdfNumpyPruned:
    """Test bit-identical pruned vs brute-force SDF."""

    def test_pruned_vs_brute_wnat(self, wnat_rings):
        """Pruned output matches brute on WNAT."""
        ax, ay, bx, by = _pack_edges_for_test(wnat_rings)
        nseg = len(ax)
        assert nseg > 128, f"expected nseg > 128, got {nseg}"

        # Query points: 20k uniform random + vertices + midpoints + epsilon shifts
        bbox = np.array([
            min(ax.min(), bx.min()),
            min(ay.min(), by.min()),
            max(ax.max(), bx.max()),
            max(ay.max(), by.max()),
        ])
        xspan = bbox[2] - bbox[0]
        yspan = bbox[3] - bbox[1]
        xmin = bbox[0] - 0.2 * xspan
        xmax = bbox[2] + 0.2 * xspan
        ymin = bbox[1] - 0.2 * yspan
        ymax = bbox[3] + 0.2 * yspan

        np.random.seed(123)
        pts_uniform = np.random.uniform(
            [xmin, ymin], [xmax, ymax], size=(20000, 2)
        )

        # Vertices
        pts_vertices = np.vstack([ring for ring in wnat_rings])

        # Segment midpoints
        pts_midpoints = np.column_stack([
            (ax + bx) / 2.0,
            (ay + by) / 2.0,
        ])

        # Epsilon shifts
        eps_shifts = []
        for pt in pts_vertices[:min(100, len(pts_vertices))]:
            eps_shifts.append(pt + np.array([1e-12, 0.0]))
            eps_shifts.append(pt + np.array([-1e-12, 0.0]))
        pts_epsilon = np.array(eps_shifts)

        # Combine all
        pts = np.vstack([pts_uniform, pts_vertices, pts_midpoints, pts_epsilon])
        px = pts[:, 0].copy()
        py = pts[:, 1].copy()

        # Build prune and compute
        prune = _build_prune(ax, ay, bx, by)
        assert prune is not None, "prune structure failed to build"

        result_pruned = _sdf_numpy_pruned(px, py, ax, ay, bx, by, prune)
        result_brute = _sdf_numpy(px, py, ax, ay, bx, by)

        # Bit-identical check
        assert np.array_equal(result_pruned, result_brute), (
            "pruned and brute results differ"
        )

    def test_pruned_vs_brute_synthetic(self, synthetic_rings):
        """Pruned output matches brute on synthetic."""
        ax, ay, bx, by = _pack_edges_for_test(synthetic_rings)
        nseg = len(ax)
        assert nseg > 128, f"expected nseg > 128, got {nseg}"

        # Query points
        bbox = np.array([
            min(ax.min(), bx.min()),
            min(ay.min(), by.min()),
            max(ax.max(), bx.max()),
            max(ay.max(), by.max()),
        ])
        xspan = bbox[2] - bbox[0]
        yspan = bbox[3] - bbox[1]
        xmin = bbox[0] - 0.2 * xspan
        xmax = bbox[2] + 0.2 * xspan
        ymin = bbox[1] - 0.2 * yspan
        ymax = bbox[3] + 0.2 * yspan

        np.random.seed(124)
        pts_uniform = np.random.uniform(
            [xmin, ymin], [xmax, ymax], size=(20000, 2)
        )

        pts_vertices = np.vstack([ring for ring in synthetic_rings])
        pts_midpoints = np.column_stack([
            (ax + bx) / 2.0,
            (ay + by) / 2.0,
        ])

        eps_shifts = []
        for pt in pts_vertices[:min(100, len(pts_vertices))]:
            eps_shifts.append(pt + np.array([1e-12, 0.0]))
            eps_shifts.append(pt + np.array([-1e-12, 0.0]))
        pts_epsilon = np.array(eps_shifts)

        pts = np.vstack([pts_uniform, pts_vertices, pts_midpoints, pts_epsilon])
        px = pts[:, 0].copy()
        py = pts[:, 1].copy()

        prune = _build_prune(ax, ay, bx, by)
        assert prune is not None

        result_pruned = _sdf_numpy_pruned(px, py, ax, ay, bx, by, prune)
        result_brute = _sdf_numpy(px, py, ax, ay, bx, by)

        assert np.array_equal(result_pruned, result_brute)

    def test_fast_sdf_with_numba_disabled(self, wnat_rings, monkeypatch):
        """fast_sdf uses pruned path when numba disabled."""
        import admesh._fast_sdf as fast_sdf_mod
        from admesh._fast_sdf import fast_sdf

        # Disable numba before calling fast_sdf
        monkeypatch.setattr(fast_sdf_mod, "_HAVE_NUMBA", False)

        # Build SDF - this should now use pruned path instead of numba
        sdf = fast_sdf(wnat_rings)

        # Query points
        ax, ay, bx, by = _pack_edges_for_test(wnat_rings)
        bbox = np.array([
            min(ax.min(), bx.min()),
            min(ay.min(), by.min()),
            max(ax.max(), bx.max()),
            max(ay.max(), by.max()),
        ])
        xspan = bbox[2] - bbox[0]
        yspan = bbox[3] - bbox[1]
        xmin = bbox[0] - 0.2 * xspan
        xmax = bbox[2] + 0.2 * xspan
        ymin = bbox[1] - 0.2 * yspan
        ymax = bbox[3] + 0.2 * yspan

        np.random.seed(125)
        pts = np.random.uniform([xmin, ymin], [xmax, ymax], size=(1000, 2))

        # Compute with disabled numba (should use pruned)
        result_pruned = sdf(pts)

        # Compute brute force reference
        px = pts[:, 0].copy()
        py = pts[:, 1].copy()
        result_brute = _sdf_numpy(px, py, ax, ay, bx, by)

        assert np.array_equal(result_pruned, result_brute)

    def test_pruned_points_outside_grid(self, wnat_rings):
        """Pruned output matches brute for points far outside segment bbox."""
        ax, ay, bx, by = _pack_edges_for_test(wnat_rings)

        # Get segment bounding box
        bbox = np.array([
            min(ax.min(), bx.min()),
            min(ay.min(), by.min()),
            max(ax.max(), bx.max()),
            max(ay.max(), by.max()),
        ])
        xspan = bbox[2] - bbox[0]
        yspan = bbox[3] - bbox[1]

        # Points far outside: expanded 3x from bbox
        xmin_far = bbox[0] - 1.5 * xspan
        xmax_far = bbox[2] + 1.5 * xspan
        ymin_far = bbox[1] - 1.5 * yspan
        ymax_far = bbox[3] + 1.5 * yspan

        np.random.seed(126)
        pts_far = np.random.uniform([xmin_far, ymin_far], [xmax_far, ymax_far], size=(500, 2))

        # Points exactly on bbox max edges
        pts_edges = np.array([
            [bbox[2], bbox[1]],
            [bbox[2], bbox[3]],
            [bbox[0], bbox[3]],
            [bbox[0], bbox[1]],
            [(bbox[0] + bbox[2]) / 2, bbox[3]],
            [(bbox[0] + bbox[2]) / 2, bbox[1]],
            [bbox[2], (bbox[1] + bbox[3]) / 2],
            [bbox[0], (bbox[1] + bbox[3]) / 2],
        ])

        pts = np.vstack([pts_far, pts_edges])
        px = pts[:, 0].copy()
        py = pts[:, 1].copy()

        # Build prune and compute
        prune = _build_prune(ax, ay, bx, by)
        assert prune is not None, "prune structure failed to build"

        result_pruned = _sdf_numpy_pruned(px, py, ax, ay, bx, by, prune)
        result_brute = _sdf_numpy(px, py, ax, ay, bx, by)

        # Bit-identical check
        assert np.array_equal(result_pruned, result_brute), (
            "pruned and brute results differ for outside-grid points"
        )
