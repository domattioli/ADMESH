---
name: log-interrupt
description: Append a row to `docs/persistence_journal.md` when a persistent session is interrupted, stalls, or gets redirected. Use when the user gives mid-session direction (redirect, status-check, resumption after silence), when I pause for confirmation that wasn't needed, or when a tool error breaks flow. Skip for normal WS-to-WS transitions that proceed on-plan. The journal is how we diagnose why persistent runs break and tighten the next session's plan.
---

# log-interrupt

## When to invoke

Fire when any of these happens during a session running under a
persistent-run plan (e.g. `docs/session_<N>_plan.md`):

1. User gave mid-workstream direction that wasn't "keep going"
   (redirect, scope change, priority swap).
2. I paused for user confirmation on something the plan already
   authorized.
3. I gave a status update only after the user asked — should have
   volunteered at the last WS boundary.
4. A tool error, stream timeout, or MCP failure broke the flow.
5. I hit a derailment branch in the plan and switched tracks.
6. Session resumed after `/compact`.

Skip: routine tool retries; routine WS-to-WS transitions; user asking
a question that doesn't redirect work.

## Steps

### 1 — classify

Pick one `trigger_class`:

| Class | Meaning |
|---|---|
| USER_REDIRECT | User changed direction / scope / priority |
| IDLE_CHECK_IN | User prompted for status because I hadn't volunteered one |
| UNCONFIRMED_PAUSE | I waited for confirmation the plan had authorized |
| CONTEXT_COMPACT | Context-budget threshold hit |
| STREAM_TIMEOUT | Stream / API / network interruption |
| TOOL_ERROR | Tool returned an error that broke flow |
| BLOCKER_ESCALATION | Hit a derailment branch; had to escalate |
| SCOPE_CHANGE | User expanded or cut the plan's scope |
| RESUME_POST_COMPACT | Session resumed after `/compact` |

### 2 — append row

Append to `docs/persistence_journal.md`. Do NOT overwrite existing
rows. Format:

```
| <YYYY-MM-DDTHH:MM> | s<N> | <trigger_class> | <ws_at_interrupt> | <what_i_was_doing> | <user_verbatim_or_N/A> | <resumption_cost> | <lesson> |
```

- `ws_at_interrupt`: e.g. `M2/WS2` or `between:M1→M2`.
- `what_i_was_doing`: ≤ 10 words, concrete.
- `user_verbatim_or_N/A`: quote verbatim if the trigger was a user
  message; else `N/A`.
- `resumption_cost`: `low` (< 1 min) / `med` (1–5 min) / `high` (> 5 min).
- `lesson`: ≤ 20 words, actionable. Good: "Emit WS-boundary status
  without user ping." Bad: "Be better at persistence."

### 3 — mirror into session state

If `docs/session_<N>_state.md` exists, also append the row to its
`## Live interrupts` section.

### 4 — confirm

```
Logged interrupt (<trigger_class> at <ws>) to persistence_journal.md.
```

Return to the interrupted work.

## Rollup at session close

At WS-final, the session report's `## Persistence retro`:

1. Count rows by `trigger_class` for the current session.
2. Compare to prior 3 sessions (journal tail).
3. Flag classes with count ≥ 3 this session OR ≥ 2 consecutive sessions.
4. Propose one concrete plan/constitution edit per systemic class.

## Hard rules

- Append-only. No editing existing rows.
- No GH issues from this skill (`/log-issue` does that).
- No Agent tool invocations.
- No emojis.
