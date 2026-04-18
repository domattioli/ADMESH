---
name: log-issue
description: Capture a problem discovered during work by creating a GitHub issue on `domattioli/ADMESH` directly via `gh issue create`. Use when the problem is NOT on the current session's critical path — tech debt, related bugs, follow-up ideas, MATLAB-port quirks, lessons needing their own session. Skip for issues on the critical path (just fix them inline). Skip if a near-duplicate already exists on GH. No local markdown draft — issues live on GitHub.
---

# log-issue

## When to invoke

Invoke when all of the following are true:

1. You discovered a real, actionable problem during the current work.
2. Fixing it inline is out-of-scope or would derail the session.
3. No near-duplicate exists in the GH issue tracker.
4. The problem is concrete enough to write acceptance criteria for.

## Pre-flight

- `gh` CLI on PATH; `$GH_TOKEN` or `$GITHUB_TOKEN` set.
- Target repo is always `domattioli/ADMESH`.

## Steps

### 1 — title + slug

Title: one-line imperative, ≤ 80 chars, no emojis, no hedging. Slug
(for branches): lowercase kebab, ≤ 40 chars.

| Bad | Good |
|---|---|
| `Fix it` | `Fix negative area in L-shape distmesh` |
| `Improve performance` | `Vectorize in_polygon boundary loop` |
| `MATLAB stuff` | `Port PTS2PointList edge-spacing logic` |

### 2 — dedupe

```
gh issue list --repo domattioli/ADMESH --state all --search "<title keywords>" --limit 10
```

If a near-duplicate exists, comment on the existing issue — do not
open a new one.

### 3 — draft body (temp file)

```markdown
<!--
type: [bug | port | refactor | docs | infra]
severity: [blocker | high | medium | low]
effort: [S | M | L | XL]
depends_on: [<other GH #numbers>]
discovered_in: session_<N>
-->

## Problem

<one paragraph; what's wrong, why it matters>

## Evidence

<file:line refs, commit SHAs, measured values, MATLAB source pointers.
If you can't point to evidence, the issue is too vague to log.>

## Proposed approach

<1–3 sentences. "unclear — needs investigation" is allowed if genuinely
open, but name what a diagnostic session must produce.>

## Files likely affected

- `<path>`

## Acceptance criteria

- [ ] <observable outcome 1>
- [ ] <observable outcome 2>
- [ ] Tests added/updated
- [ ] `docs/PORTING_NOTES.md` updated if a MATLAB→Python divergence
      emerged
```

### 4 — create

```bash
gh issue create --repo domattioli/ADMESH \
  --title "<title>" \
  --body-file <temp> \
  --label "severity:<sev>" --label "type:<type>" \
  --label "<topical>" [--label "stage:<N>_<name>"]
```

If a label doesn't exist yet, create it with `gh label create <name>
--color <hex>` first. Palette: blocker=b60205, high=d93f0b,
medium=fbca04, low=c2e0c6, type:*=1d76db, stage:*=5319e7,
topical=0e8a16.

### 5 — confirm

```
Logged #N: <title> — <url>
```

Do not spawn agents. Do not modify repo files.

## Severity rubric

- **blocker** — current session cannot proceed
- **high** — next session's primary goal depends on this
- **medium** — quality-of-life; worth a dedicated session
- **low** — nice-to-have; picked up opportunistically

## Type rubric

- **bug** — defect with a known correct outcome
- **port** — MATLAB function not yet ported OR port diverges from MATLAB
- **refactor** — no behavior change; diff easy to review
- **docs** — documentation only
- **infra** — tooling, CI, skills, hooks

## Effort rubric

S (< 1h) · M (1–3h) · L (3–8h) · XL (multi-session)

## Label vocabulary

Topical: `tests`, `numerics`, `performance`, `api`, `geometry`, `numba`,
`matlab-parity`.

Stage (MATLAB source dir): `stage:01_routine`, `stage:03_distance`,
`stage:09_mesh_size`, `stage:10_distmesh`, etc. — one per issue if the
issue targets a specific stage.

Meta: `severity:*`, `type:*`.

## Hard rules

- Do NOT use emojis in titles, bodies, or labels.
- Do NOT invoke any `Agent` tool from this skill — it is pure capture.
- Do NOT log an issue whose body is "TODO investigate". Diagnose first.
- Do include file:line refs (and the MATLAB source file:line when the
  issue is port-related) in Evidence.
