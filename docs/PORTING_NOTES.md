# Porting notes

Running log of MATLAB → Python substitutions and behavior differences
encountered during the port. One entry per decision; newest at top.

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

## Issue #11 — Ring sorting by signed area (2026-04-26)

**Fix**: `_derive_boundary_segments()` now sorts rings by **signed area** (shoelace formula) instead of **node count**.

**Rationale**: Multiply-connected domains (e.g., WNAT with interior Gulf of Mexico coastline) have interior coastlines with **more nodes** than the outer ocean boundary due to refinement. Sorting by node count incorrectly identified the interior ring as the outer boundary, causing domain bbox shrinkage and `triangulate()` to fail.

**Behavior change**: 
- **Before**: `rings.sort(key=len, reverse=True)` — longest ring (by node count) becomes outer
- **After**: `rings.sort(key=lambda ring: _ring_area(ring, nodes), reverse=True)` — largest ring (by signed area) becomes outer

**Impact**: 
- `Domain.from_mesh(src)` now correctly recovers multiply-connected domains
- WNAT test fixture bbox now matches source to within `1e-9` tolerance
- Ring ordering is now **canonical** and independent of mesh node sampling
- No change to faithful-port modules; only `admesh/api.py` (new `_ring_area()` helper + sort change + new `Domain.from_mesh()` method)

**Alignment with MATLAB**: The MATLAB original uses area-based sorting; this fix aligns the Python port with the reference implementation.

---

## v0.2 — Domain API consolidation (2026-04-26)

**Removed from public API:**
- `admesh.domain_from_polygon(rings, *, pfix, bc_segments)` — Shapely-based polygon→SDF builder
- `admesh.domain_from_sdf(sdf, bbox, *, pfix, pts, bc_segments)` — SDF callable + bbox wrapper

**Rationale:** File-based domain loading (TOML/JSON/fort.14) and the ADMESH-Domains registry
are now the canonical entry points. Storing domain definitions as files enables version control,
reproducibility, and integration with the federated registry (`domattioli/ADMESH-Domains`).

**Migration:**
- Polygon domains → serialize to JSON/TOML once; reload via `load_domain_from_json()` or `load_domain_from_toml()`
- Custom SDF domains → construct `Domain(sdf=callable, bbox=(...))` directly (dataclass still exported)
- See `CLAUDE.md` § "Domain Loading & API (v0.2+)" for code examples

**Internal:** `_shapely_sdf` and `_domain_from_polygon` moved to `admesh/loaders.py` as private
helpers for file-loader internals. Tests that require in-memory polygon→Domain conversion
import `_domain_from_polygon` from `admesh.loaders`.

---

## v1 Pythonic layer (2026-04-25)

A Pythonic API + ADCIRC fort.14 I/O surface lands in
`admesh/api.py`, `admesh/fort14.py`, `admesh/boundary_types.py`,
`admesh/size_field.py`, and `admesh/viz.py`. The layer is **strictly
additive** over the 13 faithful-port stage modules — Constitution
Principle I unbroken. The 142-test faithful-port suite continues to
pass with zero file modifications; `tests/test_smoke.py` was taught
to skip class re-exports (the only test-tree change). See spec
`specs/001-pythonize-and-fort14-integration/` for the full surface
contract; `output/quickstart_validation.txt` for evidence the
3-line happy path round-trips on all 5 MVP domains.

The non-obvious substitutions introduced by this layer:

### `domain_from_polygon` — Shapely-based SDF

**Python**: `admesh.api.domain_from_polygon(rings, *, pfix=None,
bc_segments=())` builds a `Domain` whose `sdf` is constructed from a
Shapely `Polygon` (outer ring first, holes after). Distance to the
`polygon.boundary` LineString gives `|d|`; `prepared.contains(point)`
flips sign for interior points.

**Substitution**: replaces ad-hoc `inpolygon` + per-edge distance
loops you'd otherwise have to write. Shapely is already a transitive
dependency via the geometry stack, so no new install graph cost.

**Behavior diff**: Shapely uses GEOS (C/C++) under the hood; tie
behaviour on the boundary is "point on the boundary returns
distance 0 with sign 0", matching our `d = 0` boundary convention.
For points *exactly* on a vertex shared between rings, GEOS picks
the same sign as the containing ring — no surprises so far.

**Impact**: callers can omit explicit fixed-point lists for simple
polygon domains; the bbox is auto-derived from the outer ring's
extent. Two new dataclass fields on `admesh.api.Domain` (`pts`,
`bc_segments`) ride along but are reserved for the PTS path
(faithful-port) and the bc-label-passthrough story.

### `Mesh.plot()` — lazy matplotlib import

**Python**: `admesh.viz.plot_mesh` is imported only when
`Mesh.plot()` is called, not at module-import time. The
`pyproject.toml` `[viz]` extra (`matplotlib>=3.7`) is opt-in.

**Substitution**: keeps `import admesh` cheap (no matplotlib
backend init) and lets headless / lambda / CI environments use the
package without a display dependency. On `ImportError`, the wrapper
re-raises with a message naming the `admesh2D[viz]` extra so users
get an actionable install hint instead of a Python traceback.

**Behavior diff**: none vs. raw `matplotlib.pyplot.triplot`; the
helper just adds boundary-segment coloring (per `BoundaryType`) and
sets `aspect='equal'` by default.

**Impact**: tests that need matplotlib use `pytest.importorskip` or
the `Agg` backend; the `viz` test suite parametrizes the missing-
matplotlib path via a `monkeypatch` of `builtins.__import__`.

### fort.14 I/O — convention isolation at the boundary

**Python**: `admesh.fort14.{read_fort14, write_fort14}` are the
**only** code path that knows about ADCIRC's 1-based node IDs and
positive-down depth convention. Every internal `Mesh` is 0-based
and stores bathymetry as elevation (positive-up). Conversions:

- `node_id_disk = node_id_internal + 1`
- `depth_disk = -elevation_internal`

The reader inverts both; the writer applies both. Other modules
treat `Mesh` arrays as opaque indices/elevations.

**Substitution**: replaces a hypothetical "convention-everywhere"
design where every consumer would have to remember which side it's
on.

**Behavior diff**: A `Mesh.bathymetry` of all-zeros round-trips as
`None` (no point preserving a meaningless column). Real bathymetry
round-trips bit-for-bit within the writer's `precision=` (default
6 decimal places).

**Impact**: writers/readers in third-party tooling that expect
positive-down depth or 1-based ids interoperate naturally; readers
that expect positive-up never need an inversion.

### Two-phase size-field composition

**Python**: `admesh.size_field.compose_size_field(builtins,
user_contribs, combine, hmin, hmax)` composes a
`(N, 2) -> (N,)` callable.

**Substitution**: replaces the implicit "build_h composes via min"
contract from earlier prototypes with a public, two-phase API.
Phase 1 (built-ins) **always** uses `np.minimum.reduce` regardless
of `combine` — Constitution Principle I (the faithful-port
`mesh_size_function` pipeline must remain numerically identical to
MATLAB). Phase 2 (user contributions) is combined with the Phase-1
result via the caller's chosen reduction (default: minimum).

**Behavior diff**: invalid user-contribution outputs (NaN, ≤ 0,
out of `[hmin, hmax]`) are clamped and a `UserWarning` names the
offending callable + affected count. This is more lenient than
the faithful-port path, which presumes well-formed inputs.

**Impact**: power users can refine specific regions without
forking the size-field stack. Demoed in
`scripts/size_field_extension_demo.py` — wave-breaker contribution
shrinks mean edge length from 0.262 → 0.145 (44%) inside a
transition band.

---

## 2026-04-25 — quad_prep — leg-not-hypotenuse `h` scaling (spec-004)

**MATLAB**: n/a — this is a new module (spec-004), not a port.
**Python**: `admesh.quad_prep.smooth_for_quadrangulation`,
specifically the per-element scale `sigma_k = h(centroid) / sqrt(2)`.
**Substitution**: For the right-isoceles target with legs `L` and
hypotenuse `L * sqrt(2)`, the user-supplied size field `h` is
interpreted as the desired **leg** length, not the hypotenuse. So
`sigma_k = h / sqrt(2)`. Rationale: after downstream tri-to-quad
fusion (CHILmesh `tri2quad`), each pair of right-isoceles triangles
fuses along their shared hypotenuse, and the resulting quad inherits
the **leg** as its edge length, not the hypotenuse. So the size field
must scale legs, not hypotenuses, for `h` to remain the natural
"target edge length" downstream consumers expect.
**Behavior diff**: None — there's no MATLAB analog to compare against.
This convention is documented per Constitution Principle II so the
choice is auditable. Validated via SC-003 (Pearson r ≥ 0.8 between
leg lengths and `h(centroid)`).
**Impact**: Callers who pass an OceanMesh2D-style mesh-size function
get the expected behavior: triangle legs (and downstream quad edges)
track `h` directly, no `sqrt(2)` rescaling needed.

## 2026-04-25 — quality — `right_iso_quality` companion metric

**MATLAB**: n/a — additive (not a port). The original `MeshQuality.m`
measures equilateral-ness only.
**Python**: `admesh.quality.right_iso_quality`.
**Substitution**: Right-isoceles deviation score in `[0, 1]` per
spec-004 FR-006. Per-element score is the product of three terms:
leg-equality, right-angle-fit, hypotenuse-fit. Mesh score is the
unweighted mean. Constitutionally additive: the existing
`mesh_quality` (equilateral target) is **not** modified (Principle I).
The two metrics report side by side; ADMESH's distmesh output
typically scores ~1.0 on `mesh_quality` and ~0.5 on
`right_iso_quality`, and the spec-004 smoother trades the former for
the latter (validated on Block_O.14: 0.977 → 0.923 for
`mesh_quality`, 0.498 → 0.686 for `right_iso_quality`).
**Behavior diff**: None to MATLAB (no analog). The metric is
documented in the public-api.md contract so its semantics are pinned.
**Impact**: Downstream consumers who run tri-to-quad fusion now have
a quality metric that meaningfully scores mesh suitability for that
operation.
