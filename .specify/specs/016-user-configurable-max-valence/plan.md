# Plan 016 — User-Configurable Max Valence

**Spec:** [spec.md](./spec.md) — resolves issue #84
**Phase:** Planning. Implementation deferred to a follow-up issue.
**Audience:** Whoever picks up the implementation issue.

---

## 1. Workflow

```
spec.md (this directory)
    │
    ▼
plan.md ── you are here
    │
    ▼
tasks.md (atomic decomposition)
    │
    ▼
[Implementation issue opened separately]
    │
    ▼
admesh/valence.py + tests/test_valence.py (deferred)
```

## 2. Architecture decision

### Where the gate lives

Inside `balance_valence_triangles`, immediately *after* the existing
`after >= before` deficit-improvement check and *before* the existing
`cd in e2t and len(e2t[cd]) >= 2` adjacency check.

Rationale:

- The deficit check is the cheap, scalar arithmetic gate. Keep it
  first so high-frequency rejection is fast.
- The new `max_valence` check is also scalar arithmetic, but it is
  conditional on `config.max_valence is not None`. Putting it second
  keeps the default-None path as fast as today.
- The adjacency check (`cd in e2t`) is the topology gate that
  protects the half-edge data structure; it should remain the last
  gate before geometry-quality.

### Why a flip-gate and not a global invariant

The user's framing in #84 ("quads should have vertices in general
that are valence-8") describes a *target*, not a hard invariant.
Pre-existing high-valence nodes (from the generator, or from a mesh
loaded via `read_fort14`) cannot always be reduced by edge flipping
alone — sometimes they require node deletion + retriangulation,
which is out of scope for the balancer.

Therefore `max_valence` is documented and implemented as a "flips
must not increase any node's valence above this ceiling" rule. It
does not promise that the *output* mesh has no node above the
ceiling.

### Receiver-side only

In a triangle edge flip, the edge `(a, b)` (shared by triangles
`t1, t2`) is replaced by edge `(c, d)` (where `c, d` are the
opposite vertices of `t1, t2` respectively). The valence changes:

- `a` decreases by 1 (was on the shared edge, now isn't)
- `b` decreases by 1 (was on the shared edge, now isn't)
- `c` increases by 1 (gains a new edge to `d`)
- `d` increases by 1 (gains a new edge to `c`)

The gate must check only `c` and `d` (the receivers): valences `a`
and `b` are decreasing, so they can never violate the ceiling on
this flip. Implementation is two scalar comparisons.

### Boundary nodes

Receivers `c` and `d` are interior to the patch (they are the
opposite vertices of two interior-adjacent triangles), so they
*can* be boundary nodes of the mesh. The current code already
treats boundary-node valence as "uncapped" via the `_deficit`
function. We preserve that: when `c` (or `d`) is a boundary node,
the cap is not enforced on it. Concretely:

```python
if cfg.max_valence is not None:
    if not bnd[c] and valence[c] + 1 > cfg.max_valence:
        continue
    if not bnd[d] and valence[d] + 1 > cfg.max_valence:
        continue
```

## 3. Public API delta

```diff
 @dataclass
 class BalanceConfig:
     ideal_valence: int = 6
     max_iterations: int = 20
     convergence_threshold: float = 0.01
     quality_gate: float = 0.05
+    max_valence: int | None = None
```

No new public function, no signature change on `balance_valence_triangles`,
no new exception type. `__init__.py` re-exports are unaffected.

## 4. Test plan

Add to `tests/test_valence.py` (existing file, 218 lines):

1. `test_max_valence_strictly_enforced` — construct a small mesh where
   *exactly one* candidate flip is available and that flip would push
   a receiver's valence from `max_valence` to `max_valence + 1`. Assert
   `result.edges_flipped == 0` and `result.converged is True`.

2. `test_max_valence_equal_ideal` — set `max_valence == ideal_valence`.
   The algorithm should still converge (some flips may still improve
   the deficit term among already-at-ideal receivers, since not every
   flip pushes the receiver above ideal). Assert no crash and
   `converged is True`.

3. `test_max_valence_none_unchanged` — pin the existing fixture
   (`_make_grid_mesh()`) output: with `max_valence=None`, the
   `edges_flipped` count and final `stats_after` must match the
   pre-feature baseline. Capture the baseline once when implementing.

4. (Optional) `test_get_valence_report_mentions_max` — if the report
   string is extended.

## 5. Implementation step ordering

1. Capture baseline `edges_flipped` and `stats_after.pct_at_ideal` for
   `_make_grid_mesh()` with current code (running test once).
2. Add `max_valence: int | None = None` to `BalanceConfig`.
3. Insert the receiver-side gate in `balance_valence_triangles`.
4. Update `get_valence_report` to include the `max_valence` line
   when non-None (optional).
5. Write the three (or four) new tests.
6. Confirm full suite `pytest -q` exits 0.

## 6. Quad-mode preset (informational)

For the eventual quad-prep follow-up, the recommended preset is:

```python
QUAD_PRESET = BalanceConfig(
    ideal_valence=8,
    max_valence=10,
    max_iterations=20,
    convergence_threshold=0.01,
    quality_gate=0.05,
)
```

These numbers come from the user's framing in #84 (valence-8 ideal
for quads, with exceptions). The `max_valence=10` is a tentative
two-step margin and should be tuned during the actual quad-prep work,
which is a *separate* issue. **This spec does not lock those numbers
in production code.**

## 7. Dependencies

None. The change is self-contained inside `admesh/valence.py` plus
its test file. No cross-repo or cross-spec coordination required.

## 8. Estimated effort

- Spec + plan + tasks (this commit): ~30 minutes (done).
- Implementation issue (separate work): ~45 minutes for code + tests
  + report-tweak + suite re-run.
