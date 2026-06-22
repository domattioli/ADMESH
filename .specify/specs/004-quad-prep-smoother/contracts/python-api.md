# Public API Contract: Pre-Quadrangulation Triangle Smoother

**Feature**: 004-quad-prep-smoother
**Phase**: 1 (Design)
**Created**: 2026-04-25

This document is the source of truth for the public API surface this
feature exposes. Any deviation in the implementation is a bug or
requires a clarification update to the spec.

## Surface summary

Two new public symbols, plus one optional enhancement to an existing
function.

| Symbol | Module | Status |
|--------|--------|--------|
| `smooth_for_quadrangulation` | `admesh.quad_prep` | NEW |
| `right_iso_quality` | `admesh.quality` | NEW (additive) |
| `triangulate(..., for_quads=True)` | `admesh.api` | OPTIONAL EXTENSION |

All three are re-exported from `admesh/__init__.py` so
`from admesh import smooth_for_quadrangulation, right_iso_quality`
works.

## `admesh.quad_prep.smooth_for_quadrangulation`

```python
def smooth_for_quadrangulation(
    p: NDArray[np.float64],
    t: NDArray[np.int64],
    fd: Callable[[NDArray], NDArray],
    h: Callable[[NDArray], NDArray] | None = None,
    pair_hint: bool = True,
    n_outer: int = 2,
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Nudge a triangle mesh toward right-isoceles for downstream quad fusion.

    Implements the SVD-invariant FEM target-Jacobian formulation
    (Formulation 1 in this feature's research.md). Per-element targets
    are oriented by closed-form argmin on the local Jacobian SVD each
    outer iteration; the right-angle corner emerges from the energy
    minimisation rather than being chosen up front.

    Connectivity is preserved (FR-002): ``t_out`` is the same array
    object as ``t``, element-for-element identical.

    Parameters
    ----------
    p : ndarray, shape (N, 2), dtype float64
        Node coordinates of the input triangulation.
    t : ndarray, shape (M, 3), dtype int64
        Triangle index triples; CCW winding (existing admesh
        convention).
    fd : callable
        Signed-distance function: ``fd(q) -> distances`` for ``q`` of
        shape ``(K, 2)``. Negative inside the domain, positive
        outside, zero on the boundary. **Required** — the smoother
        raises ``ValueError`` if ``fd is None`` (FR-013). The
        canonical caller (``admesh.triangulate(..., for_quads=True)``)
        always supplies ``Domain.fd``.
    h : callable, optional
        Size field: ``h(q) -> edge_lengths`` for ``q`` of shape
        ``(K, 2)``. When provided, per-element target leg length
        tracks ``h(centroid)`` (FR-004). When ``None``, a uniform
        target is used (output is still right-isoceles in shape).
    pair_hint : bool, default True
        When ``True``, run a greedy longest-edge-neighbour pairing
        pre-pass and bias the smoother toward aligning paired
        hypotenuses via a soft per-element stiffness penalty (FR-005).
        Topology is never changed.
    n_outer : int, default 2
        Number of outer iterations. Each outer pass does one solve +
        one boundary projection. ``n_outer=1`` is a single shot;
        ``n_outer ≥ 2`` is iterative refinement.

    Returns
    -------
    p_out : ndarray, shape (N, 2), dtype float64
        Smoothed node coordinates.
    t_out : ndarray, shape (M, 3), dtype int64
        Same array object as the input ``t`` (FR-002).

    Raises
    ------
    ValueError
        If ``fd is None`` (FR-013), or if ``p`` / ``t`` shapes are
        invalid, or if ``n_outer < 1``.

    Notes
    -----
    See ``specs/004-quad-prep-smoother/`` for the spec, research
    note, and design rationale. The leg-not-hypotenuse ``h`` scaling
    convention is documented in ``docs/PORTING_NOTES.md``.

    Examples
    --------
    >>> import admesh
    >>> domain = admesh.Domain.from_polygon(unit_square_polygon)
    >>> mesh = admesh.triangulate(domain, h_min=0.05, h_max=0.05)
    >>> p_new, t = admesh.smooth_for_quadrangulation(
    ...     mesh.nodes, mesh.elements, fd=domain.fd, h=domain.size_field
    ... )
    """
```

### Behavioural contract

| Aspect | Guarantee |
|--------|-----------|
| Connectivity | `t_out is t` (same object reference) — FR-002 |
| Node count | `len(p_out) == len(p)` — FR-002 |
| Boundary fidelity | Boundary nodes within `geps` of SDF zero set after return — FR-003 |
| Determinism | Bit-for-bit reproducible given same `(p, t, fd, h, pair_hint, n_outer)` — no internal RNG |
| Pure function | No global state mutation, no side-effects, no I/O |
| Thread-safety | Safe to call from multiple threads on disjoint inputs |
| Faithful-port modules | Not imported, not modified, not patched at runtime — Constitution Principle I |
| `fd=None` handling | Raise `ValueError` immediately — FR-013 |

## `admesh.quality.right_iso_quality`

```python
def right_iso_quality(
    p: NDArray[np.float64],
    t: NDArray[np.int64],
) -> float:
    """Mesh-wide right-isoceles quality score in [0, 1].

    Companion to the existing ``mesh_quality(p, t)`` (which scores
    deviation from equilateral). The two are reported side-by-side as
    a delta after running ``smooth_for_quadrangulation`` (spec
    SC-007).

    Per-element score is the product of three terms in [0, 1]:

    1. Leg-equality:     ``1 - |L1 - L2| / max(L1, L2)``
    2. Right-angle:      ``1 - |angle_apex - π/2| / (π/2)``
    3. Hypotenuse-fit:   ``1 - |L_hyp - sqrt(2) * (L1+L2)/2| / L_hyp``

    where ``L1, L2`` are the two shortest sides (legs) and ``L_hyp``
    the longest (hypotenuse). The mesh score is the mean over all
    elements.

    The existing ``mesh_quality`` function is NOT modified — this is
    purely additive (FR-006).

    Parameters
    ----------
    p, t : as in ``smooth_for_quadrangulation``.

    Returns
    -------
    float
        Mesh-wide right-isoceles quality, in ``[0, 1]``. 1.0 means
        every element is exactly right-isoceles.
    """
```

### Behavioural contract

| Aspect | Guarantee |
|--------|-----------|
| Range | `0.0 ≤ result ≤ 1.0` |
| Pure function | No mutation of `p` or `t` |
| Element ordering | Score is an unweighted mean; element ordering does not affect the result |
| Empty mesh | `len(t) == 0` returns `1.0` (vacuously perfect) |
| `mesh_quality` independence | Importing `right_iso_quality` does not import or alter `mesh_quality` |

## `admesh.api.triangulate(..., for_quads=True)` *(optional extension)*

```python
def triangulate(
    domain: Domain,
    *,
    h_min: float,
    h_max: float,
    seed: int = 0,
    max_iter: int = 200,
    quality_gate: tuple[float, float] = (0.30, 0.60),
    for_quads: bool = False,                     # NEW
    quad_prep_n_outer: int = 2,                  # NEW
    quad_prep_pair_hint: bool = True,            # NEW
) -> Mesh:
    """... (existing docstring) ...

    When ``for_quads=True``, runs the pre-quadrangulation smoother
    (``smooth_for_quadrangulation``) as the final stage of the
    pipeline. This is an opt-in shortcut for callers who want quads
    downstream (CHILmesh tri2quad, OceanMesh2D, ADCIRC v55+).
    Defaults to ``False`` so the existing behaviour is preserved
    (spec FR-011).
    """
```

### Behavioural contract

| Aspect | Guarantee |
|--------|-----------|
| Default behaviour | `for_quads=False` is unchanged from current `triangulate` — bit-for-bit |
| Opt-in only | The smoother runs ONLY when `for_quads=True` |
| Argument forwarding | `quad_prep_*` kwargs forwarded to `smooth_for_quadrangulation` |
| `fd` source | `domain.fd` automatically supplied to the smoother |
| `h` source | The internal size-field callable used by `triangulate` is reused |

This extension may land in a follow-up PR; v1 acceptance does not
require it (FR-011 is SHOULD, not MUST). If deferred, callers run
the smoother explicitly:

```python
mesh = admesh.triangulate(domain, h_min=..., h_max=...)
p_new, _ = admesh.smooth_for_quadrangulation(
    mesh.nodes, mesh.elements, fd=domain.fd, h=domain.size_field
)
mesh = mesh._replace(nodes=p_new)  # or mesh = dataclass.replace(mesh, nodes=p_new)
```

## Re-exports in `admesh/__init__.py`

```python
from admesh.quad_prep import smooth_for_quadrangulation
from admesh.quality import mesh_quality, right_iso_quality

__all__ = [
    # ... existing exports ...
    "smooth_for_quadrangulation",
    "right_iso_quality",
]
```

`mesh_quality` is already re-exported; the line is shown for context.
The new entries land at the end of `__all__`, alphabetised within
their module groupings.

## What this contract does NOT include

- No CLI surface (the feature is library-only).
- No fort.14 round-trip change (the smoother does not alter
  connectivity, so a smoothed mesh round-trips identically through
  `read_fort14` / `write_fort14`).
- No new exception class — `ValueError` covers all input-validation
  failures.
- No telemetry / logging hooks. Diagnostics are the test's
  responsibility (Q3 in spec.md Clarifications).
