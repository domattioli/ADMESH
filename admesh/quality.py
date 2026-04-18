"""Mesh-quality metrics.

Port of ``01_ADMESH_Library/11_Mesh_Quality/MeshQuality.m`` @ 19b2eb9.

Supported element types:

- ``"triangle"``: ``q = (b+c-a)(c+a-b)(a+b-c) / (a*b*c)`` where
  ``a, b, c`` are edge lengths. Equivalent to ``2 * r_in / r_out``.
  Equilateral triangle ⇒ q = 1; degenerate (collinear) ⇒ q ≈ 0.
- ``"quad"``: ``q = prod(1 - |pi/2 - theta| / (pi/2))`` over the four
  per-vertex angles as MATLAB computes them. Perfect square ⇒ q = 1.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


def mesh_quality(
    p: ArrayLike,
    t: ArrayLike,
    element: str = "triangle",
) -> tuple[float, float, NDArray[np.float64]]:
    """Element-quality statistics.

    Parameters
    ----------
    p : array_like, shape (n, 2)
        Nodal coordinates.
    t : array_like, shape (m, 3) or (m, 4)
        Connectivity list (0-based, per the port's indexing convention).
    element : {"triangle", "quad"}
        Element type.

    Returns
    -------
    min_q : float
    mean_q : float
    q : ndarray, shape (m,)
        Per-element quality in [0, 1].
    """
    p = np.asarray(p, dtype=float)
    t = np.asarray(t, dtype=int)

    if p.ndim != 2 or p.shape[1] != 2:
        raise ValueError("p must be (n, 2)")

    x = p[:, 0]
    y = p[:, 1]

    if element == "triangle":
        if t.shape[1] != 3:
            raise ValueError("triangle connectivity must have 3 columns")
        a = np.hypot(x[t[:, 1]] - x[t[:, 0]], y[t[:, 1]] - y[t[:, 0]])
        b = np.hypot(x[t[:, 2]] - x[t[:, 1]], y[t[:, 2]] - y[t[:, 1]])
        c = np.hypot(x[t[:, 0]] - x[t[:, 2]], y[t[:, 0]] - y[t[:, 2]])
        denom = a * b * c
        with np.errstate(divide="ignore", invalid="ignore"):
            q = np.where(
                denom > 0,
                ((b + c - a) * (c + a - b) * (a + b - c)) / denom,
                0.0,
            )
    elif element == "quad":
        if t.shape[1] != 4:
            raise ValueError("quad connectivity must have 4 columns")
        fx = np.column_stack([x[t[:, (k + 1) % 4]] - x[t[:, k]] for k in range(4)])
        fy = np.column_stack([y[t[:, (k + 1) % 4]] - y[t[:, k]] for k in range(4)])
        ax = fx
        ay = fy
        bx = np.roll(fx, -1, axis=1)
        by = np.roll(fy, -1, axis=1)
        dot = ax * bx + ay * by
        na = np.hypot(ax, ay)
        nb = np.hypot(bx, by)
        with np.errstate(divide="ignore", invalid="ignore"):
            cos_theta = np.clip(dot / (na * nb), -1.0, 1.0)
        theta = np.arccos(cos_theta)
        per_angle = 1.0 - np.abs((np.pi / 2 - theta) / (np.pi / 2))
        q = np.prod(per_angle, axis=1)
    else:
        raise ValueError(f"unknown element type: {element!r}")

    q = np.clip(q, 0.0, 1.0)
    return float(q.min()), float(q.mean()), q
