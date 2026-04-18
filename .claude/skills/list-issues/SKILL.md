---
name: list-issues
description: Summarize the ADMESH issue queue by querying GitHub via `gh issue list`. Prints the queue sorted by severity with parsed metadata, dependencies, and ready-to-pick counts. Read-only — never modifies issues or files. Use when the user asks "what's open?" / "what's in the backlog?" / before starting a new session.
---

# list-issues

## When to invoke

- User asks "what issues are open / queued / pending / ready?"
- Inside a session-start ritual to orient on carried-over work.
- As a sanity check before picking up a new workstream.

Do NOT invoke as a side-effect of other skills.

## Pre-flight

- `gh` on PATH; `$GH_TOKEN`/`$GITHUB_TOKEN` set.
- Target: `domattioli/ADMESH`.

## Steps

### 1 — fetch

```bash
gh issue list --repo domattioli/ADMESH \
  --state open --limit 100 \
  --json number,title,labels,body,assignees,updatedAt,url
```

### 2 — parse metadata

Every issue created via `/log-issue` has a top-of-body HTML comment:

```
<!--
type: port
severity: medium
effort: M
depends_on: [#N]
discovered_in: session_2
-->
```

Extract `type`, `severity`, `effort`, `depends_on`. If missing, fall
back to label-derived metadata (`severity:<sev>`, `type:<type>`); flag
in `## Anomalies`.

### 3 — print queue (sorted by severity → updatedAt desc)

```
OPEN QUEUE (domattioli/ADMESH)

  sev   type      eff  locks         #   title
  ----  --------  ---  ------------  --  --------------------------------
  high  port      L    —             12  Port full SignedDistanceFunction
  med   bug       S    —             11  distmesh2d seed ignored on retry
  low   docs      S    in-progress    9  Document mesh-size hmax behavior
```

Locks column: `in-progress` (label `claude:in-progress`),
`needs-review`, `blocked`, or `—`.

### 4 — dependencies

```
DEPENDENCIES

  #11  distmesh2d seed...        → (root)
  #12  Port full SignedDistance  → (root)
   #9  Document mesh-size hmax   → depends on: #12
```

### 5 — ready-to-pick

Roots (no open blocking deps), not in-progress, not needs-review,
not blocked. Sorted by severity then effort ascending.

```
READY TO PICK

  #11  (bug, S, medium)
  #12  (port, L, high)
```

### 6 — counts

```
COUNTS
  Open:          3
  In-progress:   1
  Needs review:  0
  Blocked:       0
  Ready:         2
```

### 7 — anomalies

Warn on: missing metadata comment; stuck `claude:in-progress` > 24h;
unresolved `depends_on` (referenced issue non-existent or closed); no
`type:`/`severity:` label.

## Hard rules

- Read-only. Never writes issues or files.
- No Agent invocations.
- No emojis.
- Sort by severity first, recency second. Never by issue number.
