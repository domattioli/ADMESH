# No technique from ADMESH+ v3 or GMesh clears the bar for immediate adoption

Tracking issue: [#186](https://github.com/domattioli/ADMESH/issues/186). This note gives a per-technique verdict for two newer mesh generators: **adopt** (additive layer, new spec), **benchmark-only**, or **decline** (with reason). It changes no code.

The strongest candidate is T4 (medial axis). It needs a full-text method read first. T1 and T2 are real new capability, but they are a multi-spec effort. Everything else is benchmark-only or declined.

## Constitution Principle I binds every verdict

This repository is a faithful port of the 2012 ADMESH library (`01_ADMESH_Library`). The 13 locked stage modules under `src/admesh/_stages/` must stay numerically identical to the MATLAB reference. No verdict here touches them.

Every "adopt" verdict lands in the additive Pythonic layer (`api.py`, `size_field.py`, `loaders.py`, a new module, …). Each one gets its own spec. None lands inside `_stages/`.

## Summary of verdicts

| # | Technique | Source | Verdict | Where it would land |
|---|-----------|--------|---------|---------------------|
| T1 | 1D constraint identification from DEM | ADMESH+ v3 | benchmark-only near-term; candidate-adopt long-term | new spec (constraint-edge model first) |
| T2 | Grid-point distribution along constraints | ADMESH+ v3 | candidate-adopt, gated on T1 | additive 1D point-placement routine |
| T3 | Constraint → 2D size-function integration | ADMESH+ v3 | benchmark-only | compare vs `min`-stacked `size_field.py` |
| T4 | Revised medial-axis computation | ADMESH+ v3 | benchmark-only (needs full-text read) | additive alt medial-axis backend; locked FMM stays default |
| T5 | GUI (`ADMESH.mlapp`) | ADMESH+ v3 | decline (package); UI reference only | n/a, playground reference |
| T6 | Voronoi connectivity-preserving cells | GMesh | decline as core; I/O-bridge at most | speculative I/O bridge only |
| T7 | Variable local refinement controls | GMesh | benchmark-only | expressiveness comparison vs `h_*`/octree |

## Recommended next steps

1. Read the ADMESH+ v3 medial-axis method section. The [OSU-CHIL/ADMESH](https://github.com/OSU-CHIL/ADMESH) MATLAB source also works. Benchmark a candidate additive backend against `medial_distance_FMM` on the WNAT and octree fixtures for runtime and robustness. Promote T4 to adopt or decline on the result.
2. If T1/T2 are pursued, open a spec for the **internal-constraint edge data model** first. This is the representation `distmesh.py`/`api.py` would need to carry constraint edges. Do it before any DEM-extraction or point-distribution work.
   - The pre-spec design is done: `docs/upstream/T1-T2-constraint-edge-data-model.md` scopes this.
   - It chooses Option C: additive `Domain.constraints` plus a densify-to-`pfix` MVP.
   - The locked `distmesh2d(pfix=)` seam is the only entry point.
   - Exact edge recovery is deferred.
3. Any PR that ports a Kang & Kubatko (2024) technique adds `Kang, Younghun` to `CITATION.cff` in the same commit (see [Author credit](#author-credit)).

## Sources

Two branches of ADMESH descend from Conroy, Kubatko & West (2012), "ADMESH: An advanced, automatic unstructured mesh generator for shallow water models" (*Ocean Dynamics* 62, 1503–1517). This repository ports that 2012 library.

The original group's current MATLAB line is **ADMESH+ v3.0.1** (Kang, Kubatko, Conroy & West; GPL-3.0; [OSU-CHIL/ADMESH](https://github.com/OSU-CHIL/ADMESH); [zenodo 10.5281/zenodo.10242565](https://doi.org/10.5281/zenodo.10242565)). Its methods are published in:

- **ADMESH+ v3**: Kang, Y. & Kubatko, E.J. (2024). "An automatic mesh generator for coupled 1D–2D hydrodynamic models." *Geoscientific Model Development* 17, 1603–1625. [doi:10.5194/gmd-17-1603-2024](https://doi.org/10.5194/gmd-17-1603-2024). The article is open-access. A preprint is at [egusphere-2023-1434](https://egusphere.copernicus.org/preprints/2023/egusphere-2023-1434/).

The second source is a different codebase: a watershed-hydrology mesher. It serves here as an element-paradigm and refinement-controls comparison, not as a port candidate:

- **GMesh**: "GMesh: A Flexible Voronoi-Based Mesh Generator with Local Refinement for Watershed Hydrological Modeling." *Hydrology* 12(10), 255 (2025). [doi:10.3390/hydrology12100255](https://doi.org/10.3390/hydrology12100255). It is open-source Python, built inside the Watershed Modeling Framework (WMF) for the GHOST hydrological model.

## Author credit

The operator noted on #186: *"If we include content from Kang's paper we should consider adding him as a codebase author."*

This rule applies to any **adopt** verdict that ports a Kang & Kubatko (2024) technique into this codebase. The implementing PR must add `Kang, Younghun` to `CITATION.cff` `authors` and to the appropriate `references` entry. It does so in the same commit that lands the technique.

The rule does not apply to benchmark-only or decline verdicts, because no adopted content means no new author.

---

## Source 1: ADMESH+ v3 (Kang & Kubatko 2024)

The paper contributes a pipeline for **1D internal constraints**. These are the channel networks and flood-control topographic features that a coupled 1D–2D shallow-water model needs as mesh-internal edges, not just as a size field.

The paper states four novelties:

1. Identify 1D constraints from a DEM plus land/water delineation.
2. Distribute grid points along those constraints by feature curvature and a user-set minimum spacing.
3. Fold the constraints into the 2D mesh size function.
4. Compute the **medial axis of a polygon** with a new method.

### T1: 1D constraint identification from DEM + land/water delineation

**Verdict: benchmark-only (near-term), candidate-adopt (long-term, new spec).**

This capability is new relative to the 2012 port. It extracts channel networks and flood-control features from raster input. It feeds them to the mesher as *internal constraints*.

This repository consumes a domain (boundary + optional SDF) and produces a triangulation. It has no DEM-to-channel-network extraction stage. It does not carry internal constraint edges through `triangulate()` at all.

Adopting the full pipeline is XL effort. It needs:

- raster/DEM handling (a new dependency surface);
- a constraint-edge data model that `distmesh.py`/`api.py` do not have today.

That is a multi-spec undertaking, not a port of one function.

**Near-term action:**

1. Treat the ADMESH+ v3 example meshes as comparison targets. They are the Middle Bosque River Watershed (~183,610 elements) and two Tidal Neches River Watershed variants. Meshes come through Valence, with attribution.
2. Scope the internal-constraint data model as its own spec before any implementation.
3. Start with the constraint-edge representation that everything downstream needs. Do not start with DEM extraction.

### T2: Grid-point distribution along constraints (curvature + minimum spacing)

**Verdict: candidate-adopt (additive layer, gated on T1's constraint model).**

This technique places 1D grid points along a constraint by local curvature and a user-prescribed minimum spacing. It is close in spirit to how our size field already treats curvature (`_stages/curvature.py` → `size_field.py`).

The mechanism is additive and touches no locked module. It is a 1D point-placement routine along a polyline, parameterized by curvature and `h_min`.

It needs T1's internal-constraint representation to place points *onto*. Implemented first, it would have nothing to consume it. Sequence it after the constraint-edge data model exists.

### T3: Internal-constraint integration into the 2D mesh size function

**Verdict: benchmark-only, compare against our `min`-stacked composition first.**

Our size field composes curvature, medial-axis, bathymetry and tide terms by `min`-stacking (`size_field.py`, `compose_size_field`). ADMESH+ v3 folds internal constraints into its 2D size function as an additional influence.

Before adopting their scheme, verify on a shared fixture that it is compatible with `min`-stacking or strictly better. Do not assume it composes cleanly.

The open question has two branches:

- A constraint contributes as just another `min` term. This is cheap and already expressible.
- A constraint needs a different blending operator. This is more work, and a measured quality/faithfulness difference must justify it.

Resolve it with a benchmark, not by porting blind.

### T4: Revised medial-axis computation

**Verdict: benchmark-only, strongest candidate, but needs a full-text method read before an adopt decision.**

This is the most directly comparable item. Our medial axis is a distance-transform / fast-marching construction (`_stages/medial_axis.py`: `MedialAxisFunction`, `TriMedialAxisFunction`, `medial_distance_FMM`). It is a faithful port of the 2012 approach. It is also one of the more runtime-sensitive and robustness-sensitive stages on real coastal boundaries.

Kang & Kubatko describe a *novel* method for the medial axis of a polygon. The abstract advertises it as a headline contribution, so it merits a rigorous comparison.

Two cautions keep this at benchmark-only:

1. **Faithfulness boundary.** `_stages/medial_axis.py` is locked, so a revised method cannot replace it. It would land as an *alternative* additive-layer medial-axis backend that `triangulate()` can opt into. The locked FMM path stays the default and the numerical reference.
2. **The exact algorithm must be read from the full text first.** The open-access GMD article and the EGUsphere preprint were both unreachable (HTTP 403 via the agent proxy). The construction, the pruning criterion, the complexity, and the robustness claims are therefore unverified.
   - The adopt/decline call needs a read of the method section (or the OSU-CHIL MATLAB source directly).
   - Then benchmark the candidate against `medial_distance_FMM` on the WNAT and octree fixtures for runtime and robustness.
   - Until that read happens, T4 stays benchmark-only.

**Baseline landed (#200).** A runtime and robustness baseline of the current grid-based path is measured. See `docs/upstream/T4-medial-axis-benchmark.md` and `scripts/bench_medial_axis.py`.

Key results:

- Cost is O(1/δ²).
- Accuracy on a *curved* medial axis is δ-bounded: ≈ 0.9 δ on the annulus, never converging below O(δ).
- The thin channel held across all tested δ.

The paper full-text read remains network-blocked, so the adopt/decline verdict is still deferred. The baseline pins *where* an exact grid-free method would have to win.

### T5: GUI (`ADMESH.mlapp`, MATLAB App Designer)

**Verdict: decline for the package; note as UI reference only.**

A desktop MATLAB GUI is out of scope for a Python library. Keep it as a UI reference for the browser playground work on domattioli.com (spec-023 GitHub-Pages interactive demo), nothing more.

---

## Source 2: GMesh (2025)

GMesh is a watershed-hydrology mesher built in Python inside the Watershed Modeling Framework. It produces **Voronoi polygons** that preserve river-segment and hillslope connectivity for surface–subsurface interaction. It offers variable local refinement targeting named watershed features. It was demonstrated on Iowa's Bear Creek watershed at 10,000–30,000 elements.

### T6: Voronoi polygons preserving river/hillslope connectivity

**Verdict: decline as a core change; benchmark-only / I/O-bridge at most.**

GMesh uses a different element paradigm from ours. This repository generates *triangular* meshes for the shallow-water equations. GMesh generates *Voronoi* control volumes for a finite-volume hydrological model (GHOST).

A Voronoi mesh is the dual of a Delaunay triangulation, so the two are related. Adopting Voronoi-cell output would still be a new output type, not an improvement to the triangulator.

The realistic ceiling is an *I/O bridge or benchmark comparison*, for example emitting the Voronoi dual of an ADMESH triangulation for a hydrological consumer. Even that is speculative demand, not a requested feature.

Decline as a core change. Revisit only if a concrete downstream consumer asks for Voronoi output.

### T7: Variable local refinement targeting named features

**Verdict: benchmark-only, expressiveness comparison against our existing knobs.**

GMesh's local-refinement controls target specific watershed sub-regions to spend resolution where it matters. We already express spatially-variable resolution through `h_min`/`h_max`/`g` and the octree adaptive background grid (`background="octree"`).

The useful exercise is a *comparison of expressiveness*. Can our existing knobs target a named sub-region the way GMesh's refinement controls do? If not, is the gap worth an additive convenience API?

This is a paper-reading and design-note task, not an implementation. Any gap it surfaces would be additive, never a locked-module change.
