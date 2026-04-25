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

__all__ = ["plot_mesh"]


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
