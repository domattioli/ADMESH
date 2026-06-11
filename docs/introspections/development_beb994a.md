# Session corpus — development_beb994a

**Repo:** ADMESH · **Branch:** development · **Date:** 2026-06-09T10Z · **Model:** claude-opus
**Routine:** unified routine §1–7, hour 10 → ADMESH active repo.

## What changed
- **#145 closed** — `scripts/bench_pipeline.py` rewritten into the per-stage wall-clock harness. Per-stage timing via runtime monkeypatch of stage entry points (zero faithful-port module edits — Principle I). Fixed the broken `h0=` kwarg (public `triangulate` takes `h_max`). Tier-0 (`UNIT_SQUARE`, `L_SHAPE`) always present; WNAT + tier-1 skip-with-note on missing/unloadable fixture, exit 0. Added `--h0`, `--json`, `--fixtures`, `--runs`. Commit `beb994a`.
- `docs/PORTING_NOTES.md` — `## Benchmark harness (#145)` section pointing #99 phases at the harness.
- Rolling PR **#142** refreshed (title → #145 headline, body + Resolves/Tracks).

## Key decisions
- **Branch:** ignored system-prompt `claude/nice-curie-dkbg6b` (harness injection); worked on `development` per DomI `branching.md` knob table.
- **Dedup catch:** `scripts/bench_pipeline.py` already existed from #96 — but only measured END-TO-END (`_instrument_pipeline` stubbed per-stage: "requires stage-level hooks"). #145's core ask (per-stage table) was genuinely unmet → rewrite, not duplicate.
- **Per-stage without touching locked modules:** monkeypatch stage entry-point callables at their resolved lookup sites (`routine.distmesh2d` by-name binding; `quality.mesh_quality`/`size_field.compose_size_field` lazy-imported at call → patch defining module). Restored on context exit. No `src/admesh/_stages/` edit → Principle I clean.
- **Honesty:** MVP path is distmesh-dominated; size-field stack (curvature/medial/bathymetry/tide/mesh_size) NOT invoked unless a `build_h` field is composed (#65 deferred). Table shows unexercised stages as 0.0 + an "other/unaccounted" row so percentages are honest — no fabricated timings.
- **Coding dispatch:** rewrite + skip-on-error fix both delegated to Haiku subagents per CLAUDE.md rule; orchestrator independently re-ran all validations (didn't trust self-report — #168).

## First numbers for #99 (the deliverable's point)
- `square` (128 nodes): `distmesh2d` ≈ 96.6% of wall-clock.
- `lshape` (376 nodes): `distmesh2d` ≈ 95.8%.
- Confirms the prior anecdotal "distmesh dominates ~46.5 s" claim is reproducible. The P0 gate gating every #99 acceleration phase is now in place.

## Env capability (re-verified this session, #223)
- Base python has **no numpy/scipy** → built `.venv` via `pip install -e ".[dev]"` (admesh 0.2.1). `.venv` gitignored.
- WNAT fixture `tests/fixtures/fort14/adcirc_examples/wnat_test.14` present but `load_domain_from_fort14` raises `No land boundary found` → harness skips it (not fatal). A loadable large fixture still needed for real WNAT timing.
- No MATLAB/Octave → #78 parity-fixture still blocked (unchanged).
- DomI marketplace plugin install fails (network) — contract skills via local-checkout inline fallback.

## Next steps
- #145 follow-on: source a loadable large mesh (or a JSON/registry Tier-1 domain) so WNAT/Tier-1 timings populate — then #99 phases can cite a multi-thousand-node before/after, not just toy domains.
- #99: with the harness landed, P1 (CPU vectorize/prange on the distmesh inner loop) is the next executable phase — distmesh is the proven hotspot.
- #78: needs MATLAB/Octave runner (hosted) for stage-02 fixture → drop xfail.
- #86 (v1.0 cpp/rust): LARGE, multi-PR (octree specs 021/022 in flight) — decomposition, not single-session.

## Open questions / pains (→ PAIN_MATRIX, probation: no skill votes)
- `tokens_wasted`: low-moderate. Venv build (numpy/scipy/numba compile) is a recurring per-container tax on any Python-test/bench session — a cached/prebuilt venv or `ensure-test-venv` warm cache would remove it.
- Per-stage instrumentation required reading the exact lookup-site of each stage fn (by-name vs module-qualified) to patch correctly — a `triangulate(profile=True)` hook in the additive API layer would make future timing first-class without monkeypatch fragility (additive, Principle-I safe). Candidate follow-up issue.
- No skill votes / new request issues — DomI probation active (#203). Pains logged here per `tokens_wasted` routing.
