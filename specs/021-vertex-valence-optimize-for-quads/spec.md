# Feature Specification: Quad-Intent Triangulation (V=8 / Even Interior Valence)

**Feature Branch**: `vertex-valence-optimize-for-quads`
**Spec ID**: 021
**Created**: 2026-05-31
**Status**: Draft (investigation — NO production code in this spec)
**Operator sanction**: Explicitly authorized by @domattioli (branch name set by operator).
**Upstream theory**: [QuADMESH#63](https://github.com/domattioli/QuADMESH/issues/63) — V=6 vs V=8 lattice mismatch.
**Related ADMESH work**: spec 004 (`quad_prep.py` right-isoceles smoother), spec 016 (`max_valence` ceiling in `valence.py`).

**Input**: "Modify ADMESH's PRIMARY mesh-generation algorithm (the truss / force-equilibrium loop) to optimize interior vertex valence toward V=8 / even, producing a triangulation that is natively quad-ready, behind an opt-in flag (`--quad-intent`) so default equilateral behavior is unchanged. Perhaps the truss solver could optimize toward right-isosceles triangles."

---

## 1. Problem Statement

ADMESH's distmesh-style truss solver (`admesh/_stages/distmesh.py`) relaxes nodes
toward force equilibrium under isotropic spring rest-lengths derived from the size
function `h(x,y)`. The equilibrium of an isotropic truss is the **equilateral**
triangulation, which drives interior vertex valence toward **V≈6** (the Delaunay /
equilateral lattice).

The downstream consumer QuADMESH+ fuses triangle pairs into quads. Its ideal is the
opposite lattice: interior valence **V≈8** (four quad-pairs around each interior
vertex, the right-isosceles grid lattice). Per QuADMESH#63, this is a **topological
lattice mismatch**, not a collection of local geometric defects — and no amount of
post-hoc smoothing/flipping changes the global valence distribution. Every odd-valence
interior vertex forces a quad singularity.

This spec investigates whether ADMESH can *natively* produce a V=8-biased / even-valence
triangulation by biasing the **primary** generation loop (not a bolt-on post-process),
exposed behind an opt-in `quad_intent` flag that leaves default behavior byte-identical.

### 1.1 The Hard Constraint (Constitution Principle I)

`distmesh.py` is **stage 10 of the 13 locked faithful-port modules** (CLAUDE.md,
`CONSTITUTION.md` Article II). It MUST stay numerically identical to the MATLAB
reference at `19b2eb9`. **Biasing the truss loop in-place would violate Principle I.**

Therefore this feature CANNOT edit the locked loop. The investigation must answer
*how* to bias "the primary algorithm" without mutating the locked module — see
the Clarify and Plan phases. The leading candidate is an **additive parallel
quad-intent solver** (a new module, e.g. `admesh/quad_intent.py`) that the public
`triangulate()` dispatches to when `quad_intent=True`, reusing the locked stages
(`_delaunay`, `fixmesh`, `mesh_size`, `quality`) as building blocks but owning its
own force/topology loop. The default path remains the untouched locked loop.

---

## 2. Investigation Findings (code map)

These are the levers the algorithm exposes today, with exact locations.

### 2.1 Core truss / equilibrium loop
| Component | File | Lines |
|---|---|---|
| Canonical loop | `admesh/_stages/distmesh.py` | 200–271 |
| ADMESH-variant loop | `admesh/_stages/distmesh.py` | 735–814 |
| Rest-length (`L0`) + force | `distmesh.py` | 214–233 (216: `hbars`; 224: `L0`; 225: `F=max(L0-L,0)`) |
| C++ hot path | `admesh/_cpp/distmesh_cpp.cpp` | 29–85 |
| Boundary projection | `distmesh.py` | 235–248, 573–595 |
| Re-Delaunay trigger | `distmesh.py` | 202–209, 280–283 |
| Fixed-point (`pfix`) handling | `distmesh.py` | 180–192 (prepend), 231–232 (force-zero) |
| Size function `h` build/eval | `admesh/_stages/mesh_size.py` | 178–349; eval at `distmesh.py:216` |
| Gradient limiter (Eikonal, `\|∇h\|≤g`) | `mesh_size.py` | 52–169 |

### 2.2 Topology operations
| Operation | File | Lines | Notes |
|---|---|---|---|
| Delaunay retri | `distmesh.py` | 43–54, 205–209 | Triangle lib or QHull; empty-circle test only |
| Density delete (boundary) | `distmesh.py` | 450–518 | Removes interior verts of poor free-boundary tris |
| Density delete (constraint) | `distmesh.py` | 521–570 | Removes points near constraint strips |
| Boundary cleanup | `distmesh.py` | 371–447 | Sliver removal |
| **Edge flips (valence)** | `admesh/valence.py` | 94–204 | `balance_valence_triangles`, additive, toward ideal 6 |
| Valence compute | `admesh/valence.py` | 48–66 | `compute_valence` (element-star count) |
| Right-iso smoother | `admesh/quad_prep.py` | 57–140 | `smooth_for_quadrangulation` (SVD target-Jacobian, additive) |

**Key existing asset**: `valence.py` already implements a valence-deficit edge-flip
loop with a quality gate, and spec 016 adds a `max_valence` ceiling. `quad_prep.py`
already does right-isoceles geometry via per-element SVD target-Jacobian with optional
longest-edge pairing hints and `h`-tracking. **This feature largely re-targets and
fuses existing additive machinery rather than inventing from scratch.**

### 2.3 The four valence levers (from the task)
1. **Anisotropic rest-length** — replace scalar `hbars` with a 2×2 local metric tensor
   `M(x)` so springs are shorter along the layer-propagation direction and longer
   transverse → elongated triangles that pair into squares. (New; locked loop is isotropic.)
2. **Insertion/deletion criteria** — raise an odd interior vertex toward even by inserting,
   or lower by merging. Existing density-control only keys on *quality*, not *valence parity*.
3. **Edge-flip acceptance** — `valence.py` already flips on valence-deficit vs ideal 6.
   Re-target to ideal **8** + reward **even** parity (deficit term + parity penalty).
4. **Energy functional penalty** — add a valence-deviation term to the force/energy so
   equilibrium itself prefers V=8. (New; would live in the parallel solver.)

---

## 3. User Scenarios & Testing

### User Story 1 — Opt-in quad-ready triangulation (Priority: P1)
A QuADMESH+ user calls `triangulate(domain, h_max=…, quad_intent=True)` and receives a
triangulation whose interior valence histogram is shifted toward 8/even, measurably more
quad-ready than the default, **without** the default path changing at all.

**Why P1**: This is the feature. It's the minimum viable slice and is independently testable.

**Independent Test**: Run `triangulate(domain)` and `triangulate(domain, quad_intent=True)`
on the MVP domains; assert (a) default output is byte-identical to pre-feature baseline,
(b) quad-intent output has higher `pct_even_interior` and lower `mean |valence-8|`.

**Acceptance Scenarios**:
1. **Given** any MVP domain, **When** `quad_intent=False` (default), **Then** output mesh
   nodes/elements are identical to the current `triangulate()` baseline (regression-locked).
2. **Given** an interior-rich domain, **When** `quad_intent=True`, **Then** the fraction of
   even-valence interior vertices increases vs default by a target margin (set in Clarify).
3. **Given** `quad_intent=True`, **When** the mesh is built, **Then** size-function fidelity
   `|edge|/h_local` for ≥90% of edges stays within `[0.7, 1.4]` (FR-007).

### User Story 2 — Valence/quadability diagnostics (Priority: P2)
The user can request a valence + quadability report on any mesh to quantify quad-readiness
(reusing/extending `valence.py::get_valence_report` and the QuADMESH#63 "quadability profile").

**Independent Test**: Call the report function on a known mesh; assert reported histogram
matches a hand-computed fixture.

**Acceptance Scenarios**:
1. **Given** a mesh, **When** report requested, **Then** output includes interior valence
   histogram, `pct_even`, `mean |v-8|`, and per-edge `|edge|/h` distribution.

### User Story 3 — Right-isosceles geometry bias in the loop (Priority: P3)
With `quad_intent=True`, generated triangles trend toward right-isosceles (45/45/90) so
pairs fuse to near-square quads, oriented along an approximated layer direction.

**Independent Test**: Compare mean `right_iso_quality` (see `quality.py`) of quad-intent vs
default output on a domain with a clear propagation direction (annulus).

**Acceptance Scenarios**:
1. **Given** `quad_intent=True`, **When** generation completes, **Then** mean angle deviation
   from {45,45,90} decreases vs default.

---

## 4. Functional Requirements

- **FR-001**: A public, opt-in `quad_intent: bool = False` parameter on `triangulate()`
  (`admesh/api.py:615`). Default `False` MUST preserve exact current behavior.
- **FR-002**: When `quad_intent=False`, the locked `distmesh2d` path runs unchanged. The
  faithful-port modules (stage 1–13) MUST NOT be edited. (Constitution Principle I.)
- **FR-003**: The quad-intent path MUST live in a NEW additive module that *composes* locked
  stages (`_delaunay`, `fixmesh`, `mesh_size`, `quality`, `valence`, `quad_prep`) — never
  modifies them.
- **FR-004**: The quad-intent path targets interior valence **8** and **even parity**; it
  MUST accept a configurable `ideal_valence` (default 8 here) reusing `valence.BalanceConfig`
  (+ spec-016 `max_valence`).
- **FR-005**: Boundary / `pfix` nodes MUST remain pinned exactly as the locked loop pins them;
  the V=8 target applies to **interior** nodes only. Boundary valence target is geometry-forced
  (V=3–4) and is NOT optimized toward 8 (see §5).
- **FR-006**: The quad-intent path MUST reach a quality floor no worse than the default
  quality gate `min_q ≥ 0.30`, `mean_q ≥ 0.60` on MVP domains (else it falls back / warns).
- **FR-007**: Size-function fidelity gate: any valence-driven move (anisotropy, insert,
  delete, flip) MUST be capped so ≥90% of edges keep `|edge|/h_local ∈ [0.7, 1.4]`. Moves
  that would violate this are rejected.
- **FR-008**: A diagnostics function reports interior valence histogram, `pct_even`,
  `mean |v-8|`, and `|edge|/h` distribution (User Story 2).
- **FR-009**: The feature MUST NOT require running CHILmesh skeletonization inside ADMESH
  (see §6 feedback-loop decision). Any layer-direction needed for anisotropy MUST be
  approximated cheaply from data available during generation (SDF distance/gradient).

### Key entities
- **QuadIntentConfig** (new dataclass): `ideal_valence=8`, `max_valence`, anisotropy on/off,
  anisotropy strength, fidelity bounds `(0.7, 1.4)`, max insert/delete per pass.
- **LocalMetric `M(x)`** (new): 2×2 SPD tensor giving anisotropic rest-length; eigenvector
  aligned to approximated layer direction, eigenvalue ratio = anisotropy strength.
- **QuadabilityReport** (new dataclass): histogram + fidelity stats.

---

## 5. Boundary Analysis (task item 3)

The locked loop prepends `pfix` (fixed nodes) and zeroes their force (`distmesh.py:180–192,
231–232`); convergence excludes them (`251–255`). Boundary nodes are therefore topology-mobile
(their element star changes via retri) but position-fixed.

**Divergence requirement**: interior wants V=8, but boundary vertices are forced to low valence
(V=3–4) by domain geometry — a corner vertex physically cannot have 8 incident triangles inside
the domain. So:
- The even/V=8 objective MUST be masked to interior nodes (`valence.py` already builds a
  `_boundary_mask` and computes stats on interior only — reuse it, lines 76–80, 123).
- Edge flips touching a boundary node already treat its deficit as 0 (`valence.py:128`). Keep
  this: never penalize boundary valence against the V=8 target.
- Per QuADMESH#63, boundary OE/IE alternation is a *separate* problem that belongs to QuADMESH
  (vertex insertion / local re-mesh at layer 0). **Out of scope** for ADMESH `quad_intent`,
  but the spec must not make it harder: boundary discretization stays size-function-driven.

**Flag**: this is the cleanest interior/boundary divergence point — the objective function and
flip/insert gates branch on `boundary_mask`.

---

## 6. Feedback-Loop Feasibility (task item 5) — CRITICAL FEASIBILITY GATE

V=8 quad-readiness is defined relative to QuADMESH's **layer structure** (CHILmesh
skeletonization OE/IE), which only exists *after* a triangulation. QuADMESH#63 itself flags
the open question: is the OE/IE parity geometry-determined or triangulator-determined? If the
former, "true" quad-readiness requires `skeletonize → flip → re-skeletonize` — a feedback loop
that belongs in QuADMESH, **not** ADMESH.

**Position taken by this spec** (to be confirmed in Clarify):
- ADMESH `quad_intent` will pursue the **cheap-approximation** path only: orient anisotropy
  using the **SDF distance field and its gradient** (already computed: `fd`, and
  `mesh_size.py` already solves a distance-based Eikonal field). Layer-propagation direction
  is approximated as *transverse to ∇(boundary distance)* — i.e. layers grow inward parallel
  to the boundary, the same intuition CHILmesh layers encode, but obtainable WITHOUT
  skeletonization.
- ADMESH delivers a triangulation that is **statistically** more V=8/even and right-iso
  oriented. It does NOT promise per-layer OE/IE alternation — that remains QuADMESH's
  `skel → topo → geo` loop (QuADMESH#63 architecture diagram).
- **Decision**: `--quad-intent` IS feasible inside ADMESH as a *bias*, NOT as a *guarantee*.
  The true feedback loop stays in QuADMESH. This keeps ADMESH free of a CHILmesh dependency
  and honors the separation of concerns.

---

## 7. Tension Quantified: V=8 vs Size-Function Fidelity (task item 4)

A perfect V=8 interior lattice is the **right-isosceles grid**: each interior vertex sees 8
triangles = 4 squares split on the diagonal. The two leg lengths are equal (`= s`) and the
hypotenuse is `s√2`. So even an *isotropic* right-iso grid has edges at two lengths differing
by √2 ≈ 1.41. Measuring all edges against a single isotropic `h`:
- legs: `|edge|/h ≈ 1/c`, hypotenuse: `|edge|/h ≈ √2/c` for some normalization `c`.
- Centering `c=√2` (hypotenuse = h) gives legs at `0.707` → exactly the lower fidelity bound.
- Centering on the leg gives hypotenuse at `1.414` → just past the upper bound.

**Conclusion**: V=8 / right-iso is *barely* compatible with `[0.7, 1.4]` IF `h` is interpreted
as the **hypotenuse/diagonal** length (legs at 0.707). Anisotropic `M(x)` with eigenvalue ratio
near √2 lets BOTH legs and hypotenuse sit near their own targets, keeping fidelity in-band —
this is the technical justification for the anisotropic-rest-length lever (FR-007 cap). Pushing
anisotropy beyond ~√2 ratio WILL violate fidelity; hence the cap.

---

## 8. Scope

**In scope (this spec = planning/investigation only, NO code)**: the spec, clarify, plan,
tasks, analyze artifacts. Identification of levers, module boundary, fidelity math, feasibility.

**In scope (future implementation, behind flag)**: new `admesh/quad_intent.py` additive module;
`quad_intent` param on `triangulate()`; QuadIntentConfig; diagnostics; tests.

**Out of scope**: editing any locked stage module; CHILmesh skeletonization inside ADMESH;
per-layer OE/IE alternation guarantee; boundary vertex insertion/local-remesh (QuADMESH owns it);
C++ acceleration of the quad-intent loop (Python reference first).

## 9. Success Criteria
- **SC-001**: Default path output unchanged (regression test passes byte-for-byte).
- **SC-002**: `quad_intent=True` raises `pct_even_interior` by ≥ [target, set in Clarify] on
  ≥3 MVP domains.
- **SC-003**: `mean |valence - 8|` for interior nodes decreases vs default.
- **SC-004**: ≥90% of edges keep `|edge|/h_local ∈ [0.7, 1.4]`.
- **SC-005**: Quality gate `min_q ≥ 0.30 / mean_q ≥ 0.60` still met.
- **SC-006**: Zero edits to the 13 locked stage modules (CI/grep guard).

## 10. Assumptions & Dependencies
- Reuses `valence.py` (spec 016 `max_valence` landed or co-developed) and `quad_prep.py` (spec 004).
- No new third-party dependency.
- Anisotropy orientation from SDF gradient is "good enough" (validated empirically in Tasks).
