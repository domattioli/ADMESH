# Spec 016 — User-Configurable Max Valence (resolves #84)

**Status:** Planning-phase only. No code shipping in this commit.
**Issue:** [#84 the admesh algorithm should allow users to set a max-valence for vertices](https://github.com/domattioli/ADMESH/issues/84)
**Branch:** `daily-issue-fixing`
**Token budget:** SMALL (single dataclass field + one gate condition + 3 tests)

---

## 1. Problem statement

`admesh/valence.py::BalanceConfig` hard-codes `ideal_valence = 6` (the
equilateral-triangulation interior-vertex ideal). Issue #84 asks for the
ability to set an upper bound on interior-node valence — the user notes
that quad meshes should target valence-8 (with boundary / grading
exceptions), while triangle meshes target valence-6.

The current `balance_valence_triangles` edge-flip gate only rewards
deficit reduction relative to `ideal_valence`. There is no rejection
of flips that push a node's valence above any prescribed ceiling. This
is acceptable while the algorithm only runs on triangle meshes (the
deficit term naturally clusters around 6), but the user wants the
ceiling explicit so that:

- The post-v1 quad-prep path (spec 004, `admesh/quad_prep.py`) can
  reuse the same solver with a different ceiling.
- Users running on graded meshes can prevent the balancer from
  driving a near-boundary node's valence up to an unwanted maximum
  during a flip cascade.

## 2. Scope

In-scope (planning phase, this spec):

1. Extend `BalanceConfig` with a `max_valence: int | None = None` field.
   Default `None` preserves current behavior (no upper bound).
2. Specify the gate semantics: a flip is rejected when it would push
   the valence of either *receiver* node (`c` or `d` in the existing
   code) strictly above `max_valence`. Boundary nodes remain unaffected
   (they are excluded from the interior-edge gate already).
3. Document the quad-mode primitive (`ideal_valence=8`,
   `max_valence=10`) as the canonical preset and confirm it is the
   downstream API for spec 004 / future quad work.
4. Identify the test scaffolds for the implementation issue
   (acceptance tests, regression test for default-None behavior).

Out-of-scope (deferred to implementation issue):

- Writing the production code in `admesh/valence.py`.
- Auto-detecting triangle vs. quad topology and choosing the preset
  (separate concern; tracked under spec 004's quad-prep follow-up).
- New `min_valence` floor (the deficit term already provides a soft
  floor; #84 only asks for the ceiling).
- Per-region masking (a user wanting "no cap near the boundary" can
  do this today by adding fixed nodes; per-region caps would be a
  larger feature).

## 3. Acceptance criteria

- [ ] `BalanceConfig` gains a `max_valence: int | None = None` field.
- [ ] `balance_valence_triangles` rejects any candidate flip whose
      post-flip valence on either receiver node strictly exceeds
      `max_valence` (when `max_valence is not None`).
- [ ] When `max_valence is None`, the algorithm's behavior is
      bit-identical to the current implementation (regression test
      proves this on the existing `_make_grid_mesh` fixture).
- [ ] At least three new test cases land in `tests/test_valence.py`:
      (a) `max_valence` strictly enforced — a flip that would push a
      receiver to `max_valence + 1` is rejected;
      (b) `max_valence == ideal_valence` is a valid degenerate case
      and the algorithm still converges (possibly with `flips == 0`);
      (c) `max_valence < ideal_valence` is accepted (the gate just
      makes the deficit term harder to improve) and produces a
      non-error result with `converged=True` after no-op iteration.
- [ ] `get_valence_report` mentions the configured `max_valence` when
      it is not `None`.
- [ ] No regression on the existing `tests/test_valence.py` suite.
- [ ] No regression on `pytest -q` (full suite).

## 4. Cross-repo touchpoints

- **CHILmesh**: Per spec 015's classification work-in-progress,
  `valence.py` is a *boundary* module (consumed by both generation
  and post-processing). The `max_valence` knob is exactly the kind
  of contract that the eventual ADMESH↔CHILmesh seam needs to expose
  publicly. The implementation should be designed so that a future
  shared-base lift (per ADR-001 follow-ups) does not need to break
  this API.
- **ADMESH-Domains**: No touchpoints. Domain registry does not own
  any per-element parameters.

## 5. Risks

| Risk | Mitigation |
|---|---|
| Tight `max_valence` (close to `ideal_valence`) starves the deficit term and the algorithm exits without flips | Acceptance criterion (b) explicitly covers this case; document the trade-off in the docstring. |
| Users expect `max_valence` to also cap *initial* valence (not just post-flip) — but pre-existing high-valence nodes can only be reduced, not capped, by edge flipping | Document explicitly: `max_valence` is a *flip-gate*, not a global invariant. Pre-existing violations are left alone (they can only decrease via flips, which the deficit term already favors). |
| Default-None behavior drifts because the new branch reorders condition checks | Acceptance criterion (c)'s regression test pins the no-cap behavior to the existing fixture's edge-flip count. |
| The quad preset (`ideal=8, max=10`) is wrong in practice | This spec only locks the *mechanism*. Choice of preset values is a downstream tuning task and the spec does not enshrine specific numbers in production code. |

## 6. Token budget rationale

SMALL. The implementation is one dataclass field, one conditional
gate, and three tests. The spec doc itself is a single page. No
decomposition required.
