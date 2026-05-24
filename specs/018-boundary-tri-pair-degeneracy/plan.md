# Plan 018 — Boundary Tri-Pair Degeneracy Investigation

**Spec:** [spec.md](./spec.md) — tracks issue #85
**Phase:** Planning. No implementation in `admesh/`.
**Audience:** Whoever picks up the follow-up issue (if disposition is **preventable**),
or the CHILmesh-side author of the post-admesh protocol (if **inherent**).

---

## 1. Workflow

```
spec.md (planning scope)
    │
    ▼
plan.md ── you are here (workflow + classification rubric)
    │
    ▼
tasks.md (atomic decomposition for the investigation)
    │
    ▼
investigation.md (analytical deliverable: predicate, audit, candidates,
                  ratings, disposition)
    │
    ▼
[Disposition routing]
    │
    ├──── preventable → file follow-up implementation issue (ADMESH)
    │                  comment on #85 pointing at the follow-up
    │
    └──── inherent    → comment on #85 stating disposition + pointer to
                        CHILmesh post-admesh protocol as canonical fix
```

## 2. Investigation method

The investigation is **analytical**, not empirical. Justification:

- The configuration is defined geometrically and exists in every
  unstructured triangle mesh with sufficient boundary length; the
  question is not "does it occur?" but "is it cheap to prevent?"
- Empirical counts on real fixtures (WNAT, MVP-5) are valuable but
  not required for the disposition. They are scheduled as a follow-up
  task (see tasks.md, T-018-5).
- Running counts on every fixture requires touching `admesh/` test
  helpers or writing new diagnostic scripts; the ADMESH planning-only
  profile blocks code shipping this session.

The analysis proceeds in four passes:

### Pass A — Formalize the configuration

State the offending configuration as a predicate $P(T_1, T_2)$ on
adjacent triangles in a mesh:

- $T_1, T_2 \in \text{mesh.elements}$ share interior edge $e_{12}$.
- $T_1$ has exactly one edge in the free-boundary edge set; $T_2$
  has exactly one edge in the free-boundary edge set.
- The two boundary edges are not collinear with $e_{12}$ (so the
  configuration is geometrically a "step" rather than a single
  straight boundary segment cut by an interior edge).

Compute the geometric signature: the quad $Q = T_1 \cup T_2$ has 4
edges; two are boundary edges, two are quad-interior edges; the
quad's diagonals are $e_{12}$ and the cross-pair connecting the two
non-shared vertices.

### Pass B — Audit existing mitigations

Walk four extant ADMESH mechanisms and rate each as **mitigates /
partial / no effect**:

1. `_boundary_cleanup` (`admesh._stages.distmesh:333`). Drops
   boundary-attached triangles with element quality $q < 0.15$.
2. `_boundary_density_control` (`admesh._stages.distmesh:412`).
   Removes interior vertices of low-quality boundary-attached
   triangles during the density-control half of the distmesh loop.
3. `balance_valence_triangles` (`admesh.valence`). Edge-flips toward
   `ideal_valence=6` on interior edges.
4. `BalanceConfig.max_valence` (spec 016, in-flight). Rejects flips
   that drive a receiver node above the configured ceiling.

Audit asks: does the mechanism *break* the configuration (split the
shared edge, remove one of the two triangles, flip $e_{12}$ to a
different interior edge) when its trigger fires?

### Pass C — Enumerate candidates

For each candidate upstream prevention, sketch the change at the
level of "which module gets a new function / new gate":

1. **Boundary-edge mid-split**: when a tri-pair matching $P$ is
   detected during finalization, insert a midpoint node on the
   longer of the two boundary edges. The two triangles split into
   four; quad-merge cannot fuse them into a single sliver.
2. **Diagonal flip with boundary penalty**: extend
   `balance_valence_triangles` with a "boundary-pair" penalty that
   rejects the shared interior edge between two boundary-adjacent
   triangles if the resulting quad would have two boundary edges
   under tri2quad fusion semantics. Note: flip only moves the
   diagonal; it does not change the pair's boundary edges, so this
   is structurally limited.
3. **Pre-quad-prep gate inside `quad_prep.py`**: add a defensive
   step at the *end* of `smooth_for_quadrangulation` that detects
   the configuration and splits one triangle. This keeps the change
   inside the additive layer and out of the locked stage modules
   (Constitution Principle I clean).
4. **Do nothing in ADMESH; defer to CHILmesh**. Listed as a
   candidate for completeness — it is the **inherent** disposition.

### Pass D — Rate and dispose

Each candidate gets a 3×3 rating cell (coverage / cost / risk).
Aggregate cells into the disposition decision. Pick the
lowest-cost-with-acceptable-coverage candidate if one exists;
otherwise declare **inherent**.

## 3. Classification rubric

A candidate is rated on three axes:

| Axis | Levels |
|---|---|
| **Coverage** | Full (eliminates configuration in all cases) / Partial (eliminates in common cases, misses pathological) / Incidental (mitigates by luck) |
| **Cost** | Low (additive-layer module only) / Med (touches `admesh/quad_prep.py` or `admesh.valence`) / High (touches a Constitution-Principle-I locked stage module) |
| **Risk** | Low (no impact on existing tests; bounded change) / Med (one or two acceptance tests may need adjustment) / High (could regress structural-validity gate or MATLAB parity at `atol=1e-10`) |

A candidate is **preventable-eligible** iff Cost ≤ Med AND Risk ≤ Med
AND Coverage ≥ Partial. Otherwise it falls out of the running and
the disposition slides toward **inherent**.

## 4. Disposition contract

The investigation must produce **exactly one** disposition:

- **preventable**: name the candidate, its rating, and the follow-up
  issue title. The investigation writer files the follow-up issue
  (per acceptance criteria in spec.md §3).
- **inherent**: state the reason no preventable candidate cleared
  the rubric, and link the CHILmesh tracker (once filed) as the
  canonical fix.

A "mixed" disposition (some configurations preventable, others
inherent) is permitted only if it is collapsed into one of the two
labels above by majority of cases. The default is **inherent**
unless a candidate clears the rubric.

## 5. Spec 016 interaction (mandatory subsection in investigation.md)

The investigation must include a labeled subsection
"### Interaction with spec 016 (max-valence)" stating:

- Whether `max_valence` causes any change in the frequency of the
  configuration.
- What `max_valence` value (if any) is recommended when ADMESH is
  consumed downstream by CHILmesh's quad-merge pass.
- A one-line porting-note suggestion for spec 016's implementer to
  copy into `docs/PORTING_NOTES.md`.

## 6. Out-of-scope reaffirmed

- No code under `admesh/`.
- No fixtures generated.
- No MATLAB-side scripts touched.
- No ADR-001 amendment.
- No CHILmesh-side design.

If the investigation surfaces a need that violates any of the above,
the writer files a *new* spec rather than smuggling it into this one.
