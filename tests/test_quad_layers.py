"""Smoke tests for the additive quad_layers prototype (quarter annulus)."""
import numpy as np

from admesh.quad_layers import _peel_rings, quad_layer_mesh, resample_boundary

RO, RI, H = 152.4, 60.96, 7.62


def _loop(m=200):
    a = np.linspace(0, np.pi / 2, m)
    loop = np.vstack([
        np.c_[np.linspace(RI, RO, m)[:-1], np.zeros(m - 1)],
        np.c_[RO * np.cos(a), RO * np.sin(a)][:-1],
        np.c_[np.zeros(m - 1), np.linspace(RO, RI, m)[:-1]],
        np.c_[RI * np.cos(a[::-1]), RI * np.sin(a[::-1])][:-1],
    ])
    return loop, [0, m - 1, 2 * (m - 1), 3 * (m - 1)]


def _fh(P):
    return np.full(len(np.atleast_2d(P)), H)


def test_boundary_prepass_even_and_on_size():
    loop, corners = _loop()
    b, cm = resample_boundary(loop, corners, _fh)
    assert len(b) % 2 == 0 and cm.sum() == 4
    e = np.hypot(*(np.roll(b, -1, 0) - b).T) / H
    assert e.min() > 0.9 and e.max() < 1.1


def test_layered_mesh_rings_even_and_corner_quads():
    loop, corners = _loop()
    r = quad_layer_mesh(loop, corners, _fh, niter=30, freeze=5)
    P, T = r["points"], r["elements"]
    u, w = P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]]
    a = u[:, 0] * w[:, 1] - u[:, 1] * w[:, 0]
    assert np.all(np.abs(a) > 1e-9)
    assert all(n % 2 == 0 for n in _peel_rings(T))
    for c in loop[corners]:
        v = int(np.argmin(np.hypot(*(P - c).T)))
        assert int((T == v).any(1).sum()) == 2
