"""Tests for triangulate(channel_refine=...) in boundary='fixed' mode."""
from __future__ import annotations

import numpy as np
import pytest

import admesh
from admesh.loaders import _domain_from_polygon


def _dumbbell():
    # Two 1x1 squares joined by a 0.05-wide, 1-long channel.
    return np.array([
        [0, 0], [1, 0], [1, 0.475], [2, 0.475], [2, 0], [3, 0], [3, 1],
        [2, 1], [2, 0.525], [1, 0.525], [1, 1], [0, 1],
    ], dtype=float)


def _dom():
    return _domain_from_polygon([_dumbbell()])


def _interior_in_channel(m, dom):
    x, y = m.nodes[:, 0], m.nodes[:, 1]
    inch = (x > 1.05) & (x < 1.95) & (np.abs(y - 0.5) < 0.025)
    return inch & (np.asarray(dom.sdf(m.nodes)) < -1e-9)


def test_default_refines_channel():
    dom = _dom()
    m_on = admesh.triangulate(dom, h_max=0.25, seed=0, boundary="fixed",
                              quality_gate=(0, 0))
    m_off = admesh.triangulate(dom, h_max=0.25, seed=0, boundary="fixed",
                               quality_gate=(0, 0), channel_refine=False)
    assert _interior_in_channel(m_on, dom).any()
    assert (m_on.quality < 0.3).sum() < (m_off.quality < 0.3).sum()


def test_user_size_field_disables():
    dom = _dom()
    uni = lambda p: np.full(len(np.atleast_2d(p)), 0.25)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        a = admesh.triangulate(dom, h_max=0.25, size_field=uni, seed=0,
                               boundary="fixed", quality_gate=(0, 0))
    with pytest.warns(UserWarning, match="channel_refine ignored"):
        b = admesh.triangulate(dom, h_max=0.25, size_field=uni, seed=0,
                               boundary="fixed", quality_gate=(0, 0),
                               channel_refine=True)
    assert len(a.nodes) == len(b.nodes)


def test_cost_guard_falls_back(monkeypatch):
    dom = _dom()
    import dataclasses
    big = dataclasses.replace(dom, bbox=(0.0, 0.0, 1e4, 1e4))
    import admesh._stages.mesh_size as ms

    def boom(*a, **k):
        raise AssertionError("build_h must not run")

    monkeypatch.setattr(ms, "build_h", boom)
    monkeypatch.setattr(admesh.api, "_routine_triangulate", None, raising=False)
    import admesh._stages.routine as routine
    monkeypatch.setattr(routine, "triangulate",
                        lambda *a, **k: (np.zeros((3, 2)), np.array([[0, 1, 2]])),
                        raising=True)
    with pytest.warns(UserWarning, match="too large for automatic channel"):
        try:
            admesh.triangulate(big, h_max=0.25, boundary="fixed",
                               quality_gate=(0, 0))
        except Exception as e:  # downstream steps may reject the stub mesh
            assert not isinstance(e, AssertionError)
