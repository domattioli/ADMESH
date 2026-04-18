# Session 0 — ADMESH scaffold + M.1 leaf utilities

**Goal (plain English):** get the repo from empty to a state where
`admesh.triangulate()` has a clear path forward — governance docs
written, package imports, and the smallest stage modules
(`in_polygon`, `quality`) plus a test-domain registry (`domains.py`)
implemented against MATLAB reference behavior. M.1 is the deliverable
that lets M.2–M.4 proceed independently.

Global context: the MVP (per `PROJECT_PLAN.md`) is triangulation on 5
test domains. M.1 is leaf utilities + domain definitions; M.2 is
distance + mesh-size; M.3 is DistMesh + driver; M.4 is validation.

---

## Binding gate for session 0

`pytest tests/ -q` passes with:
- `test_smoke.py` — package imports (✅ shipped in M.0).
- `test_in_polygon.py` — at least 3 cases (point inside convex, point
  outside, point on boundary edge) pass against hand-computed
  expected values.
- `test_quality.py` — mesh-quality metric agrees with a hand-derived
  expected value on an equilateral triangle (q = 1.0) and a
  degenerate triangle (q < 0.1).
- `test_domains.py` — all 5 domain SDFs return negative inside a
  known interior point, positive outside, approximately zero on a
  known boundary point.

No PNG output required yet; that's M.4.

---

## Workstreams

### WS0 — Scaffold (✅ SHIPPED)

- Governance docs (`CONSTITUTION.md`, `PROJECT_PLAN.md`, `CLAUDE.md`).
- `admesh/` with 14 stub modules + `__init__.py`.
- `pyproject.toml`, `.gitignore`, `LICENSE` (Apache-2.0), `test_smoke.py`.
- Remote live at `github.com/domattioli/ADMESH`, pushed to `main`.

### WS1 — Port `in_polygon` (M.1a)

**MATLAB source:** `01_ADMESH_Library/12_In_Polygon/*.m` — inspect first;
may be a simple wrapper around MATLAB's `inpolygon`.

**Plan:**
1. Read the MATLAB sources; note the exact signature(s) and boundary-
   inclusion semantics.
2. Implement `admesh/in_polygon.py::in_polygon(xq, yq, xv, yv) -> bool_array`
   using a vectorized ray-casting algorithm (NumPy).
3. Add `on_boundary` tolerance argument if MATLAB's exposes one.
4. `tests/test_in_polygon.py` with ≥ 3 cases.

**Falsifier:** a point on a horizontal edge must classify
consistently with MATLAB. If MATLAB's `inpolygon` returns a tuple
`(in, on)`, we replicate.

### WS2 — Port `quality` (M.1b)

**MATLAB source:** `11_Mesh_Quality/MeshQuality.m`.

**Plan:**
1. Read the `.m` file; identify which quality metric(s) it computes
   (aspect ratio? min-angle? Pan-et-al `eta_e`?).
2. Implement `admesh/quality.py::mesh_quality(vertices, triangles)`.
3. Test on equilateral (q=1) and degenerate-sliver (q~0) triangles.

### WS3 — Define 5 test domains (M.1c)

**New module** `admesh/domains.py` (not a port — MVP infrastructure).

**Plan:**
1. Define a `Domain` dataclass: `name, sdf(points) -> distances,
   bbox, fixed_points`.
2. Implement 5 SDFs:
   - `unit_square` — `max(|x|, |y|) - 0.5`
   - `l_shape` — union / difference of two squares
   - `unit_disk` — `norm(p) - 1`
   - `annulus` — `max(inner - norm(p), norm(p) - outer)`
   - `notched_rectangle` — rectangle minus a small rectangle at the pinch
3. `tests/test_domains.py` with sign-check at interior / exterior /
   boundary probe points for each.

### WS-final — Wrap-up

- `pytest tests/ -q` green.
- Commit per WS (3 commits: one per module + tests).
- Update `PROJECT_PLAN.md` "Where we are today" to mark M.1 shipped.
- Draft `session_1_plan.md` targeting M.2 (distance + mesh_size).

---

## Out of scope for session 0

- M.2 `distance.py` / `mesh_size.py` — next session.
- Numba solver — next session.
- MATLAB reference fixtures (`.mat` → `.npz` toolchain) — deferred
  until a stage actually needs a captured fixture. `in_polygon`,
  `quality`, and the domain SDFs are small enough to test against
  hand-derived expected values without MATLAB round-trip.
- PNG rendering — M.4.

---

## Risks

- **Unknown MATLAB semantics for `inpolygon` boundary cases.** Mitigation:
  read the MATLAB source WS1 step 1 before writing code; if the source
  uses MATLAB's builtin, match `scipy`/`shapely` behavior and document
  any divergence in `docs/PORTING_NOTES.md`.
- **`MeshQuality.m` may cover multiple metrics.** Mitigation: port them
  all, one function each, named per the MATLAB function name.
- **MVP's notched-rectangle SDF design is under-specified.** Mitigation:
  make the pinch width a parameter; default to a 0.1-wide notch in a
  2×1 rectangle.
