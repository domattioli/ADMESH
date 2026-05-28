"""Basin+inlet fixture: synthetic multi-scale domain generator.

A rectangular basin of length L connected to a thin inlet of width W,
with L/W ratio controllable. Exercises the octree refinement on a
narrow feature within a large domain.
"""

import numpy as np
from admesh import Domain


def make_basin_inlet(L: float, W: float, inlet_length: float | None = None) -> Domain:
    """Create a basin+inlet domain.

    Parameters
    ----------
    L : float
        Length of the basin.
    W : float
        Width of the inlet (narrow feature).
    inlet_length : float or None
        Length of the inlet connection. Defaults to 0.2*L.

    Returns
    -------
    Domain
        Multi-scale domain with feature-size ratio L/W.
    """
    if inlet_length is None:
        inlet_length = 0.2 * L

    # Basin: rectangle [0, L] × [0, 1]
    # Inlet: narrow channel [L/2 - inlet_length/2, L/2 + inlet_length/2] × [1, 1 + W]

    def make_outer_ring():
        """Outer boundary: basin + inlet."""
        # Basin corners
        pts = [
            [0, 0],
            [L, 0],
            [L, 1],
            [L / 2 + inlet_length / 2, 1],  # Start inlet
            [L / 2 + inlet_length / 2, 1 + W],  # Inlet top-right
            [L / 2 - inlet_length / 2, 1 + W],  # Inlet top-left
            [L / 2 - inlet_length / 2, 1],  # End inlet
            [0, 1],
        ]
        return np.array(pts, dtype=np.float64)

    outer_ring = make_outer_ring()

    def sdf(points: np.ndarray) -> np.ndarray:
        """Signed-distance function: negative inside, positive outside."""
        from scipy.spatial import cKDTree

        # Densely sample boundary
        ring_pts = outer_ring
        diag = np.hypot(L, 1 + W)
        h_samp = max(diag / 200, 1e-8)

        segs = []
        n = len(ring_pts)
        for i in range(n):
            a = ring_pts[i]
            b = ring_pts[(i + 1) % n]
            seg_len = float(np.linalg.norm(b - a))
            n_samp = max(2, int(np.ceil(seg_len / h_samp)))
            ts = np.linspace(0.0, 1.0, n_samp)[:-1]
            segs.append(a + ts[:, None] * (b - a))
        dense_pts = np.vstack(segs)
        tree = cKDTree(dense_pts)

        points = np.asarray(points, dtype=np.float64)
        if points.ndim == 1:
            points = points.reshape(1, -1)

        # Distance to boundary
        distances, _ = tree.query(points)

        # Winding test: inside if polygon winding number is odd
        from admesh._stages.in_polygon import in_polygon

        inside, _ = in_polygon(
            points[:, 0], points[:, 1],
            ring_pts[:, 0], ring_pts[:, 1],
        )

        # Return signed distance
        return np.where(inside, -distances, distances)

    bbox = (0, -0.5, L, 1 + W + 0.5)

    return Domain(sdf=sdf, bbox=bbox)


if __name__ == "__main__":
    # Test fixture
    domain = make_basin_inlet(L=1000.0, W=1.0)
    print(f"Domain bbox: {domain.bbox}")
    print(f"Feature ratio: {1000.0 / 1.0}")

    # Test SDF at a few points
    test_pts = np.array(
        [
            [500, 0.5],  # Inside basin
            [500, 1.5],  # Inside inlet
            [500, 2.0],  # Outside
        ],
        dtype=np.float64,
    )
    signed_dist = domain.sdf(test_pts)
    print(f"Signed distances at test points: {signed_dist}")
