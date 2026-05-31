# Implement — 021 Quad-Intent Triangulation (status: NOT STARTED)

Phase 6 of the speckit workflow. This file is the execution ledger for `/implement`.
**Per the operator's instruction, NO production code is written yet** — this spec is the
investigation + design deliverable. Implementation begins only after the operator confirms the
`[CONFIRM]` items below.

---

## Pre-implementation gate (must be green before any code)
- [ ] **C-1** Architecture: parallel additive `quad_intent.py` loop (NOT editing locked
      `distmesh.py`). — operator confirm
- [ ] **C-2** MVP lever scope: lever-3 flips only, or lever-3 + lever-1 anisotropy. — operator confirm
- [ ] **C-4** SC-002 acceptance margin pending QuADMESH#63 quadability baseline (T-024). — operator confirm after baseline
- [ ] **C-9** spec-016 `max_valence` sequencing (co-develop vs depend). — operator confirm

## Execution order (from tasks.md)
1. **P0** T-001…T-005 — scaffolding + regression lock (byte-safe; can start immediately once C-1
   confirmed; touches only `quad_intent.py`, `api.py` dispatch, `__init__.py`, new test file).
2. **P1** T-010…T-014 — lever-3 valence flips at ideal 8 + parity + diagnostics.
3. **GATE T-024** — re-baseline acceptance margins on real ADMESH output before P2 commitment.
4. **P2** T-020…T-023 — anisotropic rest-length (held behind gate).
5. **P3** T-030…T-031 — parity insert/delete (conditional on P1+P2 shortfall).
6. **P4** T-040…T-043 — geometry finish, fallback, quality gate, docs.

## Coding dispatch
Every code-writing task above MUST be dispatched to a subagent running `claude-haiku-4-5`
(CLAUDE.md "Coding dispatch — Haiku subagent default"). The main session plans/reviews/integrates.

## Done when
SC-001…SC-006 all pass; zero locked-stage edits (T-005 guard green); CHANGELOG + docs updated;
QuADMESH#63 cross-linked from the PR.

---

## Ledger
| Date | Task | Subagent | Result |
|---|---|---|---|
| — | (none yet) | — | spec phase only; awaiting operator confirm of C-1/C-2/C-4/C-9 |
