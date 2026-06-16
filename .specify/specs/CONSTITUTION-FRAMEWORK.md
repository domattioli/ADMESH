# Spec-Level Constitution Framework

**Version**: 1.0.0 | **Effective**: 2026-05-11

## Purpose

Each feature spec (001-008) has its own CONSTITUTION.md that codifies:
- **Domain-specific principles** for that spec's work (e.g., I/O contracts, numerical accuracy, test strategy)
- **Alignment with the project** — how this spec's rules reinforce the main `docs/governance/CONSTITUTION.md`
- **Quality gates** specific to the feature's acceptance criteria

This framework ensures:
1. No principle gaps (every feature knows what "done" means)
2. No silent conflicts (when a spec narrows/extends a project principle, it says so)
3. Clear inheritance chain (spec constitutions cite the project constitution, not re-state it)

## How to Read a Spec Constitution

**Spec 001 CONSTITUTION.md**, for example, has:

- **Preamble**: References the main project constitution and states this spec's scope (Pythonize the MATLAB port + fort.14 I/O)
- **Core Principles**: I–V. These refine the project's Principles I–V for this spec's context.
  - **Principle I (Faithful fort.14 Round-Trip)** — refines project Principle I (Faithful Port) for I/O
  - **Principle II (Numeric Stability for ADCIRC Compatibility)** — refines Principles III (Reference-Test Discipline)
  - Etc.
- **Constraints**: Domain-specific rules (e.g., "fort.14 column alignment", "IBTYPE code coverage")
- **Quality Gates & Workflow**: Testing strategy, acceptance checklist, version bumping rules
- **Governance**: Who can amend this constitution, amendment procedure, compliance review process

## Template Structure

Every spec constitution follows this outline:

```markdown
# Feature NNN Constitution

**Scope**: [2–3 sentence description of the feature]
**Spec Document**: specs/NNN-feature-name/spec.md
**Related Specs**: [cross-references to upstream/downstream specs]

## How This Constitution Relates to the Project Constitution

[Statement of inheritance/alignment.]

## Core Principles

### I. [PRINCIPLE_NAME]
[Principle description + rationale]

### II. [PRINCIPLE_NAME]
...

## Domain-Specific Constraints

[Non-negotiable rules specific to this feature.]

## Quality Gates & Workflow

[Definition of done, acceptance checklist, testing strategy, version bumping rules.]

## Governance

[Amendment procedure, compliance review, contingencies if a principle is violated.]

## Amendments Log

[Dated entries for any updates to this constitution.]

---
**Version**: [MAJOR.MINOR.PATCH] | **Ratified**: [DATE] | **Last Amended**: [DATE]
```

## Cross-Reference Guide

When authoring or updating a spec constitution:

1. **Check the main project CONSTITUTION.md** for Principles I–V. Quote and refine rather than repeat.
2. **Check PROJECT_PLAN.md** for the spec's phase and dependencies.
3. **Check CLAUDE.md** for operational details that might belong in the spec's "Constraints" section.
4. **Reference sibling specs** (upstream dependencies, downstream consumers) in the preamble.
5. **Update the main constitution's Amendments log** if a spec introduces a forward-incompatible rule.

## Compliance & Auditing

**During Phase Implementation**:
- Every PR for this spec MUST verify compliance against its CONSTITUTION's "Quality Gates" checklist.
- Every PR that conflicts with the constitution is rejected with a pointer to the violating principle.

**At Release Time**:
- Version bumps MUST follow the spec constitution's versioning policy.
- The main project constitution's Amendments log MUST be updated to reference any spec-level amendments that affect future work.

## When to Amend

Spec constitutions are amended when:

1. **A constraint turns out to be wrong** → propose a PATCH
2. **A new principle is needed** → propose a MINOR
3. **A principle is made redundant or conflicts** → propose a MAJOR

All amendments go through the same review process as the feature itself.

## Example: Spec 001 (Pythonize + Fort.14 I/O)

**Relates to Project Principles I–IV**:
- Project Principle I (Faithful Port) → Spec Principle I (Faithful fort.14 Round-Trip)
- Project Principle III (Reference-Test Discipline) → Spec Principle II (Numeric Stability)
- Project Principle IV (Stage-by-Stage Bottom-Up) → Spec Principle III (Boundaries Last)

**New Spec Principles**:
- Principle IV: ADCIRC Code Losslessness — any IBTYPE code round-trips without loss

**Constraints**:
- ADCIRC fort.14 v55 format only (no v51, no custom variants)
- 1-based → 0-based index translation confined to `admesh/fort14.py`
- Elevation ↔ Depth conversion documented and reversible

---

See each spec's own CONSTITUTION.md for the filled-in version.
