"""Inpaint NaN entries in a 2-D array by Laplacian diffusion.

Faithful port of ``01_ADMESH_Library/13_In_Paint_NaNs/inpaint_nans.m``
@ ``19b2eb9`` — John D'Errico's routine.

The MATLAB source exposes six methods (0-5) selecting the underlying
PDE: plate (del^2), biharmonic (del^4), spring metaphor, 8-neighbor
average. This port implements **method 0** (the MATLAB default) —
the only method exercised by the ADMESH pipeline (the bathymetry +
tide physical-field modules call ``inpaint_nans(A)`` without a
method argument; MATLAB line 103 then picks method = 0).

Method 0 builds a del^2 finite-difference operator restricted to the
NaN cells plus their 4-neighborhood (``talks_to = [-1 0; 0 -1; 1 0;
0 1]``, MATLAB lines 111-112), solves the resulting sparse linear
system via least-squares against the known-value boundary condition,
and overwrites only the NaN entries — known values are preserved
exactly (matches the MATLAB behavior at line 137).

**Deferred**: methods 1-5 raise :class:`NotImplementedError`. They
follow the same sparse-matrix assembly pattern; none are called by
ADMESH. Faithful ports are a ≥ 1-session effort each and not on
any critical path — they land when a caller surfaces.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import lsqr


def inpaint_nans(A: NDArray[np.float64], method: int = 0) -> NDArray[np.float64]:
    """Fill NaN entries in a 2-D array by PDE diffusion.

    Port of ``13_In_Paint_NaNs/inpaint_nans.m`` @ ``19b2eb9``.

    Parameters
    ----------
    A : (n, m) ndarray
        Input array; ``np.nan`` entries are the holes to fill.
    method : int, default 0
        Only ``method = 0`` (plate del^2, restricted support) is
        implemented. See the MATLAB docstring (lines 17-70) for the
        full taxonomy.

    Returns
    -------
    B : (n, m) ndarray
        Same shape as ``A``, with NaN entries replaced. Known values
        are preserved exactly.
    """
    A = np.asarray(A, dtype=np.float64)
    if A.ndim != 2:
        raise ValueError(f"inpaint_nans requires a 2-D array; got {A.ndim}-D")
    if method != 0:
        raise NotImplementedError(
            f"inpaint_nans method={method} not implemented in this port; "
            "only method=0 (MATLAB default) is available."
        )
    return _inpaint_nans_method_0(A)


def _inpaint_nans_method_0(A: NDArray[np.float64]) -> NDArray[np.float64]:
    """Method 0 — restricted del^2, least-squares.

    Direct port of the MATLAB ``case 0`` branch (lines 106-140).

    MATLAB uses column-major linear indexing throughout (``A(:)`` =
    ``reshape(A, n*m, 1)`` flattens column-by-column). To match, we
    use ``order='F'`` flatten / reshape at the boundary and build the
    sparse operator with the same linear index layout.
    """
    n, m = A.shape
    nm = n * m

    # MATLAB: A = A(:); — column-major flatten. Python: order='F'.
    A_flat = A.flatten(order="F")
    is_nan = np.isnan(A_flat)
    nan_list_lin = np.nonzero(is_nan)[0]
    known_list = np.nonzero(~is_nan)[0]
    nan_count = len(nan_list_lin)

    if nan_count == 0:
        return A.copy()

    # MATLAB line 101: [nr, nc] = ind2sub([n, m], nan_list). Column-major:
    # nr = linear % n, nc = linear // n (0-based here; MATLAB is 1-based).
    nr = nan_list_lin % n
    nc = nan_list_lin // n
    nan_list = np.column_stack([nan_list_lin, nr, nc])

    # 1-D case: MATLAB lines 109-125. Used when n==1 or m==1.
    if m == 1 or n == 1:
        work = np.unique(np.concatenate([
            nan_list_lin, nan_list_lin - 1, nan_list_lin + 1,
        ]))
        work = work[(work >= 1) & (work <= nm - 2)]
        nw = len(work)
        # fda: nw x nm sparse with [1 -2 1] at columns [work-1, work, work+1].
        rows = np.repeat(np.arange(nw), 3)
        cols = np.concatenate([work - 1, work, work + 1])
        data = np.tile(np.array([1.0, -2.0, 1.0]), nw)
        fda = coo_matrix((data, (rows, cols)), shape=(nw, nm)).tocsr()
    else:
        # 2-D case: MATLAB lines 126-158.
        # talks_to = [-1 0; 0 -1; 1 0; 0 1] — 4-neighborhood.
        talks_to = np.array([[-1, 0], [0, -1], [1, 0], [0, 1]])
        neighbors_list = _identify_neighbors(n, m, nan_list, talks_to)
        all_list = np.vstack([nan_list, neighbors_list]) if len(neighbors_list) else nan_list

        # Row-direction 2nd partial — valid for cells with 1 <= row_idx <= n-2
        # (MATLAB used 1-based: 2 <= row <= n-1). Python 0-based equivalent
        # is 1 <= row <= n-2, i.e. strict interior in row direction.
        row_ok = (all_list[:, 1] >= 1) & (all_list[:, 1] <= n - 2)
        L_row = np.nonzero(row_ok)[0]
        nl_row = len(L_row)
        if nl_row > 0:
            linear_row = all_list[L_row, 0]
            rows = np.repeat(linear_row, 3)
            cols = np.column_stack([linear_row - 1, linear_row, linear_row + 1]).ravel()
            data = np.tile(np.array([1.0, -2.0, 1.0]), nl_row)
            fda = coo_matrix((data, (rows, cols)), shape=(nm, nm)).tocsr()
        else:
            fda = coo_matrix((nm, nm)).tocsr()

        # Column-direction 2nd partial — valid for 1 <= col_idx <= m-2.
        col_ok = (all_list[:, 2] >= 1) & (all_list[:, 2] <= m - 2)
        L_col = np.nonzero(col_ok)[0]
        nl_col = len(L_col)
        if nl_col > 0:
            linear_col = all_list[L_col, 0]
            rows = np.repeat(linear_col, 3)
            cols = np.column_stack([linear_col - n, linear_col, linear_col + n]).ravel()
            data = np.tile(np.array([1.0, -2.0, 1.0]), nl_col)
            fda = (fda + coo_matrix((data, (rows, cols)), shape=(nm, nm)).tocsr()).tocsr()

    # MATLAB line 161: rhs = -fda(:, known_list) * A(known_list).
    rhs_full = -fda[:, known_list] @ A_flat[known_list]
    # MATLAB line 162: k = find(any(fda(:, nan_list(:,1)), 2))  — rows that
    # touch any NaN column are the active equations.
    fda_nan_cols = fda[:, nan_list_lin]
    # .indptr diff: rows with ≥ 1 nonzero in the NaN-col submatrix.
    row_has_nan = np.diff(fda_nan_cols.tocsr().indptr) > 0
    k = np.nonzero(row_has_nan)[0]

    # Solve least-squares system on the active rows × NaN cols.
    B_flat = A_flat.copy()
    if len(k) > 0 and len(nan_list_lin) > 0:
        sub = fda_nan_cols[k, :]
        sub_rhs = rhs_full[k]
        # lsqr handles overdetermined systems (rows >= cols).
        x = lsqr(sub, sub_rhs)[0]
        B_flat[nan_list_lin] = x

    # MATLAB line 252: reshape(B, n, m). Column-major reshape.
    return B_flat.reshape(A.shape, order="F")


def _identify_neighbors(
    n: int, m: int, nan_list: NDArray[np.int64], talks_to: NDArray[np.int64]
) -> NDArray[np.int64]:
    """Port of the MATLAB ``identify_neighbors`` subfunction (lines 276-315).

    For each NaN cell, enumerate its ``talks_to`` neighbors, drop
    out-of-bounds neighbors, drop duplicates, and drop those that are
    themselves NaN (i.e. already in ``nan_list``).

    Returns a ``(K, 3)`` array with the same column convention as
    ``nan_list``: ``[linear_idx, row_idx, col_idx]``, 0-based,
    column-major linear indexing.
    """
    if len(nan_list) == 0:
        return np.empty((0, 3), dtype=np.int64)
    nan_count = len(nan_list)
    # All candidates: NaN (row, col) + each talks_to offset.
    rc = nan_list[:, 1:3]  # (nan_count, 2)
    # Broadcast: (talks_count, nan_count, 2) -> (talks_count * nan_count, 2)
    neighbors_rc = (rc[None, :, :] + talks_to[:, None, :]).reshape(-1, 2)
    # Drop out-of-bounds.
    in_bounds = (
        (neighbors_rc[:, 0] >= 0)
        & (neighbors_rc[:, 0] < n)
        & (neighbors_rc[:, 1] >= 0)
        & (neighbors_rc[:, 1] < m)
    )
    neighbors_rc = neighbors_rc[in_bounds]
    # Compute column-major linear index.
    linear = neighbors_rc[:, 0] + neighbors_rc[:, 1] * n
    candidates = np.column_stack([linear, neighbors_rc[:, 0], neighbors_rc[:, 1]])
    # Drop duplicates.
    candidates = np.unique(candidates, axis=0)
    # Drop those already in nan_list.
    nan_set = set(nan_list[:, 0].tolist())
    keep = np.array([lin not in nan_set for lin in candidates[:, 0]], dtype=bool)
    return candidates[keep]
