"""C++ distmesh2d acceleration (optional).

Provides fast iterative force-balance solver for distmesh2d.
Falls back to pure-Python Numba if C++ extension unavailable.
"""

import logging
import numpy as np

log = logging.getLogger(__name__)

# Try to import C++ extension
try:
    from admesh._cpp._distmesh_cpp import distmesh2d_step as _distmesh2d_step_cpp
    HAS_CPP_DISTMESH = True
    log.info("[distmesh C++] C++ extension loaded (v1.0.0alpha)")
except ImportError:
    HAS_CPP_DISTMESH = False
    log.debug("[distmesh C++] C++ extension not available; using Numba fallback")


def distmesh2d_step(p, bars, h_bars, Fscale=1.2, deltat=0.2, nfix=0):
    """
    One iteration of distmesh2d force-balance update.

    Uses C++ acceleration (Eigen) if available, falls back to NumPy.

    Args:
        p: (N, 2) point positions
        bars: (M, 2) edge connectivity
        h_bars: (M,) desired edge lengths
        Fscale: truss pressure factor
        deltat: Euler step size
        nfix: number of fixed points

    Returns:
        p_new: (N, 2) updated positions
    """
    p = np.asarray(p, dtype=np.float64, order='C')
    bars = np.asarray(bars, dtype=np.int32, order='C')
    h_bars = np.asarray(h_bars, dtype=np.float64, order='C')

    if HAS_CPP_DISTMESH:
        # Use C++ version
        return _distmesh2d_step_cpp(p, bars, h_bars, Fscale, deltat, nfix)
    else:
        # Fallback: NumPy implementation (Numba-compatible for jit when needed)
        return _distmesh2d_step_numpy(p, bars, h_bars, Fscale, deltat, nfix)


def _distmesh2d_step_numpy(p, bars, h_bars, Fscale=1.2, deltat=0.2, nfix=0):
    """Pure NumPy distmesh2d step (fallback when C++ unavailable)."""
    N = len(p)
    M = len(bars)

    if M == 0:
        return p.copy()

    # Bar vectors and lengths
    barvec = p[bars[:, 0]] - p[bars[:, 1]]
    L = np.linalg.norm(barvec, axis=1)

    # Desired edge length
    L_norm_sq = (L ** 2).sum()
    h_norm_sq = (h_bars ** 2).sum()
    L0 = Fscale * np.sqrt(L_norm_sq / h_norm_sq)

    # Forces
    F = np.maximum(L0 - L, 0.0)

    # Force vectors
    with np.errstate(divide='ignore', invalid='ignore'):
        Fvec = np.where(L[:, None] > 0, (F / L)[:, None] * barvec, 0.0)

    # Aggregate
    Ftot = np.zeros_like(p)
    np.add.at(Ftot, bars[:, 0], Fvec)
    np.add.at(Ftot, bars[:, 1], -Fvec)

    # Zero fixed points
    if nfix > 0:
        Ftot[:nfix] = 0.0

    # Euler update
    return p + deltat * Ftot
