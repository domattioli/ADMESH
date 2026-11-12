"""Tests for the API-layer gradient limiter ``admesh.size_field.limit_gradient``."""

from __future__ import annotations

import numpy as np

from admesh.size_field import limit_gradient

BBOX = (0.0, 0.0, 2.0, 1.0)


def _step(p: np.ndarray) -> np.ndarray:
    p = np.atleast_2d(p)
    return np.where(p[:, 0] < 1.0, 0.03, 0.25)


def _central_grad_max(fn, pts: np.ndarray, eps: float = 0.005) -> float:
    gx = (fn(pts + [eps, 0.0]) - fn(pts - [eps, 0.0])) / (2 * eps)
    gy = (fn(pts + [0.0, eps]) - fn(pts - [0.0, eps])) / (2 * eps)
    return float(np.max(np.hypot(gx, gy)))


def test_step_field_gradient_is_limited():
    rng = np.random.default_rng(0)
    # Keep interior points away from the bbox edge so the finite-difference
    # stencil stays inside the limited region.
    pts = np.c_[rng.uniform(0.05, 1.95, 2000), rng.uniform(0.05, 0.95, 2000)]
    h_lim = limit_gradient(_step, BBOX, g=0.2, delta=0.01)
    assert _central_grad_max(h_lim, pts) <= 0.2 * 1.5


def test_output_never_exceeds_input():
    rng = np.random.default_rng(1)
    pts = np.c_[rng.uniform(0.0, 2.0, 2000), rng.uniform(0.0, 1.0, 2000)]
    h_lim = limit_gradient(_step, BBOX, g=0.2, delta=0.01)
    assert np.all(h_lim(pts) <= _step(pts) + 2 * 0.2 * 0.01)  # bilinear overshoot <= ~g*delta


def test_uniform_field_unchanged():
    def uniform(p: np.ndarray) -> np.ndarray:
        return np.full(np.atleast_2d(p).shape[0], 0.1)

    rng = np.random.default_rng(2)
    pts = np.c_[rng.uniform(0.0, 2.0, 500), rng.uniform(0.0, 1.0, 500)]
    h_lim = limit_gradient(uniform, BBOX, g=0.2, delta=0.01)
    np.testing.assert_allclose(h_lim(pts), 0.1, atol=1e-9)
