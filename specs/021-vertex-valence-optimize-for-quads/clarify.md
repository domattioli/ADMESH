# Clarify — 021 Quad-Intent Triangulation

Phase 2 of the speckit workflow. Resolves ambiguities in `spec.md` before planning.
Each item: **Q** (question) → **Options** → **Resolution** (proposed default; flagged
`[CONFIRM]` where it needs operator sign-off before `/implement`).

---

## C-1 — Where does the V=8 bias live, given Constitution Principle I?
**Q**: The task says modify "the PRIMARY algorithm … not a bolt-on post-process," but
`distmesh.py` is a locked faithful-port module. How do we reconcile?

**Options**:
- (a) Principle-I exception: edit `distmesh.py` in place with a `quad_intent` branch.
- (b) New additive module `admesh/quad_intent.py` owning its OWN truss loop (forked from
  the distmesh structure but free to diverge), dispatched by `triangulate()`.
- (c) Pure post-process (rejected by the task — "not a bolt-on").

**Resolution**: **(b)**. It satisfies "primary algorithm" (it IS a generation loop, not a
post-pass on a finished mesh) while keeping the locked module byte-identical (FR-002, SC-006).
The locked loop's force/projection/retri code is *reimplemented* in the new module so the
two evolve independently. `_delaunay`, `fixmesh`, `mesh_size`, `quality`, `valence`, `quad_prep`
are imported and reused. `[CONFIRM]` — this is the central architectural call.

## C-2 — Which of the four valence levers do we commit to (and in what order)?
**Q**: Anisotropic rest-length, insert/delete, edge-flip re-target, energy penalty — all four,
or a subset?

**Resolution** (phased, cheapest-first):
1. **Edge-flip re-target** (lever 3) — reuse `valence.py` with `ideal_valence=8` + even-parity
   reward. Lowest risk, existing code. **MVP.**
2. **Anisotropic rest-length** (lever 1) — `M(x)` from SDF gradient. Highest leverage on native
   V=8, justified by §7 fidelity math. **Phase 2.**
3. **Valence-parity insert/delete** (lever 2) — extend density control to key on parity, not
   just quality. **Phase 3.**
4. **Energy penalty term** (lever 4) — deferred; overlaps with (1)+(3) and risks fidelity.
   **Stretch / may drop.**

`[CONFIRM]` whether MVP = lever 3 only, or lever 3 + lever 1 together.

## C-3 — Even-parity vs strict-8 objective weighting?
**Q**: QuADMESH#63 says "even valence strongly preferred; V=8 ideal." Is the objective
`|v-8|` (strict) or a two-term `α·|v-8| + β·(v odd ? 1 : 0)` (parity-weighted)?

**Resolution**: Two-term with parity dominant — `β >> α`. Rationale: an even V=6 or V=10
interior vertex is quad-mergeable (no singularity); an odd V=7 is always a defect. So reward
evenness first, nudge toward 8 second. Default `β=1.0, α=0.1`. `[CONFIRM]` weights.

## C-4 — Target margin for SC-002 (how much must `pct_even` improve)?
**Q**: Spec leaves the numeric target to Clarify.

**Resolution**: Proposed acceptance: `pct_even_interior` improves by **≥15 absolute
percentage points** vs default on ≥3 MVP domains, OR reaches **≥75%** even. These are
provisional — they MUST be re-baselined against the QuADMESH#63 "quadability profile" run
on real ADMESH output before locking (that measurement is QuADMESH#63 Phase 1, a dependency).
`[CONFIRM]` after baseline numbers exist.

## C-5 — Layer-direction approximation: SDF gradient only?
**Q**: §6 commits to approximating layer direction from the SDF (no skeletonization). Confirm
no CHILmesh dependency is introduced.

**Resolution**: Yes — anisotropy eigenvector = unit tangent to the boundary-distance iso-contour
= rotate ∇(signed distance) by 90°. The distance field and its gradient are already available
(`distance.py`, `mesh_size.py` Eikonal). NO CHILmesh import in ADMESH. The true
skel→topo→geo feedback loop stays in QuADMESH (QuADMESH#63). Confirmed direction.

## C-6 — Anisotropy ratio cap?
**Q**: §7 shows ratio ~√2 keeps fidelity in `[0.7,1.4]`; beyond that it breaks.

**Resolution**: Hard-cap eigenvalue ratio at **√2 ≈ 1.414** by default, exposed as
`QuadIntentConfig.anisotropy_ratio` (default 1.414, max-enforced). FR-007 fidelity gate is the
backstop. `[CONFIRM]` default ratio.

## C-7 — Fallback behavior if quad-intent degrades quality below the gate?
**Q**: FR-006 says reach quality floor "else falls back / warns." Which?

**Resolution**: Track best-quality mesh across passes (same pattern as the ADMESH-variant loop,
`distmesh.py:808–813`); if final quad-intent mesh is below `min_q=0.30`, emit a warning and
return the best-quality intermediate. Never silently return a degenerate mesh. `[CONFIRM]`.

## C-8 — API surface: bool flag or enum?
**Q**: `quad_intent: bool` vs `intent: Literal["equilateral","quad"]`.

**Resolution**: Start with `quad_intent: bool = False` (matches the task's `--quad-intent`
wording and is the smallest surface). Internally route to QuadIntentConfig. Can widen to an
enum later without breaking the bool. `[CONFIRM]`.

## C-9 — Does spec 016 (`max_valence`) need to land first?
**Q**: This feature reuses `BalanceConfig.max_valence`.

**Resolution**: Soft dependency. If spec 016 hasn't shipped, co-develop the one-field addition
here (it's a single dataclass field + gate condition). Note the coupling in Plan. `[CONFIRM]`
sequencing with operator.

---

## Open questions deferred to Plan/Tasks (not blocking)
- Exact `QuadIntentConfig` field list and defaults → Plan.
- Whether the quad-intent loop seeds from the equilateral lattice or a right-iso lattice
  (`distmesh.py:75–94` builds equilateral) → Plan / research spike.
- Numba/C++ acceleration → explicitly deferred (spec §8).

## Items requiring operator confirmation before `/implement`
C-1 (architecture), C-2 (lever scope of MVP), C-4 (acceptance margin pending baseline),
C-9 (spec-016 sequencing). All others have safe proposed defaults.
