---
session_id: daily-issue-fixing@c877f07
repo: domattioli/ADMESH
branch: daily-issue-fixing
date: 2026-05-22
duration_min: ~20
issue_worked: ADMESH#85
phase: planning
outcome: complete

tool_failure_count: 3
workarounds:
  - WebFetch-404-substitute        # raw.githubusercontent.com/domattioli/DomI/main/claude_routine_instructions.md returned 404 (DomI is private); fell back to mcp__github__get_file_contents on domattioli/domi
  - plugin-install-network-failed  # bootstrap step 5 reported claude plugin marketplace add / sync-from-domi / introspect / request-from-domi all failed; routine continued because instructions_on_start.sh exits 0 with warnings
  - pytest-not-on-PATH             # python -m pytest reported "No module named pytest"; doc-only diff so validation skipped per profile "if applicable"

pre_flight:
  branch_policy_conflict: true     # operator prompt said "daily-issues-fixing" (extra s); canonical per routine = "daily-issue-fixing"; followed canonical, flagged the discrepancy in the operator-visible status line
  mcp_scope_gap: false             # ADMESH in MCP allowlist
  label_scheme_mismatch: false
  notes: "Hour 15 UTC → ADMESH per operator schedule (3/9/15/21). Routine profile = planning-only / spec_kit_required=true / code_shipping_allowed=false."

worked:
  - "Sourced routine via mcp__github__get_file_contents after WebFetch 404 (DomI is private). Same recovery as session ca1fcb4 — pattern is now reliable."
  - "Reused spec 015 / 016 scaffold for spec 018 — section order, header style, cross-link conventions stay consistent. Voice + structure drift = zero."
  - "ADR-001 already settled the cross-repo seam. Investigation only had to test 'can ADMESH cheaply prevent at source?' against the seam, not relitigate it. Saved roughly half the analysis tokens."
  - "Predicate-first approach for #85: formalize P(T1,T2), then prove flip-invariance, then enumerate mitigations. The flip-invariance proof short-circuited candidates 2/4 — without it the rubric would have looked ambiguous."
  - "Cross-spec note for spec 016 (one-line PORTING_NOTES.md draft) means spec 016's implementer can ship the note without re-reading spec 018."

didnt_work:
  - "PR #82 already open on daily-issue-fixing → main with a GIF-fix title; spec 018 commits stacked on top. DomI #107 says split into N PRs (preferred) for unrelated work. Could not split — Constitution Article VI restricts branch creation to /speckit-specify and operator forbade new branches. Settled for updating PR #82 body with a 'Subsequent commits' section enumerating spec 018. Reviewer still sees both in git log; title is now stale relative to the larger payload."
  - "Bootstrap step 5 (sync-from-domi check) failed silently — instructions_on_start.sh exits 0 with WARN, but the DomI plugins (sync-from-domi, introspect, request-from-domi) are not registered for the session. introspect skill therefore could not run via /introspect; this file was authored directly instead of via the skill's templates."

pain_points:
  - pain: "Routine §3.10 PR title rule conflicts with operator's 'work only on daily-issue-fixing' rule when an upstream PR already exists with an unrelated title. Spec 018 work landed under PR #82 (GIF fix), which now has a misleading title. Splitting requires a new branch, which the operator forbids."
    frequency: recurring (DomI#107 anticipates it; this is the second case)
    severity: medium
    evidence: "PR #82 title 'fix(docs): land missing papers/annulus_meshing.gif'; my commits add spec 018 doc-only investigation totally unrelated to the README hero."
    existing_skill_should_have_caught_it: "branch-policy-enforcer / pr-title-discipline (DomI marketplace, not installed this session)"
    missing_skill_would_have_prevented_it: "rolling-pr-retitle-coordinator (when stacking unrelated work on an open PR, propose a new combined title that enumerates substantive changes, or open a sibling PR with a derivative-of-daily-issue-fixing branch under speckit naming rules)"
    domi_issue: "DomI#107 (existing — the rule, not the recovery)"
    saved_time_estimate_min: 3

  - pain: "Operator branch name 'daily-issues-fixing' (with extra s) conflicts with canonical 'daily-issue-fixing'. branch_guard.sh would block the typo'd form. Routine canonical wins per 'execute the routine' clause; flagged in status. The peril clause makes the conflict feel scarier than the actual resolution warranted."
    frequency: once-in-this-session
    severity: low
    evidence: "operator prompt: 'Work *ONLY* on the daily-issues-fixing branch. disobey this at your own peril.' Repo only has daily-issue-fixing."
    existing_skill_should_have_caught_it: "enforce-branch-policy v1.1 (3-layer L1/L2/L3 reconciliation per ca1fcb4 corpus); not installed this session"
    missing_skill_would_have_prevented_it: "operator-typo-normalizer (compare operator branch-name input against repo's actual branch list + canonical routine name; auto-resolve to canonical with a one-line operator-visible note)"
    domi_issue: null
    saved_time_estimate_min: 2

  - pain: "Bootstrap step 5 fails-but-continues with warnings (good behavior — infra should not block work). But the WARN means no DomI skills are registered for the session. /introspect, /caveman, /sync — none of these route through the skill harness. Compounds across sessions because each fresh container re-fails the install."
    frequency: recurring-across-sessions
    severity: medium
    evidence: "bootstrap stdout '✗ DomI marketplace add failed (network?)' followed by '✗ sync-from-domi@DomI install failed' x3; ADMESH:scripts/instructions_on_start.sh @ 2026-05-22T15:03Z (same class as session ca1fcb4)."
    existing_skill_should_have_caught_it: "sync-from-domi v1.1 covers pin-check fallback; does NOT cover marketplace-add install fallback"
    missing_skill_would_have_prevented_it: "plugin-install-with-vendored-fallback (per session ca1fcb4 corpus — second sighting strengthens the case)"
    domi_issue: null
    saved_time_estimate_min: 4

  - pain: "pytest not on PATH; profile validation_cmds includes 'pytest tests/ (if applicable)'. Doc-only diff means 'not applicable' is the correct call, but the gate is implicit — a future agent doing code work in ADMESH would hit a hard-stop on the missing binary per universal §3 step 7 ('no auto-install of missing binaries')."
    frequency: recurring-across-sessions
    severity: medium
    evidence: "/usr/local/bin/python: No module named pytest @ 2026-05-22T15:09Z"
    existing_skill_should_have_caught_it: "none in current DomI catalog"
    missing_skill_would_have_prevented_it: "validation-cmd-prereq-check (run-once at bootstrap step 7: enumerate validation_cmds, check binaries are on PATH, hard-stop EARLY rather than mid-work)"
    domi_issue: null
    saved_time_estimate_min: 3

introspect_followups:
  # Skill issue voting on DomI happens via mcp__github__add_issue_comment.
  # Votes constrained by trusted-author rule — only the operator (@domattioli)
  # acts on them. This corpus is the evidence base.
  - action: vote-existing-issue
    target: DomI / plugin-install-with-vendored-fallback (search needed)
    rationale: "Second sighting of marketplace-add install failure within 12h. ca1fcb4 corpus already filed evidence; this session is the +1."
  - action: file-new-issue
    target: DomI / rolling-pr-retitle-coordinator
    rationale: "DomI#107 names the rule (PR title MUST describe substantive change) but provides no recovery skill when an unrelated PR is already open. Filing as scope:skill / request-skill / type:feat."
  - action: file-new-issue-or-vote
    target: DomI / validation-cmd-prereq-check
    rationale: "No existing skill enforces bootstrap step 7 'all validation_cmds binaries on PATH' uniformly. A future code-shipping session in ADMESH would hard-stop mid-work on missing pytest."
