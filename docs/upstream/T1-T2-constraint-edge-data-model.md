# T1/T2 — Internal-Constraint Edge Data Model (design note)

**Issue:** #186 (Evaluate ADMESH+ v3 / GMesh). Advances the two techniques the
evaluation held as *candidate-adopt, blocked on a representation we do not have
yet* — T1 (1D constraint identification) and T2 (grid-point distribution along
constraints). See `docs/upstream/ADMESH-PLUS-V3-GMESH-EVALUATION.md` §T1/§T2 and
its **Recommended next step #2**: *"open a spec for the internal-constraint edge
data model first — the representation `distmesh.py`/`api.py` would need to carry
constraint edges — before any DEM-extraction or point-distribution work."*

This note is that pre-spec design pass. It does **not** implement anything, does
**not** read the (network-blocked) Kang & Kubatko full text — it reasons only
about *our* additive representation. **No locked `_stages/` module is touched or
proposed to change** (Constitution Principle I).

---

## 1. Why a representation is the blocker

T1 feeds channel networks / flood-control features into the mesher as **internal
constraints** — polylines in the domain interior that the final triangulation
must honor as *forced edges* (a mesh edge lies along each constraint segment).
T2 then distributes 1D grid points along those polylines by local curvature and a
minimum spacing. T2 is meaningless until T1's polylines exist to place points
onto, so both gate on one artifact: **how a constraint polyline is carried from
`Domain` through `triangulate()` into the triangulation.**

Today that artifact is absent, and the gap is specific.

## 2. Current state (grounded)

| Concern | What exists today | File:line |
|---|---|---|
| Fixed **points** on the domain | `Domain.pfix: np.ndarray \| None` | `src/admesh/api.py:284` |
| Fixed points into the triangulator | `distmesh2d(..., pfix=...)` prepends them to `p` and preserves them through relaxation | `src/admesh/_stages/distmesh.py:97, 185–195` |
| Fixed **edges** (interior constraint segments) | **none** — no field, no parameter, no enforcement pass | — |
| Boundary polylines | `BoundarySegment` (node ids + ADCIRC BC code) — but this is an **output** structure on `Mesh`, describing a triangulated boundary, not an **input** constraint | `src/admesh/api.py:36` |

**Load-bearing finding: fixed points ≠ fixed edges.** `pfix` guarantees the
listed *vertices* survive relaxation; it does **not** guarantee that consecutive
constraint vertices are *connected by an edge* in the output. distmesh builds a
Delaunay triangulation over all points each iteration (`distmesh.py`), and
Delaunay will choose whichever diagonal is locally empty-circumcircle — which
need not be the constraint segment. So "densify the polyline into `pfix` points"
places the vertices but can still triangulate *across* the channel rather than
*along* it. Constraint **edge** enforcement is a strictly stronger requirement
than the `pfix` seam already provides.

## 3. Design options (all additive; the locked seam is `pfix`)

The one sanctioned seam into the locked triangulator is its existing `pfix`
parameter. Everything below lives in the **additive** api layer
(`api.py` / a new helper module); none edits `distmesh.py`.

**Option A — densify-to-`pfix` (approximate).** Sample each constraint polyline
at ≈`h_min` spacing, concatenate the samples into `Domain.pfix`, triangulate as
today. *Pro:* zero locked-module change, ~30 LOC, reuses the existing seam.
*Con:* places the points but does **not** guarantee the edges (see §2) — the
channel is *seeded* but not *enforced*. Adequate only where dense seeding makes a
cross-channel diagonal geometrically unlikely; not a correctness guarantee.

**Option B — post-hoc constrained edge recovery (exact).** After distmesh
returns, run an additive edge-flip / segment-insertion pass (or a constrained
Delaunay via the `triangle` library behind an optional extra) that forces each
constraint segment to appear as a mesh edge. *Pro:* actually honors the
constraint. *Con:* new additive routine or new optional dependency; more test
surface; must prove it preserves structural validity (positive-area tris,
watertight boundary).

**Option C — carry constraints on `Domain`, MVP via A, exact via B later.** Add
one additive field `Domain.constraints: list[np.ndarray] | None` (each entry an
`(N, 2)` polyline), thread it through `triangulate()`; the MVP path densifies to
`pfix` (Option A) and *documents the approximation*, with Option B's exact
recovery deferred behind a flag until a measured case needs it.

## 4. Recommendation

Adopt **Option C as the first spec's scope.** It is the smallest representation
that unblocks both T1 and T2, keeps the locked `_stages/` untouched, and is
honest about the A-vs-B correctness gap instead of hiding it:

1. **Representation (T1 enabler):** additive `Domain.constraints` field +
   validation (`(N, 2)` float64 polylines, ≥2 points, inside `bbox`), mirroring
   the existing `pfix` validation shape.
2. **Threading:** `triangulate()` densifies constraints to `pfix` at `h_min`
   spacing (Option A MVP), with a `docs/PORTING_NOTES.md` entry stating the
   seeded-not-enforced limitation explicitly.
3. **Point distribution (T2):** a 1D curvature+min-spacing point-placement helper
   along a polyline — additive, consumes `Domain.constraints`, parameterized by
   `h_min` and local curvature (mirrors `_stages/curvature.py` → `size_field.py`
   in spirit, no locked change).
4. **Exact enforcement (deferred):** Option B (post-hoc edge recovery / CDT)
   lands only when a fixture demonstrates the Option-A seeding produces a
   cross-channel diagonal that matters — gated on measured need, not built blind.

**Not in scope of that spec:** DEM/raster→channel extraction (a separate XL
dependency surface — the eval doc's "do not start with the DEM extraction"), and
any Kang & Kubatko method port (still blocked on the full-text read tracked in
#200; an adopt there also owes the `CITATION.cff` credit per the #186 operator
directive).

## 5. Net

The T1/T2 blocker is one missing additive field plus a documented densification
seam, not a locked-module change — the constraint-edge representation is
designable and buildable within the faithful-port boundary. This note gives the
first spec its scope; it does not open that spec (that is the successor session's
call under the pipeline gate). #186's T1/T2 verdicts move from *"needs a
representation we don't have"* to *"representation scoped; Option C ready to
spec."*
