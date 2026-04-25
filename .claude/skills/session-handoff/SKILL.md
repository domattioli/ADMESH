---
name: session-handoff
description: Write a concise `docs/sessions/session_<N>_state.md` so the next session (or the current session after /compact) can resume without re-reading everything. Captures the running plan pointer, what shipped in this session, what's in-flight, open blockers, and next concrete action. Inspired by Codex long-horizon and GSD pause-work patterns. Use before stopping work, before /compact, and when the user redirects mid-session.
---

# session-handoff

## When to invoke

1. Before stopping persistent work for the day or before `/compact`.
2. When a session is being redirected and needs a clean resume point
   for later.
3. Every time a milestone ships, to update the "where we are" pointer
   in `PROJECT_PLAN.md`.

## What it writes

A single file: `docs/sessions/session_<N>_state.md` (overwrites in-place, one
per session). Plus an update to `PROJECT_PLAN.md`'s "Where we are
today" snapshot when a milestone shipped.

## Template for `docs/sessions/session_<N>_state.md`

```markdown
# Session <N> — state snapshot

**Last updated:** <YYYY-MM-DDTHH:MM>
**Session plan:** `docs/sessions/session_<N>_plan.md`
**Active milestone:** <M.x> — <one-line description>
**Active workstream:** <WSk> — <one-line description>
**Repo head:** <git short SHA> — "<commit message first line>"

---

## Shipped this session

- <M.x / WSk>: <one line, commit SHA>
- ...

## In-flight

<what's mid-execution; NONE if nothing is>

## Open blockers

- <blocker 1> — how to unblock
- ...

## Next concrete action

<one paragraph: what the next turn should do, which files to touch,
which tests to run. Written so next-session-me can open this file
cold and start working in < 2 minutes without re-reading the plan.>

## Live interrupts

<mirror of interrupts logged via /log-interrupt this session;
append-only>

| time | trigger | ws | was_doing | user_said | cost | lesson |
|------|---------|----|-----------|-----------|------|--------|
```

## Steps

### 1 — determine session number

- Find the most recent `docs/sessions/session_<N>_plan.md`. Use that `<N>`.
- If none exists, `<N> = 0` and warn that no plan file was found.

### 2 — gather snapshot data

- `git log -1 --format="%h %s"` for repo head.
- Task list (via `TaskList`) for active / shipped / blocked state.
- Scan the session plan for the current active milestone + workstream.

### 3 — write `docs/sessions/session_<N>_state.md`

Populate the template. Keep bullets terse (< 15 words each). The
"Next concrete action" paragraph is the single most important
field — bias specificity over completeness.

### 4 — update `PROJECT_PLAN.md` "Where we are today"

If a milestone shipped since the last update, amend the snapshot.
Do NOT rewrite phase definitions or exit criteria — only the
"Where we are today" section changes.

### 5 — commit

```bash
git add docs/sessions/session_<N>_state.md PROJECT_PLAN.md
git commit -m "session <N>: handoff snapshot"
git push
```

## Hard rules

- One state file per session. Overwrite in place; do not accumulate
  per-timestamp copies.
- Never delete a prior session's state file — they are the resumption
  trail.
- No Agent tool invocations from this skill.
- No emojis.
- The "Next concrete action" paragraph is mandatory. If you can't
  write one, the session isn't ready to hand off.
