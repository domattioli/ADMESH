# Spec 029 — Octree unification, workflow integration, fold-to-main (scoping)

**Status**: scoping (operator review) · **Session**: 2026-06-13T01Z · **Supersedes-as-merge-vehicle**: PR #132 / branch `022-octree-perf-rewrite` · **Canonical predecessor**: `specs/021-octree-size-field-perf/` (main, PR #139, #115 closed)

## 1. Problem

The octree background grid was implemented **twice on divergent lineages** and is wired into nothing:

| | branch `022-octree-perf-rewrite` (PR #132) | `main`/`development` (PR #139) |
|---|---|---|
| Spec dirs | `specs/021-octree-size-field/` + `specs/022-octree-perf-rewrite/` | `specs/021-octree-size-field-perf/` (15/22 tasks done) |
| Layout | pre-`src/`-move flat `admesh/_stages/` | `src/admesh/_stages/` |
| Data structure | **flat `OctreeLeaf` list + integer index pointers** (`_parent_idx`/`_children_idx`/`_neighbor_idx`, CL-001; Numba/serialization-ready) | object pointer tree (`OctreeNode`/`OctreeTree`, Python refs) |
| Neighbor finding | Samet (1990) `_find_neighbor_of_greater_depth` descent | directional child-finder helpers + cross-parent wiring |
| Refinement driver | **`size_oracle(x, y)` callable** — the correct hook for the size-field stack | SDF-distance proportional placeholder (`lfs = max(|d|, h_min)`) |
| Tests | `tests/test_octree_grid.py` (branch variant) | `tests/test_octree_grid.py` — **15 pass** on development; ratio fixtures exist |
| Behind main | 22 commits (pre-`src/` move) | — |
| Workflow wiring | none | **none** — zero references outside `_stages/` |

`octree_medial.py` is byte-identical on both lineages.

**Merging or rebasing PR #132 as-is is wrong**: it would resurrect the deleted root `admesh/` tree beside `src/admesh/` (git reports 0 textual conflicts precisely because the paths differ — duplicate modules, no error). Salvage by port, then close #132.

## 2. Measured evidence (2026-06-13, unit-square SDF, this container)

Build + leaf_graph, main lineage vs branch module extracted standalone. Leaf counts differ because refinement criteria differ (main: distance-proportional; branch: size-oracle) — compare **per-leaf rates**, not rows:

| ratio | main leaves | build s | graph s | branch leaves | build s | graph s |
|---|---|---|---|---|---|---|
| 10 | 7 489 | 0.86 | 0.07 | 688 | 0.02 | 0.01 |
| 100 | 61 618 | 7.42 | 0.77 | 6 028 | 0.33 | 0.81 |
| 1000 | 336 286 | 44.7 | 4.70 | 49 000 | 2.75 | **59.8** |

- **Build**: branch ≈ 17–18k leaves/s vs main ≈ 7.5–8.7k — **~2.2× faster per leaf**, stable scaling. Neither hits SC-002 (<30 s @ ratio-1000) headroom comfortably in pure Python at main's leaf counts.
- **Branch `leaf_graph` is O(N²) despite its O(N) docstring**: index map built by scanning all `_nodes` per leaf (identity compare), and the `OctreeLeaf.neighbors` back-compat property recounts leaf rank by prefix scan per call (plus a module-global `_nodes` hack). Both fixable with one precomputed node→leaf-rank array; after the fix the branch design should dominate on every axis.

### 2b. Third data point — vectorized SoA prototype (2026-06-13, answers "can we implement a less expensive octree?")

Yes — by an order of magnitude over the branch and two over main. Prototype at [`prototype_octree_vec.py`](prototype_octree_vec.py) (Haiku-dispatched per coding policy; reviewed + independently re-benched by orchestrator): **level-synchronous build** (one **batched** oracle call per depth level over all active centers — both existing impls call the oracle per cell, thousands of 1-point SDF evals), **struct-of-arrays** (parallel `cx/cy/size/depth/ix/iy` arrays, zero per-cell Python objects), integer cell coords + `(depth,ix,iy)` dict for Samet-equivalent neighbor finding, worklist 2:1 balance, dict-ladder `locate`.

Correctness gates all pass: exact cover (1e-9), partition/no-ancestor-overlap, 2:1 balance on every edge, **`leaf_graph` bit-identical to brute-force O(N²) adjacency**, 1000-point `locate` containment.

| ratio | main lv / build / graph | branch lv / build / graph | **vec lv / build / graph** |
|---|---|---|---|
| 10 | 7 489 / 0.85 s / 0.07 | 688 / 0.022 / 0.01 | **316 / 0.002 / 0.00** |
| 100 | 61 618 / 7.11 / 0.72 | 6 028 / 0.34 / 0.83 | **2 968 / 0.013 / 0.02** |
| 1000 | 336 286 / 42.0 / 4.56 | 49 000 / 2.64 / (O(N²)) | **24 436 / 0.136 / 0.16** |

~180k leaves/s (≈10× branch per-leaf, ≈22× main); SC-001 (<5 s @ ratio-100) met at 0.013 s, SC-002 (<30 s @ ratio-1000) at 0.136 s — **~200× headroom in pure NumPy**. Leaf-count deltas reflect slightly different stop criteria (normalize in P0); per-leaf rates are the comparison that holds.

### 2c. ENPAC real-domain benchmark (2026-06-13, operator-requested) — the language question, settled empirically

Bench: `scripts/bench_octree_enpac.py` over **ENPAC 2003** (`EasternPacific_ENPAC2003.14`, Valence registry, 272,913-node / 531,680-elem ADCIRC tidal DB; bbox 59.3°×41.9°). Loaded via `admesh.load_domain_from_fort14`. Real domain SDF = **~2 ms/point** (brute-force point-to-272k-segment distance) — this single fact decides the architecture and the language.

**Regime A — structural (cheap oracle, octree machinery only), vec prototype:**

| ratio | leaves | build | graph |
|---|---|---|---|
| 10 | 873 | 0.005 s | 0.004 s |
| 100 | 7 875 | 0.031 s | 0.039 s |
| 1000 | 64 269 | 0.364 s | 0.429 s |

**Regime B — realistic (real ENPAC SDF oracle), ratio 10:**

| impl | leaves | build | **oracle calls / points evaluated** |
|---|---|---|---|
| **vec** (batched per level) | 882 | 0.19 s | **4 calls / 1 080 pts** |
| branch #132 (per-cell scalar) | 2 287 | 0.16 s | 5 878 / 5 878 |
| main (per-leaf-center) | 27 772 | 3.39 s | 29 405 / 29 405 |

**Interpretation (this is the answer to "C++/Rust/Python?"):**

1. **The octree shell is never the cost — the size oracle is.** At 2 ms/pt SDF, main's 29 405 evals ≈ 59 s of pure SDF; vec's 1 080 evals ≈ 2 s. The octree machinery itself (Regime A) is sub-second at every ratio in pure NumPy. **A native (C++/Rust) octree would optimize the part that is already free and leave the 2 ms/pt SDF — itself NumPy/scipy — untouched.** Wrong layer.
2. **The real lever is fewer + batched oracle calls**, which is an *algorithm* property (level-synchronous build), not a *language* property. vec wins by calling the oracle 4× (batched) vs thousands of times (1 point each) — that advantage is identical in any host language, so it does not motivate a rewrite.
3. **If anything ever needs native, it is the SDF**, not the tree — and that is `distance.py` / scipy territory (`cKDTree`, vectorized segment distance), addressable in pure Python/NumPy/Numba first. Independent of the octree.

**Verdict: implement in Python (vectorized NumPy), Numba-gate the SDF if needed, native never (this layer).** Recorded as D-029c. The ENPAC numbers are the regression baseline candidate (§4b.6) and supersede the toy unit-square bench.

## 3. Faithfulness contract — to the **concept**, not to MATLAB (operator clarification 2026-06-13)

The octree has no MATLAB counterpart and owes it nothing. "Completely faithful" = faithful to the **quadtree/octree concept** as published (Samet 1990). Binding concept invariants, each pinned by a test:

1. **2:1 balance** — no leaf neighbors a leaf more than one level apart, in all four cardinal directions, after every build (`balance=True` path).
2. **Neighbor completeness** — every edge-adjacent leaf pair appears exactly once in `leaf_graph`; no duplicates, no misses (property-checkable against brute-force O(N²) reference on small N).
3. **Cover/partition** — leaves tile the padded bbox exactly: disjoint interiors, union = bbox, no gaps (area sum check to 1e-12).
4. **Refinement correctness** — every leaf satisfies the size oracle: `leaf.size ≤ oracle(center)` or leaf is at `h_min` floor / `max_depth` cap; refinement is driven by the sizing function, not by ad-hoc distance proxies (this disqualifies main-lineage's `lfs = max(|d|, h_min)` placeholder as the keeper).
5. **Stated complexity is enforced, not asserted** — O(N log N) build/balance, O(N) leaf_graph, O(log N) locate verified empirically (log-log slope < 1.5, SC-004). §2's O(N²) `leaf_graph` despite an O(N) docstring is precisely the failure mode this invariant exists to catch.

Constitution Principle I is a **separate, orthogonal** protection: `background_grid.py` (locked stage 02) stays untouched; octree is additive-layer and opt-in until P5. Promotion gates: SC-005 size-field parity (`max |Δh| / h_max < 0.05` vs uniform-path stack on notch + river-into-bay), `solve_iter` parity `atol=1e-10` on the variable-spacing leaf graph, structural validity binding end-to-end; `min_q`/`mean_q` advisory (Article V.5, #140) but reported in every benchmark.

## 4. Workflow integration design

- `size_oracle` = the composed spec-002/025 stack (curvature → medial-axis → bathymetry → tide, min-stacked) evaluated pointwise; octree refines where the stack demands resolution. This is why the branch API is the keeper.
- `leaf_graph` (post-fix) feeds the gradient-limit Eikonal smoother on the variable-spacing graph; `octree_medial.py` (shared) provides per-leaf medial gradient fit.
- `interpolate`/`locate` back the `fh()` callable handed to `distmesh2d` — CL-004 clamp semantics retained (distmesh drift safety).
- Public surface: one kwarg on `triangulate()`; no loader/fort14 changes; `[gpu]`/Numba gating per existing conventions (`ADMESH_NUMBA=1`, main-lineage T018).

## 4b. Cost envelope — octree must never explode admesh cost on target domains (operator constraint 2026-06-13)

The octree's whole justification is cost *reduction* on multiscale coastal domains: a uniform background grid needs O((L/h_min)²) cells — ratio-1000 on a unit square = 10⁶ cells — while boundary-graded octree refinement concentrates leaves near features (§2 measured 49k leaves at ratio-1000, a 20× cell reduction). **Asymptotics favor octree; the risk is constant factors and defects** (pure-Python object churn, the §2 O(N²) bugs). Guardrails, all binding:

1. **Pipeline-share budget**: on every benchmark domain, octree build + balance + leaf_graph + locate-total ≤ **15% of end-to-end `triangulate()` wall-clock** (distmesh iteration dominates legitimately; the background grid never should). Measured per-stage in `bench_octree.py` output, asserted in the P3 report.
2. **Never-worse rule vs uniform**: for each target-domain benchmark row, octree-path total `triangulate()` time ≤ **1.10×** uniform-path time at equal `hmin`/`hmax`/`g`. Domains where octree loses get documented — if any *registry-class* domain loses, P5 default-flip is off the table until fixed.
3. **Target-domain matrix is the registry we actually mesh**, not toy squares: Tier-0 (notch, river-into-bay ratios 10–1000), Tier-1 (registry small/medium: annulus-class, Test_Cases), **Tier-2 = ENPAC 2003** (`EasternPacific_ENPAC2003.14`, 272,913 nodes — the new standard large-domain gate, **replaces WNAT for future benchmarking** per operator 2026-06-13; WNAT-Onur ~7k retained only as a lighter smoke). ENPAC's 2 ms/pt SDF over a continental-scale bbox is the realistic stress case; ADMESH-Domains registry entries are ground truth for "domains we want to make."
4. **Hard runtime caps with graceful degradation**: `max_depth` cap (existing), plus a **leaf budget** (default ~4× expected mesh node count); breaching either raises a warning and the build either coarsens or falls back to the uniform stage-02 grid — never hangs, never OOMs silently. Fallback is loud (warning names the cap hit).
5. **Memory**: flat index arrays (CL-001) keep per-leaf cost to a few dozen bytes vs object-tree pointers; peak RSS recorded in benchmarks; budget ≤ 2× uniform-grid arrays at equal effective resolution near boundaries.
6. **Regression lock**: P1's `bench_octree.py` numbers land in `benchmarks/` as the pinned baseline; the existing benchmark-gate lane (#101 pattern) flags >20% build-time regression on the ratio-100 fixture in CI.

If pure Python misses budget 1 or 2 after the O(N²) fixes: Numba gate (T018/T019) first, spec-023 native rewrite second (D-029c) — budgets stay fixed, implementations move.

## 5. Phase plan

| Phase | Work | Gate |
|---|---|---|
| **P0 salvage** | **Revised 2026-06-13**: keeper core = the §2b vectorized SoA design (batched oracle, level-synchronous, integer-coord neighbors) productionized onto `src/admesh/_stages/octree_grid.py` under main's public fn names (`build_octree`, `size_field_octree`, `leaf_graph`, `locate`, `interpolate`). Branch contributes the `size_oracle` API shape, CL-001..004 decisions, tests, and Samet references — its per-cell build loop is retired along with main's object tree. §3 concept-invariant tests (cover/partition/2:1/brute-force-graph/locate) become the permanent test suite. Salvage spec-022 CL/SC into `specs/021-octree-size-field-perf/` | existing 15 octree tests + concept-invariant tests green |
| **P1 perf proof** | Committed `scripts/bench_octree.py` (build/balance/leaf_graph/locate at ratios 10/100/1000 on `tests/fixtures/octree/`); record SC-001..SC-004 + §4b budgets 1/5 in `benchmarks/` (pinned baseline, regression lock §4b.6) | SC-001..004 met **and** §4b budgets within bounds, or Numba gate (T018/T019) closes the gap; else spec-023-native (Rust/C++, CL-001 deferral) activates |
| **P2 workflow wiring** | `triangulate(background="octree")` opt-in path: oracle = size-field stack, leaf graph → gradient limiter → `fh()` → distmesh | SC-005 parity gate + full suite green; 13 locked stages untouched |
| **P3 quality benchmark** | Uniform vs octree on the §4b.3 target-domain matrix (registry domains, not toys; salvage branch's WNAT-Onur graded-mesh scripts): wall-clock + pipeline-share, node count, min_q/mean_q, structural validity, peak RSS; SC-007 river-bay channel ≥ 3 nodes across | report committed; structural validity 100%; §4b budgets 1+2 hold on every row |
| **P4 fold + cleanup** | Land on `development` → rolling PR #150 → `main`; close PR #132 superseded-with-salvage-links; delete `022-octree-perf-rewrite` (operator — proxy blocks session deletes); PORTING_NOTES entry (main T020) | operator merge |
| **P5 default flip** (approved in principle 2026-06-13, gated) | Promote octree to default background | P3 shows ≥ parity quality + §4b never-worse rule holds on ALL registry-class rows + operator sign-off |

Implementation sessions: speckit chain on this scoping doc; code via Haiku subagents per dispatch policy.

## 6. Open decisions (operator)

- ~~**D-029a**: approve salvage-by-port + close PR #132~~ — **RESOLVED 2026-06-13: approved** ("approve"). PR #132 closed; branch retained read-only until P0 salvage complete, then operator deletes (proxy blocks session deletes).
- **D-029b**: spec numbering — branch's `021-octree-size-field`/`022-octree-perf-rewrite` dirs collide conceptually (not by name) with main's `021-octree-size-field-perf`/`022-fem-smoother-order`; salvage into canonical 021-perf dir and retire branch dirs?
- ~~**D-029c**: pure-Python perf bar — Numba vs native~~ — **RESOLVED-BY-EVIDENCE 2026-06-13 (recommendation): pure Python/NumPy.** §2b prototype clears every SC target and §4b budget with ~200× headroom; language question answered by measurement: (1) Constitution Article II bars C extensions in first cut anyway; (2) pure NumPy runs unmodified in the Pyodide GitHub-Pages demo — a cpp/rust extension would need emscripten wheels; (3) the batched oracle means build cost is dominated by the size-field stack itself, which is the same NumPy cost under any host language — a native octree shell would optimize <1% of pipeline wall-clock; (4) flat SoA arrays remain `@njit`-ready (T018 env-gate) and spec-023 native stays dormant as the documented escape hatch if a registry-class domain ever breaches §4b. CHILmesh's C++ backend precedent was justified by measured need; here the measurement says no.
- ~~**D-029d**: P5 default flip intent~~ — **RESOLVED 2026-06-13**: operator approved P5 in principle ("5 looks good"), gated on §4b never-worse rule across all registry-class domains. P3 benchmarks gate hard accordingly.
- Operator clarifications absorbed 2026-06-13: faithfulness = concept-fidelity (§3 rewritten, MATLAB-parity framing dropped); computational-cost envelope added (§4b) — octree must not increase admesh cost on the domains we actually make.
- ENPAC = Tier-2 benchmark standard (replaces WNAT), operator 2026-06-13. Benchmark-infra migration tracked at **#154**. ENPAC `.14` present in Valence registry but its `manifest.toml` entry is stale (`status="stub"`) — flagged for a Valence session (Valence#111), not actioned here (pull-only contract).
