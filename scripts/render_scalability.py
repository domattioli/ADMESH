"""Octree scalability benchmark and fixture generator.

T015 — Build octrees for river-into-bay domain at various feature-size ratios.
Measures wall-clock build time and leaf count; exports fixtures for parity tests.

Usage:
    python scripts/render_scalability.py                  # Benchmark only
    python scripts/render_scalability.py --export-fixtures  # Benchmark + save fixtures
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

from admesh._stages.octree_grid import build_octree, size_field_octree
from admesh.api import Domain


def river_into_bay_domain() -> Domain:
    """Return circular domain: center=(0.5, 0.5), radius=0.45, bbox=(0, 0, 1, 1)."""
    def sdf(pts: np.ndarray) -> np.ndarray:
        """Signed distance to circle boundary. Negative inside, positive outside."""
        center = np.array([0.5, 0.5])
        return np.linalg.norm(pts - center, axis=1) - 0.45

    return Domain(
        bbox=(0.0, 0.0, 1.0, 1.0),
        sdf=sdf,
    )


def main():
    """Run scalability benchmark and optionally export fixtures."""
    domain = river_into_bay_domain()
    h_max = 1.0
    ratios = [10, 20, 40, 100, 1000]
    export_fixtures = "--export-fixtures" in sys.argv
    fixture_dir = Path(__file__).parent.parent / "tests" / "fixtures" / "octree"

    print("Octree Scalability Benchmark (river-into-bay domain)")
    print("=" * 70)

    for ratio in ratios:
        h_min = h_max / ratio
        max_depth = min(12, max(8, int(np.ceil(np.log2(h_max / h_min))) + 1))

        # Measure build time
        t0 = time.perf_counter()
        tree = build_octree(domain, h_min=h_min, h_max=h_max, max_depth=max_depth)
        elapsed = time.perf_counter() - t0

        n_leaves = len(tree.leaves)
        print(f"ratio={ratio:5d}: leaves={n_leaves:7d}, build={elapsed:.3f}s")

        # Export fixtures if requested
        if export_fixtures:
            # Generate test points: 50 random in bbox, seed per ratio
            np.random.seed(ratio)
            pts_all = np.random.uniform(0, 1, (50, 2))

            # Filter to points inside domain (sdf < 0)
            sdf_vals = domain.sdf(pts_all)
            pts_inside = pts_all[sdf_vals < 0]

            # Take first 20 (or fewer if not enough inside)
            pts = pts_inside[:20] if len(pts_inside) >= 20 else pts_inside

            # Evaluate size field
            fh = size_field_octree(
                domain, h_min=h_min, h_max=h_max, max_depth=max_depth
            )
            h_expected = fh(pts)

            # Save to fixture
            fixture_path = fixture_dir / f"river-into-bay_ratio{ratio}.npz"
            np.savez(
                fixture_path,
                pts=pts,
                h_expected=h_expected,
                leaf_count=np.array([n_leaves]),
                bbox=np.array(domain.bbox),
            )

    if export_fixtures:
        print("\n" + "=" * 70)
        print(f"Fixtures saved to {fixture_dir}/")


if __name__ == "__main__":
    main()
