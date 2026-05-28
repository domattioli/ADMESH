# Spec 020 — Align WNAT benchmark mesh generation with the production `triangulate()` path (resolves #101)

**Status:** Planning-phase only. No code shipping in this commit (ADMESH planning profile).
**Issue:** [#101 wnat mesh for the benchmark has far too many low quality elements](https://github.com/domattioli/ADMESH/issues/101) — `priority: critical`, `Executive: Approved`, `status: ready`.
**Related:** [#65](https://github.com/domattioli/ADMESH/issues/65) / spec-017 (wire default size-field stack in `triangulate()`), [#86](https://github.com/domattioli/ADMESH/issues/86) (C++/Rust port), [#8](https://github.com/domattioli/ADMESH/issues/8) (size-field acceleration), PR [#103](https://github.com/domattioli/ADMESH/pull/103) (C++ distmesh — separate branch, does **not** address this).
**Branch:** `daily-maintenance`
**Target:** code-shipping session (this spec is the contract; implementation is out of scope here).
**Token budget:** SMALL–MEDIUM (1 worker rewrite + 1 regression test + 1 driver touch).

---

## 1. Problem statement

The WNAT version-comparison benchmark reports far too many low-quality / near-degenerate triangles. With params derived from `wnat_test.14` (hmin=0.119, hmax=0.967, g=0.209) the benchmark mesh hits `min_q=0.023` — well below the production floor — and its quality distribution does not match the WNAT (Onur/Hagen) source. The production `triangulate()` path yields WNAT `mean_q≈0.93`.

## 2. Root cause (grounded in current `daily-maintenance` code)

The benchmark is a per-stage **timing** harness that bypasses `admesh.triangulate()` and calls locked stage modules directly with a **mis-parameterized, simplified size field**:

- `benchmarks/_bench_worker.py:69-72` — `build_h(_D, base=hmax, hmin, hmax, g, curvature_scale=a.hmin, medial_scale=a.hmin)`. `curvature_scale`/`medial_scale` are set to `a.hmin` (a *length*, ≈0.12), not the spec-002/017 production defaults (`curvature_scale=20.0`, `medial_scale=0.1`, plus the bathymetry term). No bathymetry stage is composed. This produces a poor size field.
- `benchmarks/_bench_worker.py:83` — `distmesh2d(fd=dom.sdf, fh=fh, h0=a.hmin, ...)` is a raw stage call. It bypasses the production path's `quality_gate=(0.30, 0.60)` (`admesh/api.py`), 1D boundary seeding (spec-007), and `fixmesh` repair.

Net: the low quality is a **real meshing defect of the benchmark's simplified pipeline**, not merely a reporting gap. Confirmed in #101 comment thread: even with correctly derived params the benchmark fails the gate (`min_q=0.023`). The C++ session's `mean_q=0.962` is **not** comparable — it seeds on a bbox grid with bbox-only point-in-polygon and no force-balance (#101 comment 4), so it does not refute this.

**Not a Constitution Principle I concern.** The 13 locked stage modules are unchanged; this is an additive-layer / harness defect in `benchmarks/`.

## 3. Decision

Three options were surfaced on #101 (route through `triangulate()`; replicate the full stack in the worker; lower the gate). Chosen:

**Option 1 — route benchmark mesh generation through `admesh.triangulate()`.** Rationale:
- It is the single source of truth for the production size-field stack (spec-002/017), boundary seeding (spec-007), `quality_gate`, and `fixmesh`. Replicating it in the worker (Option 2) re-introduces the exact drift that caused this bug.
- Per-stage timing is preserved: the existing `_wrap()` monkeypatch already times `eval_sdf_grid` / `apply_curvature` / `apply_medial_axis` / `solve_iter`, all of which `triangulate()` calls internally. Wrap the same stage functions, then call `triangulate()` once and read the accumulated `T` dict.
- Lowering the gate (Option 3) is rejected: it hides the defect rather than fixing it and would publish quality numbers that misrepresent production output.

Dependency note: the production stack wiring lives in spec-017/#65. If #65 has not landed at implementation time, the worker must call `build_h` with the **spec-017 production parameters** (`curvature_scale=20.0, medial_scale=0.1, bathymetry=domain.bathymetry, bathy_scale=0.5, hmin=hmax/10, hmax, g=0.2`) and apply the `quality_gate` post-check — i.e. Option 1's behavior reproduced faithfully, to be replaced by a direct `triangulate()` call once #65 ships.

## 4. Acceptance criteria

- [ ] Benchmark mesh generation uses the production path (`triangulate()`), or — until #65 lands — the exact spec-017 production size-field parameters plus the `quality_gate=(0.30, 0.60)` post-check. No simplified `curvature_scale=hmin` / `medial_scale=hmin` parameterization remains.
- [ ] Per-domain `h0` is honored end-to-end (not silently replaced by `a.hmin` where the production path would derive it).
- [ ] On WNAT (`wnat_test.14`-derived params) the benchmark mesh reports `min_q ≥ 0.30` and `mean_q ≈ 0.93`, matching `triangulate()` output for the same domain/params.
- [ ] Per-stage timing breakdown is preserved (the published `## Performance` table in `README.md` still resolves SDF-grid / curvature / medial / grading-solve / distmesh).
- [ ] A regression test asserts benchmark `min_q ≥ gate floor` on the tiny/medium tiers, so a future simplification cannot silently reintroduce degenerate output.
- [ ] If the benchmark cannot use the production path for a given tier, it documents the explicit reason inline.

## 5. Files likely touched (implementation session)

- `benchmarks/_bench_worker.py` — replace the simplified `build_h` call with the production path (or spec-017 params + gate); keep the `_wrap` timing hooks.
- `benchmarks/compare_versions.py` — ensure derived `h0`/params flow through unchanged; no per-stage timing regression.
- `benchmarks/results/version_comparison.md` + `README.md` `## Performance` — regenerate numbers (quality columns will change; speed columns should be comparable).
- `tests/` — new regression test asserting benchmark `min_q ≥ 0.30` on a tiny tier.
- `docs/PORTING_NOTES.md` — note benchmark-vs-production alignment (no MATLAB-parity change).

## 6. Risks

| Risk | Mitigation |
|---|---|
| Routing through `triangulate()` changes published speedup numbers (production stack heavier than simplified field) | Speedup is *relative* (v0.2.1 vs current) and both versions route identically; re-publish with a one-line note that quality now reflects production. |
| spec-017/#65 not yet merged at impl time | Fallback path in §3 (spec-017 params + gate) is the contract until #65 lands; swap to direct `triangulate()` after. |
| Per-stage timing breaks if `triangulate()` changes internal call names | Pin the wrapped stage-function names in the regression test; fail loudly if a hook no longer fires. |
| WNAT full Onur (127K nodes) too slow for CI | Keep the 10K-node `wnat_test.14`-derived tier as the gated benchmark; full-Onur stays opt-in. |

## 7. Out of scope

- Any change to the 13 locked stage modules (Constitution Principle I).
- C++/Rust port quality (#86) and bbox-seed fidelity in `admesh-cpp` (PR #103) — separate track.
- GPU/CPU acceleration of the size-field stack (#8).
- Convergence-tuning (ttol/dptol) speedups — the harness deliberately fixes `niter` to isolate per-call cost.

## 8. Cross-references

- #101 (this issue) — root-cause thread (4 comments) culminating in the Option-1 recommendation this spec formalizes.
- #65 / spec-017 — production size-field stack wiring; hard dependency for the clean form of Option 1.
- #86 — language port; #101 comment 4 explains why its `mean_q=0.962` is not comparable.
- `benchmarks/DESIGN.md`, `.claude/handoffs/2026-05-25-wnat-version-benchmark.md` — harness design + prior session state.
