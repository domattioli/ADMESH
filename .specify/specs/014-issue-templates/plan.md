# Implementation Plan: GitHub Issue Templates for ADMESH

**Spec**: `specs/014-issue-templates/spec.md`
**Resolves**: ADMESH #83
**Branch**: `daily-maintenance` (single rolling branch per CLAUDE.md routine)

## Architecture decisions

### Decision 1 — Mirror DomI YAML schema, not Markdown templates

GitHub supports two issue-template formats:
- Legacy `.md` templates (free-form body)
- YAML "issue forms" (typed fields, required validation, auto-labelling)

Pick YAML. Two reasons:

1. **Required-field enforcement at submission time.** Markdown templates are
   advisory — contributors can delete prompts and submit empty issues. YAML
   forms hard-block with GitHub's UI validation. This is the literal ask in #83.
2. **DomI parity.** DomI already standardized on YAML. Downstream consumers
   (DomI #88 `session-resume`, dispatch heuristics) can reuse the same
   field-parsing logic across all repos.

### Decision 2 — Pre-flight label audit, defer label creation

The spec enumerates the labels each template will try to auto-apply. GitHub
silently drops labels that don't exist on the repo. Plan includes a discovery
step (T-014-1) that lists current labels via `mcp__github__list_issues` and
cross-references against the template-needed set. Gaps go in the
issue-closure comment for the maintainer to `gh label create` in one batch;
no label creation as code in this issue.

Why? Label creation requires admin permission and is properly a one-time
maintenance task; embedding it in a template-port issue couples two unrelated
lifecycle concerns.

### Decision 3 — Four templates, not three or five

| Template | Why include | Why not collapse |
|---|---|---|
| `bug_report.yml` | Distinct lifecycle (regression, reproducer) | Can't merge into feature_request (no reproducer field there). |
| `port_implementation.yml` | Highest-frequency ADMESH-specific shape (issues #65, #73, #78, plus the remaining open stage ports) — saves boilerplate every time | Collapsing into feature_request loses the MATLAB-source / SHA / parity boilerplate. |
| `feature_request.yml` | All non-port, non-bug, non-research enhancement asks | — |
| `research_prompt.yml` | Distinct lifecycle (no acceptance gate; #25/#41/#80/#84 pattern) | Mixing with feature_request makes triage messy because research issues don't close on "implementation done." |

No fifth template (no `domi_sync.yml`) because that flow is bot-driven and
bypasses the chooser; surface it via a contact link instead (spec User Story 5).

### Decision 4 — Acceptance text pre-population for port issues

The `port_implementation.yml` form pre-fills the Acceptance textarea with the
Constitution Principle I boilerplate (parity at `atol=1e-10` against a fixture
exported by `scripts/export_matlab_fixtures.m`). Saves the operator the
copy-paste step. Contributors can edit before submission.

### Decision 5 — No PR template in this issue

The original #83 body says "the DomI repo forces templates for new issues" —
specifically issues. PR templates are a related but separate concern. Add a
follow-up issue if the maintainer wants PR-template parity too.

### Decision 6 — Restrict templates to labels that already exist on the repo

Pre-flight survey of OPEN+CLOSED issues showed which labels are actually
present. Templates declare only those. Labels desired-but-missing
(`status:ready`, `scope:io`, `scope:numerics`, `scope:api`, `scope:infra`,
`scope:perf`) are listed in the closure comment, not baked into the
templates. This avoids silent label-drop failures and gives the maintainer
a single batch to act on.

## Files

```
.github/ISSUE_TEMPLATE/
├── config.yml                 # NEW
├── bug_report.yml             # NEW
├── port_implementation.yml    # NEW
├── feature_request.yml        # NEW
└── research_prompt.yml        # NEW

specs/014-issue-templates/
├── spec.md                    # NEW
├── plan.md                    # NEW (this file)
└── tasks.md                   # NEW
```

## Label inventory (post-audit)

**Present on repo** (used by current templates):
- `type:bug`, `type:enhancement`, `type:port`, `type:research`, `type:feat`,
  `type:investigation`, `type:infra`
- `severity:low`, `severity:medium`, `severity:high`, `severity:critical`
- `priority:low`, `priority:medium`, `priority:high`, `priority:critical`
- `scope:tests`, `scope:docs`
- `numerics`, `roadmap`, `io`, `performance`, `integration`, `gpu`,
  `claude-routine-sessions`, `domi-sync`, `documentation`, `enhancement`
  (legacy), `bug` (legacy), `pypi`, `post-v1`, `post-0.1.0`, `chore`,
  `duplicate`, `question`

**Desired but absent** (surfaced in closure comment):
- `status:ready` (DomI pattern; not yet on ADMESH)
- `scope:io`, `scope:numerics`, `scope:api`, `scope:infra`, `scope:perf`

## Cross-repo integration

Downstream consumers that will benefit:

- **DomI #88 (`session-resume`)**: heuristic for "what's open" reads issue
  labels by prefix (`type:*`, `severity:*`). Templates make these consistent
  across new ADMESH issues, improving resume accuracy.
- **DomI #76 (benchmark-tracker)**: the `type:port` discriminator helps
  downstream issue-dispatching routines skip ports faster.

No reverse coupling — DomI doesn't read ADMESH templates.

## Risks (plan-specific additions)

| Risk | Mitigation |
|---|---|
| YAML syntax error in any template silently breaks the chooser | Each template file gets a yamllint-style mental review; trial submission can confirm rendering on the GitHub UI post-merge. |
| Re-ordered fields after first commit break user habit | Stable field IDs (`id: severity`, `id: module`) — automation reading the form can rely on field IDs even if order or labels change. |

## Phase ordering

1. **T-014-1**: Audit current labels against required set. ✓
2. **T-014-2**: Write `config.yml`. ✓
3. **T-014-3..6**: Write four template YAMLs. ✓
4. **T-014-7**: Commit on `daily-maintenance` (via MCP API push, container's
   local git signing failed). ✓
5. **T-014-8**: Close issue with a comment listing label gaps for maintainer
   follow-up.

No tests (no executable code; YAML correctness is verified by the GitHub UI
rendering on next issue creation — the spec acceptance criteria capture
that gate).
