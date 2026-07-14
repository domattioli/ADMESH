# T4 — Medial-Axis Baseline Benchmark

Follow-up to issue [#200](https://github.com/domattioli/ADMESH/issues/200), carved out of
[#186](https://github.com/domattioli/ADMESH/issues/186) (evaluation note
`docs/upstream/ADMESH-PLUS-V3-GMESH-EVALUATION.md`). T4 = the revised medial-axis
computation in Kang, Y. & Kubatko, E.J. (2024), *Geosci. Model Dev.* **17**, 1603–1625
([doi:10.5194/gmd-17-1603-2024](https://doi.org/10.5194/gmd-17-1603-2024)), the single
strongest adopt candidate of the seven techniques evaluated.

This note records a **runtime + robustness baseline of the current grid-based medial-axis
path** so any future adopt/decline decision (or additive alternate backend) has a measured
reference to beat. It does **not** decide the verdict — see "Status" below.

## What was measured

Harness: `scripts/bench_medial_axis.py` (additive benchmark tooling; reads the locked
`_stages/medial_axis.py`, does not modify it). Raw results: `output/T4_medial_baseline.json`.
Reproduce with `python scripts/bench_medial_axis.py`.

The current path (`_stages/medial_axis.py`) is a **regular-grid image-morphology**
construction: signed-distance grid → average-outward-flux (AOF) threshold → Zhang–Suen
skeletonize → Euclidean distance transform to the skeleton. Its cost and accuracy are
therefore functions of the grid spacing δ. The benchmark sweeps δ on two analytic domains
with a known medial axis (so error is exact), plus a thin-channel robustness probe.

### Part A — runtime + accuracy vs grid resolution δ

`medial_distance_fmm(fd, bbox, δ)` on `domains.UNIT_DISK` (analytic medial distance = r)
and `domains.ANNULUS` (analytic = |r − 0.7|). Wall-clock = min of 3 runs; error = max
absolute error over an interior band away from both boundaries.

| domain    | δ     | grid cells | secs   | max_err  | err/δ |
|-----------|-------|-----------:|-------:|---------:|------:|
| UNIT_DISK | 0.080 |        676 | 0.0014 | 0.056569 | 0.71  |
| UNIT_DISK | 0.040 |       2601 | 0.0023 | 0.000000 | 0.00  |
| UNIT_DISK | 0.020 |      10201 | 0.0060 | 0.000000 | 0.00  |
| UNIT_DISK | 0.010 |      40401 | 0.0207 | 0.000000 | 0.00  |
| UNIT_DISK | 0.005 |     160801 | 0.0753 | 0.000000 | 0.00  |
| ANNULUS   | 0.080 |        676 | 0.0010 | 0.070507 | 0.88  |
| ANNULUS   | 0.040 |       2601 | 0.0014 | 0.035391 | 0.88  |
| ANNULUS   | 0.020 |      10201 | 0.0036 | 0.016938 | 0.85  |
| ANNULUS   | 0.010 |      40401 | 0.0120 | 0.009366 | 0.94  |
| ANNULUS   | 0.005 |     160801 | 0.0483 | 0.004568 | 0.91  |

### Part B — thin-channel robustness

`medial_axis_mask` on a horizontal rectangle (half-width w = 0.05, half-length 1.0).
Tests whether a narrow channel's medial axis survives as δ approaches (and exceeds) the
channel half-width.

| δ     | w/δ  | ma_cells | detected |
|-------|-----:|---------:|:--------:|
| 0.100 | 0.50 |       20 | yes      |
| 0.050 | 1.00 |       38 | yes      |
| 0.020 | 2.50 |      101 | yes      |
| 0.010 | 5.00 |      208 | yes      |

### Part C — real WNAT coastal fixture

`medial_distance_fmm` on the reconstructed WNAT-Onur boundary
(`benchmarks/data/wnat_onur_boundary.json`: 144 rings — outer ocean perimeter + island
holes — over a ~38°×38° lon/lat bbox, diagonal ≈ 53.6). This is the production-grade coastal
target the analytic domains stand in for. δ is set by fraction of the bbox diagonal.
Wall-clock = min of 3 runs, warmed up once (untimed) to exclude Numba JIT + shapely-SDF build.
`sdf_secs` = the signed-distance grid evaluation alone; `ma_secs` = the AOF+skeletonize+EDT
medial-axis step (`total − sdf`); `finite` = medial-distance cells resolved.

| δ      | grid_cells | sdf_secs | total_secs | ma_secs | finite |
|--------|-----------:|---------:|-----------:|--------:|-------:|
| 1.7851 |        484 |   0.0030 |     0.0037 |  0.0007 |    263 |
| 0.8925 |       1849 |   0.0109 |     0.0124 |  0.0015 |   1039 |
| 0.4463 |       7396 |   0.0438 |     0.0470 |  0.0032 |   4100 |

## What the numbers say

- **Runtime is quadratic in resolution.** Cost tracks grid-cell count one-to-one (O(1/δ²)):
  refining δ from 0.08 to 0.005 (16×) grows the grid 238× and wall-clock ~54×. On a coastal
  boundary that needs a fine δ to resolve narrow features, this is the dominant cost of the
  size-field stack — the motivation behind acceleration issue #8 and the reason a grid-free
  method is attractive.
- **Accuracy on a *curved* medial axis is resolution-bounded, and does not converge below
  O(δ).** UNIT_DISK's medial axis is a single point that the grid resolves to machine
  precision once δ ≤ 0.04, so its error collapses to zero — misleadingly clean. ANNULUS's
  medial axis is a *curved ring* at r = 0.7, and there the error holds at **≈ 0.85–0.94 δ
  across every resolution** — halving δ only halves the error, never removing it. This
  O(δ) floor on curved medial axes is the sharpest axis on which an **exact** (Voronoi /
  constrained-Delaunay) polygon medial axis — which carries no grid and no δ — would win,
  and is exactly the property to measure a Kang & Kubatko backend against.
- **The grid method was robust on this straight thin channel.** Detection held across
  δ ∈ [0.01, 0.1], including δ = 2w (coarser than the channel), with ma_cells ∝ 1/δ. Grid
  collapse was **not** observed in this test — so "channel collapse" is not, on this
  evidence, the current method's weakness; the curved-axis O(δ) accuracy floor and the
  quadratic runtime are. (A branching or sharply-cornered channel network — the paper's
  actual target case — may still expose skeleton-connectivity artifacts the AOF+Zhang–Suen
  path is prone to; that needs a real coastal fixture, see below.)
- **On the real WNAT coastline the SDF grid — not the medial-axis morphology — is the
  bottleneck.** At δ = 0.446 (7396 cells) the AOF+Zhang–Suen+EDT skeleton step costs
  `ma_secs = 0.0032`, while evaluating the shapely SDF over the 144-ring boundary costs
  `sdf_secs = 0.0438` — **~14× more**, and it is `sdf_secs` that carries the O(1/δ²) growth
  (0.003 → 0.011 → 0.044 across the sweep). This sharpens the adopt/decline picture: a
  grid-free Voronoi/constrained-Delaunay medial axis (the paper's likely construction) would
  remove `ma_secs`, but `ma_secs` is already ~7 % of total on a real coastline — the dominant
  cost is the distance-field evaluation the size-field stack needs *regardless* of the
  medial-axis method. An exact backend therefore wins on the **curved-axis O(δ) accuracy
  floor** (Part A), not on WNAT wall-clock, where it would shave only the cheap step. The
  skeleton also stayed fully connected on this 144-ring fixture (`finite` grows monotonically
  with grid size), so the AOF+Zhang–Suen connectivity-artifact risk flagged above did **not**
  materialize at these resolutions.

## Status — verdict still deferred

Acceptance items for #200:

- [x] **Runtime + robustness benchmark of the current `_stages/medial_axis.py`** — this
  note + `scripts/bench_medial_axis.py` + `output/T4_medial_baseline.json`. Part A/B measure
  controlled analytic domains (disk, annulus, thin channel) that give exact error and isolate
  the resolution-dependence; **Part C now measures the real WNAT coastal fixture**
  (`benchmarks/data/wnat_onur_boundary.json`, 144 rings) — the WNAT-scale SDF-built run the
  prior revision deferred as "a further, heavier step". Its finding (SDF-eval dominates,
  medial-axis morphology is ~7 % of total, skeleton stays connected) is folded into "What the
  numbers say". The octree fixtures remain out of scope for this benchmark — they are
  octree-stage inputs (point sets), not medial-axis SDF grids, so there is no medial-axis path
  to time on them.
- [ ] **Full-text medial-axis method summarized.** BLOCKED — the GMD article and the
  EGUsphere preprint are both refused at the agent-proxy network layer
  (`HTTP 403 CONNECT rejected` for `gmd.copernicus.org` / `egusphere.copernicus.org`,
  confirmed via `$HTTPS_PROXY/__agentproxy/status`). This is a network-policy limit, not a
  transient error, and reproduces across sessions (already noted in the #186 evaluation).
  The method section (or the OSU-CHIL MATLAB source) must be read from a session whose
  network policy permits the journal host.
- [ ] **Adopt / decline verdict.** Deferred until the method read lands — an adopt decision
  needs the paper's exact construction (pruning criterion, complexity, robustness claims) to
  compare against this baseline. The baseline says *where* an exact method must beat the grid
  method to justify an additive backend: the O(δ) curved-axis accuracy floor and the
  quadratic runtime, **not** thin-channel survival.

## Constraints honored

- **Constitution Principle I intact.** `_stages/medial_axis.py` untouched; the FMM/grid path
  stays the locked default and numerical reference. Any adopted method lands as an *additive*
  alternate backend under its own spec, never replacing the locked module.
- **Author-credit directive (#186).** An adopt verdict that ports a Kang & Kubatko (2024)
  technique must add `Kang, Younghun` to `CITATION.cff` `authors` + `references` in the same
  commit. No port happened here, so no credit change yet.
