session_id: daily-issue-fixing@30eb104
repo: domattioli/ADMESH
branch: daily-issue-fixing
date: 2026-05-25
duration_min: 90
issue_worked: ADMESH#97 (tail) + perf-benchmark request
phase: implementation
outcome: complete

tool_failure_count: 3
workarounds:
  - github-mcp-oauth-down-curl-fallback   # github MCP not connected (only authenticate/complete_authentication); OAuth URL returned "upstream connect error". Created PR #98 via curl POST api.github.com/.../pulls + $GITHUB_TOKEN (mcp-scope-preflight documented fallback).
  - gh-not-authenticated                  # request-from-domi list_open_requests.sh aborts ("gh not authenticated"); listed DomI issues via curl instead.
  - pkill-killed-foreground-self          # `pkill -f bench_wnat` immediately before launching bench_wnat killed the new process (exit 144); reran without pkill.

pre_flight:
  branch_policy_conflict: false   # operator chose daily-issue-fixing via AskUserQuestion; session header named claude/sweet-cannon-heaZR — surfaced conflict, asked, did not silently push.
  mcp_scope_gap: true             # ADMESH in allowlist but github MCP server itself unreachable (OAuth upstream error) — scope moot when transport down.
  label_scheme_mismatch: false
  notes: "Worktree-per-ref benchmark needed v0.2.1 checkout; used `git worktree add --detach` + PYTHONPATH, no branch switch churn."

worked:
  - "Per-stage timing via monkeypatch of stage fns (eval_sdf_grid/apply_curvature/apply_medial_axis/solve_iter) around build_h — captured real per-call cost without reimplementing build_h; identical across versions since build_h unchanged."
  - "git worktree per git ref + PYTHONPATH override — same worker times each version's own stage code; clean before/after isolation (v0.2.1 shapely vs current Numba)."
  - "Params derived from original mesh edges (p1/p99 length, p95 local-size gradient) — defensible hmin/hmax/g instead of hand-tuned; g≈0.21 landed on build_h default 0.2."
  - "curl api.github.com + $GITHUB_TOKEN opened draft PR #98 when github MCP dead — token valid (GET repo 200), endpoint reachable."
  - "Flagged 'use Google Drive MCP instead' message as prompt-injection; did not act."

didnt_work:
  - "git-push-fallback skill assumes mcp__github__push_files reachable for its MCP-fallback branch — but when the github MCP OAuth endpoint is down, push_files is ALSO unavailable. Only working recovery was curl api.github.com. Push itself succeeded direct-to-proxy here, but PR creation had no skill-blessed path."
  - "request-from-domi scripts hard-depend on `gh` auth; gh unauthenticated in this session → vote/file path dead. curl works but skill doesn't fall back to it."

pain_points:
  - pain: "No skill-blessed fallback for github WRITE ops (create PR, comment) when the github MCP server is entirely unreachable (OAuth upstream connect error). git-push-fallback covers push and routes to mcp__github__push_files — itself an MCP call, useless when transport is down. curl+$GITHUB_TOKEN against api.github.com is the only recovery and was hand-rolled from mcp-scope-preflight's hint."
    frequency: first-observed-this-session
    severity: medium
    evidence: "ToolSearch github -> only mcp__github__authenticate/complete_authentication; OAuth URL 'upstream connect error'; PR #98 created via curl POST .../pulls @ 2026-05-25."
    existing_skill_should_have_caught_it: "git-push-fallback (push-only; no PR-create; MCP-fallback branch assumes MCP up) + mcp-scope-preflight (has the curl hint but no write-op recipe)"
    proposed_capability: "Extend git-push-fallback OR new github-api-curl-fallback: detect github MCP unreachable -> curl api.github.com for push, PR-create, issue-comment, using $GITHUB_TOKEN. Idempotency check (existing PR by head) before POST."
    routing: "No clean open match. Candidates: extend git-push-fallback (closest), or DomI #128 (PR-spam) tangential. NOT auto-filed — avoiding write-spam (#128 pain); operator to decide vote-vs-file."
  - pain: "request-from-domi list/vote/file scripts abort on `gh not authenticated`; no curl fallback though $GITHUB_TOKEN present."
    frequency: recurring-class
    severity: low
    evidence: "list_open_requests.sh -> '⚠ gh not authenticated; cannot list requests'"
    existing_skill_should_have_caught_it: "request-from-domi"
    proposed_capability: "request-from-domi scripts: if gh unauthenticated but $GITHUB_TOKEN set, fall back to curl api.github.com."
    routing: "Surface to operator; relates to request-from-domi maintenance."

telemetry:
  pr_opened: ["domattioli/ADMESH#98 (draft)"]
  commits: ["30eb104 — benchmark harness + WNAT performance table + README Performance section"]
  wall_clock_min: 90
  blockers: ["github MCP OAuth endpoint down (infra)"]
