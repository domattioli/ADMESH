# ADMESH Benchmark Harness — Design Document

## Executive Summary

End-to-end + per-stage performance instrumentation for 13-stage ADMESH pipeline. Tiered inputs (tiny CI, medium dev, wnat-3m nightly/manual) with regression gating on baseline.

---

## SETUP

**Prerequisites:**
- Python ≥3.10
- `pip install -e ".[dev]"` (installs numba>=0.58, numpy>=1.24, scipy>=1.11)
- Numba JIT disabled/enabled per run; env var `NUMBA_DISABLE_JIT=0` default

**Reproducibility pinning:**
- git SHA (first 12 chars, short form)
- environment hash: MD5(python-ver + numba-ver + numpy-ver + scipy-ver + admesh-ver)
- Timestamp UTC (ISO 8601)

All three stored in result artifact; baseline = most recent main-branch result for same tier.

---

## HARNESS

**Entry point:** `scripts/bench_pipeline.py`

**Instrumentation approach:**
1. **Wall-clock timing:** `time.perf_counter()` (monotonic, unaffected by system clock adjustments)
2. **Peak memory:** `tracemalloc.get_traced_memory()[1]` (peak bytes since start)
3. **JIT warmup:** one dummy `triangulate()` call pre-measured; excluded from stats
4. **Repeat:** 3 runs for tiny/medium, 1 run for wnat-3m
5. **Statistics:** median + Q25 + Q75 percentiles over all runs

**Per-stage timing (future enhancement):**
- Monkey-patch entry to each of 13 stages in `admesh/_stages/` with context manager
- Current MVP: end-to-end only; per-stage hooks deferred to Phase 2

**CLI:**
```bash
python scripts/bench_pipeline.py --tier=tiny --runs=3
python scripts/bench_pipeline.py --tier=wnat-3m --runs=1 --fail-on-regression
python scripts/bench_pipeline.py --tier=medium --check-regression
```

---

## INPUTS

| Tier | Nodes Target | Input Source | Wall-Clock | Gate |
|------|-------------|--------------|-----------|------|
| tiny | ~100 | Synthetic annulus (generated in-code) | <5s | CI always |
| medium | ~5K | File-based (fallback: synthetic) | <30s | CI nightly |
| wnat-3m | ~3M | Reference fixture: `tests/fixtures/fort14/adcirc_examples/wnat_test.14` | minutes | Manual/nightly |

**File:** `benchmarks/data/medium_lake.toml` (optional; synthesized if missing)

**CI gating:** Default CI action runs tiny only. Nightly CI or manual run passes `--tier=medium` or `--tier=wnat-3m`.

---

## ARTIFACTS

**JSON result:** `benchmarks/results/{git_sha_12}-{env_hash_8}.json`

```json
{
  "git_sha": "abc1234def567890abcd",
  "env_hash": "5f7c9a12",
  "timestamp_utc": "2026-05-24T19:30:00Z",
  "tier": "tiny",
  "wall_clock": {
    "end_to_end": {
      "median_ms": 45.2,
      "q25_ms": 43.1,
      "q75_ms": 47.3
    }
  },
  "peak_memory_mb": {
    "end_to_end": 45.0
  },
  "end_to_end_ms": 45.2
}
```

**Human summary:** `benchmarks/results/SUMMARY_{git_sha_8}.txt`

```
ADMESH Benchmark Summary — 2026-05-24T19:30:00Z
Git: abc1234 | Env: 5f7c9a12
Tier: tiny

Stage                        | Median (ms) | Q25-Q75 (ms) | Peak Mem (MB)
-----------------------------------------------------------------------
end_to_end                   |       45.20 |  43.1-47.3   |         45.0
```

**Storage:** Both committed to `benchmarks/results/`, versioned with git SHA + env hash for traceability.

---

## CI-GUARD

**Mechanism:**
1. Benchmark runs, saves JSON
2. Script loads most recent baseline JSON for same tier
3. Compares run median vs baseline median
4. Fail if delta > 15% (configurable via `--threshold`)

**Baseline refresh:**
- Operator (or automated approval gate) commits new baseline JSON to main
- CI reads from latest on main branch
- No automatic refresh; explicit promote-to-baseline step

**Usage:**
```bash
# CI: fail if regressed >15%
python scripts/bench_pipeline.py --tier=tiny --ci --fail-on-regression

# Dev: check without failing
python scripts/bench_pipeline.py --tier=tiny --check-regression

# Establish new baseline (manual after review)
git add benchmarks/results/{sha}-{hash}.json
git commit -m "benchmark: establish baseline for tiny tier (sha={sha}, env={hash})"
git push origin main
```

---

## EXACT SETUP + RUN

```bash
# 1. Install
pip install -e ".[dev]"

# 2. Verify setup (check imports + numba available)
python -c "import numba; import admesh; print(f'admesh {admesh.__version__}, numba {numba.__version__}')"

# 3. Run tiny benchmark (CI-like)
python scripts/bench_pipeline.py --tier=tiny --runs=3

# 4. Run with regression check (optional)
python scripts/bench_pipeline.py --tier=tiny --check-regression

# 5. Full nightly (medium + wnat-3m)
python scripts/bench_pipeline.py --tier=medium --runs=3
python scripts/bench_pipeline.py --tier=wnat-3m --runs=1

# 6. Commit baseline if green
git add benchmarks/results/
git commit -m "benchmark: baseline update"
```

---

## Spec Integration Points

- **spec-002 (size-field defaults):** Baseline established on wnat-3m with uniform h0; spec-002 re-runs to show size-field stack overhead + quality gains (min_q, mean_q).
- **spec-004 (quad-prep smoother):** Optional post-process; measure smoother wall-clock + memory impact; co-locate in same result artifact.
- **Regression gates:** Both specs use same harness + CI guard; shared baseline per tier.

---

## Future Enhancements (Phase 2)

1. **Per-stage breakdown:** Instrument each of 13 stages individually
2. **Custom metrics:** Add mesh quality (min_q, mean_q) to result dict
3. **Profile-aware reporting:** CPU / GPU / memory pressure profiling
4. **Automated baseline refresh:** CI approval gate promotes results to main
5. **GitHub Actions integration:** Nightly scheduled runs, comment on PRs
