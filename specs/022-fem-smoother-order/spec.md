# Spec 022 — FEM smoother / truss-solver ordering: the equilateral-tri preconditioner hypothesis (research, resolves #124)

**Status:** Research / brainstorming. No code shipping in this commit (ADMESH planning profile). This spec is the literature review + experiment contract; implementation is a separate code-shipping session.
**Issue:** [#124 research: FEM smoother before truss solver — equilateral-tri preconditioner hypothesis](https://github.com/domattioli/ADMESH/issues/124) — `request: research`, `type: feat`, `status: brainstorming`.
**Related:** [#1](https://github.com/domattioli/ADMESH/issues/1) (the FEM smoother — `admesh/smoother.py::fem_smooth`, Balendran/target-Jacobian, **equilateral** default), spec-017 (default size-field stack, [#65](https://github.com/domattioli/ADMESH/issues/65)), spec-020 (WNAT benchmark quality, [#101](https://github.com/domattioli/ADMESH/issues/101)). NOTE: spec-004 / `quad_prep.py` is the *quad-prep* smoother (right-isoceles target) and is a **separate, independent** module — not the FEM smoother in scope here.
**Branch:** `daily-maintenance`
**Token budget:** N/A (research; deliverable is this doc).

---

## 1. Problem statement (from #124)

The FEM smoother is, in practice, applied **after** the truss solver and demonstrably improves quality even there (operator observation; #1 acceptance criteria). The hypothesis: applying the FEM smoother **before** the truss solver — preconditioning toward equilateral triangles — gives the solver a higher-quality starting configuration it can *maintain* while it optimizes toward the size function, yielding better final quality and/or faster convergence.

- **Current:** truss solver optimizes size function → FEM smoother improves quality after.
- **Proposed:** FEM smoother pre-conditions to equilateral tris → truss solver optimizes size function while preserving that quality.

## 2. Grounded reading of the current code (what actually ships)

### 2.1 The "truss solver" is DistMesh — equilateral-seeded and equilateral-attracting

- `admesh/_stages/distmesh.py:214` — `distmesh2d` — canonical Persson–Strang DistMesh: bars as springs, `F = max(L0 − L, 0)`, nodes integrated to force equilibrium; Delaunay **re-triangulation** each outer iteration.
- `admesh/_stages/distmesh.py:638` — `distmesh2d_admesh` — MATLAB-faithful variant with density control + best-quality tracking (`_element_quality_mean`, `distmesh.py:619`).
- `admesh/_stages/distmesh.py:214-225` / `:752-756` — force assembly: `L0 = h_bars · Fscale · sqrt(Σ L² / Σ h²)`.

DistMesh's initial node distribution is an equilateral lattice; its force-equilibrium attractor is equal bar lengths → near-equilateral triangles (Persson & Strang 2004). Its objective is *jointly* equilateral shape **and** adherence to the size field `h`.

### 2.2 The FEM smoother (#1) — equilateral target, general mesh-quality, NOT quadrangulation

Per [#1](https://github.com/domattioli/ADMESH/issues/1), the FEM smoother is a Balendran/Knupp **target-Jacobian** direct smoother:

> `fem_smooth(p, t, fd=None, h=None, target="equilateral", kinf=1e12, n_outer=1) -> (p_new, t)`

- **Default target = equilateral** (CHILmesh parity). `right_isoceles` exists only as an A/B option.
- **SDF-coupled:** boundary nodes (`|fd(p)| < geps`) pinned via large diagonal `kinf`; post-solve one Newton projection back to the zero level-set. Interior nodes free.
- **Size-field-coupled:** each element's local stiffness scaled by `h_bar = mean(h(p[t_k]))`, so the smoother's notion of "good" is the size field, not just shape. `n_outer ≥ 2` when `h` varies sharply.
- One sparse solve (`scipy.sparse` / `spsolve`).

The reference implementation is **CHILmesh `direct_smoother`** (`CHILmesh.py:2100` — Balendran rotation-based stiffness, equilateral target, `kinf=1e12` boundary pin). Per `CLAUDE.md:340`, ADMESH composes downstream of CHILmesh: "wrap ADMESH output for FEM smoothing." The ADMESH-native port specced in #1 (`admesh/smoother.py`) is **not present in the `daily-maintenance` tree** at the time of writing — the working smoother today is CHILmesh's. This is a wiring fact the experiment (§5) must pin down before running.

**This is NOT the quad-prep smoother.** `admesh/quad_prep.py::smooth_for_quadrangulation` (spec-004) targets *right-isoceles* for quad fusion and is, by spec-004 FR-012, an independent module that "MUST NOT import" #1's smoother. The earlier conflation of the two was wrong; they share only design lineage (Knupp 2012, Balendran), not purpose.

### 2.3 The smoother improves quality *after* DistMesh — DistMesh leaves headroom

Evidence the truss solver does **not** exhaust quality on its own:
- #1 acceptance criterion: "On all 5 MVP domains, `min_q` non-decreases and `mean_q` increases by ≥ 0.01 after one smoothing pass."
- #1 problem statement: `unit_square` has a sliver (`min_q ≈ 0`); non-convex / curved / multiply-connected domains routinely have low-min-q nodes near the boundary after DistMesh.
- Operator observation (this issue): the FEM smoother tends to improve quality even after the truss solver.

So the premise of the hypothesis is sound: DistMesh converges to a *good* but not optimal configuration, and a target-Jacobian smoother finds residual gains. The open question is whether *moving that gain earlier* (or adding it both ends, or interleaving) helps the solver rather than just polishing its output.

### 2.4 Why the equilateral target makes "pre" coherent (correcting the earlier draft)

The FEM smoother's equilateral, size-field-coupled target **aligns with** DistMesh's joint objective rather than fighting it. A pre-pass therefore hands DistMesh a mesh already near both equilateral shape *and* the size field — exactly the configuration DistMesh is trying to reach. (Contrast the quad-prep right-isoceles smoother, which *would* fight DistMesh and must stay post-pipeline.) The hypothesis is well-posed.

## 3. Literature review

| Source | Relevance | Takeaway for #124 |
|---|---|---|
| Persson & Strang, *A Simple Mesh Generator in MATLAB* (SIAM Review 2004) | The truss solver itself | Equilateral seed; force equilibrium drives toward equal bar lengths; element quality higher with force equilibrium. But it re-triangulates each iteration — node *shapes* are re-derived, so a pre-pass's angle gains are not guaranteed to survive; its *positional* gains (size-field adherence) may. |
| Balendran, *A direct smoothing method for surface meshes* (IMR 1999); Knupp, *Target-Matrix Paradigm* (Eng. w/ Comp. 2012) | The smoother itself | Direct, single-solve, target-Jacobian. Cheap relative to iterative optimization; a pre-pass is affordable. Equilateral target = DistMesh-aligned. |
| Freitag & Plassmann, *Local optimization-based simplicial mesh untangling and improvement* (IJNME 2000); Canann, Tristano & Staten (combined Laplacian + optimization smoothing) | Pre/post ordering in the smoothing literature | Established pattern: cheap global smoother as a **preconditioner first**, expensive optimizer last. The FEM direct smoother is cheap (one solve) → using it as a preconditioner before DistMesh is consistent with this pattern. |
| Botsch & Kobbelt, *A Remeshing Approach to Multiresolution Modeling* (SGP 2004); PMP isotropic remeshing | SOTA equilateral remeshing | Best equilateral quality comes from **interleaving** local ops with tangential smoothing every iteration (target = equilateral + valence 6) — neither pure-pre nor pure-post. Strongest signal: if equilateral quality is the goal, interleave the smoother into DistMesh's iteration loop. |

**Synthesis:** the literature supports the hypothesis far better than the earlier draft claimed. (a) A cheap direct smoother as a preconditioner-first is a recognized pattern (Freitag–Plassmann). (b) Equilateral target aligns with DistMesh. (c) The strongest equilateral results come from *interleaving* (Botsch–Kobbelt). The one caution unique to DistMesh: its per-iteration Delaunay re-triangulation may wash out a pure-pre pass's connectivity/angle gains — which is precisely the thing the experiment must measure.

## 4. Research questions (scoped from #124)

1. **Truss-solver sensitivity to input quality.** DistMesh re-triangulates + re-equilibrates each iteration, so it is somewhat insensitive to initial *angles* but sensitive to initial *node positions vs. the size field*. Because the FEM smoother is size-field-coupled, a pre-pass changes both. Hypothesis: pre-conditioning reduces iterations-to-converge more than it raises the final quality ceiling. **Testable** (§5, H1).
2. **Idempotency / over-smoothing risk.** Equilateral target aligns with DistMesh, so the pre-pass does not conflict with the size function the solver imposes (unlike the right-isoceles quad-prep smoother). With `n_outer=1` and SDF pinning, over-smoothing risk is low; the risk is boundary drift, mitigated by the post-solve Newton projection. **Testable** (§5, H2).
3. **Prior art.** §3 — Persson–Strang, Balendran/Knupp, Freitag–Plassmann, Botsch–Kobbelt. Net: cheap-preconditioner-first is supported; interleaved is SOTA.
4. **Cost model.** FEM smoother = one global sparse solve per pass. Pre-only adds ~1 solve; both adds 2; interleaved adds `n_iter/k`. The smoother is cheap vs. the full DistMesh iteration budget, so even "both" is plausibly < 1.5× if the pre-pass cuts DistMesh iterations. **Testable** (§5, wall-time + iteration count).
5. **Boundary vs. interior.** Boundary nodes are SDF-pinned in both stages; the headroom is on the interior and near sharp size-field gradients (where DistMesh's uniform-equilibrium assumption is weakest). Expect ordering to matter most on graded domains. **Testable** (§5, stratified).

## 5. Proposed experiment design

**Prerequisite (resolve first):** confirm which smoother the experiment calls. Either (a) the CHILmesh `direct_smoother` applied to ADMESH `(p, t)`, or (b) land the `admesh/smoother.py::fem_smooth` port from #1. The experiment needs `target="equilateral"` with size-field coupling (`h`) and SDF pinning (`fd`). Do **not** use `quad_prep.smooth_for_quadrangulation` (wrong target).

**Independent variable — pipeline order (4 arms):**
- `A. post` (control / current practice): DistMesh → FEM smoother after.
- `B. pre`: FEM smoother → DistMesh.
- `C. both`: FEM smoother → DistMesh → FEM smoother.
- `D. interleaved`: FEM smoother every `k` DistMesh iterations (Botsch–Kobbelt pattern), `k ∈ {5, 10}`.

All arms call `fem_smooth(target="equilateral", h=<size field>, fd=<domain sdf>)`. Hold DistMesh solver params (`Fscale`, `dt`, `n_iter` cap) fixed across arms; vary only ordering.

**Test meshes** (the 5 MVP domains + a size-field stressor):
- square (has the known `unit_square` sliver — a sensitive min-q probe), L-shape, U-shape, square-with-hole, doughnut/annulus (uniform `fh`).
- one strongly graded domain (WNAT `wnat_test.14`-derived params, per spec-020) where ordering should matter most.

**Metrics** (#124 + convergence):
- min angle (deg): distribution + min — lead metric (catches the slivers DistMesh leaves).
- mean aspect ratio + `mesh_quality` q (`quality.py:25`).
- size-function L2 error: `‖ edge_len − h(midpoint) ‖₂` normalized by `h`.
- DistMesh iterations-to-converge + wall-clock (cost model, RQ4) — **the discriminating measurement for the "faster convergence" half of the hypothesis.**
- whether pre-pass angle gains survive iteration 1's Delaunay re-triangulation (RQ1 crux): measure min-angle immediately after the first DistMesh retriangulation in arm B vs. arm A.
- stratified boundary-incident vs. interior (RQ5).

**Decision thresholds (pre-registered):**
- Adopt a non-control arm if it improves **min angle by ≥ 2°** *or* **size-field L2 by ≥ 10%** on ≥ 4 of 6 domains, **without** regressing mean q, at wall-time < 1.5× control.
- Independently, adopt for convergence if an arm cuts **iterations-to-converge by ≥ 20%** at neutral final quality.

## 6. Recommendation

**Run the A/B/C/D experiment. Prior favors `C. both` or `D. interleaved`, not the earlier "no change."** Rationale:

1. The FEM smoother demonstrably adds quality *after* DistMesh (#1 acceptance; operator observation) → DistMesh leaves real headroom, so polishing is not the whole story.
2. The smoother's **equilateral, size-field-coupled** target *aligns with* DistMesh's joint objective (§2.4) → "pre" reinforces the solver rather than fighting it; the hypothesis is well-posed.
3. Literature favors a cheap preconditioner-first (Freitag–Plassmann) and, most strongly, *interleaved* tangential smoothing for equilateral quality (Botsch–Kobbelt). Arm D operationalizes the latter.
4. The single real risk to "pre" is that DistMesh's per-iteration Delaunay re-triangulation washes out the pre-pass's angle gains — which is exactly why "both" and "interleaved" hedge it: the post-pass (or repeated passes) recapture quality the re-triangulation disturbs while the pre-pass still buys a size-field-adherent start that may cut iterations.

**Concretely:** start by measuring arm B's first-retriangulation survival (cheap, decisive) and arm C's quality/cost delta on the `unit_square` sliver + WNAT stressor. If B's gains survive and C is < 1.5× cost with a quality win, ship `smooth=` as a `pre|post|both` kwarg on `triangulate()` (the #1 spec already anticipates a `smooth=True` kwarg on `triangulate()`). If only interleaving wins, that is a larger change (smoother must be callable inside the DistMesh loop) and warrants its own implementation spec.

**Do not** invert the quad-prep (right-isoceles) smoother's position — that is a separate module whose post-pipeline placement is correct (it deliberately moves away from equilateral for quad fusion).

## 7. Acceptance criteria (for this research spec)

- [x] Correctly identify the FEM smoother (#1, `fem_smooth`, equilateral target) and distinguish it from the quad-prep smoother (§2.2).
- [x] Establish that the smoother improves quality after the truss solver, with evidence (§2.3).
- [x] Literature review on smoother ordering (§3).
- [x] Experiment design: 4 ordering arms, test meshes, metrics (min angle, mean aspect ratio, size-function L2 error) + iteration/cost, pre-registered thresholds (§5).
- [x] Recommendation (pre / post / both / interleaved / no change) with rationale (§6).
- [ ] Operator triage: accept recommendation (close #124 as researched) or approve a follow-up code-shipping spec for the experiment + `smooth=pre|post|both` wiring on `triangulate()`.

## 8. Risks / open questions

| Item | Note |
|---|---|
| Which smoother does the experiment call? `admesh/smoother.py` from #1 is not in the `daily-maintenance` tree; CHILmesh `direct_smoother` is the working one | Resolve in §5 prerequisite before running; may require landing the #1 port first. |
| DistMesh Delaunay re-triangulation may erase pure-pre angle gains | RQ1 crux; measured directly (min-angle after first retriangulation, arm B vs A). |
| `mesh_quality` q is a single scalar; min-angle distribution is more diagnostic | Lead with min-angle + size-field L2; report q alongside. |
| Interleaved (D) requires the smoother to be callable inside the DistMesh loop | Larger change than a `pre/post/both` kwarg; gate behind its own spec if D is the only winner. |
