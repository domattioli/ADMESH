# Implementation Plan — 021 Quad-Intent Triangulation

Phase 3 of the speckit workflow. Translates `spec.md` + `clarify.md` into an architecture and
phased build order. **No production code is written in this spec phase** — this is the design.

---

## 1. Architecture

```
admesh/api.py::triangulate(domain, *, quad_intent=False, quad_config=None, ...)
        │
        ├─ quad_intent is False  ─────────────►  admesh._stages.distmesh.distmesh2d   (LOCKED, untouched)
        │
        └─ quad_intent is True   ─────────────►  admesh.quad_intent.distmesh2d_quad   (NEW additive module)
                                                        │  composes (imports, never edits):
                                                        ├─ _stages.distmesh._delaunay, fixmesh, _boundary_cleanup
                                                        ├─ _stages.mesh_size  (h field + ∇ for anisotropy)
                                                        ├─ _stages.distance   (SDF, ∇ for layer direction)
                                                        ├─ _stages.quality    (right_iso_quality, mesh_quality)
                                                        ├─ valence            (compute_valence, balance loop, ideal=8)
                                                        └─ quad_prep          (right-iso SVD smoother, optional finish)
```

### New module: `admesh/quad_intent.py` (additive layer)
- `distmesh2d_quad(...)` — the parallel quad-intent generation loop.
- `QuadIntentConfig` dataclass.
- `LocalMetric` helper — builds `M(x)` (anisotropic rest-length tensor) from SDF gradient.
- `quadability_report(mesh, h)` — diagnostics (FR-008).

### New tests: `tests/test_quad_intent.py`
- Regression lock: default path byte-identical (SC-001, SC-006).
- Valence-shift assertions (SC-002/003), fidelity gate (SC-004), quality gate (SC-005).

---

## 2. The quad-intent loop (design, not code)

Mirrors `distmesh2d` structure (`distmesh.py:200–271`) with four divergences:

1. **Rest-length → anisotropic** (lever 1). Replace
   `L0 = hbars*Fscale*norm` (scalar, `distmesh.py:224`) with a metric-aware length:
   `L0_dir = Fscale * sqrt(barvecᵀ M(midpoint) barvec)` normalized as before. `M(x)` is SPD,
   eigenvector `e₁ = rot90(∇fd/|∇fd|)` (tangent to boundary-distance contour = approx layer
   direction, C-5), eigenvalues `(λ, λ/ratio)` with `ratio ≤ √2` (C-6). Interior only; near
   boundary `M → isotropic` (ratio→1) to avoid fighting pinned nodes.
2. **Topology → valence-aware flips** (lever 3, MVP). After each retri, run a re-targeted
   `valence.balance_valence_triangles` with `BalanceConfig(ideal_valence=8, max_valence=…)`
   plus an even-parity reward (C-3). This is the cheapest, highest-confidence lever.
3. **Insert/delete on parity** (lever 2, Phase 3). Extend the density-control idea: insert at
   an odd interior vertex's largest incident edge to raise valence; merge to lower. Gated by
   the fidelity bound (FR-007) so inserts respect `h`.
4. **Geometry finish** (optional). Run `quad_prep.smooth_for_quadrangulation` as the final
   relax with `pair_hint=True`, `h` passed through — it already does right-iso SVD targeting
   and boundary pinning. This makes the loop end in a right-iso-biased state.

Boundary/`pfix` handling copied verbatim from the locked loop's contract (prepend, force-zero,
exclude from convergence + from the V=8 objective) — see spec §5.

### Convergence & quality safety
- Same `dptol`/`ttol` displacement criterion.
- Best-quality tracking (C-7) — retain best mesh by `mesh_quality`, fall back + warn if final
  below `min_q=0.30`.

---

## 3. Fidelity enforcement (FR-007, spec §7)
After every move-type, recompute `r = |edge|/h_local` per edge. Reject/relax any move that
drops the in-band fraction below 90% or pushes an edge outside `[0.7, 1.4]`. The √2 anisotropy
cap (C-6) is the structural guarantee; this gate is the runtime backstop. `h` is interpreted as
the **hypotenuse/diagonal** length so legs land at ~0.707 (lower bound), per §7 derivation.

## 4. Data structures
```python
@dataclass
class QuadIntentConfig:
    ideal_valence: int = 8
    max_valence: int | None = 10        # spec-016 ceiling; None = no cap
    even_parity_weight: float = 1.0     # β (C-3)
    valence_target_weight: float = 0.1  # α (C-3)
    anisotropy: bool = True
    anisotropy_ratio: float = 1.4142136 # ≤ √2 enforced (C-6)
    fidelity_band: tuple[float, float] = (0.7, 1.4)  # FR-007
    fidelity_min_fraction: float = 0.9
    max_insert_per_pass: int = 0        # 0 until Phase 3 lever
    run_quad_prep_finish: bool = True
```

## 5. Build phases (map to Tasks)
- **P0 — Scaffolding + regression lock**: module skeleton, `triangulate(quad_intent=…)` dispatch
  that (initially) just calls the locked loop; regression test proving default unchanged.
- **P1 — Lever 3 (flips, MVP)**: re-targeted valence balancing at ideal 8 + parity; diagnostics
  (`quadability_report`); SC-002/003 assertions.
- **P2 — Lever 1 (anisotropy)**: `LocalMetric` from SDF gradient; anisotropic rest-length;
  fidelity gate (SC-004). Re-baseline acceptance margins (C-4) against QuADMESH#63 profile.
- **P3 — Lever 2 (parity insert/delete)**: optional, gated; only if P1+P2 fall short of SC-002.
- **P4 — Geometry finish + hardening**: wire `quad_prep` finish, best-quality fallback (C-7),
  quality gate (SC-005), docs + `PORTING_NOTES.md`/`docs` update.

## 6. Risks & mitigations
| Risk | Mitigation |
|---|---|
| Principle-I violation if loop drifts into locked module | New module only; CI grep guard on `_stages/*` diff (SC-006). |
| V=8 fights size-function fidelity | √2 anisotropy cap + 90% in-band gate (§7, FR-007). |
| "Quad-ready" unmeasurable without QuADMESH layers | Bias-not-guarantee scope (§6); SDF-gradient proxy; defer true loop to QuADMESH. |
| Acceptance margins guessed | Gate P2 sign-off on QuADMESH#63 quadability baseline (C-4). |
| Quality regression | Best-quality tracking + fallback (C-7); reuse existing quality gate. |
| spec-016 not landed | Co-develop the single `max_valence` field (C-9). |

## 7. Out of scope (restated)
No edits to locked stages; no CHILmesh dependency; no boundary insertion/local-remesh (QuADMESH
owns it); no C++/Numba acceleration (Python reference first); no per-layer OE/IE guarantee.

## 8. Constitution check
- Principle I (faithful port): **PASS** — additive module, zero locked-stage edits (gated by CI).
- Additive-layer rule (CLAUDE.md): **PASS** — composes stages, never reverse.
- Branch policy: operator-sanctioned branch name overrides NNN-<short> convention (explicit).
- Coding-dispatch policy: implementation tasks dispatch to a Haiku subagent; this spec phase
  (docs only) stays on the main session.
