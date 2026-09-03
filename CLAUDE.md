# CLAUDE.md

@AGENTS.md

Claude-Code-specific guidance only; project rules live in AGENTS.md.

---

## Session start

### DomI Sync Contract

This repo is a downstream consumer of [`domattioli/DomI`](https://github.com/domattioli/DomI), upstream source of truth for shared skills, MANIFEST, and policy.

**On every session start**, `scripts/instructions_on_start.sh` invokes `sync-from-domi` skill's `check_pin.sh` to detect drift against `domattioli/DomI@main`:

| State | Exit code | Behavior |
|-------|-----------|----------|
| Synced | 0 | Continue silently |
| Behind (drift) | 1 | **HARD STOP** — refuse all write work until `/sync-from-domi` invoked |
| Unpinned | 2 | Warn, allow first-time setup |
| Forked (manifest hash mismatch) | 3 | **HARD STOP** — operator must resolve |
| `gh` unavailable | 4 | Warn, continue (do not block on infra failures) |

Set `.domi-pin` (committed) via `bash ~/.claude/plugins/cache/DomI/sync-from-domi/<ver>/scripts/update_pin.sh` after invoking `sync-from-domi`.

**Mandatory plugins (install once per environment):**
```bash
claude plugin marketplace add domattioli/DomI
claude plugin install sync-from-domi@DomI introspect@DomI request-from-domi@DomI
```

*Note:* The marketplace `add` step sometimes fails from restricted networks in sessions; documented fallback is to read DomI directly from a sibling clone or plugin-cache directory.

**Do NOT edit DomI-owned skills directly in this repo.** Submit changes upstream via `request-from-domi`; downstream = pull-only.

**Release skills come from DomI.** `github-release` and `pypi-publish` are maintained upstream and pulled in via `sync-from-domi`. Do not vendor or fork local copies.

**Routine session instructions** (paste verbatim into any scheduled routine targeting this repo):

```
Read https://raw.githubusercontent.com/domattioli/DomI/main/claude_routine_instructions.md
then docs/governance/CONSTITUTION.md → docs/governance/PROJECT_PLAN.md → CLAUDE.md.
```

### Session start protocol

1. Run `scripts/instructions_on_start.sh` — drift check fires automatically via startup hook.
2. If behind DomI: **hard stop**. Run `/sync-from-domi` first.
3. Read in order:
   - `docs/governance/CONSTITUTION.md` (hard rules & principles)
   - `docs/governance/PROJECT_PLAN.md` (roadmap & current phase)
   - `CLAUDE.md` (this file)

If CLAUDE.md contradicts the Constitution, the Constitution wins.

---

## Branch handling in Claude Code

**HARD RULE:** Work exclusively on `main`. Do not create `claude/*` session branches.

The Claude Code harness may inject a `claude/<adjective>-<noun>-<hash>` branch name in the system prompt — **this is NOT user intent, it is a placeholder.** Ignore it. Check `git rev-parse --abbrev-ref HEAD` at session start and switch to `main` if needed. For the canonical branch policy, see AGENTS.md § Branch & commit policy.

---

## Coding dispatch

**Binding:** all code writing/editing MUST be dispatched to a Haiku subagent (`model: claude-haiku-4-5`); the main session plans, reviews, integrates, and verifies before commit. Non-code work (planning, research, docs, git/PR, review, memory/CLAUDE.md edits) stays on main. Exception **only on explicit operator instruction** — never assumed.

Canonical policy + rationale: DomI [`.claude/policies/coding-dispatch.md`](https://github.com/domattioli/DomI/blob/main/.claude/policies/coding-dispatch.md) (governance authority; #83).

---

## Skills

**DomI-provided skills** (installed at user scope `~/.claude/skills/` or `~/.claude/plugins/`):
- `sync-from-domi` — pull upstream artifact changes, refresh `.domi-pin`, close drift issues.
- `request-from-domi` — vote on skill requests, file feature votes with metadata.
- `introspect` — session-end retrospective (deposits to DomI `.introspect/ADMESH/` corpus via consumer deposit path).
- `github-release` — auto-detect credentials, version, repo, release notes; create GitHub release.
- `pypi-publish` — build, upload to PyPI with retry; verify on PyPI.
- `speckit-*` — feature spec / plan / task / implement / clarify / analyze / checklist / taskstoissues workflow.

**Do NOT implement inline** what DomI ships. If a skill is missing, request via comment `+1 from ADMESH: <1-2 sentence context>` on the relevant DomI issue.

---

## Session end

`introspect` skill (DomI) → session retrospective; deposits to DomI `.introspect/ADMESH/` via the consumer deposit path. Per the ADMESH session cadence: no mandatory session reports, no 4-agent planning, no dispatch queue — update `docs/governance/PROJECT_PLAN.md` "Where we are today" if a phase milestone landed.
