# ADMESH Hooks Audit

Read-only audit of the ADMESH Claude Code hook footprint. Companion to
`TEST-AUDIT.md`. Per issue [#61](https://github.com/domattioli/ADMESH/issues/61).

**Audit date:** 2026-05-18
**Branch:** `daily-issue-fixing`

## 1. Inventory

| Location | Present? | Notes |
|---|---|---|
| `~/.claude/settings.json` (user-scope) | yes (managed) | `Stop` hook → `~/.claude/stop-hook-git-check.sh`; `permissions.allow = ["Skill"]`. DomI-managed envelope. |
| `.claude/settings.json` (repo-scope) | **no** | ADMESH does not declare any repo-scope hooks. |
| `.claude/CLAUDE.md` (repo-scope) | yes | Operational reference doc. Not a hook. |
| `scripts/hooks/` | **no** | Empty / absent. |
| `.githooks/` | **no** | Empty / absent. |
| `scripts/instructions_on_start.sh` | yes | DomI drift check; manually invoked by SessionStart hooks elsewhere. |
| `.domi-pin` | yes (committed) | DomI sync ledger. |

## 2. Comparison against DomI's specified hook set

`domattioli/DomI#60` (commit `d11ca39`) specifies a set of 5 wired hooks
plus 7 more in spec. ADMESH wires **zero** of them at repo scope:

| Event | Hook | ADMESH state |
|---|---|---|
| SessionStart | `session_start.sh` (DomI) → `instructions_on_start.sh` | NOT wired — operator must invoke manually |
| PreToolUse:Bash | `branch_guard.sh` | NOT wired |
| PreToolUse:Bash | `commit_msg_guard.sh` | NOT wired |
| PreToolUse:Write\|Edit | `secret_path_guard.sh` | NOT wired |
| Stop | `stop_introspect.sh` (advisory) | NOT wired locally; user-scope Stop hook is a different script |

**Implication.** Every guard policy DomI specifies (no `claude/*`
branches, no `--no-verify`, no force-push, conventional commit format,
secret-path blocker, advisory introspect) is **unenforced** in
ADMESH sessions. The only guard ADMESH gets is whatever runs at
user scope via the host machine's `~/.claude/settings.json`.

## 3. Findings (severity tagged)

### F1 — **HIGH: no repo-scope `.claude/settings.json`**

Every consumer repo should ship its own `.claude/settings.json` that
wires the DomI-specified hooks. ADMESH ships none.

**Fix**: drop in a `.claude/settings.json` referencing the
DomI-managed hook scripts under
`~/.claude/plugins/cache/DomI/<plugin>/hooks/*` (or the
sync-from-domi materialized location). Belongs to a follow-up issue
since the DomI hook scripts must be in a known path before the
wiring lands here. See domattioli/DomI#64 (inbox).

### F2 — **MEDIUM: `instructions_on_start.sh` not wired to SessionStart**

`scripts/instructions_on_start.sh` exists and works, but no
`SessionStart` hook invokes it. It runs only when a startup-hook
elsewhere (DomI plugin, user shell rc) shells out manually.

**Fix**: once F1 lands, the repo-scope `SessionStart` matcher should
call `bash scripts/instructions_on_start.sh`. Until then, the
drift-check semantics in `CLAUDE.md` ("HARD STOP on drift")
are aspirational, not enforced.

### F3 — **NO-ACTION: `.claude/CLAUDE.md` exists alongside top-level `CLAUDE.md`**

ADMESH has both `CLAUDE.md` (top-level) and `.claude/CLAUDE.md`. The
`.claude/`-scoped one is a shorter operational reference; the
top-level one is the canonical doc. Some readers will be confused.

**Decision: no action** — the two files have different intended
audiences (`.claude/` = session-loaded context; top-level = repo
documentation). Audit-only flag.

## 4. Backlog

| # | Title | Effort | From finding |
|---|---|---|---|
| H-01 | Drop `.claude/settings.json` wiring DomI hooks | S | F1 |
| H-02 | Wire `SessionStart` to invoke `instructions_on_start.sh` | XS | F2 |

## 5. Upstream-relevant findings (`domattioli/DomI#64`)

| Finding | Why upstream |
|---|---|
| F1 | The gap (no consumer-repo `.claude/settings.json`) is universal across consumers. DomI should ship a `templates/.claude/settings.json` that consumers symlink or `cp`. |
| F2 | The `SessionStart → instructions_on_start.sh` wiring is the same pattern across every consumer that runs a DomI drift check. DomI's `sync-from-domi` plugin could materialize the hook wiring automatically when it lays down the drift-check script. |

Both are cross-posted on DomI#64 (this audit's reporting inbox).

## 6. Local-only findings (followed up here)

None. The hook footprint at repo scope is empty; every gap belongs
upstream. F3 is no-action.

## 7. Methodology

This audit is **static**. Findings come from:

- `ls -la .claude/`
- `find . -name "settings.json"`
- `find . -name "*.sh" -path "*hooks*"`
- `cat ~/.claude/settings.json` (read-only)
- Cross-reference against DomI#60 commit `d11ca39`'s hook list.

No hook scripts were executed.

## Related

- Issue #61 — this audit.
- Issue #60 — sibling TEST-AUDIT.md (separate).
- Upstream: `domattioli/DomI#64` — inbox issue for cross-repo
  hook findings.
- Upstream: `domattioli/DomI#60` — DomI's full hook spec.
