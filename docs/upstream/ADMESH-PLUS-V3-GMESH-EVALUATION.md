# Evaluating ADMESH+ v3 and GMesh for Techniques Worth Adopting

Tracking issue: [#186](https://github.com/domattioli/ADMESH/issues/186). This note
records a per-technique verdict — **adopt** (additive layer, new spec),
**benchmark-only**, or **decline** (with reason) — for two newer mesh generators
that are technically adjacent to this repository. It changes no code.

**Constitution Principle I binds this whole exercise.** This repository is a
faithful port of the 2012 ADMESH library (`01_ADMESH_Library`); the 13 locked
stage modules under `src/admesh/_stages/` must stay numerically identical to the
MATLAB reference. Nothing here proposes touching them. Every "adopt" verdict below
lands in the additive Pythonic layer (`api.py`, `size_field.py`, `loaders.py`, a
new module, …) under its own spec, never inside `_stages/`.

## Provenance and lineage

Two branches of ADMESH descend from Conroy, Kubatko & West (2012), "ADMESH: An
advanced, automatic unstructured mesh generator for shallow water models" (*Ocean
Dynamics* 62, 1503–1517). This repository ports that 2012 library. The original
group's current MATLAB line is **ADMESH+ v3.0.1** (Kang, Kubatko, Conroy & West;
GPL-3.0; [OSU-CHIL/ADMESH](https://github.com/OSU-CHIL/ADMESH);
[zenodo 10.5281/zenodo.10242565](https://doi.org/10.5281/zenodo.10242565)), whose
methods are published in:

- **ADMESH+ v3** — Kang, Y. & Kubatko, E.J. (2024). "An automatic mesh generator
  for coupled 1D–2D hydrodynamic models." *Geoscientific Model Development* 17,
  1603–1625. [doi:10.5194/gmd-17-1603-2024](https://doi.org/10.5194/gmd-17-1603-2024).
  Open-access; a preprint is at
  [egusphere-2023-1434](https://egusphere.copernicus.org/preprints/2023/egusphere-2023-1434/).

The second source is a different lineage entirely — a watershed-hydrology mesher,
included here as an element-paradigm and refinement-controls comparison, not a
port candidate:

- **GMesh** — "GMesh: A Flexible Voronoi-Based Mesh Generator with Local Refinement
  for Watershed Hydrological Modeling." *Hydrology* 12(10), 255 (2025).
  [doi:10.3390/hydrology12100255](https://doi.org/10.3390/hydrology12100255).
  Open-source Python, built inside the Watershed Modeling Framework (WMF) for the
  GHOST hydrological model.

## Author-credit note (operator directive)

The operator noted on #186: *"If we include content from Kang's paper we should
consider adding him as a codebase author."* This binds any **adopt** verdict that
ports a Kang & Kubatko (2024) technique into this codebase — the implementing PR
must add `Kang, Younghun` to `CITATION.cff` `authors` and to the appropriate
`references` entry, in the same commit that lands the technique. It does **not**
apply to benchmark-only or decline verdicts (no adopted content ⇒ no new author).

---

## Source 1 — ADMESH+ v3 (Kang & Kubatko 2024)

The paper's contribution is a pipeline for **1D internal constraints** — the
channel networks and flood-control topographic features that a coupled 1D–2D
shallow-water model needs represented as mesh-internal edges, not just as a size
field. Its stated novelties are (i) identifying 1D constraints from a DEM plus
land/water delineation, (ii) distributing grid points along those constraints by
feature curvature and a user-set minimum spacing, (iii) folding the constraints
into the 2D mesh size function, and (iv) a new method for the **medial axis of a
polygon**.

### T1 — 1D constraint identification from DEM + land/water delineation

**Verdict: benchmark-only (near-term), candidate-adopt (long-term, new spec).**

This is genuinely new capability relative to the 2012 port: extracting channel
networks and flood-control features from raster input and feeding them to the
mesher as *internal constraints*. This repository currently consumes a domain
(boundary + optional SDF) and produces a triangulation; it has no
DEM-to-channel-network extraction stage, and it does not carry internal
constraint edges through `triangulate()` at all.

Adopting the full pipeline is XL effort and pulls in raster/DEM handling
(a new dependency surface) plus a constraint-edge data model that
`distmesh.py`/`api.py` do not have today. That is a multi-spec undertaking, not a
port of one function. **Near-term action:** treat the ADMESH+ v3 example meshes
(Middle Bosque River Watershed, ~183,610 elements; two Tidal Neches River Watershed
variants) — already registered in the Valence registry with attribution — as
comparison targets, and scope the internal-constraint data model as its own spec
before any implementation. Do not start with the DEM extraction; start with the
constraint-edge representation that everything downstream would need.

### T2 — Grid-point distribution along constraints (curvature + minimum spacing)

**Verdict: candidate-adopt (additive layer, gated on T1's constraint model).**

Distributing 1D grid points along a constraint by local curvature and a
user-prescribed minimum spacing is close in spirit to how our size field already
treats curvature (`_stages/curvature.py` → `size_field.py`). The mechanism is
additive and does not touch a locked module: it is a 1D point-placement routine
along a polyline, parameterized by curvature and `h_min`. It is, however,
meaningless without T1's internal-constraint representation to place points *onto*.
Sequence it after the constraint-edge data model exists; implementing it first
would have nothing to consume it.

### T3 — Internal-constraint integration into the 2D mesh size function

**Verdict: benchmark-only — compare against our `min`-stacked composition first.**

Our size field composes curvature, medial-axis, bathymetry and tide terms by
`min`-stacking (`size_field.py`, `compose_size_field`). ADMESH+ v3 folds internal
constraints into its 2D size function as an additional influence. Before adopting
their integration scheme, verify it is compatible with — or strictly better than —
`min`-stacking on a shared fixture, rather than assuming it composes cleanly. The
open question is whether a constraint contributes as just another `min` term
(cheap, already expressible) or requires a different blending operator (more work,
must be justified by a measured quality/faithfulness difference). Resolve that with
a benchmark, not by porting blind.

### T4 — Revised medial-axis computation

**Verdict: benchmark-only — strongest candidate, but needs a full-text method read
before an adopt decision.**

This is the most directly comparable item. Our medial axis is a
distance-transform / fast-marching construction (`_stages/medial_axis.py`:
`MedialAxisFunction`, `TriMedialAxisFunction`, `medial_distance_FMM`) — a faithful
port of the 2012 approach, and one of the more runtime-sensitive and
robustness-sensitive stages on real coastal boundaries. Kang & Kubatko describe a
*novel* method for the medial axis of a polygon; the abstract advertises it as a
headline contribution, which makes it worth a rigorous comparison.

Two cautions keep this at benchmark-only rather than adopt:

1. **Faithfulness boundary.** `_stages/medial_axis.py` is locked. A revised
   medial-axis method cannot replace it — it would have to land as an *alternative*
   additive-layer medial-axis backend that `triangulate()` can opt into, with the
   locked FMM path staying the default and the numerical reference.
2. **The exact algorithm must be read from the full text before committing.** The
   open-access GMD article and the EGUsphere preprint were both unreachable from
   this session's network (HTTP 403 via the agent proxy), so the specific
   construction — the pruning criterion, complexity, and robustness claims — is not
   yet verified here. The adopt/decline call on T4 needs a session that can read the
   method section (or the OSU-CHIL MATLAB source directly) and then benchmark the
   candidate against `medial_distance_FMM` on the WNAT and octree fixtures for both
   runtime and robustness. Until that read happens, T4 stays benchmark-only.

**Baseline landed (#200).** A runtime + robustness baseline of the current grid-based
path is now measured — see `docs/upstream/T4-medial-axis-benchmark.md` +
`scripts/bench_medial_axis.py`. Key result: cost is O(1/δ²) and accuracy on a *curved*
medial axis is δ-bounded (≈ 0.9 δ on the annulus, never converging below O(δ)); the thin
channel stayed robust across all tested δ. The paper full-text read remains network-blocked,
so the adopt/decline verdict is still deferred — but the baseline now pins *where* an exact
grid-free method would have to win.

### T5 — GUI (`ADMESH.mlapp`, MATLAB App Designer)

**Verdict: decline for the package; note as UI reference only.**

A desktop MATLAB GUI is out of scope for a Python library. Keep it noted as a UI
reference for the browser playground work on domattioli.com
(spec-023 GitHub-Pages interactive demo), nothing more.

---

## Source 2 — GMesh (2025)

GMesh is a watershed-hydrology mesher built in Python inside the Watershed Modeling
Framework, producing **Voronoi polygons** that preserve river-segment and hillslope
connectivity for surface–subsurface interaction, with variable local refinement
targeting named watershed features. It was demonstrated on Iowa's Bear Creek
watershed at 10,000–30,000 elements.

### T6 — Voronoi polygons preserving river/hillslope connectivity

**Verdict: decline as a core change; benchmark-only / I/O-bridge at most.**

This is a different element paradigm from ours. This repository generates
*triangular* meshes for the shallow-water equations; GMesh generates *Voronoi*
control volumes for a finite-volume hydrological model (GHOST). A Voronoi mesh is
the dual of a Delaunay triangulation, so the two are related, but adopting
Voronoi-cell output would be a new output type, not an improvement to the
triangulator. The realistic ceiling here is an *I/O bridge or benchmark
comparison* — e.g. emitting the Voronoi dual of an ADMESH triangulation for a
hydrological consumer — and even that is speculative demand, not a requested
feature. Decline as a core change; revisit only if a concrete downstream consumer
asks for Voronoi output.

### T7 — Variable local refinement targeting named features

**Verdict: benchmark-only — expressiveness comparison against our existing knobs.**

GMesh's local-refinement controls target specific watershed sub-regions to spend
resolution where it matters. We already express spatially-variable resolution
through `h_min`/`h_max`/`g` and the octree adaptive background grid
(`background="octree"`). The useful exercise is a *comparison of expressiveness*:
can our existing knobs already target a named sub-region the way GMesh's refinement
controls do, or is there a gap worth an additive convenience API? This is a
paper-reading + design-note task, not an implementation — and any gap it surfaces
would be additive, never a locked-module change.

---

## Summary of verdicts

| # | Technique | Source | Verdict | Where it would land |
|---|-----------|--------|---------|---------------------|
| T1 | 1D constraint identification from DEM | ADMESH+ v3 | benchmark-only now; candidate-adopt long-term | new spec (constraint-edge model first) |
| T2 | Grid-point distribution along constraints | ADMESH+ v3 | candidate-adopt, gated on T1 | additive 1D point-placement routine |
| T3 | Constraint → 2D size-function integration | ADMESH+ v3 | benchmark-only | compare vs `min`-stacked `size_field.py` |
| T4 | Revised medial-axis computation | ADMESH+ v3 | benchmark-only (needs full-text read) | additive alt medial-axis backend; locked FMM stays default |
| T5 | GUI (`ADMESH.mlapp`) | ADMESH+ v3 | decline (package); UI reference only | n/a — playground reference |
| T6 | Voronoi connectivity-preserving cells | GMesh | decline as core; I/O-bridge at most | speculative I/O bridge only |
| T7 | Variable local refinement controls | GMesh | benchmark-only | expressiveness comparison vs `h_*`/octree |

**No technique clears the bar for immediate adoption.** T4 (medial axis) is the
strongest candidate and the right first deep-dive, but it is blocked on a full-text
method read that this session's network could not complete. T1/T2 are real new
capability but are a multi-spec effort that must start from an internal-constraint
data model, not from DEM extraction. Everything else is benchmark-only or declined.

**No locked stage module is touched by any verdict above** — Constitution
Principle I is preserved.

### Recommended next steps

1. A session with journal access reads the ADMESH+ v3 medial-axis method section
   (or the [OSU-CHIL/ADMESH](https://github.com/OSU-CHIL/ADMESH) MATLAB source) and
   benchmarks a candidate additive backend against `medial_distance_FMM` on the WNAT
   and octree fixtures for runtime and robustness. Promote T4 to adopt or decline on
   the result.
2. If T1/T2 are pursued, open a spec for the **internal-constraint edge data model**
   first — the representation `distmesh.py`/`api.py` would need to carry constraint
   edges — before any DEM-extraction or point-distribution work. **Pre-spec design
   done:** `docs/upstream/T1-T2-constraint-edge-data-model.md` scopes this
   (Option C — additive `Domain.constraints` + densify-to-`pfix` MVP; the locked
   `distmesh2d(pfix=)` seam is the only entry point; exact edge recovery deferred).
3. Any PR that ports a Kang & Kubatko (2024) technique adds `Kang, Younghun` to
   `CITATION.cff` in the same commit (operator directive, above).
