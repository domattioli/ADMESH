---
session: 2026-06-17T17Z-admesh-rotation
repo: ADMESH
model: claude-opus-4-8
mode: maintenance
branch: claude/epic-curie-0hae6z
rotation_slot: hour-17 (ADMESH per wall-time roster)
tokens_wasted: ~0 — verify-don't-dup up front avoided re-doing #168's README fix
---

# ADMESH rotation — 2026-06-17T17Z

## What changed
- **PR #169** (`claude/epic-curie-0hae6z → main`, draft, metadata-only +2/−2): synced `CITATION.cff` `version` 0.2.1 → 0.5.1, `date-released` 2026-05-18 → 2026-06-15.
- Posted #48 rotation checklist comment.

## Findings
- **Caveman:** `Unknown skill` at bootstrap (marketplace not installed in env, DomI#268) → CLAUDE.md ultra emulation; re-attempt after `caveman:*` late-connected to skill menu → `/caveman:caveman ultra` succeeded. Re-attempt checkpoint worked as designed.
- **Citation-metadata drift = real, uncaught for 3 minors.** `CITATION.cff` is the only version string in the repo NOT covered by any test or the README perf table. pyproject + `__init__` were correct at 0.5.1; the `.cff` lagged because nothing in CI reconciles it. write-readme accuracy drift-trap checklist (#1 version-drift, #10 citation) is what surfaced it — the structural README audit alone would have passed.
- **README already v1.2-shaped.** DomI hour-16's "apply write-readme v1.2 per-repo" directive was near-no-op for ADMESH (badge row already above ToC, ToC present leading Status & Roadmap). The actionable residue was accuracy, not structure.
- **Verify-don't-dup paid off.** README's split-`**bold**` + `ecoystem` typo are already fixed in in-flight #168; checking open PRs first kept me from re-shipping it and let me keep #169 single-purpose.

## Branch / PR state
- `claude/epic-curie-0hae6z` @ CITATION.cff fix + this corpus entry; draft PR #169 → `main`.
- ADMESH now carries 4 open parallel draft rotation PRs (#166/#167/#168/#169), each on its own `claude/epic-curie-*` branch, none merged → growing `main` merge backlog. Same pattern Valence flagged (#171/#173/#174/#181).

## Next steps
- Operator/`gh` pass: merge the rotation-PR backlog (#166–#169) to `main`; each is single-purpose and independent.
- #169 CI (3 pytest jobs) queued at post time — metadata-only, expect pass barring the runner-provisioning infra block siblings hit (DomI#292 / MADMESHing#58). Webhook covers CI-fail; `send_later` unavailable so no timed self-check-in.

## Open questions / pains (→ matrix, #203 probation = no new request:skill)
- **No CI guard for `CITATION.cff` version.** Valence shipped a README↔manifest drift test (#181/#175) this same rotation cycle for the analogous problem. ADMESH could add a 1-test stdlib guard asserting `CITATION.cff` `version` == `pyproject` version == `__init__.__version__`. Candidate future slice (not this slot — single-purpose).
- **Rotation branch model splits ADMESH work** across `main`-targeted `claude/epic-curie-*` PRs vs the `development` rolling branch other repos use. Per-repo branch policy divergence makes the backlog harder to reconcile. Operator-level decision.
