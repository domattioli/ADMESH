# ADMESH Project Plan

Phased roadmap for porting `QuADMesh-MATLAB/01_ADMESH_Library` to
Python. Governance rules in `CONSTITUTION.md`; code layout in
`CLAUDE.md`.

---

## Where we are today (2026-04-18, session 0)

**Shipped:**
- Repo scaffolded (`domattioli/ADMESH`, private).
- Governance docs (`CONSTITUTION.md`, `PROJECT_PLAN.md`, `CLAUDE.md`).
- Package skeleton: `admesh/` with stage-module stubs.
- `pyproject.toml`, `.gitignore`, MIT `LICENSE`.
- Local MATLAB reference clone at `/workspace/QuADMesh-MATLAB`.

**Not shipped:** any stage implementations, reference fixtures, or an
end-to-end pipeline.

---

## North star

A Python package that reproduces the MATLAB ADMESH pipeline on the
reference test domains within documented floating-point tolerance,
installs without a C toolchain, and exposes each of the 13 stages as
an independently-callable function.

---

## MVP — Triangulation on well-planned test domains

**Goal**: given a 2D domain polygon (straight-edge, possibly non-convex,
possibly multiply-connected), produce a triangular mesh. This is the
first deliverable of several.

**In scope for MVP** — the minimum subset of the 13 stages needed to
triangulate:

| Stage | MATLAB source | Python module |
|---|---|---|
| Leaf utilities | `12_In_Polygon/`, `11_Mesh_Quality/MeshQuality.m` | `in_polygon.py`, `quality.py` |
| Signed distance | `03_Distance_Function/SignedDistanceFunction.m` + `PTS2PointList.m` | `distance.py` |
| Mesh-size field | `09_Mesh_Size/MeshSizeIterativeSolver.c` (Numba port) | `mesh_size.py` |
| Triangulation engine | `10_Distmesh_2d/distmesh2d.m` + `fixmesh.m` | `distmesh.py` (triangulation only — NO `tri2quad` yet) |
| Driver | minimal subset of `01_ADMESH_Routine/ADmeshRoutine.m` | `routine.py::triangulate(domain, params)` |

**Explicitly OUT of MVP scope** (deferred to post-MVP phases):
- Quad conversion (`tri2quad`) and mixed-element output.
- Bathymetry-driven sizing (`06_Bathymetry_Function`).
- Tidal-wavelength sizing (`07_Dominate_Tide`).
- Medial-axis sizing (`05_Medial_Axis`) — MVP uses uniform or
  curvature-based mesh-size by default.
- Curvature field (`04_Curvature_Function`) — defer; MVP starts with
  uniform size, adds curvature later if needed for quality gates.
- Boundary-condition enforcement (`08_Enforce_Boundary_Conditions`).
- NaN in-painting (`13_In_Paint_NaNs`) — only needed for grid fields
  that MVP doesn't yet construct.
- Full `ADmeshRoutine.m` + `ADmeshSubMeshRoutine.m` orchestration.

### Test domains (the "well-planned" part)

Design these before porting code; they are the acceptance gate for MVP.

1. **Unit square** `[0,1]²` — trivial sanity; uniform mesh size.
2. **L-shape** — non-convex re-entrant corner.
3. **Unit disk** (curved) — tests boundary resolution with a
   non-polygonal signed-distance function.
4. **Annulus** — doubly-connected topology.
5. **Notched rectangle** (figure-8 or keyhole) — tight pinch point,
   mirrors MADMESHR's `pinch_figure8` as a stress test.

Each domain is defined in `admesh/domains.py` as a `(signed_distance_fn,
bounding_box, fixed_points)` tuple. Tests in `tests/test_mvp_*.py`
generate a mesh on each and assert: completion (no orphaned regions),
element-count within ±15% of a target, and min-quality ≥ 0.30 (loose
gate — we tighten once the port is validated against MATLAB).

### MVP acceptance criteria

- `admesh.triangulate(domain, params)` returns `(vertices, triangles)`
  for all 5 test domains.
- `pytest tests/test_mvp_*.py` all green.
- At least one rendered PNG per domain committed to
  `tests/output/mvp_<domain>.png` as visual evidence.
- Runtime ≤ 60 s per domain on a laptop (the Numba size-field solver
  must not be a wall-clock blocker).

---

## MVP phasing (sub-steps)

**M.0 — Scaffold** (this session).
- Package layout, docs, empty stubs, passing import-smoke test.

**M.1 — Leaf utilities + domain registry**.
- Port `in_polygon.py`, `quality.py`.
- Define the 5 test domains as signed-distance functions in
  `admesh/domains.py`.

**M.2 — Signed distance + mesh-size solver**.
- Port `distance.py` (grid evaluation of a domain sdf).
- Port `mesh_size.py` including the Numba solver (with pure-Python
  parity reference).

**M.3 — DistMesh triangulation + driver**.
- Port `distmesh2d.m` → `distmesh.py::distmesh2d()`, plus `fixmesh`.
- Wire the top-level `admesh.triangulate()` that composes M.1–M.3.

**M.4 — Validate + visualize**.
- Run on all 5 test domains; generate PNGs; tune tolerances.
- If Numba solver is slow, profile; consider Cython fallback per
  constitution Article II.2.

---

## Post-MVP phases

Once triangulation works, the remaining stages port in this order:

**Phase P1 — Quad conversion.**
- `10_Distmesh_2d/tri2quad.m` → `admesh/distmesh.py::tri2quad()`.
- `distquadmesh2d.m`, `distADMESH.m`, `createMeshStruct*.m`.

**Phase P2 — Sizing enrichments.**
- `04_Curvature_Function` → `curvature.py`.
- `05_Medial_Axis` → `medial_axis.py` (FMM + heap helper).
- Integrate into `mesh_size.py` size-field composition.

**Phase P3 — Physical-field sizing.**
- `06_Bathymetry_Function` → `bathymetry.py`.
- `07_Dominate_Tide` → `dominate_tide.py`.
- `13_In_Paint_NaNs` → `inpaint.py` (prerequisite for sparse field
  interpolation).

**Phase P4 — Boundary + full routine.**
- `08_Enforce_Boundary_Conditions` → `boundary.py`.
- `01_ADMESH_Routine/ADmeshRoutine.m` + `ADmeshSubMeshRoutine.m`
  → full `routine.py`.

**Phase P5 — Polish & release.**
- Public API review, type hints, optional PyPI publish, flip repo to
  public.

---

## Deferred / parking lot

- **GUI / visualization.** The MATLAB repo has a GUI (not in
  `01_ADMESH_Library`); not in scope here.
- **ADCIRC `.fort.14` I/O.** Downstream concern.
- **Zero-C-extension permanence.** Article II.2 permits a fallback to
  Cython/C if Numba underperforms.

---

## Revision history

### 2026-04-18 — Initial plan; MVP = triangulation

Adopted at session 0. MVP defined as triangulation-only on 5 test
domains, deferring quad conversion and advanced sizing to post-MVP
phases. Rationale: get an end-to-end "polygon → mesh" pipeline
working before broadening stage coverage.
