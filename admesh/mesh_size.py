"""Mesh-size field: iterative gradient-limited PDE solver.

Port of ``01_ADMESH_Library/09_Mesh_Size/MeshSizeIterativeSolver.c``
@ 19b2eb9 from C (MATLAB mex) to Python.

The C routine solves (to steady state) the upwind iteration

    h_{t+1}(i,j) = h_t(i,j) + (delta/2) * (min(|grad h|, g) - |grad h|)

over cells where ``D[i,j] <= 4 * hmin`` (boundary-ish region), with
``|grad h|`` computed from one-sided upwind differences of the current
``h_t``. The iteration terminates when the L1 residual falls below
``tol = 1e-5`` (MATLAB ``10e-6`` == 1e-5).

Parameter mapping (mex signature vs. Python):

    mex: MeshSizeIter(h0, D, hmax, hmin, g, delta) -> h
    py:  solve_iter(h0, D, hmax, hmin, g, delta) -> h

``hmax`` is accepted for API parity but unused in the C kernel (only
``hmin`` gates the update region).

Two implementations ship in-module:

- :func:`_solve_iter_py` — pure-NumPy reference. Vectorized row by row
  would break the serial cell-order update pattern of the mex, so we
  keep it a scalar loop.
- :func:`_solve_iter_nb` — Numba ``@njit`` acceleration of the same
  loop; enabled automatically when ``numba`` is importable.

``solve_iter`` dispatches to the Numba path by default; pass
``use_numba=False`` to force the pure-Python path (used for debugging
and for the parity test).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

try:
    import numba as _nb

    _HAVE_NUMBA = True
except ImportError:  # pragma: no cover
    _HAVE_NUMBA = False


_TOL = 1e-5


def _solve_iter_py(
    h0: NDArray[np.float64],
    D: NDArray[np.float64],
    hmin: float,
    g: float,
    delta: float,
) -> NDArray[np.float64]:
    h = h0.astype(np.float64, copy=True)
    LY, LX = h.shape
    deltat = delta / 2.0
    four_hmin = 4.0 * hmin

    while True:
        R = 0.0
        for i in range(1, LX - 1):
            for j in range(1, LY - 1):
                if D[j, i] > four_hmin:
                    continue

                xfor = min((h[j, i + 1] - h[j, i]) / delta, 0.0)
                xfor *= xfor
                xback = max((h[j, i] - h[j, i - 1]) / delta, 0.0)
                xback *= xback
                yfor = min((h[j + 1, i] - h[j, i]) / delta, 0.0)
                yfor *= yfor
                yback = max((h[j, i] - h[j - 1, i]) / delta, 0.0)
                yback *= yback

                Delta = (xfor + xback + yfor + yback) ** 0.5
                hn = h[j, i] + deltat * (min(Delta, g) - Delta)
                R += abs(hn - h[j, i])
                h[j, i] = hn

        if R <= _TOL:
            break

    return h


if _HAVE_NUMBA:

    @_nb.njit(cache=True)
    def _solve_iter_nb(
        h0: NDArray[np.float64],
        D: NDArray[np.float64],
        hmin: float,
        g: float,
        delta: float,
    ) -> NDArray[np.float64]:
        h = h0.copy()
        LY, LX = h.shape
        deltat = delta / 2.0
        four_hmin = 4.0 * hmin
        tol = 1e-5

        while True:
            R = 0.0
            for i in range(1, LX - 1):
                for j in range(1, LY - 1):
                    if D[j, i] > four_hmin:
                        continue
                    xfor = (h[j, i + 1] - h[j, i]) / delta
                    if xfor > 0.0:
                        xfor = 0.0
                    xfor *= xfor

                    xback = (h[j, i] - h[j, i - 1]) / delta
                    if xback < 0.0:
                        xback = 0.0
                    xback *= xback

                    yfor = (h[j + 1, i] - h[j, i]) / delta
                    if yfor > 0.0:
                        yfor = 0.0
                    yfor *= yfor

                    yback = (h[j, i] - h[j - 1, i]) / delta
                    if yback < 0.0:
                        yback = 0.0
                    yback *= yback

                    Delta = (xfor + xback + yfor + yback) ** 0.5
                    if Delta < g:
                        hn = h[j, i]
                    else:
                        hn = h[j, i] + deltat * (g - Delta)
                    R += abs(hn - h[j, i])
                    h[j, i] = hn

            if R <= tol:
                break

        return h


def solve_iter(
    h0: NDArray[np.float64],
    D: NDArray[np.float64],
    hmax: float,  # noqa: ARG001 — accepted for mex-signature parity
    hmin: float,
    g: float,
    delta: float,
    *,
    use_numba: bool = True,
) -> NDArray[np.float64]:
    """Solve the gradient-limited mesh-size field.

    See module docstring for the algorithm and parameter meaning.
    Returns a new array; ``h0`` is not mutated.
    """
    h0 = np.asarray(h0, dtype=np.float64)
    D = np.asarray(D, dtype=np.float64)
    if h0.shape != D.shape:
        raise ValueError("h0 and D must have the same shape")

    if use_numba and _HAVE_NUMBA:
        return _solve_iter_nb(h0, D, float(hmin), float(g), float(delta))
    return _solve_iter_py(h0, D, float(hmin), float(g), float(delta))
