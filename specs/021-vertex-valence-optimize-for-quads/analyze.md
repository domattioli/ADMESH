# Analyze — 021 Quad-Intent Triangulation

Phase 5 of the speckit workflow. Cross-artifact consistency check across `spec.md`,
`clarify.md`, `plan.md`, `tasks.md` before `/implement`. Surfaces gaps, conflicts, and the
go/no-go feasibility verdict.

---

## 1. Requirement → Task coverage matrix

| Req | Covered by | Status |
|---|---|---|
| FR-001 opt-in flag | T-002 | ✅ |
| FR-002 default unchanged | T-004 | ✅ regression-locked |
| FR-003 additive module | T-001, T-005 | ✅ |
| FR-004 ideal-8 + parity | T-010, T-011, T-012 | ✅ |
| FR-005 boundary pinned/excluded | T-012 (reuse `_boundary_mask`) | ✅ |
| FR-006 quality floor | T-041, T-042 | ✅ |
| FR-007 fidelity cap | T-020 (√2 cap), T-022 (gate) | ✅ |
| FR-008 diagnostics | T-013 | ✅ |
| FR-009 no skeletonization | T-020 (SDF-gradient only) | ✅ |
| SC-001 default byte-identical | T-004 | ✅ |
| SC-002 pct_even margin | T-014, T-023, T-024(gate) | ⚠️ margin provisional until T-024 |
| SC-003 mean\|v-8\| down | T-014 | ✅ |
| SC-004 fidelity ≥90% | T-022, T-023 | ✅ |
| SC-005 quality gate | T-042 | ✅ |
| SC-006 no locked edits | T-005 | ✅ |

**No orphan requirements; no orphan tasks.** Every FR/SC maps to ≥1 task and vice versa.

## 2. Conflicts & how they resolve
- **C-A (task wording vs Constitution)**: "modify the PRIMARY algorithm" vs locked `distmesh.py`.
  Resolved by C-1/plan §1: a *parallel* primary loop in a new module — it is primary (a
  generator, not a post-pass) AND additive. The phrase "not a bolt-on post-process" is honored
  because the V=8 bias acts *during* equilibrium/topology, not after a finished mesh. The
  optional `quad_prep` finish (T-040) is a relax step *inside* the loop, not the mechanism.
- **C-B (V=8 vs fidelity)**: spec §7 proves the tension is real but bounded; the √2 anisotropy
  cap + 90% in-band gate resolve it. Quantified, not hand-waved.
- **C-C ("quad-ready" needs QuADMESH layers)**: spec §6 downgrades the promise from *guarantee*
  to *bias* and keeps the true skel→topo→geo feedback loop in QuADMESH. This is the single most
  important scoping decision and it removes the otherwise-circular dependency.

## 3. Gaps / risks flagged for operator
1. **Acceptance margin (C-4/SC-002)** is a guess until the QuADMESH#63 Phase-1 quadability
   profile runs on real ADMESH output. T-024 is a hard GATE. **Do not lock SC-002 numbers
   before that measurement.** This is an external dependency (QuADMESH#63 + ADMESH-Domains#84
   quality-CI harness).
2. **Seeding question** (deferred in clarify): does the quad-intent loop seed from the
   equilateral lattice (`distmesh.py:75–94`) or a right-iso/square lattice? A square seed may
   reach V=8 far faster. Recommend a 1-day research spike at the start of P2. Not blocking P0/P1.
3. **Lever 4 (energy penalty)** intentionally dropped from committed scope — overlaps levers
   1+3 and risks fidelity. Revisit only if P1–P3 plateau.
4. **spec-016 coupling (C-9)** — confirm sequencing so the `max_valence` field isn't authored twice.

## 4. Feasibility verdict (answers the task's item-5 gate)
**`--quad-intent` IS feasible inside ADMESH — as a statistical bias, not a per-layer guarantee.**
- Cheap layer-direction proxy (SDF gradient) exists and is already computed → anisotropy can be
  oriented without skeletonization. ✅
- Existing additive machinery (`valence.py` flips, `quad_prep.py` right-iso SVD) does ~70% of the
  work; this feature re-targets + fuses it. ✅
- The fidelity tension is bounded by the √2 anisotropy cap (math in §7). ✅
- True OE/IE alternation remains topology-determined and per-layer → stays in QuADMESH's feedback
  loop. ADMESH delivers a *better-conditioned seed*, which is exactly what QuADMESH#63's
  architecture diagram asks of the `[gen]` stage. ✅

**No-go conditions** (would kill or reshape the feature): (a) if T-024 shows ADMESH output is
*already* mostly even/quad-ready → preprocessing wrapper suffices, no new loop needed; (b) if the
SDF-gradient layer proxy correlates poorly with real CHILmesh layers → anisotropy orientation is
worthless and the feature degrades to lever-3 flips only.

## 5. Constitution & policy re-check
- Principle I: PASS (additive; T-005 guards). Branch: operator-sanctioned override (explicit).
- Coding dispatch: implementation tasks → Haiku subagent; spec phase stayed on main session. ✅

## 6. Recommendation
**Proceed to `/implement` for P0 + P1 only** (regression lock + lever-3 flips + diagnostics),
which is low-risk, byte-safe on the default path, and immediately measurable. **Hold P2
(anisotropy) behind the T-024 quadability-baseline GATE** and operator `[CONFIRM]` on C-1, C-2,
C-4, C-9. P3 is conditional on P1+P2 results.
