# Tasks 016 — User-Configurable Max Valence

**Spec:** [spec.md](./spec.md) · **Plan:** [plan.md](./plan.md)
**Issue:** [#84](https://github.com/domattioli/ADMESH/issues/84)
**Branch (when implementing):** `daily-issue-fixing`

Each task is atomic, testable, and references the acceptance criterion
it satisfies. Tasks marked `[planning]` are complete with this commit.
Tasks marked `[impl]` are for the follow-up implementation issue.

---

## T-016-1 — Confirm current public API contract `[planning]`

- **Action:** Re-read `admesh/valence.py` and verify the four-field
  shape of `BalanceConfig`. Confirm `__init__.py` re-exports
  `BalanceConfig` so any new field is automatically public.
- **Output:** Plan.md §3 captures the API delta.
- **Acceptance:** None directly — preparation for T-016-2.
- **Status:** Done (in plan.md).

## T-016-2 — Capture pre-feature behavioral baseline `[impl]`

- **Action:** Run `pytest -q tests/test_valence.py -v` and record
  the `edges_flipped` count from any test that asserts on it, plus
  `stats_after.pct_at_ideal` from any test that asserts on it.
- **Output:** A short comment block in the implementation PR
  capturing the numbers (e.g. "baseline: edges_flipped=N on
  `_make_grid_mesh()` no-boundary fixture").
- **Acceptance:** Feeds T-016-6 (regression test pinning default-None
  behavior).
- **Depends on:** none.

## T-016-3 — Extend `BalanceConfig` `[impl]`

- **Action:** Add `max_valence: int | None = None` as the fifth
  field of `BalanceConfig` in `admesh/valence.py`. Update the
  class docstring to describe it.
- **Acceptance criterion:** spec.md §3 item 1
  ("`BalanceConfig` gains a `max_valence: int | None = None` field").
- **Depends on:** T-016-2.
- **Effort:** XS (≤ 5 lines).

## T-016-4 — Insert receiver-side gate in `balance_valence_triangles` `[impl]`

- **Action:** In the inner loop of `balance_valence_triangles`,
  after the existing `if after >= before: continue` line and before
  the `cd in e2t` adjacency check, insert:

  ```python
  if config.max_valence is not None:
      if not bnd[c] and valence[c] + 1 > config.max_valence:
          continue
      if not bnd[d] and valence[d] + 1 > config.max_valence:
          continue
  ```

  Place under the existing `# valence deficit` comment block.
- **Acceptance criterion:** spec.md §3 item 2
  ("rejects any candidate flip whose post-flip valence on either
  receiver node strictly exceeds `max_valence`").
- **Depends on:** T-016-3.
- **Effort:** XS (≤ 5 lines).

## T-016-5 — Acceptance test: max_valence strictly enforced `[impl]`

- **Action:** Add `test_max_valence_strictly_enforced` to
  `tests/test_valence.py`. Build a small mesh where one candidate
  flip exists and that flip would push a receiver's valence from
  `max_valence` to `max_valence + 1`. Assert
  `result.edges_flipped == 0` and `result.converged is True`.
- **Acceptance criterion:** spec.md §3 item 4(a).
- **Depends on:** T-016-4.
- **Effort:** S (~30 lines).

## T-016-6 — Acceptance test: max_valence == ideal_valence `[impl]`

- **Action:** Add `test_max_valence_equal_ideal` to
  `tests/test_valence.py`. Use the existing `_make_grid_mesh()`
  fixture with `BalanceConfig(ideal_valence=6, max_valence=6)`.
  Assert `result.converged is True` and no crash.
- **Acceptance criterion:** spec.md §3 item 4(b).
- **Depends on:** T-016-4.
- **Effort:** S (~15 lines).

## T-016-7 — Regression test: max_valence == None unchanged `[impl]`

- **Action:** Add `test_max_valence_none_baseline` to
  `tests/test_valence.py`. Run `balance_valence_triangles(mesh,
  BalanceConfig())` on `_make_grid_mesh()` and assert
  `result.edges_flipped == <baseline from T-016-2>` and
  `result.stats_after.pct_at_ideal == pytest.approx(<baseline>)`.
- **Acceptance criterion:** spec.md §3 item 4(c) and
  ("When `max_valence is None`, the algorithm's behavior is
  bit-identical to the current implementation").
- **Depends on:** T-016-2, T-016-4.
- **Effort:** S (~20 lines).

## T-016-8 — Update `get_valence_report` `[impl]`

- **Action:** Append a `Max cap` line to the report string when
  `cfg.max_valence is not None`. Format:
  `f"  Max cap        : {cfg.max_valence}"`.
- **Acceptance criterion:** spec.md §3 item 5.
- **Depends on:** T-016-3.
- **Effort:** XS (≤ 3 lines).

## T-016-9 — Full suite green `[impl]`

- **Action:** Run `pytest -q`. Confirm exit 0 and no new warnings.
- **Acceptance criterion:** spec.md §3 item 7
  ("No regression on `pytest -q` (full suite)").
- **Depends on:** T-016-3..T-016-8.
- **Effort:** XS (CI).

## T-016-10 — Close issue #84 with implementation summary `[impl]`

- **Action:** After commit + push of implementation, comment on
  issue #84 with: changes summary, list of new tests, link to the
  commit, and which acceptance criteria are satisfied. Close the
  issue.
- **Depends on:** T-016-9.
- **Effort:** XS.

---

## Dependency graph

```
T-016-1 (done)
T-016-2 ──► T-016-3 ──► T-016-4 ──┬─► T-016-5
                                  ├─► T-016-6
                                  ├─► T-016-7
                                  └─► T-016-8
                                  └─► T-016-9 ──► T-016-10
```

## Cross-repo integration points

None. This work is fully internal to ADMESH.

## Total estimated effort (impl phase)

- 4 tasks at XS (≤ 5 lines each): ~10 minutes
- 3 tasks at S (~15-30 lines each): ~30 minutes
- CI + close-out: ~5 minutes

Total: **~45 minutes** for the implementation issue.
