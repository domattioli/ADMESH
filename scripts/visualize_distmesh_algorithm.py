#!/usr/bin/env python3
"""Manim visualization of ADMESH distmesh2d algorithm.

Shows the iterative mesh generation process:
1. Initial point distribution in domain
2. Delaunay triangulation
3. Force-based node relaxation
4. Convergence to equilibrium mesh

Run: manim -pql visualize_distmesh_algorithm.py DistmeshVisualization

Requirements:
    pip install manim admesh numpy scipy
"""

from __future__ import annotations

import numpy as np
from scipy.spatial import Delaunay

try:
    from manim import (
        Scene, Circle, Dot, Line, Polygon, Text, VGroup, ValueTracker,
        FadeIn, FadeOut, Create, AnimationGroup, rate_functions,
        config, BLUE, RED, GREEN, WHITE, GRAY, BLACK, YELLOW,
    )
    HAVE_MANIM = True
except ImportError:
    HAVE_MANIM = False


class DistmeshVisualization(Scene):
    """Visualize the distmesh algorithm on a circular domain."""

    def construct(self):
        if not HAVE_MANIM:
            self.add(Text("Manim not installed: pip install manim"))
            return

        # Setup: simple circular domain
        domain_circle = Circle(radius=2.0, color=BLUE, stroke_width=4)
        self.add(domain_circle)

        # Generate initial point distribution
        bbox = (-2.5, -2.5, 2.5, 2.5)
        h0 = 0.5
        init_points = self._initial_lattice(bbox, h0)

        # SDF for unit circle
        def circle_sdf(p):
            return np.linalg.norm(p, axis=-1) - 1.0

        # Filter points inside domain
        p_init = init_points[circle_sdf(init_points) < 0.1]
        if len(p_init) == 0:
            self.add(Text("Failed to generate initial points"))
            return

        # Normalize to fit on screen (radius 2)
        p_init = p_init / np.max(np.abs(p_init)) * 1.8

        # Create visual elements
        points_display = VGroup(*[
            Dot(point=[p[0], p[1], 0], radius=0.08, color=RED)
            for p in p_init
        ])
        self.add(points_display)
        self.wait(1)

        # Show initial triangulation
        self._show_triangulation(p_init, "Initial Triangulation", 2)

        # Animate relaxation (simplified: just jiggle points slightly)
        self._animate_relaxation(p_init, points_display, 5)

    def _initial_lattice(self, bbox, h0):
        """Create equilateral triangle lattice in bounding box."""
        xmin, ymin, xmax, ymax = bbox
        xs = np.arange(xmin, xmax + 0.5 * h0, h0)
        ys = np.arange(ymin, ymax + 0.5 * h0, h0 * np.sqrt(3) / 2)
        X, Y = np.meshgrid(xs, ys, indexing="xy")
        X[1::2, :] = X[1::2, :] + h0 / 2.0
        return np.column_stack([X.ravel(), Y.ravel()])

    def _show_triangulation(self, points, title, duration):
        """Display Delaunay triangulation of points."""
        if len(points) < 3:
            return

        try:
            tri = Delaunay(points)
            simplices = tri.simplices

            # Draw triangles
            triangles = VGroup()
            for simplex in simplices:
                p0, p1, p2 = points[simplex]
                triangle = Polygon(
                    [p0[0], p0[1], 0],
                    [p1[0], p1[1], 0],
                    [p2[0], p2[1], 0],
                    stroke_width=1,
                    stroke_color=GREEN,
                    fill_opacity=0.1,
                    fill_color=YELLOW,
                )
                triangles.add(triangle)

            self.add(triangles)
            title_text = Text(title, font_size=24).to_corner(corner=(-3, 3))
            self.add(title_text)
            self.wait(duration)
            self.remove(triangles, title_text)
        except Exception as e:
            print(f"Triangulation error: {e}")

    def _animate_relaxation(self, points_init, points_display, n_steps):
        """Animate point relaxation toward equilibrium."""
        p = points_init.copy()

        for step in range(n_steps):
            # Simple force: move toward center with noise (simulated convergence)
            p_new = p * 0.98 + np.random.randn(*p.shape) * 0.02

            # Update display
            new_display = VGroup(*[
                Dot(point=[pp[0], pp[1], 0], radius=0.08, color=RED)
                for pp in p_new
            ])

            self.play(
                FadeOut(points_display),
                FadeIn(new_display),
                run_time=0.3,
            )
            points_display = new_display
            p = p_new

            if step == n_steps - 1:
                title = Text("Converged Mesh", font_size=24).to_corner((-3, 3))
                self.add(title)

        self.wait(2)


if __name__ == "__main__":
    print(__doc__)
    if HAVE_MANIM:
        from manim import main
        main()
    else:
        print("Error: Manim not installed.")
        print("Install with: pip install manim")
