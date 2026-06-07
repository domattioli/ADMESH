"""Mesh visualization, delegated to the ``chilmesh`` package.

``admesh`` does not implement its own plotting; it converts a
:class:`admesh.api.Mesh` to a :class:`chilmesh.CHILmesh` and calls that
package's plot methods. ``chilmesh`` owns the matplotlib dependency. The
``[viz]`` extra in ``pyproject.toml`` pulls ``chilmesh`` in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from admesh.api import Mesh

__all__ = ["to_chilmesh", "plot_mesh", "plot_mesh_quality", "plot_mesh_layers"]

_VIZ_HINT = (
    "chilmesh is required for mesh plotting. "
    "Install with: pip install admesh2D[viz]"
)


def _require_chilmesh():
    try:
        from chilmesh import CHILmesh
    except ImportError as exc:  # pragma: no cover - exercised under monkeypatch
        raise ImportError(_VIZ_HINT) from exc
    return CHILmesh


def to_chilmesh(mesh: "Mesh"):
    """Wrap ``mesh`` as a :class:`chilmesh.CHILmesh` for plotting / analysis.

    Parameters
    ----------
    mesh : Mesh
        Source mesh; ``mesh.nodes`` and ``mesh.elements`` are passed straight
        through as the CHILmesh ``points`` and ``connectivity``.

    Returns
    -------
    chilmesh.CHILmesh
        A CHILmesh view of the same triangulation.

    Raises
    ------
    ImportError
        If ``chilmesh`` is not installed (``pip install admesh2D[viz]``).
    """
    CHILmesh = _require_chilmesh()
    return CHILmesh(connectivity=mesh.elements, points=mesh.nodes)


def plot_mesh(mesh: "Mesh", ax=None, **kwargs):
    """Draw the mesh wireframe via :meth:`chilmesh.CHILmesh.plot`.

    Parameters
    ----------
    mesh : Mesh
        The mesh to draw.
    ax : matplotlib.axes.Axes, optional
        Existing axes to draw onto. If ``None``, chilmesh creates a figure.
    **kwargs
        Forwarded to :meth:`chilmesh.CHILmesh.plot` (e.g. ``edge_color``,
        ``linewidth``, ``elem_color``).

    Returns
    -------
    matplotlib.axes.Axes
        The axes the mesh was drawn onto.

    Raises
    ------
    ImportError
        If ``chilmesh`` is not installed (``pip install admesh2D[viz]``).
    """
    _, ax = to_chilmesh(mesh).plot(ax=ax, **kwargs)
    return ax


def plot_mesh_quality(mesh: "Mesh", ax=None, cmap="cool", **kwargs):
    """Colormap elements by shape quality via :meth:`chilmesh.CHILmesh.plot_quality`.

    Parameters
    ----------
    mesh : Mesh
        The mesh to draw.
    ax : matplotlib.axes.Axes, optional
        Existing axes to draw onto. If ``None``, chilmesh creates a figure.
    cmap : str, optional
        Matplotlib colormap name (default: ``"cool"``).
    **kwargs
        Forwarded to :meth:`chilmesh.CHILmesh.plot_quality`.

    Returns
    -------
    matplotlib.axes.Axes
        The axes the mesh was drawn onto.

    Raises
    ------
    ImportError
        If ``chilmesh`` is not installed (``pip install admesh2D[viz]``).
    """
    _, ax = to_chilmesh(mesh).plot_quality(ax=ax, cmap=cmap, **kwargs)
    return ax


def plot_mesh_layers(mesh: "Mesh", ax=None, cmap="viridis", **kwargs):
    """Color elements by onion-peel layer via :meth:`chilmesh.CHILmesh.plot_layer`.

    Parameters
    ----------
    mesh : Mesh
        The mesh to draw.
    ax : matplotlib.axes.Axes, optional
        Existing axes to draw onto. If ``None``, chilmesh creates a figure.
    cmap : str, optional
        Matplotlib colormap name (default: ``"viridis"``).
    **kwargs
        Forwarded to :meth:`chilmesh.CHILmesh.plot_layer`.

    Returns
    -------
    matplotlib.axes.Axes
        The axes the mesh was drawn onto.

    Raises
    ------
    ImportError
        If ``chilmesh`` is not installed (``pip install admesh2D[viz]``).
    """
    _, ax = to_chilmesh(mesh).plot_layer(cmap=cmap, ax=ax, **kwargs)
    return ax
