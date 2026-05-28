# Feature Specification: GitHub Issue Templates for ADMESH

**Feature Branch**: `daily-maintenance` (no per-spec branch; per CLAUDE.md routine)
**Created**: 2026-05-20
**Status**: Draft
**Resolves**: [#83](https://github.com/domattioli/ADMESH/issues/83)
**Input**: User description: "the DomI repo forces templates for new issues. so should the downstream repos."

## Problem

`domattioli/ADMESH` accepts free-form GitHub issues with no template enforcement. The
upstream governance repo `domattioli/DomI` already forces a template-driven submission
flow (`.github/ISSUE_TEMPLATE/*.yml` plus `blank_issues_enabled: false` in
`config.yml`). ADMESH is a downstream consumer of DomI's governance and currently
diverges from that contract — anyone can file unstructured issues with no severity,
no scope, no acceptance criteria.

That divergence has concrete downstream cost:

- Routine sessions (this one, plus #76, #77, the issue triage waves) re-read every
  issue body to recover labels and severity the operator already had in mind.
- Cross-repo dispatch (DomI #88 `session-resume`, #84 `deploy-state-check`) needs
  predictable issue-frontmatter to match its heuristics.
- Spec 010 (`registry-rewrite-for-admesh-domains-0.3`) and TEST-AUDIT.md backlog
  items rely on `scope:*` / `severity:*` / `type:*` labels that are inconsistently
  applied today.

## Goals

1. **Mandatory templates** — `blank_issues_enabled: false`. The "New issue" button
   leads to a template chooser, never a blank body.
2. **ADMESH-shaped fields** — templates are tuned to the kinds of issues this repo
   actually receives (port issues, numerics regressions, spec proposals, perf
   investigations, research prompts, infrastructure asks), not DomI's
   skills/plugins/automation framing.
3. **Label parity** — each template auto-applies the same `type:*`,
   `severity:*`, `scope:*`, and `priority:*` labels the maintainer already
   uses by hand. No new label taxonomy.
4. **Authoring frictionless** — keep each template under ~10 fields. Reuse
   DomI's YAML schema conventions (`type: input | textarea | dropdown | markdown`)
   so contributors who file in DomI feel at home here.

## Non-goals

- Pull-request templates (`PULL_REQUEST_TEMPLATE.md`) — separate concern; defer
  to a follow-up issue.
- Issue forms for closed bot-driven channels (the `domi-sync` issues opened by
  the upstream `notify-downstream` workflow); those have a fixed body and don't
  need a UI template.
- A label-creation workflow — the templates assume the labels already exist
  (they do; this issue audits and pins that assumption).

## User Scenarios

### User Story 1 — File a bug against a port-stage module (Priority: P1)

A user (or a future automated agent like CHILmesh's daily-maintenance routine)
hits a numerical-identity regression in `admesh/_stages/curvature.py` against the
MATLAB reference. They click "New issue" → "Bug Report" → fill in:
- Affected module / stage (input)
- Observed vs. expected behavior (textarea x2)
- Reproduction (textarea: `pytest` command + minimum fixture)
- Severity dropdown (low / medium / high / critical)
- Constitution principle violated? (dropdown — I/II/III/IV/V/none)

**Why this priority**: the headline use case. ADMESH's core invariant is
numerical identity to a MATLAB reference; structured bug reports must capture
that delta.

**Independent Test**: file a dummy bug issue using the new template on a draft
branch; confirm the labels `type:bug` and severity apply and that all required
fields block submission when blank.

### User Story 2 — Propose a faithful-port spec (Priority: P2)

A contributor wants to file an issue for porting one of the remaining MATLAB
stage modules to NumPy. They pick "Port / Faithful Re-implementation" and fill
MATLAB source path, QuADMesh-MATLAB SHA, target Python module, acceptance
(pre-populated with Constitution Principle I parity boilerplate), severity, and
out-of-scope notes.

**Why this priority**: ports are the dominant template for issues like #78,
#73, #65, and the four open faithful-port stage modules. Pre-populated
acceptance text saves operator from copy-pasting the Constitution Principle I
boilerplate each time.

### User Story 3 — Propose a feature / enhancement (Priority: P2)

A user wants to file a non-port enhancement. They pick "Feature Request" and
fill problem, proposed solution, scope dropdown (ADMESH-flavored:
`io`, `numerics`, `scope:tests`, `scope:docs`, `performance`, `integration`,
`roadmap`), severity, priority, acceptance.

### User Story 4 — Capture a research / exploration prompt (Priority: P3)

Issues like #25 (DL for repair), #41 (dimensional remapping), #80, #84 are
exploratory. The "Research / Exploration" template captures research question,
why now / why not yet, acceptance criteria for AI agent (pre-filled with the
#25-style comparative-analysis boilerplate), adjacent issues.

### User Story 5 — DomI-sync notification issue (Priority: P3, contact link only)

When DomI's upstream `notify-downstream` workflow opens a sync issue (like
#79), it bypasses the template UI entirely (API-driven POST with a fixed
body). The chooser hides this flow via a contact link explaining that
operators should not file these by hand.

## Files to Create

```
.github/ISSUE_TEMPLATE/
├── config.yml             # disable blank issues, declare contact links
├── bug_report.yml         # P1
├── port_implementation.yml # P2
├── feature_request.yml    # P2
└── research_prompt.yml    # P3
```

## Approach

Mirror DomI's `.github/ISSUE_TEMPLATE/*.yml` shape and naming conventions
(YAML schema, `type: input | textarea | dropdown | markdown`, the
`labels: [...]` frontmatter). Specialize:

- **Field set per template** — drop DomI's skill-marketplace voting field
  from `feature_request.yml`. Add MATLAB-source-path + QuADMesh-SHA fields
  to the new `port_implementation.yml`. Pre-fill the parity-acceptance
  textarea with the Constitution Principle I boilerplate.
- **Label palette** — restrict to labels already present on the repo
  (audited via existing-issues survey before commit). Surface missing
  labels in the issue-closure comment for the maintainer to
  `gh label create` in one batch.
- **Validation** — require the minimum spine (description + severity +
  one identifier field) and leave everything else optional.
- **Blank issues** — `blank_issues_enabled: false`. Operators with elevated
  permission can still bypass via the API or the `gh` CLI for emergency
  filing.

## Risks

| Risk | Mitigation |
|---|---|
| Existing issue labels don't include every label the template tries to apply → GitHub silently drops them | Pre-flight audit; templates only declare labels that already exist; remaining gaps surfaced in closure comment. |
| Bot-driven `domi-sync` issues (e.g. #79) lose their flow | They use the GitHub API directly, not the template UI — unaffected. The chooser hides them via the contact-links pattern. |
| Contributors used to free-form bodies push back | Acceptable; this is the explicit ask in #83 (`priority:critical`). |

## Token Budget

**Small.** Four YAML files (~50 lines each) plus one `config.yml` (~12 lines)
plus this spec + plan + tasks. Implementation is mechanical translation of
the DomI templates with ADMESH-flavored field sets; no algorithmic work,
no test code, no MATLAB porting.

This issue is small enough to ship implementation in the same session as
the spec, per the CLAUDE.md routine's STEP 6 implementation branch.

## Acceptance Criteria

- [x] `.github/ISSUE_TEMPLATE/config.yml` exists with
      `blank_issues_enabled: false` and a contact-links section explaining
      the DomI-sync auto-flow.
- [x] `.github/ISSUE_TEMPLATE/bug_report.yml` exists, requires module +
      severity, auto-applies `type:bug`.
- [x] `.github/ISSUE_TEMPLATE/port_implementation.yml` exists, pre-fills the
      Constitution Principle I acceptance boilerplate, auto-applies
      `type:port` and `numerics`.
- [x] `.github/ISSUE_TEMPLATE/feature_request.yml` exists with ADMESH-flavored
      scope dropdown.
- [x] `.github/ISSUE_TEMPLATE/research_prompt.yml` exists, auto-applies
      `type:research`, `roadmap`, `severity:low`.
- [ ] The "New issue" UI on GitHub shows exactly these four templates plus
      the contact-links section, with no "Open a blank issue" option
      (verified post-merge).
- [x] Each template's auto-applied labels match labels that already exist
      on the repo (no silent-drop failures); gaps surfaced in closure comment.
- [x] Spec, plan, tasks land on `daily-maintenance`; commit references #83.

## Out of Scope

- Pull-request templates (`PULL_REQUEST_TEMPLATE.md`).
- Creating new labels (closure comment surfaces gaps as maintainer action).
- Auto-triage automation.

## Related

- DomI `.github/ISSUE_TEMPLATE/` (the canonical reference).
- ADMESH #83 (this issue).
- DomI #76, #88 (downstream session-resume / dispatch consumers).
- ADMESH #79 (the DomI-sync issue type that bypasses templates).
