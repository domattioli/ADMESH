# Cross-Artifact Analysis: Full C++ Rewrite of ADMESH

**Date**: 2026-05-25 | **Artifacts**: spec.md, plan.md, research.md, data-model.md, contracts/, tasks.md

Consistency / coverage / constitution scan across the spec-kit artifacts. No
code changed.

## Requirement → Task coverage

| Req | Covered by | Status |
|---|---|---|
| FR-001 standalone C++ lib | T002, T014, T016, T017 | ✅ (implicit — see Finding A1) |
| FR-002 Python source-compat | T031, T032 | ✅ |
| FR-003 per-stage parity | T011, T026, T027, T029 | ✅ |
| FR-004 permanent Numba fallback | T010, T038 | ✅ |
| FR-005 no `-ffast-math` / pinned order | T004 | ✅ |
| FR-006 wheel matrix | T035 | ✅ |
| FR-007 Python callbacks | T009 | ✅ |
| FR-008 fort.14 byte-faithful | T007, T012 | ✅ |
| FR-009 benchmark C++ column | T039 | ✅ |
| FR-010 backend select | T010 | ✅ |
| SC-001 full suite green | T033, T034 | ✅ |
| SC-002 standalone C++ test | T016 | ✅ |
| SC-003 speedup measured | T039 | ✅ |
| SC-004 wheels + lib per target | T036, T037 | ✅ |
| SC-005 no output change | T033 | ✅ |
| US1 / US2 / US3 / US4 | Phase 3 / 5 / 4 / 6 | ✅ all have tasks |

All 10 FRs, 5 SCs, 4 user stories trace to ≥1 task.

## Findings

**A1 — RESOLVED.** FR-001 now tagged on T002/T006/T015/T018; every req carries
an inline tag + a coverage map appended to tasks.md.

**A2 — RESOLVED.** Degenerate-input fixture coverage is now **T012** (Phase 2
foundational): audit `tests/fixtures/<stage>/*.npz` for collinear slivers +
zero-area triangles, extend from the MATLAB oracle where nominal-only. T012
blocks the parity gates so every stage is exercised against degenerate cases.

**A3 — spec text stale vs plan / low.** Spec still marks FR-006 and FR-010
"[DEFERRED to plan]"; research.md R2/R5 now resolves both. Harmless (plan is
allowed to resolve deferrals) but the spec could be back-annotated. *Fix:
optional.*

**A4 — phase ordering note / informational.** tasks.md Phase 3=US1, Phase 4=US3,
Phase 5=US2 — not in numeric US order. **Intentional**: US1 (native lib) is MVP;
US2 (bindings) depends on US3 (native stages existing) so it must follow. Stated
in Dependencies. No action.

**A5 — unresolved operator gate / high (carried, not a defect).** Two items are
explicitly operator-blocked, correctly surfaced in both plan and tasks:
- **Article II.2** amendment (T043) — required before merge to `main`; deferred
  this iteration by user direction. Plan Constitution Check marks it ⚠️ DEFERRED,
  not silently passed. Consistent across artifacts.
- **R7 Triangle license** (T042) — Apache-2.0 redistribution vs Triangle's
  non-commercial terms; gate as optional, default `delaunator` (MIT). Needs
  operator/legal call before wheel publish.

## Constitution alignment

| Principle | Verdict |
|---|---|
| I — faithful-port identity | ✅ per-stage parity gate is the spine of the plan |
| Art II.2 — no C/C++ first cut | ⚠️ DEFERRED (operator), tracked T043 — not waived |
| Art IV.4 — leaf→integrator order | ✅ tasks T018–T030 ordered leaves first, routine last |
| Art IV.6 — divergence is a bug | ✅ parity-gate contract forbids widening bit-parity tol |
| Art V — every stage a ref test | ✅ existing fixtures reused as oracle, both backends |
| Art VI.7 — reuse branch | ✅ rides on `cpp-distmesh`, no new branch |
| North star — no-toolchain install | ✅ permanent Numba fallback + soft-degrade sdist |

## Verdict

Artifacts are **internally consistent and execution-ready**. A1 + A2 closed in
the regenerated tasks.md (FR tags + T012 degenerate fixtures). Two **operator
gates** remain (**A5**: Art II.2 amendment for merge, Triangle license for
publish) — neither blocks Phase 1 start. No conflicting or duplicated
requirements, no ambiguous tasks.
