# Session 3 — Phase P3 lift: boundary + mesh_size + distmesh

**Goal (plain English):** lift the three core-algorithm modules
above MVP level in one coordinated pass.

1. Add a **boundary** module that models ADMESH's "PTS" domain
   (polygonal boundaries + per-segment boundary-condition tags) and
   can enforce BCs on a mesh node set.
2. Extend **mesh_size** so `build_h` can take a PTS and shrink `h`
   near BC segments by configurable per-type weights — a more
   faithful analogue of the MATLAB size-field composition than the
   current pure-SDF composer.
3. Add an **ADMESH-variant distmesh** pathway that layers boundary
   constraints, a better boundary-cleanup pass, and a structured
   mesh output on top of the canonical Persson loop shipped in M.3.

When this session ships, `triangulate(domain_or_pts, ...)` can
consume either a bare `Domain` (MVP path, unchanged) or a `PTS`
with BCs (P3 path, richer), and the downstream modules compose
naturally.

> **Scope note.** This plan replaces the original 2-branch session
> 3 plan (Branch A faithful-port backfill / Branch B Phase P2
> clean-room) drafted at session-2 close. The 2-branch plan is
> preserved in git history under commit `d2fb540`. Bathymetry,
> tide, and inpaint are explicitly **out of scope** for this
> session — deferred to Phase P2 under a later plan.

**Session-start read order** (per `CLAUDE.md` + Article VII):
`CONSTITUTION.md` → `PROJECT_PLAN.md` → `CLAUDE.md` →
`docs/session_2_state.md` → `docs/session_2_report.md` → this plan.

---

## WS0 — Environment check (short)

```bash
ls /workspace/QuADMesh-MATLAB/01_ADMESH_Library/ 2>/dev/null
```

- **If present:** Article II.1 applies normally — faithful port;
  add MATLAB-parity fixtures under `tests/fixtures/<stage>/`.
- **If absent:** continue clean-room, log a `SOURCE_UNAVAILABLE`
  row in `docs/persistence_journal.md`. If this is the 3rd
  occurrence, propose a Constitution amendment (Article II.1
  codicil: clean-room + deferred-faithful-port is the default mode
  when `/workspace/QuADMesh-MATLAB` is absent).

---

## Binding gate

All six of:

1. `admesh.boundary` exposes a `PTS` (or equivalently named)
   dataclass with: outer + inner polygon rings, per-segment BC
   type (enum: `OPEN`, `WALL`, or a 2–3 value clean-room subset),
   and a `from_domain(domain, *, n_bnd)` constructor that samples a
   `Domain`'s zero-level set into a discrete polygon.
2. `admesh.boundary.enforce_boundary_conditions(pts, p)` returns a
   per-node classification (interior / boundary-with-type) with
   parity on a small fixture (unit square: 4 corner nodes, each
   side labeled WALL).
3. `admesh.mesh_size.build_h` accepts a `pts` keyword (optional);
   when provided, `h` is multiplicatively reduced within a
   user-supplied `boundary_scale` band of each BC segment. The
   zero-argument path still returns a uniform lambda (MVP default).
4. `admesh.distmesh.distmesh2d_admesh` (or `distmesh2d(..., pts=,
   cleanup=True)`) runs the canonical loop plus: (a) per-PTS-segment
   fixed-point interpolation into `pfix`; (b) a post-loop
   `_boundary_cleanup` pass that culls slivers at the boundary;
   (c) returns a `MeshOutput` dataclass with `p`, `t`, and a
   node→BC-type label vector.
5. `admesh.routine.triangulate` accepts a `PTS` (dispatched to the
   ADMESH path) or a `Domain` (existing MVP path). The MVP binding
   gate from session 1 (`tests/test_mvp_domains.py`:
   `min_q ≥ 0.30, mean_q ≥ 0.60` on all 5 domains) continues to
   pass unchanged.
6. `pytest tests/ -q` green; new files: `tests/test_boundary.py`,
   `tests/test_distmesh_admesh.py`; extensions to
   `tests/test_mesh_size.py`. Target ≥ 80 tests (65 → 80, +15).

---

## Workstreams

### WS1 — `admesh/boundary.py` (PTS + BC enforcement)

**Deliverables:** `admesh/boundary.py`, `tests/test_boundary.py`.

**Algorithm:**
- `PTS` dataclass: `rings: list[np.ndarray]` (each `(N,2)`, ring 0
  is outer, rings 1+ are inner/holes), `bc_type: list[np.ndarray]`
  (same length, each `(N,)` enum array aligned to segment start),
  `attributes: dict` (opaque passthrough).
- `BoundaryType(IntEnum)`: `OPEN=0`, `WALL=1`. (Clean-room: 2-type
  minimum. MATLAB has more; expand in a faithful-port backfill.)
- `PTS.from_domain(domain, *, n_bnd)` — marches a contour along
  the zero-level set of `domain.fd` using a grid evaluation + a
  simple contour tracer (or `matplotlib._contour` if stable). Emits
  `(n_bnd,)` roughly-evenly-spaced boundary samples per ring.
- `enforce_boundary_conditions(pts, p, *, tol)` — for each node in
  `p`, returns the index of the nearest `pts` segment if distance
  < `tol`, else `-1`. Resulting `(N,)` int array is consumed by
  downstream modules.

**Tests:**
- Unit square → 4 rings with BC=WALL everywhere; corner nodes
  detected at 4 known locations.
- Annulus → 2 rings (outer + 1 inner), lengths in ratio π·outer :
  π·inner to within grid tolerance.
- `enforce_boundary_conditions` on synthetic nodes at known (x,y)
  returns correct segment labels.

**Risk:** the contour tracer. Cheap alternative: re-use the M.4
mesh's boundary edges — since `triangulate(domain)` already
produces boundary-coincident nodes, sample those instead of
contour-tracing. Fallback documented inline.

### WS2 — `build_h` PTS-aware reduction

**Deliverables:** updated `admesh/mesh_size.py::build_h`,
extensions in `tests/test_mesh_size.py`.

**Algorithm:**
- New optional kwarg `pts: PTS | None = None` and
  `boundary_scale: dict[BoundaryType, float] | float | None = None`.
- Effect: for each grid cell, compute the distance to the nearest
  PTS segment of each type, then `h_bnd[type] = max(boundary_scale
  [type], d_to_type_segment)`. Final `h = min(h, min(h_bnd[t] for
  t))`. Composes with existing `curvature_scale`, `medial_scale`.
- When `pts=None`, behavior is identical to the current `build_h`.

**Tests:**
- Unit square with `boundary_scale=0.03`: `fh` near a side is
  ≤ 0.04, `fh` at the center is ≈ `base`.
- End-to-end `triangulate(unit_square, fh=build_h(..., pts=pts,
  boundary_scale=0.03))` passes M.4 quality gate and shows a
  higher node density near boundaries than the uniform-fh version.
- Regression: the MVP M.4 gate still passes on all 5 domains.

### WS3 — ADMESH-variant distmesh pathway

**Deliverables:** extensions in `admesh/distmesh.py`
(`_boundary_cleanup`, `distmesh2d_admesh`), updated
`admesh/routine.py` dispatcher,
`tests/test_distmesh_admesh.py`.

**Algorithm:**
- `MeshOutput` dataclass: `p`, `t`, `node_bc: np.ndarray` (int, -1
  interior / else BoundaryType).
- `_boundary_cleanup(p, t, pts, *, min_area)` — after the main
  loop, drop triangles whose minimum altitude is below
  `min_area_factor * h_local` AND that have two or more boundary
  nodes on the same segment (classic sliver). Reindex.
- `distmesh2d_admesh(pts, *, fh, h0, **opts)` — canonical loop
  seeded with PTS ring vertices as initial `pfix`; post-loop runs
  `_boundary_cleanup`; returns `MeshOutput`.
- `triangulate` in `routine.py` gets a thin dispatcher: if the
  first arg is a `PTS`, call `distmesh2d_admesh`; else preserve
  the existing `Domain` path.

**Tests:**
- `unit_square` via PTS path produces mesh with
  `(node_bc == WALL).sum() == N_boundary_nodes`.
- `annulus` via PTS path has 2 BC rings, both labeled WALL.
- Sliver-removal: construct a degenerate input (repeat an old
  failure case like the pre-M.4 `unit_square`) and verify
  `_boundary_cleanup` would have caught it.
- MVP regression: `tests/test_mvp_domains.py` unchanged-and-green.

### WS-final

1. `pytest tests/ -q` green; target ≥ 80 tests.
2. 3 new `docs/PORTING_NOTES.md` entries (boundary / build_h-PTS /
   distmesh-admesh), each flagged with the clean-room status.
3. `PROJECT_PLAN.md` "Where we are today" rolled to post-P3-lift.
4. `docs/session_3_report.md` + `docs/session_3_state.md` +
   `docs/session_4_plan.md` (Phase P2 kickoff: bathymetry + tide
   + inpaint, now that the PTS structure can carry per-segment
   physical data).
5. Commit + push to the session's designated branch. Do NOT
   auto-open a PR.

---

## Out of scope for session 3

- **Bathymetry + tide + inpaint** (Phase P2) — deferred per user
  redirect at session-3 start.
- **Faithful-port backfill** of session-2 curvature / medial /
  composer — blocked on MATLAB clone.
- **Full MATLAB PTS field set** — our clean-room PTS is
  minimum-viable (rings + 2 BC types + opaque attrs). Additional
  MATLAB fields (hydraulic sub-types, node attributes) backfill in
  a later session with MATLAB source.
- **Quad conversion** — permanently out of ADMESH (see 2026-04-18
  project-plan revision).

---

## Session budget

- WS0: ≤ 3%.
- WS1 (boundary + PTS): ~35%.
- WS2 (build_h PTS-aware): ~20%.
- WS3 (distmesh-admesh + cleanup + dispatcher): ~30%.
- WS-final: ~12%.

If WS1 overflows, WS2 can ship with a simplified "boundary_scale
applied uniformly to the domain boundary, ignoring BC type" — still
a net forward step. WS3 is the item most likely to compress; if so,
the dispatcher + `MeshOutput` land without the cleanup pass, and
cleanup rolls to session 4.

---

## Falsifier

If WS3's `_boundary_cleanup` tries to remove triangles that pass
the M.4 binding gate — STOP. That means the cleanup criterion is
wrong, not that the MVP gate is too strict. Revert, diagnose,
adjust. Never widen the M.4 gate to accommodate cleanup behavior.
