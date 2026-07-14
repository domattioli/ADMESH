# T4 — Revised medial-axis evaluation (Kang & Kubatko 2024)

Tracking issue: [#200](https://github.com/domattioli/ADMESH/issues/200) — carved out of the
closed ADMESH+ v3 technique evaluation (#186), where **T4 (the revised medial-axis
computation)** was held at *benchmark-only* because a verdict requires the paper's
full-text method section.

**Status of this note:** interim / partial. The full-text method read (acceptance box 1)
is **blocked this session** by a source-access failure (see *Paper access blocker* below).
This note records what can be established without the paper — the current locked
implementation's method, the decision axes, and a documented handoff so a
paper-equipped session can finish the verdict — without touching any locked
`_stages/` module (Constitution Principle I preserved).

---

## Current faithful-port medial-axis method (the baseline to beat)

Source of truth: `src/admesh/_stages/medial_axis.py` (faithful port of
`01_ADMESH_Library/05_Medial_Axis/MedialAxisFunction.m` @ `19b2eb9`). This module is
**locked** (numerically identical to the 2012 MATLAB) — any adopted alternative lands as
an additive, selectable backend under its own spec, never replacing it.

The current medial axis is computed **grid-based**, in this pipeline:

1. **Average Outward Flux (AOF)** — `_average_outward_flux` (module lines ~41–100).
   For each interior grid cell, sum `û · ∇D` over 8 neighbour directions (4 cardinal +
   4 diagonal), divided by 8. Cells that "look outward" score `AOF > 0`.
2. **Threshold** — `medial_axis_mask` (lines ~169): medial axis = cells with
   `AOF > 0.15` (`_AOF_THRESHOLD`, MATLAB `MedialAxisFunction.m` line 47), restricted to
   the interior (`D ≤ 0`).
3. **Morphological thinning** — `_skeletonize_zhang_suen` (lines ~101): scipy
   substitution for MATLAB `bwmorph(MA,'skel',inf)` (Lantuéjoul iteration), giving a
   1-pixel skeleton up to boundary-order symmetry.
4. **Clean** — `_remove_isolated` (lines ~157): drop pixels with zero 8-connected
   neighbours (MATLAB `bwmorph(MA,'clean',inf)`).
5. **Distance-to-axis + LFS** — `apply_medial_axis` (lines ~190):
   `MAD = distance_transform_edt(~MA) * delta`; `LFS = |D| + |MAD|`; `h_lfs = LFS / R`
   clamped to `[hmin, hmax]`; `h0 = min(h_lfs, h0)`.

A Fast-Marching distance variant, `medial_distance_fmm` (lines ~226), also exists.

**Cost/robustness characteristics of the baseline** (grounded in the method, not in a
run this session):
- Cost scales with the **background-grid resolution** `O(N_grid)`, independent of domain
  polygon complexity — the AOF and EDT passes are dense-grid stencils.
- Accuracy of the axis (and therefore of LFS-driven sizing) is **resolution-bounded**:
  thin channels narrower than a few grid cells can under-resolve or fragment the
  skeleton, and morphological thinning near junctions is sensitive to grid-order
  symmetry (documented in `PORTING_NOTES.md`).
- Valid benchmark targets are analytic domains with a known medial axis (unit disk,
  annulus, thin rectangle) plus the real WNAT coastal boundary — see
  `T4-medial-axis-benchmark.md` (Parts A/B/C), which measures these. **The octree
  `tests/fixtures/octree/river-into-bay_ratio{10,20,40,100,1000}.npz` fixtures are NOT
  medial-axis comparison targets:** they are point-set inputs to the octree
  background-grid stage, not medial-axis SDF grids, so there is no grid medial-axis path
  to time on them (established in the benchmark note's Part C — do not re-scope them into a
  medial-axis harness).

## The candidate (T4)

Kang, Y. & Kubatko, E.J. (2024), *Geosci. Model Dev.* **17**, 1603–1625,
[doi:10.5194/gmd-17-1603-2024](https://doi.org/10.5194/gmd-17-1603-2024) (open access).
Per the #186 evaluation, its revised medial-axis computation was the single strongest
adopt candidate of the 7 techniques surveyed. The specific mechanism (grid-flux vs a
Voronoi/Delaunay medial-axis transform vs a distance-field approach) and its stated
runtime/robustness claims are **exactly what the full-text method section is needed to
confirm** — this note does not guess them.

Author-credit note: `Kang, Younghun` is **already present** in `CITATION.cff`
`references` (lines ~43–44). The #186 directive additionally requires adding him to
`authors` in the same commit *that ports a technique* — i.e. only on an **adopt** verdict,
which this note does not reach.

## Paper access blocker (this session)

Full-text read could not be completed. Both fetch routes returned the same error:

```
The server returned HTTP 403 Forbidden.
```

- `https://gmd.copernicus.org/articles/17/1603/2024/` → 403
- `https://gmd.copernicus.org/articles/17/1603/2024/gmd-17-1603-2024.pdf` → 403
- `https://gmd.copernicus.org/articles/17/1603/2024/gmd-17-1603-2024.html` → 403 (full-text HTML, retried 2026-07-12)

Cause: the Copernicus host blocks the automated fetcher user-agent; the article is
open-access to a normal browser but not to `WebFetch` from this environment. This is an
environmental access limit, not a licensing one.

**Additional routes confirmed dead (2026-07-12 rotation — do not re-attempt these):**
- ResearchGate mirror (`researchgate.net/publication/378444596`, same paper, title *An
  automatic mesh generator for coupled 1D–2D hydrodynamic models*) → 403.
- Hugging Face `paper_search` MCP → no match (indexes ML papers only; this GMD paper is
  not in the corpus).
- The EGUsphere preprint (`egusphere.copernicus.org/preprints/2023/egusphere-2023-1434/`)
  is the same Copernicus host → same UA block, not a viable alternate.

Net: every automated route reachable from this environment (Copernicus HTML/PDF,
ResearchGate, HF) is blocked. A hosted-runner fetch or an operator paste of the method
section is the only remaining path to acceptance box 1 — no further route-hunting is
worthwhile from a rotation session.

**Handoff:** the baseline runtime + robustness benchmark (box 2) is **already done** — see
`T4-medial-axis-benchmark.md` + `scripts/bench_medial_axis.py` + `output/T4_medial_baseline.json`
(analytic disk/annulus/thin-channel giving exact error, plus the real WNAT coastal fixture).
What remains is box 1 (full-text method summary — blocked, see above) and box 3 (verdict).
A session with paper access (hosted runner able to reach Copernicus, or an operator paste of
the method section) reads the method, then scores the revised construction against the
baseline on the axis the benchmark identified as decisive — the **O(δ) curved-axis accuracy
floor** and the **quadratic-in-resolution runtime**, not thin-channel survival (which held
across the tested resolutions). No new octree-fixture benchmark is needed or possible.

## Interim verdict

**DEFER** — cannot responsibly record adopt or decline without the method section. The
grounded position: the baseline is a resolution-bounded grid-flux method whose known weak
spot is exactly thin high-aspect-ratio channels, so a revised method that improves axis
robustness there is a plausible additive backend — but the mechanism and its cost must be
read first. No locked module changed under this note.

### Acceptance status (#200)

- [ ] Full-text medial-axis method summarized — **blocked** (paper 403; handoff recorded).
- [x] Runtime + robustness benchmark of the baseline `_stages/medial_axis.py` — **done** in
  `T4-medial-axis-benchmark.md` (analytic disk/annulus/thin-channel + real WNAT coastal
  fixture). Octree fixtures are point-set octree-stage inputs, not medial-axis SDF grids, so
  they are out of scope for a medial-axis benchmark (see that note's Part C).
- [ ] Adopt / decline verdict — **DEFER** recorded above; final verdict pending box 1.
- [x] No change to any locked `_stages/` module under this issue.
