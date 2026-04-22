"""Tests for admesh.mesh_size."""

import numpy as np
import pytest

from admesh import domains
from admesh.mesh_size import _HAVE_NUMBA, build_h, solve_iter
from admesh.quality import mesh_quality
from admesh.routine import triangulate


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


# --------------------------- build_h composer --------------------------------


def test_build_h_defaults_to_uniform() -> None:
    """With no enrichment, build_h returns a uniform-``base`` callable."""
    fh = build_h(domains.UNIT_DISK, base=0.12)
    p = np.array([[0.0, 0.0], [0.5, 0.3], [-0.2, 0.4]])
    np.testing.assert_allclose(fh(p), 0.12)


def test_build_h_curvature_shrinks_with_curvature() -> None:
    """On the unit disk ``κ = 1/r``: high-κ region (near origin) gets
    smaller h than low-κ region (near boundary)."""
    fh = build_h(
        domains.UNIT_DISK, base=0.2, curvature_scale=0.05,
        grid_delta=0.02,
    )
    hi_kappa = np.array([[0.15, 0.0]])   # r≈0.15 → κ≈6.7
    lo_kappa = np.array([[0.9, 0.0]])    # r≈0.9  → κ≈1.1
    assert fh(hi_kappa)[0] < fh(lo_kappa)[0]
    # And both are bounded below by curvature_scale after smoothing.
    assert fh(hi_kappa)[0] >= 0.05 - 1e-9


def test_build_h_medial_refines_at_medial() -> None:
    """``medial_scale`` enables LFS-style refinement: h is smallest
    AT the medial axis (narrow-feature refinement) and grows toward
    the boundary. On the annulus, medial is r=0.7."""
    fh = build_h(
        domains.ANNULUS, base=0.2, medial_scale=0.03,
        grid_delta=0.02,
    )
    at_medial = np.array([[0.7, 0.0]])
    off_medial = np.array([[0.95, 0.0]])
    assert fh(at_medial)[0] < fh(off_medial)[0]


def test_triangulate_accepts_composed_fh() -> None:
    """End-to-end: triangulate(..., fh=build_h(...)) produces a valid
    mesh whose min/mean quality still pass the M.4 gate."""
    dom = domains.UNIT_DISK
    fh = build_h(dom, base=0.15, curvature_scale=0.05, grid_delta=0.03)
    p, t = triangulate(dom, h0=0.15, fh=fh, niter=150, seed=0)
    assert len(p) >= 20 and len(t) >= 20
    min_q, mean_q, _ = mesh_quality(p, t)
    assert min_q >= 0.30
    assert mean_q >= 0.55  # slightly looser — enriched fh makes meshes less uniform
