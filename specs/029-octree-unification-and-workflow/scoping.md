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
3. **Target-domain matrix is the registry we actually mesh**, not toy squares: Tier-0 (notch, river-into-bay ratios 10–1000), Tier-1 (registry small/medium: annulus-class, Test_Cases), Tier-2 (WNAT-Onur ~7k-node graded; WNAT/HSOFS-class scale extrapolation). ADMESH-Domains registry entries are the ground truth for "domains we want to make."
4. **Hard runtime caps with graceful degradation**: `max_depth` cap (existing), plus a **leaf budget** (default ~4× expected mesh node count); breaching either raises a warning and the build either coarsens or falls back to the uniform stage-02 grid — never hangs, never OOMs silently. Fallback is loud (warning names the cap hit).
5. **Memory**: flat index arrays (CL-001) keep per-leaf cost to a few dozen bytes vs object-tree pointers; peak RSS recorded in benchmarks; budget ≤ 2× uniform-grid arrays at equal effective resolution near boundaries.
6. **Regression lock**: P1's `bench_octree.py` numbers land in `benchmarks/` as the pinned baseline; the existing benchmark-gate lane (#101 pattern) flags >20% build-time regression on the ratio-100 fixture in CI.

If pure Python misses budget 1 or 2 after the O(N²) fixes: Numba gate (T018/T019) first, spec-023 native rewrite second (D-029c) — budgets stay fixed, implementations move.

## 5. Phase plan

| Phase | Work | Gate |
|---|---|---|
| **P0 salvage** | Port branch flat-index implementation onto `src/admesh/_stages/octree_grid.py` (keep main's public fn names: `build_octree`, `size_field_octree`, `leaf_graph`, `locate`, `interpolate`); fix the two O(N²) defects (precomputed leaf-rank array; kill `_nodes` global); port branch tests; salvage spec-022 clarifications CL-001..004 + SC-001..007 into `specs/021-octree-size-field-perf/` | existing 15 octree tests + ported tests green |
| **P1 perf proof** | Committed `scripts/bench_octree.py` (build/balance/leaf_graph/locate at ratios 10/100/1000 on `tests/fixtures/octree/`); record SC-001..SC-004 + §4b budgets 1/5 in `benchmarks/` (pinned baseline, regression lock §4b.6) | SC-001..004 met **and** §4b budgets within bounds, or Numba gate (T018/T019) closes the gap; else spec-023-native (Rust/C++, CL-001 deferral) activates |
| **P2 workflow wiring** | `triangulate(background="octree")` opt-in path: oracle = size-field stack, leaf graph → gradient limiter → `fh()` → distmesh | SC-005 parity gate + full suite green; 13 locked stages untouched |
| **P3 quality benchmark** | Uniform vs octree on the §4b.3 target-domain matrix (registry domains, not toys; salvage branch's WNAT-Onur graded-mesh scripts): wall-clock + pipeline-share, node count, min_q/mean_q, structural validity, peak RSS; SC-007 river-bay channel ≥ 3 nodes across | report committed; structural validity 100%; §4b budgets 1+2 hold on every row |
| **P4 fold + cleanup** | Land on `development` → rolling PR #150 → `main`; close PR #132 superseded-with-salvage-links; delete `022-octree-perf-rewrite` (operator — proxy blocks session deletes); PORTING_NOTES entry (main T020) | operator merge |
| **P5 default flip** (approved in principle 2026-06-13, gated) | Promote octree to default background | P3 shows ≥ parity quality + §4b never-worse rule holds on ALL registry-class rows + operator sign-off |

Implementation sessions: speckit chain on this scoping doc; code via Haiku subagents per dispatch policy.

## 6. Open decisions (operator)

- **D-029a**: approve salvage-by-port + close PR #132 (vs attempting rebase — not recommended, §1).
- **D-029b**: spec numbering — branch's `021-octree-size-field`/`022-octree-perf-rewrite` dirs collide conceptually (not by name) with main's `021-octree-size-field-perf`/`022-fem-smoother-order`; salvage into canonical 021-perf dir and retire branch dirs?
- **D-029c**: pure-Python perf bar — accept Numba gate as the SC-002 closer, or pre-authorize spec-023 native rewrite scoping.
- ~~**D-029d**: P5 default flip intent~~ — **RESOLVED 2026-06-13**: operator approved P5 in principle ("5 looks good"), gated on §4b never-worse rule across all registry-class domains. P3 benchmarks gate hard accordingly.
- Operator clarifications absorbed 2026-06-13: faithfulness = concept-fidelity (§3 rewritten, MATLAB-parity framing dropped); computational-cost envelope added (§4b) — octree must not increase admesh cost on the domains we actually make.
