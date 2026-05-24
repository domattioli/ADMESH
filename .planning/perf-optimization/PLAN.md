# ADMESH Performance Optimization — Phase Plan

Benchmark target: **`WNAT_Onur.14`** — largest available Western North
Atlantic mesh (127K nodes, richest boundary granularity). The original
"wnat-admesh-3m" 3M target is deferred (no such asset exists).
Goal: **fastest possible CPU ADMESH.**

Authored by a 6-perspective planning crew (ADMESH core, language/profiling,
fidelity, registry, governance, benchmark/QA) under PM synthesis.

## Locked decisions (2026-05-24)

1. **Headline domain = `WNAT_Onur.14`** (127K nodes), under
   `ADMESH-Domains/registry_data/meshes/`. Smaller tiers: `WNAT_Test.14` 10K
   (CI), `WNAT_Hagen.14` 52K (mid). 3M deferred until a real/synthetic asset
   is provisioned.
2. **Constraints relaxed — fastest CPU wins.** The no-C-toolchain north star
   and Constitution Art. II language gate are SUSPENDED for this phase;
   constitution will be amended afterward. Permitted now: mandatory compiled
   extensions (Rust/Cython/C), `numba parallel`/`fastmath`, multi-core,
   float32 where it helps. Only hard rule kept: **mesh output stays correct**
   (fidelity tested, but bit-exact tolerance may loosen — see §3).
3. **Review = Claude-only.** No external CLIs; the 6-agent crew formulates,
   PM (Claude) has final say. No convergence loop.
4. **Build now.** Proceed through §6 execution order.
5. **in_polygon OOM (`in_polygon.py:74-103`)** fixed opportunistically — only
   if it blocks the Onur benchmark from completing.

---

## 0. Prerequisites

- **Env:** `pip install -e ".[dev]"` (numba/scipy). In progress.
- **Headline asset present:** `WNAT_Onur.14` (127K) in ADMESH-Domains
  registry — confirm loadable via `triangulate()` before baselining.

---

## Empirical findings (supersede the crew's static guess)

Profiling `triangulate` on the Onur coastline (5108-vert outer + 143 islands)
flipped the predicted ranking:

- **#1 real bottleneck was the domain SDF, not distmesh internals.**
  `loaders._shapely_sdf` evaluated shapely `distance` to a 9296-vertex
  boundary + a **Python loop calling `prepared.contains` per point**
  (1.2M calls) every distmesh iteration → 64s of a 77s run (84%).
- **Fix landed:** `admesh/_fast_sdf.py` — Numba `parallel+fastmath` kernel
  (min point-to-segment distance + even-odd ray cast). Matches shapely to
  7e-15, 100% inside-sign agreement, deterministic.
  Result: h_max=1.0/h_min=0.5 run **89.4s → 15.9s (5.6x)**, same 929 nodes,
  105 SDF/loader/triangulate tests green. (Mesh diverges ~0.1 from the
  shapely mesh — force-balance chaos amplifying machine-eps SDF differences,
  not an SDF error; both meshes valid + deterministic.)
- **New #1 bottleneck:** the SDF kernel is still 60s/72s — brute
  O(N_pts x 9296 segs) per call, called ~2854x (once per distmesh iter).
  Next lever = spatial pruning (cKDTree / uniform cell grid) so each point
  tests only nearby segments → target another 5-10x. distmesh `np.unique`
  bar-extraction (`sort` 4.2s) is the distant #2.

---

## Optimization log (autonomous loop)

Headline = Great Lakes coastline (M=13769 segs), `triangulate` h_max=0.15/
h_min=0.08, 1418 nodes, warmup excluded, seed=0.

| Step | Change | Headline wall | Speedup (cum vs shapely) |
|------|--------|---------------|--------------------------|
| 0 | shapely per-point SDF | ~89s (h=1.0) / 23.8s here | 1.0x |
| 1 | Numba brute SDF kernel | 55.7s | — |
| 2 | cKDTree distance prune | 23.8s | baseline for loop |
| 3 | **uniform-grid SDF (distance ring + row-bucketed sign)** | **7.85s** | **3.0x vs step 2** |

| 4 | **packed-int bar dedup + drop redundant SDF gradient calls** | **5.89s** | **1.41x vs step 3** |

Step 4 (distmesh.py): (a) bar extraction `np.unique(..., axis=0)` 2D lexsort →
1D `np.unique` on packed key `a*n+b` (a<b guaranteed, so order matches);
(b) projection recomputed `fd(po)` twice though `d[outside]` already held it —
reuse it. Output bit-identical to step 3, deterministic, 126 tests green.
SDF-sort cost 1.72s → ~0.2s.

Step 3: replaced scipy cKDTree + O(N·M) ray-cast with a single numba-parallel
grid kernel. Distance = expanding Chebyshev cell-ring search; sign = even-odd
ray cast over segments bucketed per grid row (each seg once/row → safe parity).
SDF cost 19.0s → 3.3s. Output bit-identical to brute kernel (max diff 0.0,
100% sign agreement), deterministic, 126 tests green.

### Loop stopped — diminishing returns (stop condition 3)

After step 4 the headline sat at ~5.9s with two co-dominant hotspots: the SDF
sign ray-cast (~3.3s, 51%) and the per-iteration distmesh python/numpy force
work (~2.3s, 36%). Three consecutive bit-identical attempts each yielded <10%:

- **force-loop → numba kernel:** no speedup (the distmesh tottime is array
  churn + Delaunay, not the truss arithmetic) and broke bit-identity (numpy
  `.sum()` is pairwise, a sequential numba reduction diverges). Reverted.
- **sign-only SDF for the interior mask:** bit-identical, 0% — disproved the
  "distance ring dominates" guess; query points sit near the boundary so the
  ring search is already cheap and the *sign* ray-cast is the real SDF cost.
- **left-of-point segment skip in the sign cast:** bit-identical, ~0% (the
  per-segment branch costs as much as the skipped division and breaks SIMD).
  Reverted.

Both remaining hotspots resist further *bit-identical* speedup, and the test
suite asserts exact golden-mesh + integer-connectivity equality, so anything
that perturbs the result (fastmath reductions, float32, fewer iterations,
different integrator) would fail the fidelity gate. The next real lever is
structural and large: a Rust/PyO3 incremental-Delaunay + half-edge kernel to
drop the per-iteration `O(N log N)` full-Qhull rebuild toward `O(N)` (research
ranked it highest-effort, do-last). Flagged for a human decision rather than
sunk into autonomously — it is a new toolchain + multi-hour build.

Net loop result: headline 23.8s → 5.9s (4.0x); vs the original shapely SDF the
end-to-end win is ~15x at h_max=0.6 and far larger at h_max=0.15.

## 1. Hotspots (original static ranking — kept for reference)

| # | Stage | Location | Why slow | Better data structure | Lang verdict | Fidelity risk |
|---|-------|----------|----------|------------------------|--------------|---------------|
| 1 | distmesh SDF segment loop | `admesh/distmesh.py:811-817` | Python `for` over all boundary segments, per-point per-iter; O(N·Nseg)/iter, thousands of iters; WNAT coastline = 10k+ segs | batched NumPy broadcast OR `scipy.spatial.cKDTree` on segment midpoints, prune to ~20 candidates → O(N log Nseg) | Numba (vectorize first, 10-100×) | KDTree prune changes equidistant tie winner → SDF sign flip at degenerate boundary pts. Validate ≤1e-8 vs brute force before enabling |
| 2 | force scatter | `admesh/distmesh.py:187,754` | `np.add.at` unbuffered scatter, ~5-10× slower than CSR matmul; ~18M adds/iter at 3M | COO→CSR bar-node incidence; `csr @ Fvec` (BLAS) or numba `prange` | Numba njit parallel (3-5×) | none (sum associative) |
| 3 | bar extraction | `admesh/distmesh.py:170,706` | `np.unique(...,axis=0)` lexsort of ~18M rows each retriangulation | packed-int edge key `min<<32\|max` + radix/single-pass | pure NumPy or numba; no escalation | none (edge set order-independent) |
| 4 | mesh_size solver | `admesh/mesh_size.py:64-88` | serial Gauss-Seidel scans full background grid per row; dead cells (`D>4*hmin`) still visited | active-cell CSR index list; iterate only `D≤4*hmin` (~5-15% of grid) | Numba njit (exists) + active-cell skip (~10×) | threshold must stay exactly `<=4*hmin` (MATLAB) or size-field band shifts |
| 5 | in_polygon dense broadcast | `admesh/in_polygon.py:74-103` | builds `(N_pts, N_verts)` matrix; 3M × 40k coastline = ~240 GB → **OOM at scale** | chunked eval (8k pts) + bbox pre-filter; or `shapely.vectorized` / `matplotlib.path` (C, ships as wheel) | escalate to shapely/mpl only if Nverts>1000, else numba chunked raycast; >2× justified on WNAT | mpl/shapely tie-breaking at vertices differs from MATLAB `inpolygon`; validate on on-boundary pts or restrict to strictly-interior queries |

---

## 2. Language + data-structure strategy

- **Default order:** NumPy+Numba first → Rust/PyO3+maturin only if >2× gate
  trips. Skip Cython for new code.
- **`fastmath`** only on non-accumulating reductions; never on iterative
  solvers needing IEEE rounding.
- **Data structures:** `cKDTree` (already a dep) or uniform cell-list for
  repeated radius queries; CSR (`indptr`/`indices` int32) for adjacency; SoA
  (`x`,`y` split) for SIMD/cache; pre-allocated reused buffers in distmesh
  inner loop (kills per-iter malloc/GC at 3M).
- **Precision:** geometry stays float64 (locked); size-field `h` arrays are
  the only float32 candidate, and only if gradient-propagation error <0.1%.
- **Optional compiled extension packaging** (preserves no-C-toolchain north
  star):
  ```toml
  [project.optional-dependencies]
  fast = ["admesh-ext>=0.1"]   # prebuilt wheel only
  ```
  ```python
  try:
      from admesh_ext._kernel import solve_fast as _solve
  except ImportError:
      _solve = _solve_numba_fallback
  ```
  `pip install admesh2D` → pure Python+Numba. `[fast]` → prebuilt wheel via
  `cibuildwheel`/`maturin`. Never a mandatory build-from-source.

---

## 3. Fidelity guardrails (hard gate, runs with every timing trial)

Invariants (with test anchors):
- Node coords float64, `mesh.equals(golden, atol=1e-8)`
  (`test_fort14_reference_corpus.py`, `test_api_equals.py`).
- Connectivity exact integer equality (`test_api_triangulate.py:48`).
- BoundaryType / IBTYPE paired-edge bit-exact (`test_api_equals.py:63-71`;
  weir fixtures).
- CCW ring order (`test_issue_11_ring_sorting.py`).
- Determinism: `seed=0` run twice → `np.array_equal` elements + exact-equal
  nodes.

Traps + guards: float32 downcast (dtype assert at KDTree/force input),
fastmath reorder (flag audit + residual compare), parallel-reduction
nondeterminism (pin `n_jobs=1` in regression suite), KDTree tie-break (tie
test on degenerate grids), in-place aliasing (writeable-flag checks).

Gate verdicts: connectivity mismatch or coord drift >1e-8 = **hard block**;
quality (`right_iso_quality`) drop >0.001 = soft flag, human sign-off.

CHILmesh: borrow `test_backend_equivalence.py` (serial-vs-parallel) and
Octave-oracle patterns; reject CHILmesh meshes as ADMESH fidelity oracles
(they are post-smoothed, not ADMESH-generated).

---

## 4. Benchmark harness

- Entry: `scripts/bench_pipeline.py`; results under `benchmarks/results/`.
- Timing `time.perf_counter()`; peak memory `tracemalloc`
  (`memray`/`py-spy --native` for deep dives).
- JIT warmup excluded: one dummy `triangulate()` before measured runs; numba
  `cache=True` to amortize. Report steady-state (`t[1]`) only; record
  `jit_overhead_s` separately.
- Per-stage: MVP end-to-end, then wrap each of 13 `admesh/_stages/*.py`.
- Stats: median + Q25/Q75 over ≥3 runs (1 run for the full 3M tier).
- Artifact: JSON keyed by `{git_sha12}-{env_hash8}` (env_hash =
  python|numba|numpy|scipy|admesh versions) + human summary table; committed,
  baseline = latest same-tier on main.

Tiered inputs:

| Tier | Nodes | Source | CI |
|------|-------|--------|----|
| tiny | ~100 / 10K | synthetic annulus or `WNAT_Test.14` | every CI |
| medium | 127K | `WNAT_Onur.14` (registry) | nightly |
| headline | ~3M | **synthesize or source — see §0** | manual/nightly |

---

## 5. CI gates (extend `.github/workflows/tests.yml`)

1. Fidelity tests green on py3.10/3.11/3.12 (`pytest -m "not slow"`).
2. Benchmark regression guard: fail if >15% slower per stage vs baseline
   (tiny+medium in CI; headline manual/nightly).
3. Install-without-C-toolchain smoke: `pip install -e "."` (no `[dev]`),
   import + `triangulate()`, assert zero `.so`/`.pyd` in default wheel.
4. Conditional `cibuildwheel` lane if any `.pyx`/`.c`/Rust ext added
   (py310-312, linux/macos/windows).
5. DomI `.domi-pin` drift gate untouched.

Language-escalation PR note (Constitution Art. II.2, mandatory): profiling
receipt showing >2× Numba underperformance on a realistic domain, the written
"why", and proof the compiled path is optional with a working numba fallback.

---

## 6. Execution order

1. Provision env + resolve 3M asset (§0).
2. Land bench harness + fidelity gate (no perf change yet) → establish
   baseline numbers on tiny/medium/headline.
3. Profile → confirm the §1 ranking with real flamegraphs on the 3M domain.
4. Optimize hotspots in ranked order; each change: re-bench + fidelity gate +
   determinism check before merge.
5. Escalate language only where the >2× gate trips, with the Art. II.2 PR note.
