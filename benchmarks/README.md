# ADMESH Benchmark Harness

## Setup Prerequisites

```bash
# Install dev dependencies + numba (REQUIRED — not in base)
pip install -e ".[dev]"

# Pinned env (reproducibility)
# Python >=3.10, numba>=0.58, numpy>=1.24, scipy>=1.11
```

## Harness Architecture

**File layout:**
- `scripts/bench_pipeline.py` — main entry point; CLI with tiered inputs
- `benchmarks/results/` — machine-readable (.json) + human summary tables
- `benchmarks/data/` — input domains (tiny, medium, wnat-3m)

**Per-stage instrumentation:**
- Wrap each of 13 stages in `admesh/_stages/` with `_BenchTimer` context manager
- Capture wall-clock (perf_counter) + peak memory (tracemalloc) per stage
- Store results keyed by `[stage_name]` in output dict

**JIT warmup & repeatability:**
- Numba first call excluded: run one dummy triangulation before measured runs
- Steady-state: 3× runs per input size, report median + IQR (25th, 75th percentile)
- Peak memory: max observed across all runs per stage

## Tiered Inputs

| Tier | Nodes | Wall-clock | Gate | Input File |
|------|-------|-----------|------|-----------|
| tiny | ~100 | <5s | CI (always run) | `benchmarks/data/tiny_annulus.toml` |
| medium | ~5K | <30s | CI nightly | `benchmarks/data/medium_lake.toml` |
| wnat-3m | ~3M | minutes | manual/nightly | `tests/fixtures/fort14/wnat_test.14` |

**CI gating:** Default CI runs tiny + medium only. Manual arg `--tier=full` or `--nightly=true` enables wnat-3m.

## Large-domain standard — ENPAC 2003 (#154)

Per operator directive (#154), the **standard large-domain benchmark is ENPAC 2003**
(`EasternPacific_ENPAC2003.14` — 272,913 nodes / 531,680 elems, continental-scale
Eastern Pacific, 59.3°×41.9°), replacing WNAT as the large-domain stress case.

- **Gate:** `python benchmarks/bench_enpac.py` — times domain load + SDF build,
  SDF grid eval, and a coarse full `triangulate()`; reports stage breakdown,
  per-point SDF cost, and mesh quality.
- **Portable fixture:** `benchmarks/data/enpac_boundary.json` (240 KB, 10,365-node
  outer ring extracted from the `.14`). The 29 MB `.14` itself stays in the Valence
  registry / HuggingFace — **not vendored** here.
- **Version comparison:** `compare_versions.py --domain benchmarks/data/enpac_boundary.json`
  (already domain-parametrized; ENPAC is now the documented default target).
- **WNAT-Onur retained** as a lighter ~7k-node smoke (`benchmarks/bench_wnat.py`,
  `benchmarks/data/wnat_onur_boundary.json`) — migration ≠ deletion.

> Note: ENPAC's SDF dominates naive full-domain bench cost; a `cKDTree`/vectorized
> segment-distance optimization in `distance.py` is tracked separately as a perf
> item (out of scope for #154's standard-switch).

## Artifacts

**Machine-readable:** `benchmarks/results/{git_sha}-{env_hash}.json`
```json
{
  "git_sha": "abc1234def567890...",
  "env_hash": "python3.11-numba0.58-numpy1.24-...",
  "timestamp": "2026-05-24T19:30:00Z",
  "tier": "tiny",
  "wall_clock": {
    "stage_01_routine": {"median_ms": 2.1, "q25_ms": 1.9, "q75_ms": 2.3},
    "stage_02_background_grid": {"median_ms": 0.8, ...},
    ...
    "stage_13_inpaint": {"median_ms": 0.1, ...},
    "end_to_end_ms": 45.2
  },
  "peak_memory_mb": {
    "stage_01_routine": 12.3,
    "stage_02_background_grid": 15.7,
    ...
  }
}
```

**Human summary:** `benchmarks/results/SUMMARY_{timestamp}.txt`
```
ADMESH Benchmark Summary — 2026-05-24 19:30 UTC
Git: abc1234def567890... | Env: python3.11 numba0.58 numpy1.24
Tier: tiny

Stage                          | Median (ms) | IQR (ms) | Peak Mem (MB)
-----------------------------------------------------------------------
01 routine                     |        2.1  | 0.4     |      12.3
02 background_grid             |        0.8  | 0.1     |      15.7
...
13 inpaint                      |        0.1  | 0.0     |       8.2
-----------------------------------------------------------------------
END-TO-END                     |       45.2  | 2.1     |      45.0
```

Results stored under git (committed); baseline = most recent `main` branch run for same tier.

## CI Regression Guard

**Mechanism:** After benchmark run, fetch baseline from `benchmarks/results/` for same tier on `main`.

**Threshold:** Fail if any stage >15% slower OR end-to-end >10% slower than baseline median.

**Refresh baseline:** Commit new baseline result to main after review (manual step or CI approval gate).

```bash
# Local check (before PR)
python scripts/bench_pipeline.py --tier=tiny --check-regression

# CI (auto on PR)
python scripts/bench_pipeline.py --tier=tiny --ci --fail-on-regression
```

## Exact Run Command

```bash
# Warmup (excluded from timing)
python -c "import admesh; admesh.triangulate('benchmarks/data/tiny_annulus.toml', h0=0.05)"

# Measured runs (3× for tiny/medium, 1× for wnat-3m)
python scripts/bench_pipeline.py --tier=tiny --runs=3
python scripts/bench_pipeline.py --tier=wnat-3m --runs=1 --output benchmarks/results/wnat_baseline.json
```

## Integration with Specs

Benchmark harness scaffolds for **spec-002** (size-field defaults) + **spec-004** (quad-prep smoother) regression gates on WNAT re-mesh quality metrics (min_q ≥0.30, mean_q ≥0.60) — not perf, but co-located in same result artifact.
