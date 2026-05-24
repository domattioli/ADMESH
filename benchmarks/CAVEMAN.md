# ADMESH Benchmark Harness — Caveman Ultra

## SETUP

Install: `pip install -e ".[dev]"` (numba ≥0.58 required; NOT in base deps).
Pin: git SHA (12-char) + env_hash MD5(py-ver | numba-ver | numpy-ver | scipy-ver | admesh-ver) + UTC timestamp.
Test: `python -c "import numba; import admesh; print(admesh.__version__, numba.__version__)"`

## HARNESS

Entry: `scripts/bench_pipeline.py --tier=[tiny|medium|wnat-3m] --runs=[1|3]`
Timing: `time.perf_counter()` wall-clock; `tracemalloc.get_traced_memory()[1]` peak-mem.
JIT warmup: one dummy call excluded. Measured: 3 runs (tiny/medium) or 1 (wnat-3m).
Stats: median + Q25/Q75 percentiles. Per-stage hooks deferred; MVP = end-to-end only.

## INPUTS

| Tier | Nodes | Source | Gate |
|------|-------|--------|------|
| tiny | ~100 | synthetic annulus (in-code) | CI always |
| medium | ~5K | `benchmarks/data/medium_lake.toml` or synthesized | CI nightly |
| wnat-3m | ~3M | `tests/fixtures/fort14/adcirc_examples/wnat_test.14` | manual/nightly |

CI default: tiny only. Args: `--tier=medium`, `--tier=wnat-3m` override.

## ARTIFACTS

JSON: `benchmarks/results/{git_sha_12}-{env_hash_8}.json`
```json
{"git_sha":"abc1234def567890","env_hash":"5f7c9a12","timestamp_utc":"2026-05-24T19:30:00Z",
 "tier":"tiny","wall_clock":{"end_to_end":{"median_ms":45.2,"q25_ms":43.1,"q75_ms":47.3}},
 "peak_memory_mb":{"end_to_end":45.0},"end_to_end_ms":45.2}
```

Summary: `benchmarks/results/SUMMARY_{sha_8}.txt` — human table (stage | median | Q25-Q75 | peak_MB).

Committed to repo (versioned by SHA+hash); baseline = latest same-tier on main.

## CI-GUARD

Load baseline JSON from `benchmarks/results/` for same tier; compare run median vs baseline.
Fail if >15% slower. Manual promote-to-baseline: `git add benchmarks/results/{sha}-{hash}.json && git commit -m "baseline: ..."` on main.

Usage:
```bash
# Check without failing
python scripts/bench_pipeline.py --tier=tiny --check-regression

# CI: fail if regressed
python scripts/bench_pipeline.py --tier=tiny --ci --fail-on-regression
```

## EXACT STEPS

```bash
pip install -e ".[dev]"
python scripts/bench_pipeline.py --tier=tiny --runs=3 --check-regression
python scripts/bench_pipeline.py --tier=medium --runs=3
python scripts/bench_pipeline.py --tier=wnat-3m --runs=1
git add benchmarks/results/ && git commit -m "benchmark: baseline"
```

Spec integration: spec-002/spec-004 use same harness; add quality metrics (min_q, mean_q) to result dict in Phase 2.
