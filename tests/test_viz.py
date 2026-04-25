"""Tests for ``Mesh.plot`` and the matplotlib-import fallback (T018)."""

from __future__ import annotations

import sys

import numpy as np
import pytest

from admesh import BoundarySegment, BoundaryType, Mesh


def _toy_mesh() -> Mesh:
    nodes = np.array(
        [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]], dtype=np.float64
    )
    elements = np.array([[0, 1, 2], [1, 3, 2]], dtype=np.int64)
    seg = BoundarySegment(
        node_ids=np.array([0, 1, 3, 2], dtype=np.int64),
        bc_type=BoundaryType.MAINLAND,
        is_open=False,
    )
    return Mesh(nodes=nodes, elements=elements, boundaries=(seg,))


def test_plot_returns_axes_when_matplotlib_present():
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")  # non-interactive backend for CI
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    result = _toy_mesh().plot(ax=ax)
    assert result is ax
    # At least one Line2D / Triangulation artist was added.
    assert len(ax.lines) > 0 or len(ax.collections) > 0
    plt.close(fig)


def test_plot_creates_axes_when_none_supplied():
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ax = _toy_mesh().plot()
    assert ax is not None
    plt.close(ax.figure)


def test_plot_raises_importerror_when_matplotlib_missing(monkeypatch):
    """Simulate matplotlib-not-installed by intercepting the import."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "matplotlib.pyplot":
            raise ImportError("simulated missing matplotlib")
        if name.startswith("matplotlib"):
            raise ImportError("simulated missing matplotlib")
        return real_import(name, *args, **kwargs)

    # Drop any cached matplotlib so the fresh import runs through fake_import.
    for key in list(sys.modules):
        if key == "matplotlib" or key.startswith("matplotlib."):
            monkeypatch.delitem(sys.modules, key, raising=False)
    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ImportError, match=r"admesh2D\[viz\]"):
        _toy_mesh().plot()
