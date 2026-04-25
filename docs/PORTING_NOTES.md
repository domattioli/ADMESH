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

## v1 Pythonic layer (2026-04-25)

A Pythonic API + ADCIRC fort.14 I/O surface lands in
`admesh/api.py`, `admesh/fort14.py`, `admesh/boundary_types.py`,
`admesh/size_field.py`, and `admesh/viz.py`. The layer is **strictly
additive** over the 13 faithful-port stage modules — Constitution
Principle I unbroken. The 142-test faithful-port suite continues to
pass with zero file modifications; `tests/test_smoke.py` was taught
to skip class re-exports (the only test-tree change). See spec
`specs/001-pythonize-and-fort14-integration/` for the full surface
contract; `tests/output/quickstart_validation.txt` for evidence the
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

## 2026-04-24 — distmesh — late-run density-control branch (`BoundaryDensityControl` + `ConstraintDensityControl`)

**MATLAB**: `01_ADMESH_Library/10_Distmesh_2d/{BoundaryDensityControl,ConstraintDensityControl}.m`, invoked at `distmesh2d.m:183-195` on the `mod(k,75)==0 && k > niter/2` branch.
**Python**: `admesh.distmesh._boundary_density_control`, `admesh.distmesh._constraint_density_control`; wired into `distmesh2d_admesh`'s density-control block.
**Substitution**: Retires the deferred-port TODO comment previously left in `distmesh2d_admesh`. `BoundaryDensityControl` drops the interior (off-free-edge) vertex of any free-boundary-attached triangle with `q = (b+c-a)(c+a-b)(a+b-c)/(abc) < 0.2`, excluding fixed (`<nC`) and constraint (`C`) nodes. `ConstraintDensityControl` drops non-fixed points inside a `sqrt(3)/8·fh(midpoint)` rectangular strip straddling each constraint segment; no-op when `C` is empty (our current PTS path).
**Behavior diff**: None intentional vs. MATLAB. The mid-run thinning now fires every 75 iters past `niter/2`, so `h0 = min(fh)`-style runs shed redundant interior nodes that the initial lattice + rejection over-populated. Renderer pass confirms: `unit_disk` after-medial demo drops 1452 → 419 nodes (quality `mean_q = 0.957`), `annulus` PTS demo 1907 → 772 (`mean_q = 0.962`). `notched_rectangle` stays at 3426 because its K+R-driven boundary triangles all have `q > 0.2` — density control correctly finds no bad triangles; count is genuinely fh-driven.
**Impact**: +5 port-correctness tests in `tests/test_matlab_port.py`. No regression on existing 137 tests. MVP quality gates hold on all demos.

---

## 2026-04-24 — boundary — **faithful port** of MATLAB `EnforceBoundaryConditions.m`

**MATLAB**: `01_ADMESH_Library/08_Enforce_Boundary_Conditions/
{EnforceBoundaryConditions,create_polygon_structure}.m`
**Python**: `admesh.boundary.enforce_boundary_conditions` (MATLAB-
faithful), `admesh.boundary.create_polygon_structure`,
`admesh.boundary.PolygonStructure`, `admesh.boundary.BCSegment`,
`admesh.boundary.classify_nodes_against_pts` (session-3 clean-room
renamed — the old name is now the MATLAB-faithful port).
**Substitution**: Replaces the session-3 clean-room
``enforce_boundary_conditions(pts, p, *, tol)`` with the MATLAB
semantics: ``(h_ic, X, Y, D, IB, pts, hmax, hmin) -> h_bc``.
Algorithmic specifics:

- ``create_polygon_structure`` (MATLAB lines 1-80): flattens
  ``pts.Points`` cell array into an ``L, x, y`` master list
  separated by NaN row markers, plus per-ring
  ``circ_x, circ_y`` circumscribing-box extents.
- ``enforce_boundary_conditions`` (MATLAB lines 35-183):
  - Line 35-37: clip ``h_ic`` to ``[hmin, hmax]``; force
    ``D > hmin`` (far-exterior) to ``hmax``.
  - Line 42: early return if no BC segments.
  - Line 47: open-ocean ``IB`` indices → ``hmax``.
  - Lines 94-136: per external-barrier (num ∈ {3, 13, 23}) —
    build a sample rectangle from segment vertices and force the
    segment's ``hmax`` setting on enclosed nodes.
  - Lines 142-183: per internal-barrier (num ∈ {4, 5, 24, 25}) —
    two-sided reach (front + back face) with point-in-band test.

The ``BCSegment`` dataclass replaces MATLAB's ``PTS.Constraints``
struct slots; ``num`` holds the ADCIRC IBTYPE code, ``points`` the
per-vertex ``(x, y)`` array.
**Behavior diff**: Session-3 clean-room used an SDF-plus-tol
membership test (``|D(p_i)| ≤ tol``) to label each output node
with ``(ring_id, BC)``. Faithful port acts in-place on the
h-field grid (``h_bc``), not the point list — caller composes via
``min(h_bc, h0)`` in the size-field solver. The clean-room
node-labelling function is preserved as
``classify_nodes_against_pts`` (same signature; ``distmesh.py``
call sites updated).
**Impact**: Retires the last session-3 clean-room stage. 9 new
``test_boundary`` tests for ``create_polygon_structure`` +
faithful enforce-bc; 8 new ``test_matlab_port`` tests (1 skips
until MATLAB fixture emitted). Session-3 PTS dataclass +
``BoundaryType`` enum preserved unchanged — they remain the API
surface for ``build_h(..., pts=...)``.

## 2026-04-24 — inpaint — **faithful port** of MATLAB `inpaint_nans.m` method 0

**MATLAB**: `01_ADMESH_Library/13_In_Paint_NaNs/inpaint_nans.m`
**Python**: `admesh.inpaint.inpaint_nans`
**Substitution**: Replaces the session-1 placeholder stub with a
faithful port of John D'Errico's method 0 (default):

1. Column-major flatten (``A.flatten(order='F')``) — matches MATLAB
   linear indexing (`A(k)` runs columns first). Return value is
   reshaped with ``order='F'``.
2. 4-neighbor ``talks_to`` stencil ``[(-1, 0), (0, -1), (1, 0), (0, 1)]``
   (MATLAB lines 126-129).
3. Sparse del² operator ``-4 * e_i + sum(e_{neighbors})`` built only
   for NaN cells + their immediate (non-NaN) neighbors.
4. Solve via ``scipy.sparse.linalg.lsqr(A, b)`` — MATLAB uses
   ``A \ rhs`` but LSQR is a direct drop-in for the overdetermined
   linear system method 0 constructs.
5. Known cells pass through unchanged (MATLAB line 137).

Methods 1-5 raise ``NotImplementedError`` — the MATLAB file
implements them but MATLAB ADMESH never calls with a non-zero
method (default is 0), so method 0 alone is enough for port
parity. Full method coverage is a Phase P4 polish task.
**Behavior diff**: On linear fields (Δ²f ≡ 0) inpaint recovers
missing values exactly. On quadratic fields the reconstruction
is smooth but not exact — matches MATLAB method 0 behavior. LSQR
convergence tolerance is at default; tests verify `atol=1e-8`.
**Impact**: Unblocks WS4 (bathymetry) which runs inpaint on
NaN-ful depth samples (MATLAB ``CreateElevationGrid.m`` line
19-21). 7 new ``test_inpaint`` tests.

## 2026-04-24 — bathymetry — **faithful port** of MATLAB `BathymetryFunction.m`

**MATLAB**: `01_ADMESH_Library/06_Bathymetry_Function/
{BathymetryFunction,CreateElevationGrid}.m`
**Python**: `admesh.bathymetry.apply_bathymetry`,
`admesh.bathymetry.create_elevation_grid`
**Substitution**: Replaces the session-1 stub. Two entry points:

- ``create_elevation_grid(X, Y, xyz_fun)`` — port of
  ``CreateElevationGrid.m``. Samples ``xyz_fun(X, Y) -> Z`` onto
  the grid and, if any NaN entries are produced, fills them via
  :func:`admesh.inpaint.inpaint_nans` (MATLAB line 19-21).
  Returns ``None`` for ``xyz_fun=None`` (MATLAB
  ``isempty(xyzFun) -> Z = []``).
- ``apply_bathymetry(h0, D, Z, delta, *, s, hmin, hmax,
  mask_boundary_band=True)`` — port of ``BathymetryFunction.m``.
  Core formula (MATLAB line 112):

      h_bathy = s * |Z| / |∇Z|

  with ``∇Z`` computed by MATLAB's 4th-order central-difference
  stencil on the interior ``[2:LY-2, 2:LX-2]`` window (MATLAB
  lines 51-55; the border strip remains 0 under MATLAB's narrower
  stencil support too). Where ``|∇Z| = 0`` the value is set to
  ``hmax`` (division guard; also what MATLAB ``inf → hmax`` clip
  produces). Clipped to ``[hmin, hmax]`` (lines 115-116); cells
  with ``D ≥ -4·hmin`` pinned to ``hmax`` when
  ``mask_boundary_band`` is on (MATLAB line 121, active when
  ``Settings.K.Status == 'On'``); composed via ``min(h_bathy, h0)``
  (line 129).

**Behavior diff**: The boundary-band mask defaults to True — the
curvature stage owns that band in the canonical MATLAB pipeline,
so bathymetry yielding hmax there is the correct behavior when
curvature is active. ``build_h`` passes ``mask_boundary_band =
(curvature_scale is not None)``; callers using bathymetry alone
get sizing everywhere.
**Impact**: ``build_h`` gains ``bathymetry=`` +
``bathy_scale=`` kwargs routing to the faithful port. 7 new
``test_bathymetry`` tests; 1 new ``test_mesh_size`` test for
the routing.

## 2026-04-24 — dominate_tide — **faithful port** of MATLAB `Dominate_tide.m`

**MATLAB**: `01_ADMESH_Library/07_Dominate_Tide/Dominate_tide.m`
**Python**: `admesh.dominate_tide.apply_tide`
**Substitution**: Replaces the session-1 stub. MATLAB line 35
formula (shallow-water dispersion, resolving a tidal wavelength
at ``sz`` elements):

    h_tide = (T / sz) * sqrt(g * |Z|),  g = 9.81

MATLAB line 37 promotes ``h_tide == 0`` (i.e. ``Z == 0``, land
cells) to ``hmax`` — avoids zero-sizing on land. Clipped to
``[hmin, hmax]`` (lines 40-41); composed via
``min(h_tide, h0)`` (line 44).
**Behavior diff**: None — direct translation of the closed-form
formula plus the three post-processing steps. Uses ``np.abs(Z)``
so the sign convention on ``Z`` (positive-down vs. positive-up)
is irrelevant.
**Impact**: ``build_h`` gains ``tide_period=`` + ``tide_scale=``
kwargs (the latter is MATLAB's ``tide_value``, aka ``sz``).
Requires ``bathymetry=`` to be set so ``Z`` is available. 6 new
``test_dominate_tide`` tests; 1 new ``test_mesh_size`` test for
the routing. **Completes the 13-stage faithful port** — zero
clean-room modules remain.

## 2026-04-23 — curvature — **faithful port** of MATLAB `CurvatureFunction.m`

**MATLAB**: `01_ADMESH_Library/04_Curvature_Function/CurvatureFunction.m`
**Python**: `admesh.curvature.apply_curvature` (MATLAB-faithful),
`admesh.curvature.curvature_grid` (kept as thin κ computation),
`admesh.curvature.curvature_function` (backward-compat wrapper)
**Substitution**: Replaces the session-2 clean-room composition with
MATLAB's narrow-band formula from line 64:

    h_curve(I) = (1 + κ·|D|) / ((K/π)·κ) − g·D,   I = {|D| ≤ 2·hmin}

outside the band ``h_curve = hmax``; clipped to ``[hmin, hmax]``;
composed via ``min(h_curve, h0)``. ``K`` is MATLAB's "elements per
radian" parameter; ``build_h`` maps the user-facing
``curvature_scale`` via ``K = π / curvature_scale`` (the formula
then yields ``h ≈ curvature_scale`` at unit curvature on the
boundary).

The κ computation (∇·(∇D/|∇D|)) uses our 4th-order ``grad_sdf``
instead of MATLAB's 2nd-order ``divergence``; this is an allowed
numerical optimization per Article II.1 (faithful algorithm,
numerically-equivalent stencil upgrade).
**Behavior diff**: Clean-room composition was
``h_curv = 1/(|κ| + 1/hmax)`` applied everywhere; faithful port
acts only in the narrow band ``|D| ≤ 2·hmin`` — cells outside the
band are left at ``h0``. This changes behavior far from boundaries.
**Impact**: Retires one session-2 clean-room entry. Two
``test_mesh_size`` tests updated to reflect new semantics (band-only
action; LFS is near-constant along feature axes). 5 new
``test_matlab_port`` tests.

## 2026-04-23 — medial_axis — **faithful port** of MATLAB `MedialAxisFunction.m`

**MATLAB**: `01_ADMESH_Library/05_Medial_Axis/{MedialAxisFunction,
medial_distance_FMM, heap, min_sort}.m`
**Python**: `admesh.medial_axis.apply_medial_axis` (MATLAB-faithful),
`admesh.medial_axis._average_outward_flux`,
`admesh.medial_axis._skeletonize_zhang_suen`,
`admesh.medial_axis._remove_isolated`,
`admesh.medial_axis.medial_axis_mask`,
`admesh.medial_axis.medial_distance_fmm` (backward-compat wrapper).
**Substitution**: Full port of MATLAB lines 45-95:

1. 8-neighbor Average Outward Flux (AOF); medial = ``AOF > 0.15``.
2. Restrict to interior ``D ≤ 0``.
3. Morphological skeletonize (MATLAB ``bwmorph(MA, 'skel', inf)``)
   → substituted with vectorized Zhang-Suen iterative thinning.
   Both produce 1-pixel skeletons; Zhang-Suen is marginally different
   at endpoint symmetry but preserves 8-connected topology.
4. Remove isolated pixels (MATLAB ``bwmorph(MA, 'clean', inf)``) →
   8-connectivity count via ``scipy.signal.convolve2d``.
5. ``MAD = distance_transform_edt(~MA) * delta`` (MATLAB ``bwdist``
   × ``delta``).
6. ``LFS = |D| + |MAD|``; ``h_lfs = LFS/R``; clip; ``h0 = min(h_lfs, h0)``.

``MedialAxisFunction.m`` itself doesn't call the FMM file — it uses
``bwdist``. The FMM subroutine (``medial_distance_FMM.m``) is
unused in the reference pipeline; Python port retains a placeholder
wrapper for backward compat but uses the same EDT approach.

``build_h`` maps the user-facing ``medial_scale`` via
``R = 0.4 / medial_scale``, calibrated so that on a typical feature
(LFS ≈ 0.4) the formula yields ``h ≈ medial_scale``.
**Behavior diff**: Clean-room implementation detected the medial
axis via ``|∇D_edt| < 0.85`` (gradient-magnitude threshold);
faithful port uses AOF threshold > 0.15 which is a different
detection rule. Both produce a skeletal mask, but the faithful AOF
approach is more robust on non-convex geometry (e.g. notched
rectangle).
**Impact**: Retires one session-2 clean-room entry. 3 new
``test_matlab_port`` tests (AOF, medial mask on annulus, LFS
constant-along-feature).

## 2026-04-23 — distmesh — canonical `distmesh2d` adds BoundaryCleanUp

**MATLAB**: `01_ADMESH_Library/10_Distmesh_2d/BoundaryCleanUp.m`
(already ported in session 4 for ``distmesh2d_admesh``)
**Python**: `admesh.distmesh.distmesh2d` now calls
`_boundary_cleanup(p, t, None)` after the final retriangulation.
**Rationale**: MATLAB's canonical Persson ``distmesh2d`` does not
include BoundaryCleanUp (Persson's reference implementation). MATLAB
ADMESH's ``distmesh2d.m`` (line 226) DOES. For Python's
``distmesh2d`` (our MVP path) to produce ADMESH-quality output on
non-uniform ``fh``, we call the same cleanup. Pure Persson doesn't
have it, but the Python MVP path is a hybrid — Persson's core loop
with ADMESH-style final cleanup. Documented deviation.
**Behavior diff**: Drops triangles attached to the free boundary
with ``q < 0.15`` (MATLAB's threshold). MVP domains unchanged (all
already have min_q > 0.69); enriched-``fh`` Domain-path meshes
(e.g. notched_rect with medial refinement) see large quality
improvements (notched min_q: 0.020 → 0.162 in session 5).

---

## 2026-04-23 — distmesh — **faithful port** of MATLAB `distmesh2d.m` + helpers

**MATLAB**: `01_ADMESH_Library/10_Distmesh_2d/{distmesh2d,
BoundaryCleanUp,projectBackToBoundary,createInitialPointList}.m`
**Python**: `admesh.distmesh.distmesh2d_admesh` (rewritten),
`admesh.distmesh._boundary_cleanup` (rewritten),
`admesh.distmesh._project_back_to_boundary` (new),
`admesh.distmesh._initial_point_list_from_pts` (new)
**Substitution**: Replaces the session-3 clean-room implementations
with a faithful port from MATLAB source at `@ 19b2eb9` (now present
at `/workspace/QuADMesh-MATLAB/` as declared in Constitution
Article I). Algorithmic specifics:

- **`distmesh2d_admesh`**: parameters `ttol=0.5, Fscale=1.15,
  deltat=0.3, geps=1e-3*hmin, niter=1000` (MATLAB defaults). Density
  control every 75 iterations drops points where `L0 > 2*L` (never
  `pfix`). Best-quality tracking in the last 50 iterations — the
  returned mesh is the argmax over those iterations of
  `MeshQuality`-mean. Final output is `BoundaryCleanUp(P,T,C);
  fixmesh(P,T)`.
- **`_boundary_cleanup`**: uses free-boundary edge detection (edges
  appearing in exactly one triangle), computes the MATLAB q-formula
  on boundary-attached triangles, drops those with `q < 0.15`.
  Preserves any triangle incident to a constrained edge.
  **Signature change** (breaking): `(p, t, C)` where `C` is an
  `(K, 2)` array of constrained edges (or `None`). Session-3
  clean-room signature `(p, t, pts)` is retired.
- **`_project_back_to_boundary`**: projects all points with
  `d > -geps*100` (broader than Persson's `d > 0`) — pulls
  boundary-adjacent interior nodes onto the boundary. This is the
  main driver of the min_q improvement on PTS-path meshes.
- **`_initial_point_list_from_pts`**: replaces `_initial_distribution`
  on the ADMESH path. Bbox from PTS ring vertices; even rows
  (MATLAB `2:2:end` = Python `1::2`) shifted by `hmin/2`; rejects
  points with `fd >= geps` directly.

**Behavior diff**: Canonical Persson `distmesh2d` (MVP path) is
untouched — MVP M.4 gate green, byte-identical PNGs. Annulus
PTS-path demo: `min_q` went `0.120 → 0.343` (2.9× improvement,
crosses the `≥ 0.30` gate). MATLAB `distmesh2d.m` branches NOT yet
ported (deferred follow-up): `BoundaryDensityControl.m` +
`ConstraintDensityControl.m` (k > niter/2 density branch), full
PTS-constraint integration via `GetMeshConstraints.m`.
**Impact**: 3 clean-room entries below this one (session 3) are
superseded for the distmesh stage. Curvature / medial_axis /
boundary clean-room ports are the remaining backfill debt.

---

**MATLAB**: `10_Distmesh_2d/{distmesh2d,createInitialPointList,
rejectionMethod,GetMeshConstraints,projectBackToBoundary,
BoundaryCleanUp,createMeshStruct}.m`
**Python**: `admesh.distmesh.distmesh2d_admesh`,
`admesh.distmesh._boundary_cleanup`,
`admesh.distmesh.MeshOutput`,
`admesh.routine.triangulate` (dispatcher)
**Substitution**: Clean-room — MATLAB source still not available in
this environment (2nd `SOURCE_UNAVAILABLE` row; see
`docs/persistence_journal.md` 2026-04-23T(s3-start)). The new path
layers on top of the canonical `distmesh2d`: seeds `pfix` with all
PTS ring vertices; synthesizes an SDF from the PTS via inside-test
+ per-segment Euclidean distance when the caller doesn't supply
`fd`; runs `_boundary_cleanup` to drop near-collinear slivers with
2+ nodes on the same ring (same pattern that motivated session-1's
stale-`t` bugfix); classifies every node by `(ring_id, BC)` via
`admesh.boundary.enforce_boundary_conditions`. Returns a typed
`MeshOutput` dataclass. The MVP `triangulate(Domain)` tuple path is
preserved verbatim; a new `triangulate(PTS)` branch dispatches to
the admesh path and returns `MeshOutput`.
**Behavior diff**: The MVP binding gate
(`tests/test_mvp_domains.py::test_mvp_domain`) passes unchanged —
54 of 82 tests run along the pre-existing canonical path. The
admesh path is exercised by 6 new `tests/test_distmesh_admesh.py`
cases and produces annulus meshes labeled across both rings with
`min_q ≥ 0.25, mean_q ≥ 0.55`. Faithful-port backfill against the
MATLAB helper set is deferred.
**Impact**: `admesh.routine.triangulate` now accepts a `PTS` for
rich-boundary workflows; rings and BC tags flow through to the
output without the caller managing the plumbing.

## 2026-04-23 — mesh_size — `build_h` gains PTS boundary reduction

**MATLAB**: boundary-distance contribution is folded into MATLAB's
mesh-size pipeline inside `ADmeshRoutine.m`; there is no standalone
function for it.
**Python**: `admesh.mesh_size.build_h(..., pts=, boundary_scale=)`
+ `_pts_boundary_field` helper.
**Substitution**: Adds two new kwargs to the existing composer.
When set, the composer samples each PTS segment's distance to every
grid cell, then composes `h_bnd[type] = max(scale[type], d)` per
BC type and takes the elementwise min. Composes with existing
`curvature_scale` / `medial_scale`. Zero-enrichment path is
preserved — `build_h(domain, pts=pts, boundary_scale=None)` still
returns the uniform-`base` lambda.
**Behavior diff**: Accepts a dict keyed by
`BoundaryType`-int so callers can refine OPEN vs. WALL asymmetrically.
Unit-square near-boundary `fh ≤ 0.1` vs. interior `fh ≥ 2 × that`
(for `boundary_scale=0.04, base=0.2`).
**Impact**: `build_h` is now PTS-aware without breaking any
existing callers. End-to-end `triangulate(pts, fh=build_h(...))`
works by passing the returned `fh` through the new admesh path.

## 2026-04-23 — boundary — PTS + BC enforcement (clean-room)

**MATLAB**: `08_Enforce_Boundary_Conditions/{EnforceBoundaryConditions,
create_polygon_structure}.m`
**Python**: `admesh.boundary.PTS`, `admesh.boundary.BoundaryType`,
`admesh.boundary.enforce_boundary_conditions`,
`admesh.boundary.PTS.from_polygons`, `admesh.boundary.PTS.from_domain`
**Substitution**: Clean-room — MATLAB source not accessible. The
port defines a **minimum-viable** PTS: list of polygon rings
(outer + holes), per-vertex BC tag (2-value `IntEnum`: `OPEN`,
`WALL`; MATLAB has more subtypes), and an opaque `attributes` dict
for passthrough data. `PTS.from_domain` uses a clean-room
marching-squares contour extractor on the SDF grid, chains segments
into closed rings, resamples each by arc-length. Orients outer CCW
/ holes CW.
**Behavior diff**: MATLAB's PTS has additional fields
(hydraulic-constraint subtypes, per-node attributes) — expand in a
faithful-port backfill when MATLAB source is available. The 2-BC
subset handles the P3-lift requirements (enforce_boundary_conditions
drives cleanup + per-type sizing). `from_domain` has a
``3·delta`` pad on the sampled bbox so the zero-level set is
strictly interior to the grid (avoids fencepost loss when ``delta``
doesn't evenly divide the bbox extent).
**Impact**: Unblocks PTS-driven `build_h` and
`distmesh2d_admesh`. Round-trips on `unit_square`, `annulus`, and
`unit_disk` with per-ring orientation correct and
`|r_outer - 1| ≤ 2e-2` on the disk.

## 2026-04-23 — mesh_size — `build_h` composer (new, not ported)

**MATLAB**: size-field composition is distributed across
`03_Distance_Function`, `04_Curvature_Function`, `05_Medial_Axis`,
`06_Bathymetry_Function`, `07_Dominate_Tide`, and the solver entry
in `09_Mesh_Size` — there is no single MATLAB function that wires
them together; `ADmeshRoutine.m` does the orchestration.
**Python**: `admesh.mesh_size.build_h`
**Substitution**: New-in-Python composer that builds an
``fh(p) -> np.ndarray`` callable from optional curvature + medial
contributions, applies `solve_iter` (gradient limiting), and wraps
the result in a `scipy.interpolate.RegularGridInterpolator`.
**Behavior diff**: Zero-enrichment path (no `curvature_scale` /
`medial_scale`) returns a uniform lambda with no grid work — keeps
the MVP `triangulate(domain)` default path unchanged.
**Impact**: `triangulate(domain, fh=build_h(domain, ...))` accepts
enriched size fields; verified by `tests/test_mesh_size.py::
test_triangulate_accepts_composed_fh`.

## 2026-04-23 — medial_axis — clean-room (MATLAB source unavailable)

**MATLAB**: `MedialAxisFunction.m`, `TriMedialAxisFunction.m`,
`medial_distance_FMM.m`, heap helper in `05_Medial_Axis/`
**Python**: `admesh.medial_axis.medial_distance_fmm`
**Substitution**: The session-2 environment lacks the MATLAB clone
(see `docs/persistence_journal.md` row dated 2026-04-23). Clean-room
implementation: `scipy.ndimage.distance_transform_edt` computes the
L2 distance transform (equivalent Eikonal with unit speed). Medial
cells are detected as interior cells where ``|∇D_edt| < 0.85``,
with a ``1.5·delta`` buffer against the boundary staircase (true
distance functions satisfy ``|∇D| = 1`` a.e.; the skeleton is
where that fails). Then EDT again from the medial mask yields
``medial_dist``.
**Behavior diff**: Validated against analytic references only
(unit disk: medial = origin, medial_dist = r; annulus(0.4, 1.0):
medial = circle r=0.7, medial_dist = |r - 0.7|) to
``2.5..3.0·delta``. Faithful-port pass against the MATLAB heap-FMM
is deferred to the first session with the MATLAB clone mounted.
**Impact**: `build_h(..., medial_scale=...)` works. No test yet
exercises domains with multi-branch medial skeletons like
`notched_rectangle`; that's a fixture to add when the MATLAB
reference is available.

## 2026-04-23 — curvature — clean-room (MATLAB source unavailable)

**MATLAB**: `CurvatureFunction.m` + helpers in
`04_Curvature_Function/`
**Python**: `admesh.curvature.curvature_function`,
`admesh.curvature.curvature_grid`
**Substitution**: The session-2 environment lacks the MATLAB clone
(see `docs/persistence_journal.md` 2026-04-23). Clean-room
implementation of the textbook formula
``κ = ∇·(∇f / |∇f|)`` on a rectangular grid, using the existing
``admesh.distance.grad_sdf`` 4th-order stencil twice (once for
``∇f``, once for the divergence of the normalized gradient). Cells
with ``|∇f| < 1e-3`` are masked ``NaN`` to avoid the medial-axis
singularities. Reference: Osher & Fedkiw (2003) §1.4.
**Behavior diff**: On `unit_disk` (analytic κ=1/r), coarse-grid
L∞ error ≤ 5e-2 at `delta=0.05`; halving `delta` reduces the
error (tests only a monotonic refinement — not a rate). On
`annulus` the sign flip between inner and outer halves matches
analytic to ≤ 1e-1. On `unit_square` (kinked SDF), flat-face
regions yield κ ≈ 0; diagonals produce spurious large values —
unavoidable for the 4th-order stencil across a C⁰ kink.
**Impact**: `build_h(..., curvature_scale=...)` works. Faithful-port
pass deferred.

## 2026-04-21 — distmesh — stale-`t` bug: final Delaunay added

**MATLAB**: `distmesh2d.m` in `10_Distmesh_2d/`
**Python**: `admesh.distmesh.distmesh2d`
**Substitution**: The canonical Persson algorithm re-runs Delaunay
only when `max(nodal-motion)/h0 > ttol`. The Python port followed
that literally, which meant a final set of force-step node motions
(including boundary-projection of drifted nodes) could leave the
most recent `t` slightly stale. On straight boundaries
(`unit_square`) three boundary-projected nodes at `x=0.5±1e-10` can
form a near-colinear, zero-area sliver. Added a final
`Delaunay(p)` + centroid-`fd` filter after the loop exits (either
`niter` or `dptol`), before `fixmesh`.
**Behavior diff**: `unit_square` min_q went `0.000 → 0.804`; every
other MVP domain min_q improved by ≥ 0.04. Node counts unchanged;
`unit_square` triangle count went `139 → 138` (the sliver removed).
Canonical Persson doesn't have this problem in MATLAB because the
MATLAB script ends the iteration differently; our Python port's
loop-exit conditions made it observable.
**Impact**: `tests/test_mvp_domains.py` binding gate (`min_q ≥ 0.30`)
passes. No other tests affected.

## 2026-04-18 — distmesh — canonical-only port; ADMESH helpers deferred

**MATLAB**: `distmesh2d.m` in `10_Distmesh_2d/` (plus ADMESH helpers
`createInitialPointList.m`, `rejectionMethod.m`,
`GetMeshConstraints.m`, `projectBackToBoundary.m`,
`BoundaryCleanUp.m`, `createMeshStruct.m`)
**Python**: `admesh.distmesh.distmesh2d` (canonical Persson only)
**Substitution**: The MATLAB file is a GUI-wrapped, PTS-aware variant
of Persson & Strang (2004) layered with ADMESH-specific constraint
handling. The MVP port implements the canonical algorithm only —
equilateral lattice initial distribution, probability rejection,
truss-force relaxation, boundary projection along `-grad fd` — and
omits all PTS / mesh-constraint machinery.
**Behavior diff**: MVP meshes are valid canonical DistMesh output;
they will not match the ADMESH-variant output node-for-node on
domains that exercise `GetMeshConstraints` / `BoundaryCleanUp`. On
the five MVP test domains (pure SDF inputs, no PTS constraints)
this is a non-issue.
**Impact**: Full ADMESH `distmesh2d` variant lands in post-MVP
phase P3 (boundary + full routine). Any caller needing PTS
structures or boundary-segment constraints must wait.

## 2026-04-18 — distance — SignedDistanceFunction MVP subset

**MATLAB**: `SignedDistanceFunction.m` + `PTS2PointList.m` in
`03_Distance_Function/`
**Python**: `admesh.distance.signed_distance`, `admesh.distance.grad_sdf`
**Substitution**: The MATLAB function is much heavier than the MVP
needs — it operates on a `PTS` structure (kd-tree nearest-neighbor
over per-segment exact-distance queries) and returns a full grid
distance field plus metadata. The MVP port provides grid evaluation
of a caller-supplied analytic SDF plus a 4th-order finite-difference
gradient. No kd-tree, no PTS I/O.
**Behavior diff**: Analytic SDFs are exact to floating-point
precision; the 4th-order gradient converges to 4th order on smooth
fields. For MVP domains (all analytic), this yields strictly
higher accuracy than the MATLAB path. The PTS-driven path handles
polygon inputs with arbitrary segments — the MVP path does not.
**Impact**: PTS + kd-tree implementation deferred to post-MVP
phase P4 (reference-fixture validation). MVP domains are analytic,
so this is sufficient for the triangulation gate.

## 2026-04-18 — in_polygon — mex-only MATLAB; canonical reimpl

**MATLAB**: `12_In_Polygon/` is **mex-only** in the upstream repo
(no `.m` source), so there is nothing to diff against.
**Python**: `admesh.in_polygon.in_polygon`
**Substitution**: Vectorized ray-cast test, plus an on-boundary
second-return that matches MATLAB's documented canonical
`inpolygon(xq, yq, xv, yv)` two-return signature (`in`, `on`). This
is what every ADMESH call site assumes. Chose a pure-NumPy
implementation over `matplotlib.path.Path.contains_points` because
the latter doesn't expose an `on`-boundary result.
**Behavior diff**: Matches MATLAB's canonical inpolygon on the
stage's fixture tests to the documented tolerance. Floating-point
ties on polygon vertices are resolved by a small `geps`-style
epsilon, which differs from MATLAB's implementation choice by an
unobservable amount in practice (no test has surfaced a difference).
**Impact**: Every downstream caller (distance, distmesh, routine)
gets drop-in compatibility.

## 2026-04-18 — general — `.mex*` binaries discarded

**MATLAB**: `.mexw64`, `.mexmaci64`, `.mexa64` files throughout the
upstream tree (chiefly builds of `MeshSizeIterativeSolver.c`).
**Python**: n/a — these platform binaries are skipped.
**Substitution**: Constitution Article II.8 declares them
throwaway; the Python port replaces the C source with Numba
(`admesh.mesh_size._solve_iter_nb`) and never ships a binary.
**Behavior diff**: None at the API level; the `.mex*` files are
build artifacts, not source.
**Impact**: `pip install admesh` needs no C toolchain — satisfies
the Article I north-star "installs without a C toolchain".
