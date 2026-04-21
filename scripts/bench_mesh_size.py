"""Benchmark the Numba vs. pure-Python mesh-size solver.

Runs :func:`admesh.mesh_size.solve_iter` with ``use_numba=True`` and
``use_numba=False`` on a representative synthetic input (a radial
distance field with a small central size, gradient-limited by ``g``).
Reports wall-clock per call plus the Numba speedup.

The Numba path's first call is dominated by JIT compilation — the
benchmark warms up once, then times the steady-state runs.

Run:
    python scripts/bench_mesh_size.py
"""

from __future__ import annotations

import time

import numpy as np

from admesh.mesh_size import solve_iter


def _make_inputs(n: int) -> tuple[np.ndarray, np.ndarray]:
    """Synthetic ``(h0, D)`` pair on an ``n x n`` grid."""
    xs = np.linspace(-1.0, 1.0, n)
    ys = np.linspace(-1.0, 1.0, n)
    X, Y = np.meshgrid(xs, ys, indexing="xy")
    D = np.hypot(X, Y)
    # A "size" field that's small near the center, large at the edges;
    # the solver propagates the small size outward under grad limit g.
    h0 = 0.02 + 0.18 * D
    return h0, D


def _time_one(fn, n_runs: int) -> float:
    t0 = time.perf_counter()
    for _ in range(n_runs):
        fn()
    return (time.perf_counter() - t0) / n_runs


def main(n: int = 200, n_runs: int = 3) -> None:
    h0, D = _make_inputs(n)
    hmax, hmin, g, delta = 0.2, 0.02, 0.2, (2.0 / (n - 1))

    # Warm up Numba JIT (first call compiles).
    solve_iter(h0, D, hmax, hmin, g, delta, use_numba=True)

    t_nb = _time_one(
        lambda: solve_iter(h0, D, hmax, hmin, g, delta, use_numba=True),
        n_runs=n_runs,
    )
    t_py = _time_one(
        lambda: solve_iter(h0, D, hmax, hmin, g, delta, use_numba=False),
        n_runs=1,  # py path is slow; one run is enough
    )

    # Sanity: the two paths agree.
    h_nb = solve_iter(h0, D, hmax, hmin, g, delta, use_numba=True)
    h_py = solve_iter(h0, D, hmax, hmin, g, delta, use_numba=False)
    max_abs = float(np.max(np.abs(h_nb - h_py)))

    print(f"Grid: {n}x{n}")
    print(f"Numba (avg of {n_runs}): {t_nb * 1000:.2f} ms")
    print(f"Python (1 run):          {t_py * 1000:.2f} ms")
    print(f"Speedup (py/nb):         {t_py / t_nb:.1f}x")
    print(f"Max |nb - py|:           {max_abs:.2e}")


if __name__ == "__main__":
    main()
