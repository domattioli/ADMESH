# Spec 006 Constitution — Verify h_min/h_max Parameter Usage

**Scope**: Audit how `h_min`, `h_max`, `h0`, `h`, and size-field return values are interpreted across all ADMESH pipeline stages. Document inconsistencies between stages, between Python port and MATLAB source, and between user-facing docs and implementation. File follow-up issues for code changes. No code changes in this spec.  
**Spec Document**: `specs/006-verify-h-parameter-usage/spec.md`  
**Related Specs**: ↑ Spec 002 (size-field stack is the primary consumer of `h` parameters) | → Issue #10 (overshoot investigation may involve h-parameter confusion)

## How This Constitution Relates to the Project Constitution

Directly reinforces Article IV of `docs/governance/CONSTITUTION.md` (Stage-by-Stage Bottom-Up Porting):

- **Article IV** Rule 2 (docstrings cite MATLAB source): this spec audits whether every `h`-related function satisfies this rule.
- **Article IV** Rule 3 (preserve algorithmic comments): the audit checks whether `h`-parameter semantics are consistent across function boundaries.

No code changes → no deviations from any main constitution principle.

## Core Principles

### I. Documentation-Only Investigation

This spec produces an audit report and (if needed) follow-up GitHub issues. It does not produce code commits. If the audit finds a bug, that bug is filed as a new issue (not fixed inline). Updated docstrings are the one permitted exception to the "no code" rule.

**Why**: Mixing investigation artifacts with code changes makes the audit hard to review and attribute.

### II. Consistency Audit

`h` must have one interpretation per call site. The audit determines:
1. Is `h` an edge length, point spacing, or element size?
2. Does each stage's docstring state its interpretation?
3. Does the MATLAB source use the same interpretation?

Ambiguous usages are flagged with "recommended clarification" and a follow-up issue number.

**Why**: If `h_min=0.1` means "minimum edge length" in `distmesh.py` but "minimum point spacing" in `mesh_size.py", the pipeline silently produces meshes that don't match user intent.

## Domain-Specific Constraints

- **No code changes**: Output is a Markdown audit report and optionally updated docstrings. No logic changes.
- **Scope**: All files in `admesh/` that accept or pass `h`-related parameters. Focus on: `distmesh.py`, `mesh_size.py`, `curvature.py`, `medial_axis.py`, `bathymetry.py`, `api.py`.
- **MATLAB comparison**: For each major usage, compare to the corresponding MATLAB function at commit `19b2eb9`.
- **Deliverable format**: Markdown table (file, function, line range, parameter, interpretation, MATLAB comparison, status: consistent/inconsistent/ambiguous).
- **Follow-up issues**: File one GitHub issue per inconsistency that requires code or doc change.

## Quality Gates & Workflow

**Definition of done**:

- [ ] Audit report created at `docs/h-parameter-audit.md`
- [ ] Every `h`-related parameter in `admesh/*.py` cataloged with line-number reference
- [ ] MATLAB source comparison completed for each major usage
- [ ] Inconsistencies and ambiguities flagged with recommended clarification
- [ ] Follow-up issues filed for any required code or doc changes
- [ ] Docstring updates (if any) committed (documentation changes only — no logic)
- [ ] `pytest tests/ -q` green (no test changes expected)

**Versioning policy**: PATCH only — this is documentation. No API or behavior changes.

## Governance

**Amendment procedure**: This spec is self-contained. Amendments only if scope expands (e.g., audit also covers `h` in boundary-seeding path). Scope expansion triggers a MINOR bump.

**Compliance review**: PR review verifies audit report covers all files in scope and all flagged inconsistencies have corresponding follow-up issues.

## Amendments Log

### 2026-05-11 — v1.0.0 — Initial constitution

Synthesized from `spec.md`, `impl_plan.md`. Two principles suffice for an investigation spec. The "no code" constraint is the load-bearing rule.

---
**Version**: 1.0.0 | **Ratified**: 2026-05-11 | **Last Amended**: 2026-05-11
