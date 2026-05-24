# Tasks 018 — Boundary Tri-Pair Degeneracy Investigation

**Spec:** [spec.md](./spec.md). **Plan:** [plan.md](./plan.md).
**Phase:** Planning. Only doc tasks; no code under `admesh/`.

---

## Task index

| ID | Title | Output artifact | Status |
|---|---|---|---|
| T-018-1 | Define the configuration predicate $P$ | `investigation.md` §1 | required for this spec |
| T-018-2 | Audit four existing mitigations | `investigation.md` §2 | required for this spec |
| T-018-3 | Enumerate ≥3 upstream-prevention candidates + rate | `investigation.md` §3 | required for this spec |
| T-018-4 | Reach + record disposition; route follow-up | `investigation.md` §4 + GH side-effects | required for this spec |
| T-018-5 | Empirical count on MVP-5 + WNAT fixtures | new ADMESH issue | follow-up (NOT this spec) |
| T-018-6 | Spec 016 max-valence interaction subsection | `investigation.md` §5 | required for this spec |

---

## T-018-1 — Define the configuration predicate

**Output:** `investigation.md` §1.

State $P(T_1, T_2)$ precisely:

- Inputs: a tri-mesh with `nodes : (N,2) float`, `elements : (M,3) int`.
- Free-boundary edge set: edges appearing in exactly one triangle.
- $T_1, T_2$ are *adjacent* iff they share exactly one edge $e_{12}$
  that is NOT a free-boundary edge (i.e. $e_{12}$ is interior).
- Each of $T_1, T_2$ contains exactly one edge in the free-boundary
  edge set.

Add the **geometric signature**: the quad $T_1 \cup T_2$ has two
boundary edges (one per triangle) and two interior-of-quad edges
(the triangles' non-shared, non-boundary edges). The quad's two
diagonals are $e_{12}$ and the cross-pair connecting the two
non-shared vertices.

Add the **degeneracy criterion** (the *real* reason the configuration
hurts downstream): the quad's two boundary edges are approximately
*opposite* in the quad (not adjacent), so a tri2quad fuse produces a
quad with two boundary edges on opposite sides — a "boundary
sandwich". When the four points are also near-collinear, the result
is a sliver. Cite ADCIRC's quad-merge semantics where helpful.

## T-018-2 — Audit four existing mitigations

**Output:** `investigation.md` §2.

For each of:

1. `_boundary_cleanup` (`admesh/_stages/distmesh.py:333`).
2. `_boundary_density_control` (`admesh/_stages/distmesh.py:412`).
3. `balance_valence_triangles` (`admesh/valence.py`).
4. `BalanceConfig.max_valence` (spec 016 — in-flight,
   `specs/016-user-configurable-max-valence/`).

Walk:

- Trigger condition (what makes it fire on a configuration?).
- Action (what does it do when it fires?).
- Effect on $P$ (does it break the configuration, partially weaken
  it, or have no effect?).
- Rate as **mitigates / partial / no effect**.

Write the audit as a single table in `investigation.md` §2.

## T-018-3 — Enumerate candidates + rate

**Output:** `investigation.md` §3.

List ≥3 upstream-prevention candidates. Required minimum set:

1. **Boundary-edge mid-split** at finalization.
2. **Diagonal flip with boundary penalty** inside
   `balance_valence_triangles`.
3. **Pre-quad-prep gate** inside `admesh/quad_prep.py`.

Optional additional candidates the writer surfaces during analysis
go below the minimum set, numbered 4+.

For each candidate, fill the 3×3 rating cell:

| Axis | Levels |
|---|---|
| Coverage | Full / Partial / Incidental |
| Cost | Low / Med / High |
| Risk | Low / Med / High |

Apply the **preventable-eligible** rule from plan.md §3:

> A candidate is preventable-eligible iff Cost ≤ Med AND Risk ≤ Med
> AND Coverage ≥ Partial.

Mark each candidate **eligible** or **out**.

## T-018-4 — Disposition + routing

**Output:** `investigation.md` §4 and one of:

- (a) a follow-up ADMESH issue (if **preventable**), OR
- (b) a comment on #85 stating **inherent** + CHILmesh pointer.

Either way, post a **status comment** on #85 referencing
`investigation.md` and stating the disposition label.

Disposition labels (exactly one):

- **preventable** — name the winning candidate, its 3×3 rating, and
  the follow-up issue title.
- **inherent** — state the reason no candidate cleared the rubric;
  reaffirm CHILmesh as the canonical fix; do not file an ADMESH
  follow-up.

### T-018-4a — If preventable: file follow-up issue

Title: `Implement boundary tri-pair mitigation: <candidate name>
(spec 018 follow-up)`.

Labels: `planning-required`, `cross-repo`, `enhancement`.

Body: link spec 018 + investigation.md, copy the candidate's rating
cell, copy the disposition paragraph.

### T-018-4b — Always: comment on #85

Use the C-status template (per COMMENT-TEMPLATES.md if present;
otherwise a plain comment with the standard footer). Body has:

- One-line disposition label.
- Link to `specs/018-boundary-tri-pair-degeneracy/investigation.md`.
- If **preventable**: link to the new follow-up issue.
- If **inherent**: explicit statement that CHILmesh is the canonical
  fix and this tracker can close once the CHILmesh issue ships.

Footer (mandatory per claude_routine_instructions.md §8):

```
[model: claude-opus-4-7, repo: ADMESH, session: 2026-05-22-routine-h15]
```

## T-018-5 — Empirical count (follow-up, NOT this spec)

**Output:** new ADMESH issue, NOT part of this spec.

File an issue titled `Empirical count of boundary tri-pair
configuration on MVP-5 + WNAT fixtures (spec 018 follow-up)`.

Body: short script sketch (read `tests/fixtures/fort14/*.14`, build
edge-incidence map, count $P(T_1, T_2)$, emit per-fixture counts).
Labels: `scope:tests`, `severity:low`, `planning-required`.

This task does NOT block T-018-4. The disposition is analytical;
empirical counts refine, not gate.

## T-018-6 — Spec 016 interaction subsection

**Output:** `investigation.md` §5.

Write the labeled subsection
"### Interaction with spec 016 (max-valence)" answering:

- Does `max_valence` change the frequency of $P$? Yes / No / Unknown
  + one-sentence reason.
- What `max_valence` value (if any) is recommended when ADMESH output
  feeds CHILmesh's quad-merge pass? `None` is a valid answer.
- One-line `docs/PORTING_NOTES.md` entry that spec 016's
  implementer copies in their port commit.
