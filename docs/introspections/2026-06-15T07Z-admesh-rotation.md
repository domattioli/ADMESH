---
date: 2026-06-15
session: 2026-06-15T07Z-rotation
repo: ADMESH
severity: low
freq: recurring
issues: [158, 155, 162, 289, 268]
wasted_min: 6
wasted_tok: 220000
missing_skill: none
---

# ADMESH rotation 2026-06-15T07Z — maintenance track

**Task:** hour-07 slot (rotation script → ADMESH, slot=2, maintenance). DomI pin sync + top-of-queue bug.
**Outcome:** complete. 2 commits on `development`, rolling PR #163, #48 checklist posted.

## Pre-flight
- branch_policy_conflict: caught. SDK injected `claude/modest-clarke-383hu0`; §6 knob = `development` → switched before any write. No orphan branch.
- mcp_scope_gap: no (ADMESH in scope).
- domi_drift: yes → pin `3e46639 → 69b073d` synced via sibling-clone `update_pin.sh` (no net dep). DomI delta internal-only; ADMESH vendors none.

## Shipped
1. **#158** bench_wnat.py stale schema (`KeyError: 'vertices'` + removed ctor + dead imports) → mirror bench_enpac.py. Code → Haiku subagent; orchestrator verified run (94776 nodes, exit 0). `72d5194`.
2. **DomI pin** `2372ab2`.
3. **#155** verified fixed-not-closed on dev (`8f7e005`, regression-tested) — closes on PR #163 merge.

## Pains (→ matrix)
- **mcp-token-cap-blowout** (freq recurring, sev low): `actions_list` + `get_file_contents(MANIFEST)` + `list_workflow_runs` each overflowed tool-result cap. Recovered via saved-file `python3 json.load`/jq (DomI #289 pattern). ~220k tok wasted across 3 hits. True fix = MCP-side field projection, out of DomI reach.
- **caveman-marketplace-race** (sev low): `Skill(caveman:caveman ultra)` → `Unknown skill` at bootstrap; succeeded on re-attempt after MCP connected mid-session (DomI #268, tracked).
- **admesh-branch-divergence** (sev low): `development` behind `main` by #162 introspect-migration + 3 commits; no open rolling PR until this slot. Reconcile flagged operator-only (docs/introspections conflict risk). Not a re-fileable skill gap — coordination state.

No new `request: skill` (#203 probation).
