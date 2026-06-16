# Contract: Python Facade (pybind11 bindings)

The existing `import admesh` surface, **unchanged** (FR-002, US2). Calls
dispatch into the C++ core when available, else the permanent Numba fallback
(FR-004). No signature or observable-behavior change for current PyPI users.

## Unchanged public surface

```python
import admesh
from admesh import domains

mesh = admesh.triangulate(
    domain,                  # Domain | path str | domains.* constant
    h_max=0.1,
    h_min=None,
    size_field=None,         # callable: pts (M,2) -> sizes (M,) ; batched (R6)
    seed=0,
    max_iter=None,
    quality_gate=True,
    backend="auto",          # NEW kwarg, default "auto" — additive, non-breaking (R5/FR-010)
)
mesh.to_fort14("out.14")
```

- `Mesh` stays a frozen dataclass: `nodes`, `elements`, `boundaries`
  (`tuple[BoundarySegment,...]`), `bathymetry`, `quality`.
- `read_fort14` / `write_fort14` byte-faithful (FR-008).
- `Mesh.plot()` / `plot_quality()` / `plot_layers()` unchanged (delegate to viz).

## Backend selection (additive)

| Precedence | Mechanism | Values |
|---|---|---|
| 1 (highest) | `backend=` kwarg | `"cpp"`, `"python"`, `"auto"` |
| 2 | env `ADMESH_BACKEND` | `cpp`, `python`, `auto` |
| 3 | default | `auto` (cpp if module present, else python) |

- `backend="cpp"` with no compiled module ⇒ **raise** (no silent fallback, R5).
- `backend="auto"` ⇒ cpp if available, else python — zero-config, never fails to mesh.

## Equivalence guarantee (the contract that protects users)

For the same `(domain, args, seed)`:
- node/element **counts** and per-element **quality** match the prior Numba
  release within the stage's parity tolerance (US2 scenario 1, SC-005).
- The existing `tests/` suite passes **unchanged** against the binding-backed
  build (SC-001).

## Callback contract

`size_field` / custom SDF callables MUST be **pure array→array**:
input `(M,2)` query points, output `(M,)` sizes. Invoked **batched** across the
binding (R6) — per-point side effects are unsupported and may observe batching.
