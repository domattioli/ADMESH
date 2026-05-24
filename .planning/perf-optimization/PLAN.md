# ADMESH Performance Optimization — Phase Plan

Benchmark target: Western North Atlantic ~3M-node mesh ("wnat-admesh-3m").
Goal: best-fit language + data structures per hotspot, without breaking
MATLAB fidelity or the no-C-toolchain install north star.

Authored by a 6-perspective planning crew (ADMESH core, language/profiling,
fidelity, registry, governance, benchmark/QA) under PM synthesis.

---

## 0. Blockers to resolve first

- **wnat-admesh-3m asset does not exist in any repo.** Largest real domain is
  `WNAT_Onur.14` (127K nodes). Largest registry assets:
  `WNAT_Hagen.14` 52K, `WNAT_Onur.14` 127K, `WNAT_Test.14` 10K,
  `nc_inundation_v6c.grd` 31K (all under
  `ADMESH-Domains/registry_data/meshes/`).
  Decision required: source a real 3M ADCIRC grid (NOAA HSOFS/ESTOFS) OR
  generate a deterministic synthetic 3M domain. Recommended: synthetic
  `seed=42`, stored as `tests/fixtures/fort14/wnat_synthetic_3m.14`, with a
  real-grid run as a stretch validation.
- **Env not provisioned:** `numba` not installed. Prereq:
  `pip install -e ".[dev]"`. No benchmarks runnable until then.
- **Cross-AI convergence review unavailable in sandbox:** only `claude` CLI
  present (no codex/gemini/opencode); local model servers down. The
  external-reviewer convergence loop must run where those CLIs exist, OR use
  `--claude` reviewer only.

---

## 1. Hotspots (ranked for 3M nodes)

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
