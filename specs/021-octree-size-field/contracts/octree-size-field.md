# Contract: Octree Size-Function & Medial-Axis Interfaces (internal)

ADMESH is a library; its "contracts" are the internal stage interfaces and the one public-facing invariant that must not break. Signatures are design intent for `/speckit-plan`; exact kwargs settle during implementation.

## C1 — Public invariant (MUST NOT change)

`admesh.api.triangulate(domain, *, h_max=None, h_min=None, size_field=None, user_contribs=(), ...) -> Mesh` keeps its signature and behaviour. The size function reaching `distmesh` stays the callable `fh(p: ndarray[N,2]) -> ndarray[N]`. The octree is entirely below this line — **no public API change** (additive-layer/`api.py` untouched).

## C2 — Octree construction (`admesh/_stages/octree_grid.py`, NEW)

```python
def build_octree(domain, *, h_min, h_max, size_oracle, padding=None, balance=True) -> OctreeGrid
```
- **Pre**: `domain.fd` callable SDF; `h_min < h_max`; `size_oracle(x, y) -> target_h` cheap per-point sizing.
- **Post**: returns a 2:1-balanced `OctreeGrid`; every leaf size ∈ `[h_min, root]`; leaves tile padded bbox without overlap. Raises `OctreeConstructionError` on failure (→ caller falls back, C6).

```python
def locate(grid, p: ndarray[N,2]) -> ndarray[N]          # leaf index per query point, O(log) each
def interpolate(grid, values: ndarray[n_leaves], p) -> ndarray[N]   # within-leaf interpolation
def leaf_graph(grid) -> tuple[edges, spacing]             # adjacency + centre-to-centre distances
```

## C3 — Medial axis on the octree (`medial_axis.py`, MODIFIED)

```python
def apply_medial_axis_octree(h, D_leaves, grid, *, R, hmax, hmin) -> ndarray[n_leaves]
```
- Detects medial leaves via generalised AOF over leaf neighbours; computes `MAD` with `medial_distance_fmm` on `leaf_graph(grid)` (variable spacing); `LFS = |D| + MAD`; `h_lfs = clip(LFS/R, hmin, hmax)`; returns `min(h_lfs, h)`.
- **Post (FR-006)**: for any feature wider than `h_min`, `MAD` is finite on its interior leaves (no empty/boundary-only fallback). Sets `resolved=False` + warns when a feature needs finer than `h_min` (FR-012).
- The existing uniform `apply_medial_axis(h0, D, delta, *, R, hmax, hmin)` is **retained unchanged** for the fallback/uniform path.

## C4 — Size-function build (`mesh_size.py::build_h`, MODIFIED)

`build_h(domain, *, base, hmin, hmax, g, curvature_scale, medial_scale, bathymetry, tide_*, ...) -> fh`
- Builds `OctreeGrid` (C2) instead of `eval_sdf_grid` uniform arrays; evaluates `D` per leaf.
- Min-stacks curvature / medial (C3) / bathymetry / tide on leaves (composition rule unchanged).
- Gradient-limits on `leaf_graph` (C5); clips to `[hmin, hmax]`.
- Returns `fh(p)` via `locate`+`interpolate` (C2) — **same callable contract as today** (C1).
- On `OctreeConstructionError`: fall back to the current uniform `build_h` body (C6).

## C5 — Leaf-graph gradient limiter (`mesh_size.py`, MODIFIED)

```python
def solve_iter_graph(h, edges, spacing, hmax, hmin, g) -> ndarray   # |∇h| <= g on the leaf graph
```
- Pure-NumPy `_py` + `@njit` `_nb` variants; parity asserted `atol=1e-10` (Principle II). Uniform `solve_iter(...)` kept for the fallback path and its existing parity test.

## C6 — Fallback (FR-018)

`build_octree` failure ⇒ `build_h` emits `UserWarning("octree construction failed; falling back to uniform grid")` and runs the existing uniform path, returning a valid `fh`. Degenerate no-multi-scale domains need no special handling (single-level octree ≡ uniform, FR-017).

## C7 — Governance gate (FR-015)

Shipping requires the Constitution amendment (v2.0.0) naming `background_grid` / `medial_axis` / `mesh_size` as Principle-I-exempt. Until merged, `pytest tests/ -q` must still pass on `main`.
