# DomI Project Constitution

**Version**: 1.0.0  
**Ratification Date**: 2026-05-11  
**Last Amended**: 2026-05-11  
**Status**: Ratified

---

## Purpose

DomI is the upstream **skills marketplace and governance authority** for all downstream Claude Code repos. It does not ship application code. Every artifact here is a skill, plugin, script, or governance document used by downstream consumer repos.

---

## Principle I — Skills Are the Product

Every deliverable in `skills/` and `plugins/` MUST be immediately usable by a downstream repo via install or plugin command. Skills MUST have valid frontmatter (`name:`, `description:`). A skill without a working `SKILL.md` does not ship.

**Rationale**: Downstream repos depend on DomI skills as infrastructure. Broken or incomplete skills propagate failures to all consumers.

---

## Principle II — Correctness Is Non-Negotiable

No commit MAY knowingly break an existing skill or violate MANIFEST.md sync. `scripts/instructions_on_start.sh` MUST exit zero before any PR merges. CI hard-blocks enforce this — bypasses are forbidden.

**Rationale**: This repo is an upstream dependency. Breakage here cascades silently to 7+ consumer repos.

---

## Principle III — Governance by Consensus, Not Velocity

Skill requests MUST accumulate the composite threshold (5+ unique-repo votes with metadata + Opus eval APPROVE per #57) before building. The `/skill-issue-closure` framework governs all `request: skill` issue closures (the vote gate keys on `request: skill`, not the filesystem-scope label — ADR-0001). Auto-closes are only permitted for DUPLICATE or STALE decisions; REDUNDANT and READY_TO_BUILD require human review.

**Rationale**: Building premature or duplicate skills wastes effort and fragments the skill namespace. Voting ensures real cross-repo demand.

---

## Principle IV — Downstream-Pulled, Never Upstream-Pushed

DomI MUST NOT edit downstream repo files directly. The sync contract is pull-only: downstream repos run `sync-from-domi` when notified of upstream changes via `chore: sync DomI@<sha>` issues. DomI's `notify-downstream.yml` opens issues; downstream Claude closes them.

**Rationale**: Pushing to downstream repos violates their autonomy and risks overwriting in-progress work.

---

## Principle V — Branch Discipline Prevents Sprawl

The working branch is `development` (per DomI `branching.md`; supersedes the deprecated `daily-maintenance` as of 2026-06-02, #196). No `claude/*` branches MUST persist beyond session start. The startup script enforces this with a HARD STOP. PRs merge to `main` only via deliberate `<author>/<short-kebab>` branches. Creating more than 5 branches per session is forbidden.

**Rationale**: Branch sprawl (issue #13) caused repeated cleanup overhead and orphaned work across sessions.

---

## Principle VI — Commits Are Atomic and Typed

Every commit MUST follow `<type>: <imperative summary>` where type ∈ `{fix, feat, docs, chore, refactor, test}`. WIP commits are blocked on shared branches via `.githooks/pre-commit`. Max 20 commits per PR.

**Rationale**: Clean commit history enables downstream consumers to trace what changed and why, and CI can enforce message format.

---

## Governance

### Amendment Procedure

1. File a GitHub issue describing the proposed change and rationale.
2. Discuss in issue comments; the change requires no formal vote for PATCH-level amendments.
3. MINOR and MAJOR amendments require the repo owner's explicit approval before merging.
4. Update `Last Amended` date and bump `Version` per semantic versioning.
5. Run `/speckit-constitution` to propagate changes to dependent templates.

### Versioning Policy

- **MAJOR**: Principle removed, renamed, or redefined incompatibly.
- **MINOR**: New principle added or existing principle materially expanded.
- **PATCH**: Clarifications, wording, formatting, non-semantic refinements.

### Compliance Review

The startup script (`scripts/instructions_on_start.sh`) enforces Principles II, V, and VI on every session start. CI workflows enforce Principles I and II on every PR. Principles III and IV are enforced by the `/skill-issue-closure` framework and the downstream sync contract respectively.

---

## Relationship to CLAUDE.md

This constitution defines the *why* behind DomI's governance rules. `CLAUDE.md` defines the *how* — specific commands, file paths, and operational procedures. When the two conflict, CLAUDE.md takes precedence for operational decisions; the constitution takes precedence for governance decisions (e.g., whether to build a skill, whether to auto-close an issue).
