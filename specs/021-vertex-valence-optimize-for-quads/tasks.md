# Tasks — 021 Quad-Intent Triangulation

Phase 4 of the speckit workflow. Ordered, independently-testable tasks derived from `plan.md`.
**No code is written in this spec phase.** These are the units a future `/implement` would
execute (each dispatched to a Haiku subagent per CLAUDE.md coding-dispatch policy).

Legend: `[P#]` build phase from plan §5. `→ SC/FR` = which criterion it satisfies.

---

## P0 — Scaffolding + regression lock
- **T-001** [P0] Create `admesh/quad_intent.py` skeleton with module docstring (additive-layer
  note), `QuadIntentConfig` dataclass (plan §4), and a `distmesh2d_quad` stub that delegates to
  the locked `distmesh2d` for now. → FR-003
- **T-002** [P0] Add `quad_intent: bool = False` + `quad_config: QuadIntentConfig | None = None`
  params to `admesh/api.py::triangulate` (line ~615); dispatch to `quad_intent.distmesh2d_quad`
  only when `True`. → FR-001
- **T-003** [P0] Export `QuadIntentConfig`, `quadability_report` from `admesh/__init__.py`.
- **T-004** [P0] `tests/test_quad_intent.py`: regression test — for each MVP domain, assert
  `triangulate(d)` == `triangulate(d, quad_intent=False)` and both == saved baseline
  (nodes/elements array-equal). → SC-001
- **T-005** [P0] CI/grep guard test: assert no diff in `admesh/_stages/*` vs `main` (or a
  unit-level guard asserting `quad_intent.py` imports but never monkeypatches stage modules).
  → SC-006

## P1 — Lever 3: valence-aware edge flips (MVP)
- **T-010** [P1] Add even-parity reward to `valence.py` deficit function: generalize `_deficit`
  to `α·|v-ideal| + β·odd(v)` controlled by `BalanceConfig` (new fields `even_parity_weight`,
  `valence_target_weight`); default weights preserve current behavior when unset. → FR-004, C-3
- **T-011** [P1] Confirm/co-develop spec-016 `max_valence` field + gate in `valence.py` if not
  yet landed. → C-9, FR-004
- **T-012** [P1] In `distmesh2d_quad`: after each retri, run `balance_valence_triangles` with
  `BalanceConfig(ideal_valence=8, max_valence=cfg.max_valence, even_parity_weight=…)`. Keep
  boundary nodes excluded (reuse `_boundary_mask`). → FR-004, FR-005
- **T-013** [P1] Implement `quadability_report(mesh, h=None)`: interior valence histogram,
  `pct_even`, `mean|v-8|`, and `|edge|/h` distribution. Extend `valence.get_valence_report`.
  → FR-008, US-2
- **T-014** [P1] Tests: assert `pct_even_interior` and `mean|v-8|` improve vs default on ≥3 MVP
  domains; assert `quadability_report` matches a hand-computed fixture. → SC-002, SC-003

## P2 — Lever 1: anisotropic rest-length
- **T-020** [P2] Implement `LocalMetric`: given `fd`/SDF and a point set, return per-point SPD
  `M(x)` with eigenvector `rot90(∇fd/|∇fd|)`, ratio `min(cfg.anisotropy_ratio, √2)`, blending to
  isotropic within `_BOUNDARY_BAND_FACTOR·h` of the boundary. → FR-009, C-5, C-6
- **T-021** [P2] Replace scalar `L0` in `distmesh2d_quad`'s force computation with metric length
  `sqrt(barvecᵀ M barvec)`; preserve the global normalization. Interior bars only. → lever 1
- **T-022** [P2] Implement fidelity gate: per-edge `r=|edge|/h_local` (h = diagonal interp),
  reject moves dropping in-band fraction below `fidelity_min_fraction` or any edge outside band.
  → FR-007, SC-004
- **T-023** [P2] Tests: ≥90% edges in `[0.7,1.4]`; `pct_even` margin meets re-baselined C-4
  target on annulus + ≥2 domains. → SC-004, SC-002
- **T-024** [P2] **GATE**: re-baseline C-4 acceptance margins against the QuADMESH#63
  quadability-profile run on real ADMESH output; record numbers in this spec; get operator
  `[CONFIRM]`. → C-4

## P3 — Lever 2: parity-driven insert/delete (conditional)
- **T-030** [P3] Only if P1+P2 miss SC-002: insert a node on the longest incident edge of an
  odd interior vertex (raise valence), gated by fidelity bound; merge to lower. → lever 2
- **T-031** [P3] Tests: inserts/deletes never push edges out of fidelity band; valence parity
  improves. → FR-007

## P4 — Geometry finish + hardening
- **T-040** [P4] Wire optional `quad_prep.smooth_for_quadrangulation(pair_hint=True, h=…)` as the
  final relax when `cfg.run_quad_prep_finish`. → US-3
- **T-041** [P4] Best-quality tracking + fallback-with-warning if final `min_q < 0.30`
  (mirror `distmesh.py:808–813`). → C-7, SC-005
- **T-042** [P4] Tests: quality gate `min_q≥0.30 / mean_q≥0.60` on MVP domains; mean angle
  deviation from {45,45,90} decreases vs default (right_iso_quality). → SC-005, US-3
- **T-043** [P4] Docs: `docs/` quad-intent usage note; `PORTING_NOTES.md` entry; CHANGELOG;
  update `CLAUDE.md` spec list. Cross-link QuADMESH#63.

## Dependencies / ordering
- T-001..T-005 (P0) first; regression lock MUST be green before any lever lands.
- P1 before P2 before P3 (cheapest, highest-confidence first).
- T-024 GATE blocks P3 commitment and final acceptance numbers.
- spec-016 (T-011) is a soft prerequisite of T-010/T-012.

## Definition of done (feature, post-implement)
All SC-001…SC-006 pass; zero locked-stage edits; operator confirmed C-1, C-2, C-4, C-9.
