# Porting notes

Running log of MATLAB → Python substitutions and behavior differences encountered during the port. One entry per decision; newest at top.

Template:

```
## YYYY-MM-DD — <stage> — <title>

**MATLAB**: `function(args)` in `<path>.m`
**Python**: `admesh.<module>.function(args)`
**Substitution**: <what was replaced>
**Behavior diff**: <closed-vs-open boundary, tie-break, ordering, etc.>
**Impact**: <how tests / callers are affected>
```

---

## 2026-06-05 — octree_grid.py — Adaptive refinement bug fix (spec 021 / issue #115)

**MATLAB**: N/A — `octree_grid.py` is new Python-only code, not a MATLAB port.
**Python**: `admesh._stages.octree_grid._build_tree_recursive`
**Bug fixed**: `_build_tree_recursive` condition `d > 2.0 * node.size` only skipped far-EXTERIOR cells. Interior cells (d < 0, negative SDF) always passed the check → entire interior subdivided to h_min → O(N²)–like leaf growth at high feature-size ratios.
**Fix**: Replace exterior-only check with local-feature-size (LFS) adaptive stopping. `lfs = max(abs(d), h_min)`, `target_h = min(lfs, h_max)`. Stop subdividing when `node.size <= target_h`. This halts interior cells at the depth appropriate for their distance to the boundary.
**Impact**: ratio=1000 build time 26.8s → 6.68s, leaf count 698,644 → 77,800. All 16 octree tests pass. `_build_tree_recursive` now accepts `h_max` parameter; `build_octree` passes it through.

---

## 2026-05-25 — stage 02 — CreateBackgroundGrid

**MATLAB**: `[X,Y,delta] = CreateBackgroundGrid(PTS,hmax,hmin,res)` in `02_Create_Background_Grid/CreateBackgroundGrid.m`
**Python**: `admesh._stages.background_grid.create_background_grid(domain, h0, padding=None, res=1) -> BackgroundGrid`
**Substitution**: MATLAB `vertcat(PTS.Points{:})` + min/max → `domain.bbox`. `meshgrid(xmin:delta:xmax, ...)` → `np.arange(xmin, xmax + 0.5*delta, delta)` + `np.meshgrid(..., indexing="xy")`. The bare `[X,Y,delta]` tuple is packaged as a frozen `BackgroundGrid` (fields `X`, `Y`, `delta`, `bbox`).
**Behavior diff**: MATLAB pads the box by `hmax`; this signature carries no separate coarse size, so `padding` defaults to `h0` (one cell) and is overridable. Spacing maps `hmin → h0`, so `delta = h0 / res`. The `arange` half-open upper bound `xmax + 0.5*delta` reproduces MATLAB colon inclusivity and matches `eval_sdf_grid`.
**Impact**: New callable surface only; routine.py still builds its grid via `eval_sdf_grid` (delegation deferred to a MATLAB-equipped parity run per spec 013 FR-013-5). `tests/test_background_grid.py` locks five property/contract tests now; the `atol=1e-10` MATLAB-fixture parity test stays `xfail(strict)` until the stage-02 fixture is exported (spec 013 T-013-B5). Shim `admesh/background_grid.py` re-exports both new names.

---

## Issue #11 — Ring sorting by signed area (2026-04-26)

**Fix**: `_derive_boundary_segments()` now sorts rings by **signed area** (shoelace formula) instead of **node count**.

**Rationale**: Multiply-connected domains (e.g., WNAT with interior Gulf of Mexico coastline) have interior coastlines with **more nodes** than outer ocean boundary due to refinement. Sorting by node count incorrectly identified interior ring as outer boundary, causing domain bbox shrinkage and `triangulate()` failure.

**Behavior change**:
- **Before**: `rings.sort(key=len, reverse=True)` — longest ring (by node count) becomes outer
- **After**: `rings.sort(key=lambda ring: _ring_area(ring, nodes), reverse=True)` — largest ring (by signed area) becomes outer

**Impact**:
- `Domain.from_mesh(src)` now correctly recovers multiply-connected domains
- WNAT test fixture bbox now matches source to within `1e-9` tolerance
- Ring ordering now **canonical** and independent of mesh node sampling
- No change to faithful-port modules; only `admesh/api.py`

**Alignment with MATLAB**: MATLAB original uses area-based sorting; this fix aligns Python port with reference implementation.

---

## v0.2 — Domain API consolidation (2026-04-26)

**Removed from public API:**
- `admesh.domain_from_polygon(rings, *, pfix, bc_segments)` — Shapely-based polygon→SDF builder
- `admesh.domain_from_sdf(sdf, bbox, *, pfix, pts, bc_segments)` — SDF callable + bbox wrapper

**Rationale:** File-based domain loading (TOML/JSON/fort.14) and ADMESH-Domains registry are now canonical entry points. Storing domain definitions as files enables version control, reproducibility, and registry integration.

**Migration:**
- Polygon domains → serialize to JSON/TOML once; reload via `load_domain_from_json()` or `load_domain_from_toml()`
- Custom SDF domains → construct `Domain(sdf=callable, bbox=(...))` directly (dataclass still exported)
- See `CLAUDE.md` § "Domain Loading & API (v0.2+)" for code examples

**Internal:** `_shapely_sdf` and `_domain_from_polygon` moved to `admesh/loaders.py` as private helpers for file-loader internals. Tests that require in-memory polygon→Domain conversion import `_domain_from_polygon` from `admesh.loaders`.

---

## v1 Pythonic layer (2026-04-25)

Pythonic API + ADCIRC fort.14 I/O surface in `admesh/api.py`, `admesh/fort14.py`, `admesh/boundary_types.py`, `admesh/size_field.py`, `admesh/viz.py`. **Strictly additive** over 13 faithful-port stage modules — Constitution Principle I unbroken. See spec `specs/001-pythonize-and-fort14-integration/` for full surface contract.

### `domain_from_polygon` — Shapely-based SDF

**Python**: `admesh.api.domain_from_polygon(rings, *, pfix=None, bc_segments=())` builds `Domain` whose `sdf` is constructed from Shapely `Polygon`. Distance to `polygon.boundary` LineString gives `|d|`; `prepared.contains(point)` flips sign for interior points.

**Substitution**: replaces ad-hoc `inpolygon` + per-edge distance loops. Shapely already transitive dependency; no new install graph cost.

**Behavior diff**: Shapely uses GEOS under the hood; tie behaviour on boundary is "point on boundary returns distance 0 with sign 0", matching `d = 0` boundary convention.

**Impact**: callers can omit explicit fixed-point lists for simple polygon domains; bbox auto-derived from outer ring extent.

### `Mesh.plot()` — lazy matplotlib import

**Python**: `admesh.viz.plot_mesh` imported only when `Mesh.plot()` called, not at module-import time. `pyproject.toml` `[viz]` extra (`matplotlib>=3.7`) is opt-in.

**Substitution**: keeps `import admesh` cheap (no matplotlib backend init) and lets headless/CI environments use package without display dependency. On `ImportError`, re-raises with message naming `admesh2D[viz]` extra.

**Behavior diff**: none vs. raw `matplotlib.pyplot.triplot`; helper adds boundary-segment coloring (per `BoundaryType`) and sets `aspect='equal'` by default.

### fort.14 I/O — convention isolation at the boundary

**Python**: `admesh.fort14.{read_fort14, write_fort14}` are the **only** code path that knows about ADCIRC's 1-based node IDs and positive-down depth convention. Every internal `Mesh` is 0-based and stores bathymetry as elevation (positive-up). Conversions:
- `node_id_disk = node_id_internal + 1`
- `depth_disk = -elevation_internal`

**Behavior diff**: `Mesh.bathymetry` of all-zeros round-trips as `None`. Real bathymetry round-trips bit-for-bit within writer's `precision=` (default 6 decimal places).

### Two-phase size-field composition

**Python**: `admesh.size_field.compose_size_field(builtins, user_contribs, combine, hmin, hmax)` composes `(N, 2) -> (N,)` callable. Phase 1 (built-ins) **always** uses `np.minimum.reduce` regardless of `combine` — Constitution Principle I. Phase 2 (user contributions) combined via caller's chosen reduction.

**Behavior diff**: invalid user-contribution outputs (NaN, ≤ 0, out of `[hmin, hmax]`) are clamped with `UserWarning`. More lenient than faithful-port path.

---

## 2026-04-25 — quad_prep — leg-not-hypotenuse `h` scaling (spec-004)

**MATLAB**: n/a — new module (spec-004), not a port.
**Python**: `admesh.quad_prep.smooth_for_quadrangulation`, specifically per-element scale `sigma_k = h(centroid) / sqrt(2)`.
**Substitution**: For right-isoceles target with legs `L` and hypotenuse `L * sqrt(2)`, user-supplied size field `h` is interpreted as desired **leg** length. So `sigma_k = h / sqrt(2)`. Rationale: after downstream tri-to-quad fusion, each pair of right-isoceles triangles fuses along shared hypotenuse, and resulting quad inherits **leg** as its edge length.
**Behavior diff**: None — no MATLAB analog. Convention documented per Constitution Principle II so choice is auditable. Validated via SC-003 (Pearson r ≥ 0.8 between leg lengths and `h(centroid)`).
**Impact**: Callers passing OceanMesh2D-style mesh-size function get expected behavior: triangle legs (and downstream quad edges) track `h` directly, no `sqrt(2)` rescaling needed.

## 2026-04-25 — quality — `right_iso_quality` companion metric

**MATLAB**: n/a — additive (not a port). Original `MeshQuality.m` measures equilateral-ness only.
**Python**: `admesh.quality.right_iso_quality`. Right-isoceles deviation score in `[0, 1]` per spec-004 FR-006. Per-element score = product of three terms: leg-equality, right-angle-fit, hypotenuse-fit. Mesh score = unweighted mean. Constitutionally additive: existing `mesh_quality` (equilateral target) **not** modified (Principle I).
**Behavior diff**: None to MATLAB (no analog). Metric documented in public-api.md contract. ADMESH distmesh output typically scores ~1.0 on `mesh_quality` and ~0.5 on `right_iso_quality`; spec-004 smoother trades former for latter (validated on Block_O.14: 0.977 → 0.923 for `mesh_quality`, 0.498 → 0.686 for `right_iso_quality`).
**Impact**: Downstream consumers running tri-to-quad fusion have quality metric meaningfully scoring mesh suitability.
