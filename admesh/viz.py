"""Optional matplotlib visualization for :class:`admesh.api.Mesh` (T028).

Lazily imports matplotlib inside :func:`plot_mesh` so the package can be
imported (and the rest of the API used) without matplotlib installed.
The ``[viz]`` extra in ``pyproject.toml`` pulls it in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from admesh.boundary_types import BoundaryType

if TYPE_CHECKING:
    from admesh.api import Mesh

__all__ = ["plot_mesh", "plot_mesh_layers"]


_BC_COLORS = {
    BoundaryType.OPEN: "#1f77b4",          # blue — open ocean
    BoundaryType.MAINLAND: "#2ca02c",       # green — mainland
    BoundaryType.ISLAND: "#ff7f0e",         # orange — island
    BoundaryType.MAINLAND_FLUX: "#d62728",  # red — flux-specified mainland
}
_DEFAULT_BC_COLOR = "#7f7f7f"               # grey — unmapped numeric codes


def plot_mesh(mesh: "Mesh", ax=None, **kwargs):
    """Render ``mesh`` with matplotlib.

    Parameters
    ----------
    mesh : Mesh
        The mesh to draw.
    ax : matplotlib.axes.Axes, optional
        Existing axes to draw onto. If ``None``, a new figure + axes are
        created.
    **kwargs
        Forwarded to ``ax.triplot``.

    Returns
    -------
    matplotlib.axes.Axes
        The axes the mesh was drawn onto.

    Raises
    ------
    ImportError
        If matplotlib is not installed. Install with::

            pip install admesh2D[viz]
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - exercised under monkeypatch
        raise ImportError(
            "matplotlib is required for mesh.plot(). "
            "Install with: pip install admesh2D[viz]"
        ) from exc

    if ax is None:
        _, ax = plt.subplots()

    # Triangulation.
    triplot_kwargs = {"color": "#999999", "linewidth": 0.4}
    triplot_kwargs.update(kwargs)
    ax.triplot(
        mesh.nodes[:, 0],
        mesh.nodes[:, 1],
        mesh.elements,
        **triplot_kwargs,
    )

    # Boundary segments coloured by BC type.
    for seg in mesh.boundaries:
        if seg.node_ids.size < 2:
            continue
        bc = seg.bc_type
        color = _BC_COLORS.get(bc, _DEFAULT_BC_COLOR) if isinstance(bc, BoundaryType) else _DEFAULT_BC_COLOR
        ring = mesh.nodes[seg.node_ids]
        # Close the ring visually.
        closed = np.vstack([ring, ring[:1]]) if not np.array_equal(ring[0], ring[-1]) else ring
        ax.plot(closed[:, 0], closed[:, 1], color=color, linewidth=1.2)

    ax.set_aspect("equal")
    return ax


def plot_mesh_layers(mesh: "Mesh", ax=None, cmap="viridis", **kwargs):
    """Render mesh layers (onion-peel BFS from boundary) with colors.

    Computes layers via breadth-first search from boundary elements (those with
    a one-owner edge). Each layer is colored distinctly; a colorbar maps layer
    index to color.

    Parameters
    ----------
    mesh : Mesh
        The mesh to draw.
    ax : matplotlib.axes.Axes, optional
        Existing axes to draw onto. If ``None``, a new figure + axes are
        created.
    cmap : str, optional
        Colormap name (default: "viridis").
    **kwargs
        Forwarded to ``ax.tripcolor`` (e.g. edgecolors, linewidth).

    Returns
    -------
    matplotlib.axes.Axes
        The axes the mesh was drawn onto.

    Raises
    ------
    ImportError
        If matplotlib is not installed.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "matplotlib is required for mesh.plot_layers(). "
            "Install with: pip install admesh2D[viz]"
        ) from exc

    if ax is None:
        _, ax = plt.subplots()

    # Compute layers via BFS from boundary.
    layers = _compute_mesh_layers(mesh.elements)
    layer_ids = np.arange(mesh.elements.shape[0])
    for layer_idx, elem_indices in enumerate(layers):
        layer_ids[elem_indices] = layer_idx

    # Color each element by layer.
    tripcolor_kwargs = {"cmap": cmap, "edgecolors": "k", "linewidth": 0.5, "alpha": 0.7}
    tripcolor_kwargs.update(kwargs)

    coll = ax.tripcolor(
        mesh.nodes[:, 0],
        mesh.nodes[:, 1],
        mesh.elements,
        facecolors=layer_ids,
        vmin=0,
        vmax=len(layers) - 1,
        **tripcolor_kwargs,
    )

    cbar = plt.colorbar(coll, ax=ax, label="Layer index")
    ax.set_aspect("equal")
    return ax


def _compute_mesh_layers(elements):
    """Compute layers via onion-peel BFS from boundary elements.

    A boundary element has at least one edge owned by exactly one triangle
    (no neighbor across that edge). Returns a list of arrays, where each
    array contains the element indices in that layer.
    """
    n_elem = len(elements)

    # Build edge-to-element adjacency.
    edge_to_elem = {}
    for e_idx in range(n_elem):
        tri = elements[e_idx]
        edges = [(tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])]
        for u, v in edges:
            key = (min(u, v), max(u, v))
            if key not in edge_to_elem:
                edge_to_elem[key] = []
            edge_to_elem[key].append(e_idx)

    # Identify boundary elements (at least one edge with only one owner).
    boundary_elems = set()
    for edge_key, elem_list in edge_to_elem.items():
        if len(elem_list) == 1:
            boundary_elems.add(elem_list[0])

    # BFS layers.
    visited = set()
    layers = []
    current_layer = list(boundary_elems)

    while current_layer:
        visited.update(current_layer)
        layers.append(np.array(current_layer, dtype=np.int64))

        # Find neighbors of current layer.
        next_layer = set()
        for e_idx in current_layer:
            tri = elements[e_idx]
            edges = [(tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])]
            for u, v in edges:
                key = (min(u, v), max(u, v))
                for nbr_idx in edge_to_elem.get(key, []):
                    if nbr_idx not in visited:
                        next_layer.add(nbr_idx)

        current_layer = list(next_layer)

    return layers
