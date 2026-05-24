# Spec 015 — Tasks (atomic decomposition)

Per plan.md phases. Each task ties to one or more acceptance criteria (AC1–AC7).

## Phase A — Inventory

- [ ] **T-015-A1.** Walk `admesh/*.py`. For each public module, capture path + one-line purpose + primary public symbols + initial classification (gen/cons/bdry). Write to `inventory.md §A1`. (AC1)
- [ ] **T-015-A2.** Read CHILmesh public surface from README + PyPI. Write same table to `inventory.md §A2` with `inferred=true` flag. (AC2)
- [ ] **T-015-A3.** List every `tests/test_*chilmesh*.py` file with the contract each pins. Write to `inventory.md §A3`. (AC4)

Dependencies: A1, A2, A3 are independent. Can run in parallel reads.

## Phase B — Classification rubric

- [ ] **T-015-B1.** Apply rubric (plan.md §B) to A1 entries. Surface any module that resists the three-way classification. (AC1)
- [ ] **T-015-B2.** Resolve ambiguous classifications by consulting the module's import graph: does it appear in `triangulate()`'s call stack? Does any test import it for post-processing? Document the tiebreaker per module. (AC1)

Dependencies: B requires A1 complete.

## Phase C — Disposition

- [ ] **T-015-C1.** For every `cons` module from B, write a disposition row (keep / move / extract) per plan.md §C. Each row cites its justification. (AC3)
- [ ] **T-015-C2.** For every `bdry` module from B, write a contract note: data structure, version lock, test contract location. (AC4)
- [ ] **T-015-C3.** Cross-check dispositions against open issues #84, #41, #9. Flag any disposition that conflicts with an in-flight issue. (AC4)

Dependencies: C requires B complete.

## Phase D — Decision record

- [ ] **T-015-D1.** Create `docs/adr/` directory if it does not exist.
- [ ] **T-015-D2.** Write `docs/adr/ADR-001-chilmesh-boundary.md` with sections per plan.md §D. Status = Proposed. (AC5)
- [ ] **T-015-D3.** Stamp the snapshot date for CHILmesh inference. (AC5)

Dependencies: D requires C complete.

## Phase E — Follow-up issues

- [ ] **T-015-E1.** For each `move-to-chilmesh` disposition, file an issue per plan.md §E. (AC6)
- [ ] **T-015-E2.** For each `extract-to-shared-lib` disposition, file an issue per plan.md §E. (AC6)
- [ ] **T-015-E3.** Record the issue numbers in ADR-001 §Consequences. (AC5, AC6)

Dependencies: E requires D complete (ADR must exist to link).

## Phase F — Light-touch doc updates

- [ ] **T-015-F1.** Add a one-line ADR link to `CLAUDE.md` near the existing CHILmesh row in the ecosystem table.
- [ ] **T-015-F2.** Decide whether `README.md` needs an update; if so, add a single sentence pointing to ADR-001. If not, skip and document why.

Dependencies: F requires D complete.

## Phase G — Issue closure

- [ ] **T-015-G1.** Post closing comment on issue #81 per plan.md §F. (AC7)
- [ ] **T-015-G2.** Leave issue #81 OPEN until maintainer reviews ADR (default behavior — do not unilaterally close).

Dependencies: G requires all of A–F complete.

## Cross-repo integration points

- **`tests/test_fort14_chilmesh_*.py`** — must NOT change in this spec. The seam contract is fixed.
- **`admesh/__init__.py`** — must NOT change in this spec. Public re-exports stay stable until follow-up move specs.
- **ADR-001** — becomes the canonical reference for future move specs. Every future move spec opens with "Per ADR-001 disposition for `<module>`..."

## Definition of done

All tasks above checked off, AC1–AC7 satisfied, follow-up issue numbers recorded in ADR-001, closing comment posted on #81. Branch `daily-issue-fixing` has new commits scoped to spec 015 files only — zero changes outside `specs/015-*/`, `docs/adr/`, and the single CLAUDE.md / README.md line.
