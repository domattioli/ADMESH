# Spec 018 — Boundary Tri-Pair Degeneracy Investigation (tracks #85)

**Status:** Planning-phase only. No code shipping.
**Issue:** [#85 Cross-repo tracker: boundary tri-pair degeneracy (CHILmesh-side post-admesh protocol)](https://github.com/domattioli/ADMESH/issues/85)
**Branch:** `daily-maintenance`
**Token budget:** SMALL (analytical investigation + disposition write-up; no fixtures generated, no code in `admesh/`).

---

## 1. Problem statement

CHILmesh is scoping a post-admesh protocol to detect and mitigate the
following failure mode in ADMESH output:

> Two adjacent boundary triangles each have one edge on the boundary
> and share an interior edge with the other. If a downstream quad-merge
> pass fuses them into a quad, the resulting quad has two edges on the
> boundary and is geometrically prone to degeneracy (near-zero area,
> near-collinear, sliver).

Issue #85 asks whether this configuration is **preventable upstream
in ADMESH**, or whether it is an **inherent consequence** of the
boundary triangulation pattern and therefore belongs to CHILmesh's
post-admesh protocol.

The cross-repo seam is settled by ADR-001
(`docs/adr/ADR-001-chilmesh-boundary.md`): tri-to-quad fusion lives
in CHILmesh, not ADMESH. ADMESH's question is narrower — can a
small, additive change inside ADMESH eliminate the configuration at
its source, sparing CHILmesh from having to detect it after the fact.

## 2. Scope

In-scope (planning phase, this spec):

1. **Formalize** the offending configuration as a graph-theoretic
   predicate on a tri-mesh: a pair of triangles $T_1, T_2$ that share
   an interior edge, where each triangle has exactly one edge in the
   free-boundary edge set.
2. **Audit** ADMESH's existing boundary-quality machinery for
   incidental mitigations:
   - `admesh._stages.distmesh._boundary_cleanup` (quality<0.15 sliver
     drop on boundary-adjacent triangles).
   - `admesh._stages.distmesh._boundary_density_control` (interior-
     vertex removal on boundary-adjacent triangles with q<0.2).
   - `admesh.valence.balance_valence_triangles` (interior edge flips
     toward `ideal_valence=6`).
   - The pending `BalanceConfig.max_valence` field (spec 016).
3. **Enumerate** the upstream-prevention candidates and evaluate each
   on three axes:
   - **Coverage**: does it eliminate the configuration in all cases
     it occurs, or only some?
   - **Cost**: does it touch a faithful-port stage module
     (Constitution Principle I — locked), an additive layer module,
     or only a new module?
   - **Risk**: does it move quality elsewhere (e.g. introduce a
     different degeneracy, regress a structural-validity test)?
4. **Reach a disposition** for the cross-repo tracker:
   - **Preventable**: ADMESH can mitigate at source with a bounded
     change. A follow-up implementation issue is filed; CHILmesh's
     post-admesh protocol becomes a defense-in-depth layer, not a
     primary fix.
   - **Inherent**: ADMESH cannot mitigate without unacceptable cost.
     CHILmesh's post-admesh protocol is the canonical fix; this
     tracker closes once the CHILmesh issue ships.
5. **Cross-check spec 016 incidentally**: does
   `BalanceConfig.max_valence` (the in-flight flip-gate from spec
   016) reduce the configuration's frequency? Document the answer so
   the spec 016 implementer can drop a one-line note in the porting
   record.

Out-of-scope (deferred or never):

- Writing any production code in `admesh/`. ADMESH profile blocks code
  shipping this session.
- Running new MATLAB fixtures or modifying `scripts/export_matlab_fixtures.m`.
- Designing the CHILmesh-side post-admesh protocol (CHILmesh owns
  that work).
- Implementing any candidate mitigation (deferred to a follow-up
  issue if the disposition is **preventable**).
- Adding a new `min_q` or sliver-detection gate to
  `tests/test_default_size_field.py`.

## 3. Acceptance criteria

- [ ] `specs/018-boundary-tri-pair-degeneracy/investigation.md`
      defines the configuration as a predicate, audits the four
      existing mitigations, enumerates ≥3 candidate upstream
      preventions, and rates each on **coverage / cost / risk**.
- [ ] `investigation.md` reaches one of two dispositions
      (**preventable** or **inherent**) with the evidence summarized
      in a single labeled paragraph.
- [ ] If **preventable**: a follow-up implementation issue is filed
      on `domattioli/ADMESH` capturing the recommended candidate and
      labeled `planning-required`, `cross-repo`, `enhancement`.
- [ ] If **inherent**: a closing-disposition comment is posted on
      issue #85 stating the configuration is inherent and pointing
      CHILmesh at the post-admesh protocol as the canonical fix.
- [ ] Either way, a status comment lands on #85 linking
      `investigation.md` and naming the disposition.
- [ ] Spec 016's `max_valence` interaction with the configuration is
      explicitly recorded (one short paragraph in `investigation.md`).
- [ ] No code added or modified under `admesh/` or `tests/`.

## 4. Files to create / modify

**Create:**
- `specs/018-boundary-tri-pair-degeneracy/spec.md` (this file)
- `specs/018-boundary-tri-pair-degeneracy/plan.md` — investigation workflow
- `specs/018-boundary-tri-pair-degeneracy/tasks.md` — atomic task decomposition
- `specs/018-boundary-tri-pair-degeneracy/investigation.md` — the analytical deliverable

**Modify (doc-only, light touch):**
- None expected. Cross-references in existing docs (CLAUDE.md, ADR-001)
  remain authoritative and need no edit unless the disposition
  reshapes the boundary recorded by ADR-001 — it does not (this
  investigation operates inside the boundary, not on it).

**Do NOT modify (planning phase):**
- Any file in `admesh/` (no code moves).
- Any file in `tests/`.
- `scripts/export_matlab_fixtures.m` (no new MATLAB fixtures).
- `docs/adr/ADR-001-chilmesh-boundary.md` (boundary stays where it stands).

## 5. Cross-repo touchpoints

- **CHILmesh** owns the post-admesh protocol for the failure mode
  named in #85. This spec produces a disposition that informs whether
  the CHILmesh issue (once filed) is the canonical fix or a
  defense-in-depth layer.
- **Spec 016** (max-valence) is the closest in-flight ADMESH work
  that touches the same plumbing. Investigation must record whether
  spec 016's flip-gate incidentally mitigates the configuration.
- **ADR-001** is unaffected. The disposition lands inside the
  generator side; no module moves across the seam.

## 6. Risks

| Risk | Mitigation |
|---|---|
| Investigation declares the configuration "preventable" but the recommended candidate is found to be expensive or regressive at implementation time. | Disposition includes coverage / cost / risk rating; implementation issue is a *recommendation*, not a binding contract. Implementer may downgrade to **inherent** with new evidence and reopen #85. |
| Investigation relies on intuition rather than counts on real fixtures. | Investigation is explicitly analytical; empirical counts are listed as a follow-up task under tasks.md, not a prerequisite for this spec. The disposition states its evidence basis explicitly. |
| Spec 016 lands `max_valence` independently and changes the picture. | Investigation pins spec 016's contribution (or non-contribution) in a single labeled paragraph; spec 016's implementer adds a one-line PORTING_NOTES.md entry citing this investigation. |
| Wrong call (declares preventable, isn't) wastes downstream cycles. | Disposition is reversible: filing a new "actually inherent" issue is cheap; ADR-001 is not amended; CHILmesh work is not blocked. |

## 7. Token budget

SMALL. Single investigation doc, no fixtures, no code, no tests. Per
ADMESH profile (planning only), this spec produces docs + a follow-up
issue (if applicable) + a comment on #85.
