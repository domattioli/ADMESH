"""Tests for admesh.mesh_size."""

import numpy as np
import pytest

from admesh.mesh_size import _HAVE_NUMBA, solve_iter


def _make_inputs(n: int = 21, delta: float = 0.05) -> tuple[np.ndarray, np.ndarray]:
    # Simple setup: 21x21 grid, h0 linear ramp 0.05..0.25 in x; D = 0 everywhere
    # (so the entire interior updates — boundary cells are untouched).
    xs = np.linspace(0, 1, n)
    h0 = np.broadcast_to(np.linspace(0.05, 0.25, n)[None, :], (n, n)).copy()
    D = np.zeros((n, n), dtype=float)
    return h0, D


def test_solve_iter_returns_same_shape() -> None:
    h0, D = _make_inputs()
    h = solve_iter(h0, D, hmax=0.3, hmin=0.02, g=0.1, delta=0.05, use_numba=False)
    assert h.shape == h0.shape


def test_solve_iter_does_not_mutate_input() -> None:
    h0, D = _make_inputs()
    h0_copy = h0.copy()
    _ = solve_iter(h0, D, hmax=0.3, hmin=0.02, g=0.1, delta=0.05, use_numba=False)
    np.testing.assert_array_equal(h0, h0_copy)


def test_solve_iter_limits_gradient() -> None:
    # After solving with growth rate g, the resulting field's forward-difference
    # magnitude should everywhere in the UPDATED region be ≤ g + numerical slop.
    # The solver does not touch border cells (i in {0, LX-1}, j in {0, LY-1}),
    # so if those borders aren't themselves consistent with |grad h| ≤ g, a
    # cliff will form against the border; we exclude the border strip from
    # the check.
    h0, D = _make_inputs(n=15, delta=0.05)
    g = 0.1
    h = solve_iter(h0, D, hmax=0.3, hmin=0.02, g=g, delta=0.05, use_numba=False)
    # Interior-only diffs: drop two border cells on each side so the remaining
    # differences are all between updated cells.
    interior = h[2:-2, 2:-2]
    dh_dx = np.abs(np.diff(interior, axis=1)) / 0.05
    dh_dy = np.abs(np.diff(interior, axis=0)) / 0.05
    assert dh_dx.max() <= g + 5e-3
    assert dh_dy.max() <= g + 5e-3


def test_solve_iter_constant_field_is_fixed_point() -> None:
    h0 = np.full((11, 11), 0.1)
    D = np.zeros_like(h0)
    h = solve_iter(h0, D, hmax=0.3, hmin=0.02, g=0.05, delta=0.1, use_numba=False)
    np.testing.assert_allclose(h, h0, atol=1e-12)


@pytest.mark.skipif(not _HAVE_NUMBA, reason="numba not available")
def test_solve_iter_numba_matches_python() -> None:
    h0, D = _make_inputs(n=15, delta=0.05)
    h_py = solve_iter(h0, D, hmax=0.3, hmin=0.02, g=0.1, delta=0.05, use_numba=False)
    h_nb = solve_iter(h0, D, hmax=0.3, hmin=0.02, g=0.1, delta=0.05, use_numba=True)
    np.testing.assert_allclose(h_py, h_nb, atol=1e-10)


def test_solve_iter_gated_by_hmin() -> None:
    # When D > 4*hmin everywhere, NO cells update — output equals h0.
    h0, _ = _make_inputs()
    D = np.full_like(h0, 1.0)  # large D gates out all cells
    h = solve_iter(h0, D, hmax=0.3, hmin=0.02, g=0.1, delta=0.05, use_numba=False)
    np.testing.assert_array_equal(h, h0)
