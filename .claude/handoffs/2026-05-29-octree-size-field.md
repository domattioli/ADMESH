# Handoff — spec 021 octree size-field (2026-05-29)

**Branch**: `021-octree-size-field` · **PR**: #113 (draft) · **Verdict**: partial success.

## What shipped (PR #113)

- **Spec Kit pipeline** under `specs/021-octree-size-field/`: spec → clarify (4 Qs) → plan → tasks (32) → analyze. Plan scopes a **Constitution Principle I exception** (modifies locked stages) gated on a v2.0.0 amendment.
- **Octree core** `admesh/_stages/octree_grid.py`: `build_octree`, 2:1 balance, `locate`, `interpolate`, `leaf_graph` (T001–T008).
- **Medial on leaf graph** `admesh/_stages/octree_medial.py`: gradient-convergence medial detection (fixes elongated-feature case), Dijkstra MAD, `size_field_octree` → `h = clip((|D|+MAD)/R)`.
- **Fixture** `tests/fixtures/multiscale/basin_inlet.py`.
- **Proof/scripts** + figures in `output/`: `render_octree_proof.py`, `render_sizefield_diff.py` (meshes via **admesh** distmesh), `render_scalability.py`, `make_report_pdf.py` (2-page report).

## State

- Medial axis resolves a feature a tractable uniform grid misses; admesh meshes ~4 elements across the river (108 river nodes vs 1 uniform).
- **Not scalable**: `build_octree` adjacency O(N²); `_balance_2to1` up to O(N³); `locate`/`interpolate` O(N). Leaf *count* ~linear. → **#115**.
- **distmesh coupling fragile**: raw graded field collapses distmesh; current proof seeds `initial_points=` octree leaf centers + relaxes `quality_gate` (min_q~0.16). Principled fix → **#114** (feed octree field into the existing 1D boundary seeding from #2 / spec 007).
- Principle I exception **not yet ratified** (v2.0.0 amendment unwritten) — release gate.

## Open work

- **#115** — octree O(N log N) rewrite (pointer/hash quadtree, parent/sibling neighbours, work-queue balance, Numba).
- **#114** — octree → 1D boundary seeding; drop the seeding hack, restore the 0.30 quality gate.
- `tasks.md` remaining: fold medial into locked `medial_axis.py` (currently in `octree_medial.py`); US2 verify-on-real-mesh; US3 fallback tests; US4 Constitution amendment.

## Resume

```bash
git checkout 021-octree-size-field
pytest tests/ -q                         # confirm non-octree stages green
python scripts/render_sizefield_diff.py  # regen figures
python scripts/render_scalability.py
python scripts/make_report_pdf.py
```

## Introspection / retro

- **Haiku subagent stalled ~2h** on the hard medial-on-octree step (silent, no completion event). Detected via file mtimes (2h cold) → opus took over and unblocked it. Lesson: for novel-algorithm steps, use opus from the start; for background subagents, add a liveness check rather than waiting on a completion event that may never arrive.
- **O(N²) octree shipped knowingly** as a proof-of-concept — adequate for the visual proof, logged as #115 rather than hidden.
- **distmesh collapse surfaced late**, during rendering. Root cause is the graded-field coupling; the seeding hack works but is not production. #114 is the principled route.
- **Spec Kit chain paid off**: `/clarify` (h_min floor, target+verify, octree+fallback, benchmark) materially tightened scope before any code; `/analyze` correctly flagged the Principle I violation as the one CRITICAL.
- **Honesty held**: report and figures state the partial-success verdict, the relaxed quality gate, and the build-cost gap explicitly.
