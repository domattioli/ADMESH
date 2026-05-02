"""Mesh-quality metrics.

Port of ``01_ADMESH_Library/11_Mesh_Quality/MeshQuality.m`` @ 19b2eb9.

Supported element types:

- ``"triangle"``: ``q = (b+c-a)(c+a-b)(a+b-c) / (a*b*c)`` where
  ``a, b, c`` are edge lengths. Equivalent to ``2 * r_in / r_out``.
  Equilateral triangle ⇒ q = 1; degenerate (collinear) ⇒ q ≈ 0.
- ``"quad"``: ``q = prod(1 - |pi/2 - theta| / (pi/2))`` over the four
  per-vertex angles as MATLAB computes them. Perfect square ⇒ q = 1.

Additive (spec-004): ``right_iso_quality`` measures deviation from a
right-isoceles target shape. Companion to ``mesh_quality`` for the
pre-quadrangulation smoother. The original ``mesh_quality`` is NOT
modified (FR-006, Constitution Principle I).
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


def right_iso_quality(
    p: ArrayLike,
    t: ArrayLike,
) -> float:
    """Mesh-wide right-isoceles quality score in ``[0, 1]``.

    Companion to :func:`mesh_quality` (which scores deviation from
    equilateral). Reported side-by-side as a delta after running
    :func:`admesh.quad_prep.smooth_for_quadrangulation` (spec-004 SC-007).

    Per-element score is the product of three terms in ``[0, 1]``:

    1. Leg-equality:    ``1 - |L1 - L2| / max(L1, L2)``
    2. Right-angle:     ``1 - |angle_apex - π/2| / (π/2)``
    3. Hypotenuse-fit:  ``1 - |L_hyp - sqrt(2) * (L1+L2)/2| / L_hyp``

    where ``L1, L2`` are the two shortest sides (legs), ``L_hyp`` is the
    longest (hypotenuse), and ``angle_apex`` is the angle between the
    two legs. The mesh score is the unweighted mean over elements.

    The existing :func:`mesh_quality` is NOT modified — this is purely
    additive (spec-004 FR-006).

    Parameters
    ----------
    p : array_like, shape (N, 2)
        Nodal coordinates.
    t : array_like, shape (M, 3)
        Triangle connectivity (0-based).

    Returns
    -------
    float
        Mesh-wide right-isoceles quality, in ``[0, 1]``. ``1.0`` means
        every element is exactly right-isoceles. Empty mesh returns
        ``1.0`` (vacuously perfect).
    """
    p = np.asarray(p, dtype=float)
    t = np.asarray(t, dtype=int)

    if p.ndim != 2 or p.shape[1] != 2:
        raise ValueError("p must be (N, 2)")
    if t.ndim != 2 or t.shape[1] != 3:
        raise ValueError("t must be (M, 3)")

    if len(t) == 0:
        return 1.0

    x = p[:, 0]
    y = p[:, 1]

    a = np.hypot(x[t[:, 1]] - x[t[:, 0]], y[t[:, 1]] - y[t[:, 0]])
    b = np.hypot(x[t[:, 2]] - x[t[:, 1]], y[t[:, 2]] - y[t[:, 1]])
    c = np.hypot(x[t[:, 0]] - x[t[:, 2]], y[t[:, 0]] - y[t[:, 2]])

    sides = np.column_stack([a, b, c])
    sides_sorted = np.sort(sides, axis=1)
    L1 = sides_sorted[:, 0]
    L2 = sides_sorted[:, 1]
    L_hyp = sides_sorted[:, 2]

    with np.errstate(divide="ignore", invalid="ignore"):
        leg_eq = np.where(
            L2 > 0, 1.0 - np.abs(L1 - L2) / np.maximum(L2, 1e-300), 0.0
        )

    cos_apex = (L1 * L1 + L2 * L2 - L_hyp * L_hyp) / (2.0 * L1 * L2)
    cos_apex = np.where(np.isfinite(cos_apex), cos_apex, 1.0)
    cos_apex = np.clip(cos_apex, -1.0, 1.0)
    angle_apex = np.arccos(cos_apex)
    right_angle = 1.0 - np.abs(angle_apex - np.pi / 2.0) / (np.pi / 2.0)

    target_hyp = np.sqrt(2.0) * (L1 + L2) / 2.0
    with np.errstate(divide="ignore", invalid="ignore"):
        hyp_fit = np.where(
            L_hyp > 0, 1.0 - np.abs(L_hyp - target_hyp) / L_hyp, 0.0
        )

    leg_eq = np.clip(leg_eq, 0.0, 1.0)
    right_angle = np.clip(right_angle, 0.0, 1.0)
    hyp_fit = np.clip(hyp_fit, 0.0, 1.0)

    q = leg_eq * right_angle * hyp_fit
    q = np.where(np.isfinite(q), q, 0.0)
    q = np.clip(q, 0.0, 1.0)

    return float(q.mean())
