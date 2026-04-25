"""Two-phase size-field composition (T041, T042).

Phase 1 — built-in stages — always combined with ``np.minimum.reduce``
(Constitution Principle I, non-negotiable: the faithful-port stack is
numerically identical to MATLAB's ``MeshSizeFunction``).

Phase 2 — user contributions — combined with the Phase-1 result via a
caller-chosen reduction (default: elementwise minimum).

User contributions whose output contains NaN, ``≤ 0``, or ``> hmax``
values are clamped to ``[hmin, hmax]`` and a :class:`UserWarning`
names the offending callable and the affected count.
"""

from __future__ import annotations

import warnings
from typing import Callable, Iterable

import numpy as np

__all__ = ["SizeFieldFn", "compose_size_field"]

SizeFieldFn = Callable[[np.ndarray], np.ndarray]


def _evaluate(fn: SizeFieldFn, pts: np.ndarray) -> np.ndarray:
    """Call ``fn`` and coerce the result to a 1-D float64 array."""
    out = np.asarray(fn(pts), dtype=np.float64)
    if out.ndim != 1 or out.shape[0] != pts.shape[0]:
        raise ValueError(
            f"size-field {getattr(fn, '__qualname__', fn)!r} returned shape "
            f"{out.shape}; expected ({pts.shape[0]},)"
        )
    return out


def _sanitize_user_value(
    fn: SizeFieldFn,
    values: np.ndarray,
    *,
    hmin: float | None,
    hmax: float | None,
) -> np.ndarray:
    """Clamp NaN / non-positive / out-of-range values, warn on changes.

    Accepts ``hmin``/``hmax`` as ``None`` to mean "no clamp on that
    side"; if both are ``None`` we fall back to a permissive sanitize
    that only rejects NaN and non-positive values.
    """
    cleaned = values.copy()
    bad_nan = np.isnan(cleaned)
    bad_nonpositive = ~bad_nan & (cleaned <= 0.0)
    bad_too_large = (
        ~bad_nan & ~bad_nonpositive & (cleaned > hmax)
        if hmax is not None
        else np.zeros_like(cleaned, dtype=bool)
    )
    bad_too_small = (
        ~bad_nan & ~bad_nonpositive & (cleaned < hmin)
        if hmin is not None
        else np.zeros_like(cleaned, dtype=bool)
    )

    n_bad = int(
        bad_nan.sum() + bad_nonpositive.sum()
        + bad_too_large.sum() + bad_too_small.sum()
    )
    if n_bad == 0:
        return cleaned

    fill_lo = hmin if hmin is not None else 1.0
    fill_hi = hmax if hmax is not None else 1.0
    cleaned[bad_nan] = fill_hi
    cleaned[bad_nonpositive] = fill_lo
    cleaned[bad_too_large] = fill_hi
    cleaned[bad_too_small] = fill_lo

    name = getattr(fn, "__qualname__", repr(fn))
    warnings.warn(
        f"size-field contribution {name!r} produced {n_bad} invalid value(s) "
        f"(NaN / non-positive / out of [hmin, hmax]); clamped to "
        f"[{hmin!r}, {hmax!r}]",
        UserWarning,
        stacklevel=3,
    )
    return cleaned


def compose_size_field(
    builtins: Iterable[SizeFieldFn],
    user_contribs: Iterable[SizeFieldFn] = (),
    combine: Callable[[list[np.ndarray]], np.ndarray] = np.minimum.reduce,
    *,
    hmin: float | None = None,
    hmax: float | None = None,
) -> SizeFieldFn:
    """Return a closure that evaluates the two-phase size field at points.

    Parameters
    ----------
    builtins
        Phase-1 built-in stages — wrapped faithful-port functions
        (curvature, medial axis, bathymetry, tide, etc.). Always
        combined with ``np.minimum.reduce`` regardless of ``combine``.
    user_contribs
        Phase-2 user-supplied contributions. Each is sanitized against
        ``hmin``/``hmax`` (NaN, non-positive, out-of-range values
        clamped with a :class:`UserWarning`).
    combine
        Phase-2 reduction: takes a list of ``(N,)`` arrays, returns
        ``(N,)``. Default ``np.minimum.reduce`` (refinement-only).
    hmin, hmax
        Optional clamp bounds applied to user contributions before
        Phase 2 combination. ``None`` disables clamping on that side.

    Returns
    -------
    Callable[[np.ndarray], np.ndarray]
        A pure function ``(N, 2) -> (N,)`` suitable for passing to
        :func:`admesh.api.triangulate` as ``size_field=``.
    """
    builtins_t = tuple(builtins)
    user_t = tuple(user_contribs)

    def _composed(pts: np.ndarray) -> np.ndarray:
        pts_arr = np.asarray(pts, dtype=np.float64)
        if pts_arr.ndim != 2 or pts_arr.shape[1] != 2:
            raise ValueError(
                f"size-field input must be (N, 2); got shape {pts_arr.shape}"
            )

        # Phase 1 — always min-stack.
        phase1_inputs = [_evaluate(f, pts_arr) for f in builtins_t]
        if phase1_inputs:
            phase1 = np.minimum.reduce(phase1_inputs)
        else:
            # Empty builtins → no constraint from Phase 1; act as +inf so
            # min-combine with user contribs degenerates to user only.
            phase1 = np.full(pts_arr.shape[0], np.inf, dtype=np.float64)

        if not user_t:
            return phase1

        # Phase 2 — sanitize each user contribution, then combine.
        user_results = [
            _sanitize_user_value(
                f, _evaluate(f, pts_arr), hmin=hmin, hmax=hmax
            )
            for f in user_t
        ]
        return np.asarray(
            combine([phase1, *user_results]), dtype=np.float64
        )

    return _composed
