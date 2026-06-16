# Spec 024 — Grid-agnostic 1D boundary seeding: consume any size-field callable (resolves #114)

**Status:** Planning-phase only. No code shipping in this commit (ADMESH planning profile).
**Issue:** [#114 feat: grid-agnostic 1D boundary seeding — consume any size field (uniform or octree)](https://github.com/domattioli/ADMESH/issues/114) — `status: ready`, `type: feat`, `priority: normal`.
**Related:** [#2](https://github.com/domattioli/ADMESH/issues/2) (original 1D boundary seeding, closed), [specs/007-1d-boundary-seeding](../007-1d-boundary-seeding/spec.md) (prior seeding spec), [#115](https://github.com/domattioli/ADMESH/issues/115) / spec 021 (octree perf — provides the octree `fh` callable), PR [#113](https://github.com/domattioli/ADMESH/pull/113) (octree prototype).
**Branch:** `daily-maintenance` (planning); implementation on `daily-issue-fixing` or a new feature branch.
**Token budget:** MEDIUM (one module refactor + two fixture tests).

---

## 1. Problem statement

The current 1D boundary seeder (spec 007, `admesh/_stages/distmesh.py::_seed_boundary_1d`) was written against a specific `fh` calling convention tied to the uniform background grid path. When the octree size-field path (`size_field_octree`) is active, the seeder either falls back to uniform spacing or uses a leaf-center `initial_points=` hack that:

1. Seeds interior points from leaf centroids instead of by boundary arclength force-balance.
2. Requires the octree's internal grid representation to be exposed to the boundary seeder (tight coupling).
3. Forces the `quality_gate` to be weakened from the production default `(0.30, 0.60)` because the leaf-center seeds collapse under the SDF projection (PR #113 comment thread).

The root cause is **grid representation leaking into the seeding interface**. The seeder should only care about `fh(points) -> h` — a callable returning target element size at arbitrary 2D points. Whether that callable is backed by a uniform grid (`build_h`), an octree (`size_field_octree`), or a user-supplied lambda is irrelevant to the seeding algorithm.

## 2. Proposed design

### 2.1 Unified seeder signature

Generalize `_seed_boundary_1d` to accept a pure callable:

```python
def seed_boundary_1d(
    polygon: np.ndarray,   # (M, 2) ordered boundary vertices (CW or CCW)
    fh: Callable,          # fh(points: (K,2)) -> h: (K,) — any size-field callable
    h_min: float,          # absolute minimum spacing floor
    *,
    pin_corners: bool = True,
) -> np.ndarray:           # (N, 2) boundary node positions
```

Key behavioral contracts:
- `polygon` corners are always included in the output (pinned) when `pin_corners=True`.
- Spacing along each edge is the arclength force-balance solution with target spacing `fh(midpoints)`.
- No assumption is made about whether `fh` came from `build_h`, `size_field_octree`, or any other provider.
- If a polygon edge is shorter than `h_min`, only its endpoints are seeded (carries over from spec 007 FR-007).

### 2.2 Arclength force-balance

The seeder walks each polygon edge by cumulative arclength, querying `fh` at the midpoint of each proposed segment:

```
s = 0
nodes = [polygon[i]]
while s < edge_length - h_min:
    h_local = fh(midpoint_of_next_step)  # one fh() call per trial node
    s += max(h_local, h_min)
    nodes.append(polygon[i] + s * unit_tangent)
nodes.append(polygon[i+1])  # pin far corner
```

This is the standard 1D distmesh seeding algorithm (Persson–Strang 2004, §3). The only change is that `h_local` comes from an arbitrary callable rather than a grid lookup.

### 2.3 Integration with `triangulate()`

`triangulate()` calls `seed_boundary_1d` before launching `distmesh2d`, passing the active `fh`:

```python
# admesh/api.py  (pseudocode — no code shipping here)
if domain.boundary_polygon is not None:
    boundary_seeds = seed_boundary_1d(
        domain.boundary_polygon,
        fh=active_fh,     # build_h result or size_field_octree — same interface
        h_min=h_min,
    )
    pfix = np.vstack([pfix, boundary_seeds]) if pfix is not None else boundary_seeds
```

No special-casing for which size-field provider is active.

### 2.4 Octree path: restore default quality gate

With grid-agnostic seeding, the leaf-center `initial_points=` hack in `distmesh2d` for the octree path is removed. The production `quality_gate=(0.30, 0.60)` is restored for the octree path (the weakened gate was a workaround for the seeding defect, not a fundamental requirement of octree meshes).

## 3. Acceptance criteria

- [ ] **AC-001** (interface): `seed_boundary_1d(polygon, fh, h_min)` is a public function importable from `admesh._stages.distmesh` (or a dedicated `admesh._stages.boundary_seeding` module). Its signature matches §2.1.
- [ ] **AC-002** (uniform path, notch fixture): Given `fh = build_h(domain, ...)` and the `NOTCHED_RECTANGLE` domain at `h0=0.05`, each notch-wall segment (length ~0.25) has ≥ 4 boundary nodes spaced within 1.5 × h0 of each other. Carries over from spec 007 SC-001.
- [ ] **AC-003** (octree path, river-into-bay fixture): Given `fh = size_field_octree(octree)` and the river-into-bay domain, boundary nodes are spaced to `fh` along arclength with ≥ 4 nodes across the narrowest inlet feature.
- [ ] **AC-004** (same code path): AC-002 and AC-003 are satisfied by the **same `seed_boundary_1d` function** — no `if isinstance(fh, ...)` branching inside the seeder.
- [ ] **AC-005** (quality gate restored): The octree distmesh run uses the production `quality_gate=(0.30, 0.60)`. The leaf-center `initial_points=` hack is removed from `distmesh2d`.
- [ ] **AC-006** (no regression): All existing tests in `tests/test_routine.py`, `tests/test_default_size_field.py`, and spec 007's test file pass without modification.
- [ ] **AC-007** (performance): `seed_boundary_1d` runs in < 10 ms for a 100-vertex boundary polygon (carries over from spec 007 SC-004).

## 4. Implementation notes

### 4.1 fh vectorization contract

`fh` must accept a `(K, 2)` float64 array and return a `(K,)` float64 array. This is already the calling convention for both `build_h` (interpolant) and `size_field_octree`. If a user-supplied lambda returns a scalar, wrap it:

```python
fh_vec = lambda pts: np.full(len(pts), fh(pts[0]))  # scalar -> vectorized
```

Document this contract in the function docstring; do not silently wrap (make the user fix it).

### 4.2 Corner pinning

Corners are the vertices of `polygon` where the turning angle exceeds a threshold (e.g., 30°). Always include `polygon[0]` and `polygon[-1]` (or all explicit corners if the polygon is closed). This matches the existing spec 007 behavior.

### 4.3 Edge case: zero-length edges

If `np.linalg.norm(polygon[i+1] - polygon[i]) < h_min`, the edge is a degenerate segment. Skip the walk and return only the two endpoints. This matches spec 007 FR-007.

### 4.4 Removal of the octree-specific `initial_points=` hack

In `admesh/_stages/distmesh.py::distmesh2d_admesh` (or wherever the octree path currently calls `distmesh2d`), remove the conditional that passes leaf centroids as `initial_points`. After this change, the call becomes:

```python
p, t = distmesh2d_admesh(
    fd=domain.sdf,
    fh=fh,
    h0=h_min,
    bbox=domain.bbox,
    pfix=pfix,            # now includes boundary_seeds from seed_boundary_1d
    quality_gate=(0.30, 0.60),   # production default — no weakening
)
```

## 5. Test plan

| Test | Fixture | Assertion |
|---|---|---|
| `test_seed_uniform_notch` | `NOTCHED_RECTANGLE`, `fh=build_h(...)`, `h0=0.05` | ≥ 4 nodes on each notch wall; spacing ≤ 1.5 × h0 (AC-002) |
| `test_seed_octree_river` | river-into-bay, `fh=size_field_octree(...)` | ≥ 4 nodes across narrowest inlet (AC-003) |
| `test_same_code_path` | both fixtures | `seed_boundary_1d.__module__` is the same for both; no `isinstance` dispatch |
| `test_quality_gate_restored` | river-into-bay full `triangulate()` call | `min_q ≥ 0.30` with default `quality_gate`; no leaf-center `initial_points` kwarg present |
| `test_zero_length_edge` | synthetic polygon with a collapsed edge | Returns only the two endpoints for that edge; no division-by-zero |
| `test_performance` | 100-vertex polygon, any uniform `fh` | `seed_boundary_1d` completes in < 10 ms (AC-007) |
| Regression suite | `pytest -q` | All existing tests pass; 0 new failures |

## 6. Files likely touched (implementation session)

- `admesh/_stages/distmesh.py` — refactor `_seed_boundary_1d` into the public `seed_boundary_1d`; remove the octree-specific `initial_points=` hack; restore `quality_gate=(0.30, 0.60)` for the octree path.
- `admesh/api.py` — update `triangulate()` call site to pass `active_fh` to `seed_boundary_1d` (no grid-type branching).
- `tests/test_boundary_seeding.py` — new test file with the tests from §5.
- `docs/PORTING_NOTES.md` — note the seeder generalization and the quality-gate restoration.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Removing the `initial_points=` hack causes distmesh to converge to a lower-quality mesh even with better boundary seeds | Monitor `min_q` on the river-into-bay fixture; if quality drops, investigate whether the hack was compensating for another defect |
| The uniform-path quality regresses when `seed_boundary_1d` is called with `build_h` output (different spacing than the old seeder) | Run full Tier-0/Tier-1 test suite after refactor; accept only if `mean_q` is non-decreasing |
| `fh(points)` with octree is slower per-call than the old leaf-center lookup (O(log N) per point vs O(1) cached) | Batch query: pass all trial points along an edge at once (K points in one `fh` call); O(K log N) vs O(K) naive |
| Corner detection threshold (30°) misidentifies polygon vertices as interior points | Test on the notch: verify all four notch corners are pinned |

## 8. Out of scope

- Changing the `fh` callable interface in `build_h` or `size_field_octree` (they already satisfy the `(K,2) -> (K,)` contract).
- 3D boundary seeding.
- GPU acceleration of the boundary walk (issue #8).
- The octree scalability fix itself (spec 021 / issue #115 — parallel track).

## 9. Cross-references

- #114 — root-cause thread identifying the grid-coupling and the leaf-center workaround.
- spec 007 (`specs/007-1d-boundary-seeding/spec.md`) — the predecessor seeder spec; this spec supersedes its grid-specific assumptions while preserving SC-001/SC-004/FR-007.
- #2 — original 1D seeding implementation (closed); this spec generalizes it.
- #115 / spec 021 — octree perf fix; a prerequisite if `size_field_octree` is too slow to call in the boundary walk inner loop (O(log N) is needed, not O(N)).
- PR #113 — octree prototype; the quality-gate weakening is documented in its comment thread.
