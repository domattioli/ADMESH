# Tasks: GitHub Issue Templates for ADMESH

**Spec**: `specs/014-issue-templates/spec.md`
**Plan**: `specs/014-issue-templates/plan.md`
**Resolves**: #83

## Atomic tasks

### T-014-1 — Audit existing labels against template needs ✓

**Tied to**: Spec § Acceptance Criteria → "Each template's auto-applied
labels match labels that already exist on the repo".

**Action**: enumerate distinct labels actually applied to existing issues
via `mcp__github__list_issues(state=OPEN|CLOSED)`. Build a delta against
the required set in plan.md § "Label inventory". Capture missing labels
for the issue-closure punch list.

**Dependency**: none.

**Verification**: see plan.md § "Label inventory (post-audit)".

### T-014-2 — `.github/ISSUE_TEMPLATE/config.yml` ✓

**Tied to**: Spec User Story 5 + § Acceptance Criteria → blank issues
disabled, contact links explain DomI-sync flow.

**Auto-labels**: n/a (config file).

**Dependency**: T-014-1.

**Verification**: GitHub UI shows the chooser with these links and no
"Open a blank issue" option after merge (post-merge check).

### T-014-3 — `.github/ISSUE_TEMPLATE/bug_report.yml` ✓

**Tied to**: Spec User Story 1.

**Required fields**: module/stage (input), what happened (textarea),
expected (textarea), reproduction (textarea), severity dropdown,
constitution-principle dropdown.

**Auto-labels**: `type:bug`.

**Dependency**: T-014-2.

### T-014-4 — `.github/ISSUE_TEMPLATE/port_implementation.yml` ✓

**Tied to**: Spec User Story 2.

**Required fields**: MATLAB source path (input), QuADMesh-MATLAB SHA
(input), target Python module path (input), acceptance textarea
(pre-filled with Constitution Principle I parity boilerplate), severity
dropdown, out-of-scope textarea (optional).

**Auto-labels**: `type:port`, `numerics`.

**Dependency**: T-014-2.

### T-014-5 — `.github/ISSUE_TEMPLATE/feature_request.yml` ✓

**Tied to**: Spec User Story 3.

**Required fields**: problem (textarea), proposed solution (textarea),
scope dropdown (ADMESH-flavored), severity dropdown, priority dropdown,
acceptance textarea (optional), alternatives textarea (optional).

**Auto-labels**: `type:enhancement`.

**Dependency**: T-014-2.

### T-014-6 — `.github/ISSUE_TEMPLATE/research_prompt.yml` ✓

**Tied to**: Spec User Story 4.

**Required fields**: research question (textarea), why now / why not yet
(textarea), acceptance criteria for AI agent (textarea, pre-filled with
the #25-style boilerplate), adjacent issues (input, optional).

**Auto-labels**: `type:research`, `roadmap`, `severity:low`.

**Dependency**: T-014-2.

### T-014-7 — Commit on `daily-issue-fixing` ✓

**Tied to**: CLAUDE.md routine → STEP 7 (Validation & Commit).

**Result**: container's local git commit signing failed (`signing server
returned status 400`); fell back to MCP `push_files` API call which uses
GitHub's verified signature flow. Templates committed in
`afa69e978c96e0288a163a568022ba29badf5c27`; spec/plan/tasks
follow-on in subsequent `create_or_update_file` commits.

**Verification**: branch HEAD on `daily-issue-fixing` shows the
template-bundle commit referencing #83.

### T-014-8 — Close issue with label-gap punch list

**Tied to**: CLAUDE.md routine → STEP 8 (Documentation & Closure).

**Action**: `mcp__github__add_issue_comment` to #83 summarizing:
- Spec / plan / tasks landed.
- Templates implemented + commit SHAs.
- Missing labels surfaced by T-014-1 (so the maintainer can
  `gh label create` in one batch).
- Suggested follow-up: PR template (out of scope for #83).

Then `mcp__github__issue_write(method='update', state='closed',
state_reason='completed')`.

**Dependency**: T-014-7.

## Dependency graph

```
T-014-1 ──> T-014-2 ──> T-014-3 ─┐
                       ├─ T-014-4 ─┤
                       ├─ T-014-5 ─┼──> T-014-7 ──> T-014-8
                       └─ T-014-6 ─┘
```

T-014-3 through T-014-6 are independent of each other once T-014-2 is in.

## Cross-repo integration points

- **DomI**: none required for landing. Downstream future skills
  (#88 session-resume) will benefit but don't depend on this issue.
- **ADMESH-Domains, CHILmesh**: same template pattern is reusable;
  templates here can be copy-pasted to those repos with minimal edits
  (drop the `port_implementation.yml` if not applicable). Out of scope
  for #83.

## Out of scope for #83

- Creating any missing labels (`gh label create ...`) — surfaced in
  closure comment, maintainer action.
- PR template (`PULL_REQUEST_TEMPLATE.md`) — separate concern.
- Auto-triage workflows.
- Documentation in `docs/CONTRIBUTING.md`.
