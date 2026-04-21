"""Shared test helpers for the ADMESH suite."""

from __future__ import annotations

import numpy as np


def assert_valid_mesh(
    p: np.ndarray, t: np.ndarray, fd, geps: float, min_n: int = 4
) -> None:
    """Structural + geometric sanity checks shared across domain tests.

    Asserts that ``(p, t)`` is a valid mesh of the domain defined by
    signed-distance function ``fd``:

    - ``p`` is ``(N, 2)`` with ``N >= min_n``.
    - ``t`` is ``(M, 3)`` with every index in ``[0, N)``.
    - Every triangle centroid lies inside the domain (``fd(c) < geps``).
    - Every triangle has positive signed area (consistent CCW orientation).
    """
    assert p.ndim == 2 and p.shape[1] == 2
    assert t.ndim == 2 and t.shape[1] == 3
    assert len(p) >= min_n
    assert len(t) >= 1
    assert t.max() < len(p)
    assert t.min() >= 0
    centroids = (p[t[:, 0]] + p[t[:, 1]] + p[t[:, 2]]) / 3.0
    assert (fd(centroids) < geps).all(), "some triangle centroid is outside the domain"
    d12 = p[t[:, 1]] - p[t[:, 0]]
    d13 = p[t[:, 2]] - p[t[:, 0]]
    area = 0.5 * (d12[:, 0] * d13[:, 1] - d12[:, 1] * d13[:, 0])
    assert (area > 0).all()
