# Data Model: Pre-Quadrangulation Triangle Smoother

**Feature**: 004-quad-prep-smoother
**Phase**: 1 (Design)
**Created**: 2026-04-25

## Scope

This is a numerical-routine module, not a stateful application. The
"data model" here describes:

- The shape and dtype of the public function arguments and return
  values (FR-001, FR-002, FR-013, FR-006).
- The internal per-element data structures the SVD-invariant FEM
  solver builds during a smoothing pass.
- The callable contracts for the optional `h` and required `fd`
  domain functions.

No persistent storage, no schema migrations, no entity lifecycle.

## Public types

### `Triangulation` (implicit; `(p, t)` tuple)

Carried as two NumPy arrays — consistent with the rest of admesh.

| Field | Shape | Dtype | Constraints |
|-------|-------|-------|-------------|
| `p`   | `(N, 2)` | `float64` | Finite; no NaN. |
| `t`   | `(M, 3)` | `int64` (or `intp`) | Each row is a triple of node indices into `p`; `0 ≤ t[i, j] < N`. Counter-clockwise winding (existing admesh convention). |

**Invariants preserved by the smoother (FR-002)**:

- `len(p_out) == len(p_in)` — no node insertion or deletion.
- `t_out` is element-for-element identical to `t_in` — no
  re-indexing, no reordering, no topology change.

### `fd` (callable, required per FR-013)

```
fd: Callable[[ndarray (K, 2)], ndarray (K,)]
```

Evaluates the signed distance from each query point to the domain
boundary. Negative inside, positive outside, zero on the boundary.

Used by the smoother for:

1. Boundary-node detection: `|fd(p)| < geps` selects boundary nodes
   for pinning (along with the rotation cap of FR-007).
2. Boundary projection: after each outer iteration, boundary nodes
   that drifted past `geps` are projected back via Newton step
   `p -= fd(p) * grad_fd(p) / ||grad_fd(p)||²`. Gradient computed
   numerically by central differences (no analytic gradient
   required from the caller).

**Required, not optional** (FR-013): the smoother raises
`ValueError("fd is required; pass an SDF callable")` when `fd is
None`.

### `h` (callable, optional)

```
h: Callable[[ndarray (K, 2)], ndarray (K,)] | None
```

Evaluates the target edge length at each query point. Positive
finite values inside the domain; behaviour outside undefined (the
smoother only evaluates `h` at element centroids, which are inside
by construction).

When provided: per-element scale factor in the local stiffness
becomes `σ_k = h(centroid_k) / sqrt(2)` (FR-004 — leg, not
hypotenuse, tracks `h`).

When `None`: the smoother uses a uniform target with `σ_k = 1`. The
output is still right-isoceles in shape; only the scale differs.

### Public function signatures

#### `smooth_for_quadrangulation` (FR-001)

```python
def smooth_for_quadrangulation(
    p: NDArray[np.float64],          # (N, 2)
    t: NDArray[np.int64],            # (M, 3)
    fd: Callable,                    # required (FR-013)
    h: Callable | None = None,
    pair_hint: bool = True,
    n_outer: int = 2,
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    ...
```

Returns `(p_out, t_out)`. `t_out is t` (same array object;
connectivity preserved).

The `target` parameter from the spec's API sketch is dropped from
the v1 surface — F1 produces a right-isoceles target by definition.
If a future spec wants `target="equilateral"` on this entry point it
will need an explicit clarification; for now the function name pins
the target.

#### `right_iso_quality` (FR-006)

```python
def right_iso_quality(
    p: NDArray[np.float64],          # (N, 2)
    t: NDArray[np.int64],            # (M, 3)
) -> float:
    ...
```

Returns a scalar in `[0, 1]` measuring the mesh's deviation from
right-isoceles. Lives in `admesh/quality.py` as a peer to the
existing `mesh_quality(p, t)`. The existing function is **not
modified** (FR-006).

Per-element score (averaged across the mesh):

```
q_k = right_iso_score(triangle_k)
    = product of:
        - leg-equality term: 1 - |L1 - L2| / max(L1, L2)
        - right-angle term:  1 - |angle_apex - π/2| / (π/2)
        - hypotenuse-fit term: 1 - |L_hyp - sqrt(2) * (L1+L2)/2| / L_hyp
```

where `L1, L2` are the two shortest sides (legs), `L_hyp` is the
longest side (hypotenuse), and `angle_apex` is the angle between
the two legs. All terms in `[0, 1]`; product is also in `[0, 1]`.

This is a *score*, not a normalized quality measure — for tests, we
report the per-mesh mean, the boundary-band mean, and the interior
mean separately (Edge Cases / FR-007).

## Internal data structures (per outer iteration)

These are `quad_prep.py`-private; not exposed in the public API.

### `_ElementStiffness`

```
shape:         (M, 6, 6)  float64
nodes_per_t:   t  (already given)
```

Per-element 6×6 local stiffness block. Built from each element's
SVD-aligned target Jacobian. Assembled into the global sparse matrix
via `scipy.sparse.csr_matrix((data, (row, col)))`.

### `_GlobalSystem`

```
A:   csr_matrix (2N, 2N)   # global stiffness; SPD after kinf pinning
b:   ndarray (2N,)         # RHS: kinf * pinned_positions only
```

Solved with `scipy.sparse.linalg.spsolve(A, b)`; result reshaped to
`(N, 2)` and assigned to `p_new`.

### `_PairingMap` (only when `pair_hint=True`)

```
pairs:  ndarray (M,) int64   # pairs[k] = partner triangle index, or -1 if unpaired
```

Built by a single greedy pass:

1. For each triangle k, identify its longest edge.
2. Find the neighbour triangle across that edge.
3. If that neighbour's longest edge is also the shared edge,
   `pairs[k] = neighbour`; else `pairs[k] = -1`.

Used to scale the soft pair-hint penalty per element (D-004 in
research.md).

## Constraints summary (mapped to FRs)

| FR | Data-model expression |
|----|----------------------|
| FR-002 | `t_out is t_in` (same array object). |
| FR-003 | After each outer iteration, boundary nodes (`|fd(p)| < geps`) projected back to SDF zero set. |
| FR-004 | Per-element `σ_k = h(centroid_k) / sqrt(2)` when `h` provided; `σ_k = 1` otherwise. |
| FR-005 | `_PairingMap` built when `pair_hint=True`; soft penalty added to local stiffness. |
| FR-006 | `right_iso_quality(p, t)` exposed in `admesh/quality.py`; `mesh_quality` untouched. |
| FR-007 | Rotation cap on per-element SVD argmin near boundary (within `2*h_local` of SDF zero). |
| FR-013 | `ValueError` raised when `fd is None`. |

## What this feature does NOT add

- No new public dataclass (`Triangulation` stays as `(p, t)` tuple,
  consistent with the existing admesh API).
- No new global state (the smoother is a pure function).
- No new file format (test fixtures are `.npz` per Constitution
  Principle III pattern).
- No new IBTYPE-aware structure — boundary nodes are treated
  uniformly; per-IBTYPE differentiation is out of scope (Outstanding
  in the clarify coverage table; covered by the "admesh-first"
  framing).
