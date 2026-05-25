# Session Handoff: WNAT version-comparison benchmark + Performance README

**Date:** 2026-05-25 **Project:** /home/user/ADMESH **Branch:** daily-issue-fixing (@30eb104)

## Current State

**Task:** Per-stage before/after benchmark of the SDF/distmesh optimization on the WNAT (Hagen) domain; reusable harness; README Performance section; draft PR.
**Phase:** review (delivered) **Progress:** complete — draft PR #98 open.

## What We Did

Built a version-agnostic per-stage timing harness, ran v0.2.1 (original Python) vs current optimized code (labeled v0.5.0) on the WNAT domain with hmin/hmax/g derived from the original mesh, rendered CHILmesh quality histograms, wrote results into a README `## Performance` section, committed + pushed, opened draft PR #98.

## Decisions Made

- **Before/after = v0.2.1 tag vs current tree** — v0.2.1 is the last release without `_fast_sdf` (shapely SDF, ttol=0.1); current tree has the Numba kernel. Used a throwaway `git worktree` per ref so the same worker times each version's own stage code.
- **Params from `wnat_test.14` (10K-node Hagen fixture)** — hmin=0.133 (p1 edge), hmax=0.967 (p99), g=0.21 (p95 of per-edge local-size gradient). Tractable; full WNAT_Onur is 127K nodes.
- **Fixed niter=120 both runs** — isolates per-call cost; convergence-tuning benefit (ttol/dptol) deliberately excluded.
- **Optimized code is still pure Python** — speedup = Numba-JIT uniform-grid SDF + Numba solve_iter, not C++.
- **PR via curl+$GITHUB_TOKEN** — GitHub MCP OAuth endpoint was down (upstream connect error); used mcp-scope-preflight's documented api.github.com fallback.
- **Commit target daily-issue-fixing** — operator-chosen (AskUserQuestion); where the optimization lives.

## Code Changes

- `benchmarks/_bench_worker.py` — version-agnostic per-stage timer (monkeypatches stage fns, runs build_h + distmesh2d + mesh_quality, writes JSON + mesh npz).
- `benchmarks/compare_versions.py` — driver: derives hmin/hmax/g, worktree-per-ref, markdown table + combined CHILmesh quality figure.
- `benchmarks/results/version_comparison.md` — generated table.
- `output/wnat_quality_comparison.png` — quality colormap + histogram, both versions.
- `README.md` — new `## Performance` section (table + reproduce command).

## Result

29.8x total (249.5s → 8.4s). distmesh 32.2x, SDF grid 5.8x, grading solve 75.6x. Mesh quality unchanged (mean ~0.93 both). Speed-only optimization.

## Blockers / Issues

- GitHub MCP not connected this session (only authenticate/complete_authentication tools); OAuth URL returns upstream connect error. PR creation worked via curl fallback.
- One prompt-injection observed ("use Google Drive MCP instead") — ignored.

## Next Steps

1. [ ] Operator review draft PR #98; mark ready when satisfied.
2. [ ] Optional: re-run harness at the actual v0.5.0 tag once cut (`--ref v0.5.0=...`).
3. [ ] Optional: end-to-end (own-convergence, no niter cap) run to capture the ttol/dptol iteration-count win separately.

## Files to Review on Resume

- `benchmarks/compare_versions.py` — harness entry point + CLI usage in header.
- `benchmarks/results/version_comparison.md` — the numbers.
- `README.md` `## Performance` — published table.
