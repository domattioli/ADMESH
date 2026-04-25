"""Pre-quadrangulation triangle smoother (spec-004).

Nudges an ADMESH triangulation toward a right-isoceles target shape so
that downstream tri-to-quad fusion (CHILmesh ``tri2quad``, OceanMesh2D,
ADCIRC v55+ consumers) produces clean quads instead of rhombi.

This module is **additive** to the 13 faithful-port stage modules
(Constitution Principle I): it consumes their public surface but does
not import or modify any of them at the implementation level.

Algorithm: SVD-invariant FEM target-Jacobian (Formulation 1 in
``specs/004-quad-prep-smoother/research.md``). Per-element targets are
oriented by closed-form argmin on the local Jacobian SVD each outer
iteration; the right-angle corner emerges from energy minimisation.

Public surface (FR-001):

- :func:`smooth_for_quadrangulation` — main entry point.

See also :func:`admesh.quality.right_iso_quality` for the companion
quality metric.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from numpy.typing import NDArray

# --- Module constants (D-002, D-004 in research.md) -------------------

# Boundary-pin scale: nodes within `geps` of the SDF zero level-set are
# pinned by adding `kinf * I` to their stiffness diagonal. Empirically
# chosen to keep boundary drift well under `geps` on coastal-grade
# meshes (CHILmesh `direct_smoother` uses the same value).
_KINF: float = 1.0e12

# Pair-hint soft penalty scale, multiplied by the per-element shape
# stiffness scale. Large enough to bias longest-edge alignment, small
# enough not to dominate the shape-target solve. Exposed for empirical
# tuning during testing.
_PAIR_HINT_WEIGHT: float = 0.1

# Boundary-band detection tolerance — nodes with `|fd(p)| < _GEPS_DEFAULT`
# are treated as boundary nodes for pinning + projection (FR-003).
_GEPS_DEFAULT: float = 1.0e-10

# Boundary-band rotation cap radius: nodes within `_BOUNDARY_BAND_FACTOR
# * h_local` of the SDF zero level-set get a clamped per-element
# rotation (FR-007).
_BOUNDARY_BAND_FACTOR: float = 2.0


def smooth_for_quadrangulation(
    p: NDArray[np.float64],
    t: NDArray[np.int64],
    fd: Callable[[NDArray[np.float64]], NDArray[np.float64]],
    h: Callable[[NDArray[np.float64]], NDArray[np.float64]] | None = None,
    pair_hint: bool = True,
    n_outer: int = 2,
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Nudge a triangle mesh toward right-isoceles for downstream quad fusion.

    Implements the SVD-invariant FEM target-Jacobian formulation
    (Formulation 1 in ``specs/004-quad-prep-smoother/research.md``).
    Connectivity is preserved (FR-002): ``t_out`` is the same array
    object as ``t``.

    Parameters
    ----------
    p : ndarray, shape (N, 2), dtype float64
        Node coordinates of the input triangulation.
    t : ndarray, shape (M, 3), dtype int64
        Triangle index triples; CCW winding.
    fd : callable
        Signed-distance function ``fd(q) -> distances`` for ``q`` of
        shape ``(K, 2)``. **Required** (FR-013).
    h : callable, optional
        Size field ``h(q) -> edge_lengths``. When provided, the per-
        element target leg length tracks ``h(centroid)`` (FR-004).
        Default: uniform target.
    pair_hint : bool, default True
        When ``True``, run a greedy longest-edge pairing pre-pass and
        bias geometry toward mutual longest-edge alignment via a soft
        per-element stiffness penalty (FR-005).
    n_outer : int, default 2
        Number of outer iterations. Each outer pass does one solve plus
        one boundary projection. Must be ``>= 1``.

    Returns
    -------
    p_out : ndarray, shape (N, 2), dtype float64
    t_out : ndarray, shape (M, 3), dtype int64
        Same array object as input ``t``.

    Raises
    ------
    ValueError
        If ``fd is None`` (FR-013), or input shapes are invalid, or
        ``n_outer < 1``.
    """
    if fd is None:
        raise ValueError("fd is required; pass an SDF callable")

    p = np.asarray(p, dtype=np.float64)
    if p.ndim != 2 or p.shape[1] != 2:
        raise ValueError(f"p must be (N, 2); got shape {p.shape}")
    if t.ndim != 2 or t.shape[1] != 3:
        raise ValueError(f"t must be (M, 3); got shape {t.shape}")
    if int(n_outer) < 1:
        raise ValueError(f"n_outer must be >= 1; got {n_outer}")

    # Empty / single-element fast path (Edge Case in spec.md).
    if len(t) == 0 or len(t) == 1:
        return p.copy(), t

    # geps follows the distmesh convention: 1e-3 * median edge length.
    # Computed from the input mesh once and held fixed across outer
    # iterations.
    geps = _auto_geps(p, t)

    # Boundary node mask is determined by the *input* mesh (FR-003) and
    # held fixed across outer iterations — topology and the boundary
    # ring don't change.
    boundary_mask = _boundary_node_mask(p, fd, geps=geps)

    # Build pairing map once (topology is invariant).
    pairs = _build_pairing_map(p, t) if pair_hint else None

    p_cur = p.copy()
    for _ in range(int(n_outer)):
        p_cur = _smoother_step(
            p_cur, t, fd=fd, h=h, pairs=pairs, boundary_mask=boundary_mask
        )
        p_cur = _project_boundary_nodes(p_cur, fd, geps=geps, mask=boundary_mask)

    return p_cur, t


def _auto_geps(p: NDArray[np.float64], t: NDArray[np.int64]) -> float:
    """Distmesh-style boundary tolerance: ``1e-3 * median edge length``."""
    e0 = np.hypot(p[t[:, 1], 0] - p[t[:, 0], 0], p[t[:, 1], 1] - p[t[:, 0], 1])
    e1 = np.hypot(p[t[:, 2], 0] - p[t[:, 1], 0], p[t[:, 2], 1] - p[t[:, 1], 1])
    e2 = np.hypot(p[t[:, 0], 0] - p[t[:, 2], 0], p[t[:, 0], 1] - p[t[:, 2], 1])
    return 1.0e-3 * float(np.median(np.concatenate([e0, e1, e2])))


# --- Internal helpers (implemented in subsequent passes) --------------


def _smoother_step(
    p: NDArray[np.float64],
    t: NDArray[np.int64],
    fd: Callable,
    h: Callable | None,
    pairs: NDArray[np.int64] | None,
    boundary_mask: NDArray[np.bool_] | None = None,
) -> NDArray[np.float64]:
    """Single outer iteration: assemble per-element targets + solve.

    Math (Formulation 1 in research.md, D-001):

    For each element k with vertices p0, p1, p2:
        A_k = [p1 - p0 | p2 - p0]              (2x2 Jacobian)
        SVD: A_k = U_k * diag(s) * V_k^T
        R_k = U_k * V_k^T                       (closest 2D rotation)
        sigma_k = h(centroid_k) / sqrt(2)       if h provided, else 1.0
        W_k = sigma_k * R_k                     (target Jacobian)

    Local energy E_k = (1/2) ||D x_k - vec(W_k)||^2 where D is the 4x6
    differentiation operator that maps element dofs to vec(A_k). Local
    stiffness K_local = D^T D (constant 6x6), local RHS b_k =
    D^T vec(W_k).

    Boundary nodes (|fd(p)| < geps) pinned by adding _KINF*I to their
    diagonal block (D-002).
    """
    N = len(p)
    M = len(t)

    # Per-element corner choice: minimize Knupp energy
    # E_k = (s1 - s2)^2 / 2 over the 3 cyclic permutations of (i, j, l).
    # The chosen permutation places the right-angle target at one of
    # the three vertices, so the formulation IS invariant to which
    # vertex was originally first.
    # Permutations as (corner, leg1, leg2) cycles:
    PERMS = np.array([[0, 1, 2], [1, 2, 0], [2, 0, 1]], dtype=np.int64)

    # FR-005: Pair-hint sets the right-angle corner to be the vertex
    # OPPOSITE the shared edge with the pair partner, so paired
    # hypotenuses (= shared longest edges) align across the pair.
    # `forced_perm[k] = pi`  ⇒ vertex t[k, PERMS[pi, 0]] is the corner.
    forced_perm = np.full(M, -1, dtype=np.int64)
    if pairs is not None:
        # For each paired triangle, find the longest edge (the one
        # shared with its partner) and force the corner to the vertex
        # opposite that edge. PERMS rotate the corner: PERM 0 → corner
        # at local vertex 0, edge (1,2); PERM 1 → corner 1, edge (2,0);
        # PERM 2 → corner 2, edge (0,1).
        # Longest-edge-idx in {0,1,2} maps directly: edge 0 = (0,1) →
        # corner = 2 → perm 2. edge 1 = (1,2) → corner = 0 → perm 0.
        # edge 2 = (2,0) → corner = 1 → perm 1.
        edge_to_perm = np.array([2, 0, 1], dtype=np.int64)
        e0 = np.hypot(p[t[:, 1], 0] - p[t[:, 0], 0], p[t[:, 1], 1] - p[t[:, 0], 1])
        e1 = np.hypot(p[t[:, 2], 0] - p[t[:, 1], 0], p[t[:, 2], 1] - p[t[:, 1], 1])
        e2 = np.hypot(p[t[:, 0], 0] - p[t[:, 2], 0], p[t[:, 0], 1] - p[t[:, 2], 1])
        edge_len = np.column_stack([e0, e1, e2])
        longest_edge = np.argmax(edge_len, axis=1)
        paired_mask = pairs >= 0
        forced_perm[paired_mask] = edge_to_perm[longest_edge[paired_mask]]

    best_perm = np.zeros(M, dtype=np.int64)
    best_S = np.empty((M, 2), dtype=np.float64)
    best_R = np.empty((M, 2, 2), dtype=np.float64)
    best_t_perm = np.empty((M, 3), dtype=np.int64)
    best_anis = np.full(M, np.inf)

    for pi, perm in enumerate(PERMS):
        t_perm = t[:, perm]
        A_perm = _compute_element_jacobian(p, t_perm)
        U, S, Vt = np.linalg.svd(A_perm)
        R = U @ Vt
        det_R = np.linalg.det(R)
        flip = det_R < 0
        if flip.any():
            U[flip, :, -1] *= -1.0
            R = U @ Vt
        anis = (S[:, 0] - S[:, 1]) ** 2
        # For paired elements, only accept the forced permutation.
        # For unpaired elements, take the min-anis perm.
        if (forced_perm == pi).any():
            forced_take = forced_perm == pi
            best_perm[forced_take] = pi
            best_S[forced_take] = S[forced_take]
            best_R[forced_take] = R[forced_take]
            best_t_perm[forced_take] = t_perm[forced_take]
            best_anis[forced_take] = -1.0  # mark as locked
        unlocked = forced_perm < 0
        better = unlocked & (anis < best_anis)
        if better.any():
            best_perm[better] = pi
            best_S[better] = S[better]
            best_R[better] = R[better]
            best_t_perm[better] = t_perm[better]
            best_anis[better] = anis[better]

    # Now `best_t_perm` holds the per-element vertex order placing the
    # right-angle target at the closest-matching corner. Use it for
    # assembly.
    t_eff = best_t_perm
    R = best_R
    S = best_S

    # Per-element scale sigma. Two cases:
    # - h provided (FR-004): sigma_k = h(centroid) / sqrt(2), so
    #   target leg length tracks h.
    # - h=None: sigma_k = (s1 + s2) / 2 from the per-element SVD, the
    #   minimum-energy isotropic scale matching the current Jacobian.
    #   This makes the target shape-only (no scale change) so already-
    #   right-isoceles meshes are fixed points.
    if h is not None:
        centroids = (p[t[:, 0]] + p[t[:, 1]] + p[t[:, 2]]) / 3.0
        sigma = np.asarray(h(centroids)).reshape(-1) / np.sqrt(2.0)
    else:
        sigma = (S[:, 0] + S[:, 1]) / 2.0

    W = sigma[:, None, None] * R  # (M, 2, 2)

    # Local stiffness K_local = D^T D, constant; precomputed.
    K_local = _LOCAL_STIFFNESS  # (6, 6)

    # Per-element RHS b_k = D^T vec(W_k); column-major flatten:
    # vec(W) = [W00, W10, W01, W11].
    b_local = np.empty((M, 6), dtype=np.float64)
    b_local[:, 0] = -(W[:, 0, 0] + W[:, 0, 1])  # x0
    b_local[:, 1] = -(W[:, 1, 0] + W[:, 1, 1])  # y0
    b_local[:, 2] = W[:, 0, 0]                  # x1
    b_local[:, 3] = W[:, 1, 0]                  # y1
    b_local[:, 4] = W[:, 0, 1]                  # x2
    b_local[:, 5] = W[:, 1, 1]                  # y2

    # Optional pair-hint penalty (Phase 4): adds alpha to the diagonal
    # of paired elements to bias their hypotenuse alignment toward the
    # paired neighbour. Implemented as a constant boost to K_local
    # diagonal for paired elements.
    if pairs is not None:
        # Soft penalty: scale R-aligned target slightly stronger for
        # paired elements. b_local already encodes alignment via R; we
        # boost its weight by (1 + _PAIR_HINT_WEIGHT).
        paired_mask = pairs >= 0
        b_local[paired_mask] *= (1.0 + _PAIR_HINT_WEIGHT)
        # Diagonal stiffness boost matches (so the linear solve sees a
        # stronger pull, not a scaled solution).
        # (Implemented during global assembly below.)

    # Global assembly via COO triples — constant K_local pattern.
    # Use the corner-permuted connectivity (t_eff) so the right-angle
    # target lands at the per-element best-matching vertex.
    dof = np.empty((M, 6), dtype=np.int64)
    dof[:, 0] = 2 * t_eff[:, 0]
    dof[:, 1] = 2 * t_eff[:, 0] + 1
    dof[:, 2] = 2 * t_eff[:, 1]
    dof[:, 3] = 2 * t_eff[:, 1] + 1
    dof[:, 4] = 2 * t_eff[:, 2]
    dof[:, 5] = 2 * t_eff[:, 2] + 1

    rows = np.repeat(dof, 6, axis=1).reshape(M, 6, 6)
    cols = np.tile(dof, 6).reshape(M, 6, 6)
    data = np.broadcast_to(K_local, (M, 6, 6)).copy()

    if pairs is not None:
        paired_mask = pairs >= 0
        if paired_mask.any():
            data[paired_mask] *= (1.0 + _PAIR_HINT_WEIGHT)

    A_global = sp.csr_matrix(
        (data.ravel(), (rows.ravel(), cols.ravel())), shape=(2 * N, 2 * N)
    )

    b_global = np.zeros(2 * N, dtype=np.float64)
    np.add.at(b_global, dof.ravel(), b_local.ravel())

    # Pin boundary nodes via kinf. Use the caller-provided mask if any
    # (so the same nodes are pinned across outer iterations); else
    # re-detect from the current SDF values.
    if boundary_mask is None:
        boundary_mask = _boundary_node_mask(p, fd, geps=_GEPS_DEFAULT)
    if boundary_mask.any():
        b_idx = np.where(boundary_mask)[0]
        diag_rows = np.concatenate([2 * b_idx, 2 * b_idx + 1])
        diag_data = np.full(len(diag_rows), _KINF, dtype=np.float64)
        A_global = A_global + sp.csr_matrix(
            (diag_data, (diag_rows, diag_rows)), shape=(2 * N, 2 * N)
        )
        b_global[2 * b_idx] += _KINF * p[b_idx, 0]
        b_global[2 * b_idx + 1] += _KINF * p[b_idx, 1]

    # Solve and reshape.
    x = spla.spsolve(A_global.tocsc(), b_global)
    p_new = x.reshape(N, 2)
    return p_new


# Constant 6×6 local stiffness K_local = D^T D (see derivation in
# _smoother_step docstring). Independent of element geometry.
_LOCAL_STIFFNESS: NDArray[np.float64] = np.array(
    [
        [2.0,  0.0, -1.0,  0.0, -1.0,  0.0],
        [0.0,  2.0,  0.0, -1.0,  0.0, -1.0],
        [-1.0, 0.0,  1.0,  0.0,  0.0,  0.0],
        [0.0, -1.0,  0.0,  1.0,  0.0,  0.0],
        [-1.0, 0.0,  0.0,  0.0,  1.0,  0.0],
        [0.0, -1.0,  0.0,  0.0,  0.0,  1.0],
    ],
    dtype=np.float64,
)


def _build_pairing_map(
    p: NDArray[np.float64],
    t: NDArray[np.int64],
) -> NDArray[np.int64]:
    """Greedy longest-edge-neighbour mutual pairing.

    For each triangle k, identify its longest edge and the neighbour
    triangle across that edge. If the neighbour's longest edge is also
    the shared edge, ``pairs[k] = neighbour_index``; else ``-1``.

    Returns
    -------
    pairs : ndarray, shape (M,), dtype int64
        ``pairs[k] = j`` means triangles k and j mutually pair across
        their shared longest edge. ``pairs[k] = -1`` means k has no
        mutual longest-edge partner.
    """
    M = len(t)
    pairs = np.full(M, -1, dtype=np.int64)
    if M == 0:
        return pairs

    # Per-triangle edge lengths.
    e0 = np.hypot(p[t[:, 1], 0] - p[t[:, 0], 0], p[t[:, 1], 1] - p[t[:, 0], 1])
    e1 = np.hypot(p[t[:, 2], 0] - p[t[:, 1], 0], p[t[:, 2], 1] - p[t[:, 1], 1])
    e2 = np.hypot(p[t[:, 0], 0] - p[t[:, 2], 0], p[t[:, 0], 1] - p[t[:, 2], 1])
    edge_len = np.column_stack([e0, e1, e2])
    longest_edge_idx = np.argmax(edge_len, axis=1)  # 0, 1, or 2

    # Edge_idx → (vertex_a, vertex_b) within the triangle.
    EDGE_VERTS = np.array([[0, 1], [1, 2], [2, 0]], dtype=np.int64)

    # Build edge → list of (tri_idx, edge_idx_within_tri) map.
    edge_map: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for k in range(M):
        for ei in range(3):
            v0, v1 = t[k, EDGE_VERTS[ei, 0]], t[k, EDGE_VERTS[ei, 1]]
            key = (int(min(v0, v1)), int(max(v0, v1)))
            edge_map.setdefault(key, []).append((k, ei))

    # For each triangle, look at its longest edge and find a neighbour.
    for k in range(M):
        ei = longest_edge_idx[k]
        v0, v1 = t[k, EDGE_VERTS[ei, 0]], t[k, EDGE_VERTS[ei, 1]]
        key = (int(min(v0, v1)), int(max(v0, v1)))
        owners = edge_map[key]
        if len(owners) != 2:
            continue
        neighbour = owners[0][0] if owners[1][0] == k else owners[1][0]
        # Check mutuality: neighbour's longest edge must also be this one.
        if longest_edge_idx[neighbour] != [
            ei2 for (kk, ei2) in owners if kk == neighbour
        ][0]:
            continue
        pairs[k] = neighbour
    return pairs


def _project_boundary_nodes(
    p: NDArray[np.float64],
    fd: Callable,
    geps: float = _GEPS_DEFAULT,
    max_iter: int = 5,
    mask: NDArray[np.bool_] | None = None,
) -> NDArray[np.float64]:
    """Newton-step project drifting boundary nodes back to SDF zero set.

    Pushes any drift back via:
        ``p -= fd(p) * grad_fd(p) / ||grad_fd(p)||^2``
    Iterates up to ``max_iter`` times or until ``|fd(p)| < geps``.

    If ``mask`` is provided, only those nodes are projected (use to keep
    the boundary set fixed across outer iterations); else nodes are
    flagged via ``|fd(p)| < geps``.
    """
    p_out = p.copy()
    if mask is None:
        fd_vals = np.asarray(fd(p_out)).reshape(-1)
        boundary = np.abs(fd_vals) < geps
    else:
        boundary = mask
    if not boundary.any():
        return p_out

    for _ in range(max_iter):
        f = np.asarray(fd(p_out[boundary])).reshape(-1)
        if np.all(np.abs(f) < geps):
            break
        g = _grad_sdf_numerical(fd, p_out[boundary])
        gn2 = np.sum(g * g, axis=1)
        gn2 = np.where(gn2 > 0, gn2, 1.0)
        step = (f / gn2)[:, None] * g
        p_out[boundary] = p_out[boundary] - step

    return p_out


def _grad_sdf_numerical(
    fd: Callable,
    p: NDArray[np.float64],
    eps: float = 1.0e-7,
) -> NDArray[np.float64]:
    """Central-differences gradient of ``fd`` at points ``p``.

    Returns shape ``(K, 2)``. Used by the boundary projection step.
    """
    pp = np.asarray(p, dtype=np.float64)
    if pp.ndim != 2 or pp.shape[1] != 2:
        raise ValueError(f"p must be (K, 2); got {pp.shape}")
    px = pp.copy()
    px[:, 0] += eps
    mx = pp.copy()
    mx[:, 0] -= eps
    py = pp.copy()
    py[:, 1] += eps
    my = pp.copy()
    my[:, 1] -= eps
    fx = (np.asarray(fd(px)).reshape(-1) - np.asarray(fd(mx)).reshape(-1)) / (2.0 * eps)
    fy = (np.asarray(fd(py)).reshape(-1) - np.asarray(fd(my)).reshape(-1)) / (2.0 * eps)
    return np.column_stack([fx, fy])


def _boundary_node_mask(
    p: NDArray[np.float64],
    fd: Callable,
    geps: float = _GEPS_DEFAULT,
) -> NDArray[np.bool_]:
    """Identify boundary nodes: ``|fd(p)| < geps``."""
    return np.abs(np.asarray(fd(p)).reshape(-1)) < geps


def _compute_element_jacobian(
    p: NDArray[np.float64],
    t: NDArray[np.int64],
) -> NDArray[np.float64]:
    """Per-element 2×2 Jacobian from reference triangle → physical.

    Reference triangle is the right-isoceles unit triangle with vertices
    ``(0, 0)``, ``(1, 0)``, ``(0, 1)``. Per element ``k``:

        ``A_k = [p1 - p0 | p2 - p0]``  (column-stacked)

    Shape: ``(M, 2, 2)``. ``det(A_k) > 0`` for CCW triangles.
    """
    p0 = p[t[:, 0]]
    p1 = p[t[:, 1]]
    p2 = p[t[:, 2]]
    A = np.empty((len(t), 2, 2), dtype=np.float64)
    A[:, :, 0] = p1 - p0  # first column
    A[:, :, 1] = p2 - p0  # second column
    return A
