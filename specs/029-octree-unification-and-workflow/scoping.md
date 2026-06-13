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

## 3. Faithfulness contract (Constitution Principle I)

The octree has **no MATLAB counterpart** — "faithful implementation" here means:

1. `background_grid.py` (locked stage 02, uniform grid) stays untouched and remains the **default**. Octree is additive-layer, **opt-in** (`triangulate(..., background="octree")`); silent replacement is a Principle-I violation.
2. **Parity gate** (binding for promotion): octree-path size field vs faithful uniform-path stack, `max |Δh| / h_max < 0.05` on the spec-021 notch + river-into-bay fixtures (SC-005), and identical gradient-limit behavior (`solve_iter` parity on the variable-spacing leaf graph, `atol=1e-10` Numba-vs-Python as elsewhere).
3. End-to-end: **structural validity is binding** (positive-area tris, watertight boundary, nodes in domain); `min_q`/`mean_q` are advisory (Article V.5, #140) but reported in every benchmark.

## 4. Workflow integration design

- `size_oracle` = the composed spec-002/025 stack (curvature → medial-axis → bathymetry → tide, min-stacked) evaluated pointwise; octree refines where the stack demands resolution. This is why the branch API is the keeper.
- `leaf_graph` (post-fix) feeds the gradient-limit Eikonal smoother on the variable-spacing graph; `octree_medial.py` (shared) provides per-leaf medial gradient fit.
- `interpolate`/`locate` back the `fh()` callable handed to `distmesh2d` — CL-004 clamp semantics retained (distmesh drift safety).
- Public surface: one kwarg on `triangulate()`; no loader/fort14 changes; `[gpu]`/Numba gating per existing conventions (`ADMESH_NUMBA=1`, main-lineage T018).

## 5. Phase plan

| Phase | Work | Gate |
|---|---|---|
| **P0 salvage** | Port branch flat-index implementation onto `src/admesh/_stages/octree_grid.py` (keep main's public fn names: `build_octree`, `size_field_octree`, `leaf_graph`, `locate`, `interpolate`); fix the two O(N²) defects (precomputed leaf-rank array; kill `_nodes` global); port branch tests; salvage spec-022 clarifications CL-001..004 + SC-001..007 into `specs/021-octree-size-field-perf/` | existing 15 octree tests + ported tests green |
| **P1 perf proof** | Committed `scripts/bench_octree.py` (build/balance/leaf_graph/locate at ratios 10/100/1000 on `tests/fixtures/octree/`); record SC-001..SC-004 numbers in `benchmarks/` | SC-001..004 met or Numba gate (T018/T019) closes the gap; else spec-023-native (Rust/C++, CL-001 deferral) activates |
| **P2 workflow wiring** | `triangulate(background="octree")` opt-in path: oracle = size-field stack, leaf graph → gradient limiter → `fh()` → distmesh | SC-005 parity gate + full suite green; 13 locked stages untouched |
| **P3 quality benchmark** | Uniform vs octree on Tier-0/1 + WNAT-Onur (salvage branch's graded-mesh comparison scripts): wall-clock, node count, min_q/mean_q, structural validity; SC-007 river-bay channel ≥ 3 nodes across | report committed; structural validity 100% |
| **P4 fold + cleanup** | Land on `development` → rolling PR #150 → `main`; close PR #132 superseded-with-salvage-links; delete `022-octree-perf-rewrite` (operator — proxy blocks session deletes); PORTING_NOTES entry (main T020) | operator merge |
| **P5 default flip** (optional, separate decision) | Promote octree to default background when P3 shows ≥ parity quality + better scaling | operator sign-off only |

Implementation sessions: speckit chain on this scoping doc; code via Haiku subagents per dispatch policy.

## 6. Open decisions (operator)

- **D-029a**: approve salvage-by-port + close PR #132 (vs attempting rebase — not recommended, §1).
- **D-029b**: spec numbering — branch's `021-octree-size-field`/`022-octree-perf-rewrite` dirs collide conceptually (not by name) with main's `021-octree-size-field-perf`/`022-fem-smoother-order`; salvage into canonical 021-perf dir and retire branch dirs?
- **D-029c**: pure-Python perf bar — accept Numba gate as the SC-002 closer, or pre-authorize spec-023 native rewrite scoping.
- **D-029d**: P5 default flip intent (affects how hard P3 benchmarks gate).
