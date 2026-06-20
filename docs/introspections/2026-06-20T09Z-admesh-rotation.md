---
session: 2026-06-20T09Z-admesh-rotation
repo: ADMESH
model: claude-opus-4-8[1m]
mode: maintenance
branch: development (operator override "work development only, roll the PR"; harness-injected claude/serene-gauss-lvushx abandoned at start)
rotation_slot: hour-09 (ADMESH per wall-time roster)
tokens_wasted: ~minor — one botched `git pull --ff-only origin development` while still on the harness branch fast-forwarded the wrong ref + left a stash conflict; recovered in 3 calls
---

# ADMESH rotation — 2026-06-20T09Z

## What changed
- **No diff shipped.** `development` already current (pin `0a96f17`, all #172 backlog landed). Slot
  deliverable is measured data, not code.
- **Posted baseline profile to #8** (acceptance criterion 1): ran `scripts/bench_pipeline.py` on
  tier-0 fixtures. `distmesh2d` = 94–97% of default-path runtime; size-field stack = 0% (unwired,
  #65/#140). Redirects #8/#99 parallelization scope away from the Eikonal smoother toward distmesh2d.
- **Slot status on #172** (rolling-PR governance thread; MADMESHing#48 is closed).
- **This introspection** → corpus (rolls into PR #174).

## Findings
- **Caveman:** NOT loaded (absent from skill menu) → emulated from CLAUDE.md ultra rules. Honesty
  per #168: Skill call attempted, returned `Unknown skill`, emulated — not falsely reported active.
- **Drift hard-stop was REAL** (like the 06-18T17Z slot, unlike the 06-18 hour-09 false alarm):
  ADMESH pin `a9b240f` genuinely behind upstream `0a96f17`. Cleared via offline `update_pin.sh`
  against `/home/user/DomI` sibling mirror — but the refresh was **already on `development`** (commit
  `c99a755`), so the regenerate was a no-op once switched to the right branch.
- **The branch confusion is the recurring tax.** Operator override this slot = "develop on
  `development`, roll the PR." That contradicts the per-repo system-prompt branch
  (`claude/serene-gauss-lvushx`) AND Constitution Article VI.1 (trunk-based `main`). I followed the
  operator override. Until #172 ratifies, every slot pays a branch-orientation cost — and one
  mis-sequenced `git pull` (pulling `development` while still on the harness branch) cost a recovery
  loop this slot. Lesson: **`git checkout development` BEFORE any pull**, never pull a branch into the
  one you mean to leave.
- **Repo is maintenance-complete for low-hanging fruit.** 440 tests pass; #167/#168/#169 landed;
  bench tooling (#145) exists; unification API contract test (#143) exists. Remaining open issues
  are research / brainstorm / needs-operator. Honest read: thin maintenance surface this slot.
- **#8's premise is stale.** It assumes the size-field stack is the dominant default cost ("once
  spec-002 ships and the default stack is the headline"). spec-002's stack is NOT the default
  (#65 deferred) → distmesh2d is the real hotspot. Measuring beat assuming.

## Pains (→ matrix rows; no new request:skill per #203)
- **branch-orientation-cost** — harness branch vs system-prompt branch vs operator override vs
  Constitution VI.1, four-way conflict, every slot. Root fix is operator ratification of #172, not a
  skill. Recurring across ADMESH/CHILmesh/QuADMESH/Valence (sibling reports on #172).
- **offline-plugin-absence** — marketplace install fails every bootstrap (no egress); caveman +
  sync-from-domi/introspect plugins never load → manual emulation each slot. Expected, not a bug;
  the sibling-clone fallback works. No skill ask.

## Next slot
- If #172 ratified: align branch policy doc + retire the loser branch.
- #8 full baseline: needs #65 wiring (operator) + WNAT fixture via hosted runner (Valence token).
