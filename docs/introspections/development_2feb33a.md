# Session corpus — development_2feb33a

**Repo:** ADMESH · **Branch:** development · **Date:** 2026-06-09T03Z · **Model:** claude-opus-4-8
**Routine:** unified routine §1–7, hour 03 → ADMESH active repo.

## What changed
- **#144 closed** — DomI drift resolved. `.domi-pin` `074e4a0` → `69fdeb7` (main HEAD), manifest hash re-verified vs in-session DomI checkout (`== origin/main`). Commit `36d6e1d`.
- **#133 advanced** — spec-028 **T002** shipped: demo compute `catch` shows `Draw at least 3 vertices to define a domain` instead of bare traceback. `tasks.md` T002 → `[x]`. Commit `2feb33a`. Issue left open (operator merge → Pages redeploy gates browser-behavioral acceptance).
- Rolling PR **#142** refreshed (title + body).

## Key decisions
- **Branch:** ignored system-prompt `claude/great-tesla-v3tky0` (harness injection); worked on `development` per DomI `branching.md`.
- **Sync inline fallback:** `sync-from-domi` plugin install failed at start (marketplace network). Refreshed pin by replicating `update_pin.sh` exactly — `echo -n` manifest hashing (strips trailing newline; differs from raw `sha256sum`) against verified local checkout. Network path (api.github.com, no `GITHUB_TOKEN`) dead.
- **Coding dispatch:** T002 HTML/JS edit delegated to Haiku subagent per CLAUDE.md rule; validated via inline-`<script>` extraction → `node --check`.

## Env capability (re-verified this session, #223)
- No `matlab`/`octave` in container → #78 parity-fixture generation still blocked. Re-confirmed, not parroted.
- Base python has **no numpy/scipy** → `pytest tests/` needs a built venv (`ensure-test-venv`). Not built this session (work was config + demo HTML, no Python-test surface touched).
- `node` v22 present at `/opt/node22/bin/node`.
- DomI marketplace plugin install fails (network) — contract skills run via local-checkout inline fallback.

## Next steps
- #78: needs MATLAB/Octave runner for stage-02 fixture (`background_grid_unit_square.npz`) → drop xfail. Defer to hosted runner.
- #133: operator merge `development → main` to redeploy Pages, then close.
- #86 (v1.0 cpp/rust): LARGE, multi-PR (specs 021/022 octree in flight) — needs decomposition, not a single-session close.

## Open questions / pains (→ PAIN_MATRIX, probation: no skill votes)
- `tokens_wasted`: ~moderate. Sync inline-fallback hashing subtlety (`echo -n` vs file sha256) cost a couple tool calls to get right — a `sync-from-domi` local-checkout mode (no network) would remove the per-session manual replication.
- Repeated env-capability re-checks (matlab absent, numpy absent) every session — a cached per-container capability probe would save the rediscovery walk.

## Introspect retro (close-out, user-requested handoff+introspect)
- **Extra work after first close-out** (#99 plan + #145 filed) — operator follow-ups on research issues sit unanswered for days because routine sorts code/closeable issues first; brainstorming issues with operator questions need a "stale-operator-question" surfacing pass. `tokens_wasted`: low (the work itself was high-value).
- **What went right:** routing — #144 (closeable) first, then additive demo fix via Haiku subagent, then research synthesis. No faithful-port surface touched → zero Principle-I risk, no venv tax.
- **What'd help:** (1) `sync-from-domi` offline/local-checkout pin mode (recurring); (2) `bench_pipeline.py` (#145) would have let me ground the #99 plan in real numbers instead of citing prior anecdotal timings; (3) a `triage-stale-operator-questions` helper that flags issues where the last comment is an unanswered operator question.
- **No skill votes / new request issues** — DomI probation active (#203). Pains logged here per `tokens_wasted` routing.

