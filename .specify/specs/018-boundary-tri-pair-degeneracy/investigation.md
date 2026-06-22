# Investigation 018 — Boundary Tri-Pair Degeneracy

**Spec:** [spec.md](./spec.md). **Plan:** [plan.md](./plan.md). **Tasks:** [tasks.md](./tasks.md).
**Issue tracked:** [#85](https://github.com/domattioli/ADMESH/issues/85).
**Method:** analytical (per plan.md §2; empirical counts deferred to T-018-5).
**Disposition:** **inherent** (see §4).

---

## 1. The configuration $P$

Let a mesh be $(V, T)$ with vertices $V \subset \mathbb{R}^2$ and
triangles $T \subset \binom{|V|}{3}$. Let $E_f$ be the *free-boundary
edge set*: every edge appearing in exactly one triangle.

**Definition.** Triangles $T_1, T_2 \in T$ satisfy the
boundary tri-pair predicate $P(T_1, T_2)$ iff:

1. $T_1 \cap T_2 = \{u, v\}$ — they share exactly the edge
   $e_{12} = \{u, v\}$.
2. $e_{12} \notin E_f$ — the shared edge is interior (it appears in
   both triangles).
3. $|E(T_1) \cap E_f| = 1$ and $|E(T_2) \cap E_f| = 1$ — each
   triangle has exactly one free-boundary edge.

Write $T_1 = \{u, v, a\}$ with boundary edge $e_a = \{u, a\}$ (WLOG),
and $T_2 = \{u, v, b\}$ with boundary edge $e_b = \{v, b\}$. Then
$Q := T_1 \cup T_2$ has 4 vertices $\{a, u, v, b\}$ and 4 edges
$\{e_a, e_{uv-?}, e_b, e_{?-a}\}$ — but the precise topology is the
quad $a$–$u$–$v$–$b$ around the perimeter with diagonals
$\{u, v\} = e_{12}$ and $\{a, b\}$.

### Geometric signature

The quad $Q$ has its **two boundary edges on opposite sides**: $e_a$
spans vertices $a$–$u$, $e_b$ spans $v$–$b$, and the quad goes
$a \to u \to v \to b \to a$. Boundary edges are $a$–$u$ and $v$–$b$;
these are *not* adjacent in the quad's perimeter — they are
separated by the other two edges $u$–$v$ (which is interior to the
original mesh but becomes a quad-diagonal after fusion) and $b$–$a$
(which is an interior-of-quad edge after fusion).

Wait — that needs care. After tri2quad fusion the diagonal $\{u,v\}$
is dissolved, and the quad's perimeter is $a$–$u$–$v$–$b$–$a$ with
edges $\{a,u\}, \{u,v\}, \{v,b\}, \{b,a\}$. The edges $\{a,u\}$
and $\{v,b\}$ are the two original boundary edges; they sit on
opposite sides of the quad perimeter. The edges $\{u,v\}$ and
$\{b,a\}$ are quad-interior — $\{u,v\}$ was the original shared
interior edge, $\{b,a\}$ was the non-shared quad-spanning edge.

### Degeneracy criterion

The quad $Q$ is geometrically degenerate when the four vertices
$\{a, u, v, b\}$ are *near-collinear*. The two boundary edges sit on
opposite sides of the quad; if they nearly align (sharing direction
along the original boundary curve), $Q$ collapses into a sliver
oriented along the boundary. Equivalently: when the boundary curve
makes a *small turn* between $e_a$ and $e_b$ and the interior
vertex pair $\{u, v\}$ sits close to the line through $a$ and $b$,
$Q$ is a sliver.

### When does $P$ occur "naturally"?

$P$ occurs whenever the boundary is sampled densely enough that two
adjacent boundary edges fall within an angular tolerance and the
interior triangulation places only one shared interior edge between
the two boundary-attached triangles. On smooth boundaries with $h_0
\to 0$ refinement, the configuration appears at every smooth
boundary arc — it is asymptotically generic.

## 2. Audit of existing mitigations

| Mechanism | Trigger | Action | Effect on $P$ | Rating |
|---|---|---|---|---|
| `_boundary_cleanup` (`admesh/_stages/distmesh.py:333`) | Triangle attached to free-boundary edge with quality $q = \frac{(b+c-a)(c+a-b)(a+b-c)}{abc} < 0.15$. | Drops the triangle. | If either $T_1$ or $T_2$ already has $q < 0.15$, one of them is dropped — $P$ no longer applies because there is no pair. But $P$ usually arises with two reasonably-shaped triangles ($q \in [0.4, 0.7]$); the sliver only appears *after fusion*. | **no effect** |
| `_boundary_density_control` (`admesh/_stages/distmesh.py:412`) | Boundary-attached triangle with $q < 0.2$ during second half of distmesh iterations. | Removes the triangle's interior vertex (i.e. the non-boundary vertex). | Same as above — fires on already-bad triangles, not on the pair pattern. Does not detect the *post-fusion* sliver. | **no effect** |
| `balance_valence_triangles` (`admesh.valence`) | Interior edge whose flip would reduce $|val(\cdot) - 6|$ deficit. | Flips the interior edge. | A flip of $e_{12}$ would replace it with $\{a, b\}$, turning $T_1, T_2$ into $T_1' = \{u, a, b\}, T_2' = \{v, a, b\}$. The new triangles still each touch one boundary edge ($\{u, a\}$ on $T_1'$, $\{v, b\}$ on $T_2'$), and they still share an interior edge ($\{a, b\}$). Predicate $P$ remains satisfied. The configuration is *flip-invariant*. | **no effect** |
| `BalanceConfig.max_valence` (spec 016, in-flight) | Same as above, but reject any flip pushing receiver valence past ceiling. | Adds a rejection clause to the flip gate. | Strictly *additive* rejections on an already-flip-invariant configuration. Cannot break $P$ that was not already broken. | **no effect** |

The result is unambiguous: **no existing ADMESH mechanism breaks
$P$**. Two of the four (`_boundary_cleanup`, `_boundary_density_control`)
fire on a quality threshold that the *triangles themselves* fail, not
on the *post-fusion quad*'s degeneracy. Two of the four
(`balance_valence_triangles`, `max_valence`) operate on interior-edge
flips, but $P$ is flip-invariant under the available flip $e_{12}
\leftrightarrow \{a, b\}$.

## 3. Candidates for upstream prevention

### Candidate 1 — Boundary-edge mid-split at finalization

**Sketch.** After distmesh converges, scan all triangle pairs sharing
an interior edge. For each pair matching $P$, insert a midpoint node
on the *longer* of the two boundary edges. The triangle owning that
boundary edge splits into two; the pair pattern is broken because the
"two adjacent boundary triangles" become "two adjacent boundary
triangles plus one extra" with different adjacency.

**Rating.**

| Axis | Level | Reason |
|---|---|---|
| Coverage | Partial | Eliminates the case in the targeted pair, but the *new* triangle created by the split may itself form a new $P$-pair with the other side. Requires iteration to fixpoint; unbounded in the worst case along a smoothly-curving boundary. |
| Cost | High | Mid-splitting boundary edges adds new nodes — directly violates Constitution Principle I if implemented inside `admesh._stages.boundary` or `distmesh`. Must live in an additive layer, but is hard to keep there because the mesh-size field must be re-honored after each split (chicken-and-egg with `build_h`). |
| Risk | High | Adds nodes after structural-validity gates have passed. Could break spec 009 R4 assertions (mesh area ≥ 95% of source polygon). Could cascade — splitting boundary edge invalidates the existing valence-balance state. |

**Eligible?** No (Cost = High, Risk = High).

### Candidate 2 — Diagonal flip with boundary penalty

**Sketch.** Extend `balance_valence_triangles` (or add a sibling
`balance_boundary_tri_pairs` gate) that detects pairs matching $P$
and attempts to flip $e_{12}$ to $\{a, b\}$ *unconditionally* (not
gated on valence improvement).

**Rating.**

| Axis | Level | Reason |
|---|---|---|
| Coverage | Incidental | $P$ is flip-invariant — see §2's audit of `balance_valence_triangles`. The flip changes which vertices are shared, but the predicate still holds. The "fix" is a no-op for the configuration's downstream degeneracy. |
| Cost | Low | Single-function change in `admesh/valence.py`. |
| Risk | Med | Unconditional flips bypass the valence-improvement check; can push valence out of the equilateral-ideal zone, regressing `tests/test_valence.py`. |

**Eligible?** No (Coverage = Incidental).

### Candidate 3 — Pre-quad-prep gate inside `admesh/quad_prep.py`

**Sketch.** Add a defensive step at the *end* of
`smooth_for_quadrangulation` that detects $P$-pairs and either
(a) drops one of the two triangles, leaving a notch in the boundary
that CHILmesh's tri2quad fusion handles, or (b) inserts a midpoint
node on one boundary edge (i.e. Candidate 1 scoped to the additive
layer).

**Rating.**

| Axis | Level | Reason |
|---|---|---|
| Coverage | Partial | Same fundamental limit as Candidate 1 — the split cascades along smooth boundary arcs. Variant (a) — drop one triangle — leaves a hole in the mesh, structurally invalid. |
| Cost | Med | Lives in `admesh/quad_prep.py`, additive layer; clean against Constitution Principle I. |
| Risk | Med | `quad_prep` is the ADMESH gift to downstream tri2quad consumers. A defensive gate here changes its output contract; downstream consumers (CHILmesh + others) would need to know whether the gate ran. |

**Eligible?** Barely — Coverage = Partial is the threshold. Cost +
Risk are both acceptable.

**Subtlety.** Even with a Partial coverage label, the *value* of
this gate is low: CHILmesh's planned post-admesh protocol must
already handle $P$-pairs (because not every ADMESH consumer runs
`quad_prep` — the consumer may use `triangulate()` output directly).
A defensive gate in `quad_prep` does not relieve CHILmesh of the
duty to detect $P$ post-hoc; it only reduces the count CHILmesh
sees on `quad_prep`-prepared meshes.

### Candidate 4 — Do nothing in ADMESH; defer to CHILmesh

**Sketch.** ADMESH ships output that may contain $P$-pairs. CHILmesh's
post-admesh protocol detects $P$ on the input mesh (before
tri2quad fusion) and either (a) splits one boundary edge, or (b)
declines to fuse the pair into a quad.

**Rating.**

| Axis | Level | Reason |
|---|---|---|
| Coverage | Full | The post-admesh layer sees every input mesh, regardless of origin. |
| Cost | Low | Pure CHILmesh work; zero ADMESH change. |
| Risk | Low | ADR-001 already settles that tri2quad fusion lives in CHILmesh. The protocol is on the side that performs the fusion. |

**Eligible?** Yes (and the cost/risk is on the CHILmesh side, not
ADMESH's). This is the **inherent** disposition.

### Summary table

| # | Candidate | Coverage | Cost | Risk | Eligible? |
|---|---|---|---|---|---|
| 1 | Boundary-edge mid-split at finalization | Partial | High | High | No |
| 2 | Diagonal flip with boundary penalty | Incidental | Low | Med | No |
| 3 | Pre-quad-prep gate in `quad_prep.py` | Partial | Med | Med | Marginal — see subtlety |
| 4 | Do nothing in ADMESH; defer to CHILmesh | Full | Low (zero in ADMESH) | Low | **Yes** |

## 4. Disposition

**Disposition:** **inherent**.

The boundary tri-pair configuration $P$ is *flip-invariant* under
ADMESH's available interior-edge flip operations and arises
asymptotically on any smooth boundary as $h_0 \to 0$. No upstream
candidate clears the rubric:

- Candidate 1 (mid-split) is High-cost AND High-risk and only
  Partial-coverage (cascades along smooth arcs).
- Candidate 2 (flip-with-boundary-penalty) is Incidental-coverage
  because $P$ is flip-invariant.
- Candidate 3 (pre-quad-prep gate) is *marginally* eligible but
  contributes no real coverage that CHILmesh's protocol doesn't
  already need to provide for non-`quad_prep` consumers. Filing an
  ADMESH follow-up on Candidate 3 would create work that duplicates
  the canonical CHILmesh fix without obviating it.
- Candidate 4 (do nothing in ADMESH) is the canonical fix and aligns
  with ADR-001's settled boundary: tri2quad fusion lives in CHILmesh,
  therefore the configuration that is *only relevant to tri2quad
  fusion* should be detected on the fusion side.

CHILmesh's planned post-admesh protocol is the canonical fix. This
ADMESH tracker (#85) can close once the CHILmesh issue ships, per
the suggestion in the issue body.

### No follow-up ADMESH issue filed

Per the disposition contract in plan.md §4, **inherent** means no
follow-up ADMESH issue is filed. ADMESH's contribution to mitigating
$P$ is constrained to documentation: this investigation, the
disposition comment on #85, and the spec-016 interaction note in §5.

## 5. Interaction with spec 016 (max-valence)

**Does `max_valence` change the frequency of $P$?** No. The audit
in §2 establishes that $P$ is flip-invariant under
`balance_valence_triangles`; `max_valence` adds *rejections* to that
flip gate, which can only *reduce* the number of flips, not increase
them. The configuration cannot be eliminated by reducing flip count.

**Recommended `max_valence` value when ADMESH feeds CHILmesh
tri2quad?** `None`. The default (no upper bound) is the recommended
value. There is no value of `max_valence` that mitigates $P$;
choosing a non-default value to "help" with $P$ would be cargo-cult.

**`docs/PORTING_NOTES.md` entry for spec 016 implementer to copy:**

```
Spec 016 (max-valence) does not affect boundary tri-pair degeneracy
described by issue #85. Configuration P (two boundary-attached
triangles sharing an interior edge) is flip-invariant under the
available interior-edge flip; max_valence only adds flip rejections
and cannot eliminate P. See specs/018-boundary-tri-pair-degeneracy/
investigation.md §5 for details. Disposition for #85 was "inherent"
(CHILmesh post-admesh protocol is the canonical fix).
```

## 6. References

- Issue #85 — cross-repo tracker that prompted this investigation.
- Spec 015 — chilmesh overlap analysis, established ADR-001.
- Spec 016 — user-configurable max-valence, the in-flight valence work.
- ADR-001 (`docs/adr/ADR-001-chilmesh-boundary.md`) — the cross-repo
  boundary that puts tri2quad fusion on the CHILmesh side.
- `admesh/_stages/distmesh.py:333` — `_boundary_cleanup`.
- `admesh/_stages/distmesh.py:412` — `_boundary_density_control`.
- `admesh/valence.py` — `balance_valence_triangles`, `BalanceConfig`.
