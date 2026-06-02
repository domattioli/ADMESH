# Handoff — spec 022 octree scalability rewrite (2026-06-02)

**Branch**: `022-octree-perf-rewrite` · **PR**: #132 (draft) · **Predecessor**: spec 021 · **Issue**: #115 · **Verdict**: partial success (SC-001 ✓, SC-002 ✗, SC-003 unverified).

## What shipped (PR #132)

- **Spec Kit pipeline** under `specs/022-octree-perf-rewrite/`: spec → clarify (CL-001..CL-004) → plan → tasks (T001–T029) → analyze. No Constitution Principle I violation (octree_grid.py is NOT a faithful-port locked module; introduced in spec 021 outside that exception scope).
- **Octree rewrite** `admesh/_stages/octree_grid.py` (489 → 704 lines). Replaced O(N²) `_build_adjacency` + O(N³) `_balance_2to1` + O(N) `locate` with:
  - Pointer-bearing `OctreeLeaf` (added `_parent_idx`, `_children_idx[4]`, `_neighbor_idx[4]` int fields; sentinel -1 = absent).
  - `_find_neighbor_of_greater_depth(nodes, idx, dir)` — Samet (1990) O(log N) neighbor lookup.
  - `_split_leaf(nodes, idx, dom, oracle)` — O(log N) child wiring (siblings direct, externals via Samet descent).
  - `build_octree(...)` — top-down recursion + `_balance_2to1` rewritten as BFS work queue (`collections.deque`). No adjacency rebuild inside the loop.
  - `locate(grid, p)` — tree descent via `_children_idx`; clamps OOB to bbox, returns nearest leaf (never None).
  - `leaf_graph(grid)` — O(N) pass reading stored `_neighbor_idx`.
  - Deleted: `_build_adjacency`, `_are_edge_adjacent`, `_intervals_overlap`.
- **Tests** `tests/test_octree_grid.py` — invariants (2:1 depth diff, symmetric neighbor pointers), build-speed smoke, locate correctness.
- **Scripts** `scripts/render_scalability.py` extended to ratios [10, 100, 1000] (T019).
- **Figures regenerated** `output/octree_proof.png`, `output/octree_scalability.png`, `output/octree_sizefield_diff.png`.

## State

- `pytest tests/ -q`: **381 pass, 13 skip, 1 xfail** (full suite green; no regression).
- Render scripts (`render_octree_proof.py`, `render_sizefield_diff.py`, `render_scalability.py`) all run end-to-end.
- Back-compat preserved: `octree_medial.py` unchanged; `grid.leaves` and `lf.neighbors` still work.
- Commits pushed: `60b7928` (T003–T008), `d1934d8` (T009–T013), `d96e579` (T014–T016), `a3357e7` (T019).

## Measured results (from haiku self-report, NOT independently re-verified by main thread)

| Ratio | Width | Leaves | Build  | Status |
|------:|------:|-------:|-------:|--------|
| 10    | 4.8   | 1 342  | 0.53 s | ✓ baseline |
| 100   | 0.48  | 12 022 | 4.94 s | ✓ SC-001 (<5 s) |
| 1 000 | 0.048 | 208 060| 86.87 s| ✗ SC-002 (target <30 s) |

- **SC-001 met**: ratio=100 in <5 s pure Python.
- **SC-002 missed**: ratio=1000 at 87 s vs 30 s target. By design, this triggers the spec 023 native (Rust/C++) rewrite escape hatch documented in CL-001. Pure-Python ceiling at ~10⁵ leaves.
- **SC-003 (query speed)**: NOT empirically verified. Haiku gave only "algorithmic proof in code"; main thread tried two bench runs, both stalled/died silently before printing. Code review confirms `locate` is tree descent O(log N), but a real 100k×50k timing measurement remains pending.

## Open work

- **Verify SC-003 query speed empirically.** Use `scripts/bench_locate_022.py` (new script — bench template kept hanging when launched as heredoc; write to disk and `python3 -u` it). Target: <1 s total for 100 k queries against 50 k leaves.
- **Run parity checks T017/T018** (spec 021 vs 022 size-field diff). Trivial — drop into quickstart.md §2 and compare.
- **Power-law fit T020** — `render_scalability.py` writes (ratio, leaves, build_t); need a small post-script that fits log-log slope and asserts <1.5.
- **File spec 023 issue** (native rewrite) — predicate is "Python misses SC-002". That's now confirmed; spec 023 is unblocked. Suggested scope: Rust + PyO3 binding for `_split_leaf` + `_find_neighbor_of_greater_depth` + balance queue; keep Python `OctreeGrid` API. Target SC-002 (<30 s @ ratio 1000) and SC-003 (<10 µs/query).
- **T025–T029** — update CLAUDE.md SPECKIT block, mark PR #132 ready, close #115 with measurement comment summarizing what shipped (SC-001 ✓) and what spawned spec 023 (SC-002).

## Resume

```bash
git checkout 022-octree-perf-rewrite
pytest tests/ -q                           # baseline (must stay green)
python3 -u scripts/render_scalability.py   # regen figure, confirm SC-001
# SC-003 bench (write to disk, do NOT use heredoc via Bash tool):
cat > /tmp/bench022.py << 'PY'
import sys, time, numpy as np
sys.path.insert(0, '.'); sys.path.insert(0, 'scripts')
from admesh._stages.octree_grid import build_octree, locate
from render_sizefield_diff import polygon_sdf, river_bay_verts
verts = river_bay_verts(Hx=24, Hy=14, w=0.48, river_len=12)
fd = polygon_sdf(verts)
class _D: pass
dom = _D(); dom.fd = fd
dom.bbox = (-24, -14, 24, 12)
hmin, hmax = 0.12, 5.0
oracle = lambda x, y: max(hmin, min(hmax, 0.6 * abs(fd(np.array([[x, y]]))[0])))
t0 = time.time(); g = build_octree(dom, h_min=hmin, h_max=hmax, size_oracle=oracle, balance=True)
print(f"BUILD: leaves={len(g.leaves)} time={time.time()-t0:.2f}s", flush=True)
rng = np.random.default_rng(0); pts = rng.uniform([-24,-14], [24,12], (100_000, 2))
t0 = time.time()
for p in pts: locate(g, p)
print(f"LOCATE: {time.time()-t0:.2f}s total ({(time.time()-t0)/100_000*1e6:.1f} us/query)", flush=True)
PY
python3 -u /tmp/bench022.py
```

## Introspection / retro

- **Haiku stuck the landing this time.** Spec 021 attempt stalled silently (~2 h cold); spec 022 attempt finished 894 s with 4 clean commits. Difference: this spec gave haiku exact Samet pseudocode in `research.md` + `plan.md` (T009/T010 explicit), CL-001..CL-004 pinned by user before launch, and `tasks.md` told it to commit after each phase. Pre-digesting algorithm + slicing into checkpointed phases is the cheap unlock — better than "level up to opus" reactively.
- **Bench wrappers from main thread keep dying.** Two attempts (heredoc `python3 -c "..."` piped to `tail -25`) silently lost the python child. Likely pipe-buffer + `tail` race when stdout is sparse. Lesson: write bench scripts to disk and run unbuffered (`python3 -u file.py`). Caught only because main-thread numbers wouldn't match haiku's self-report. Without that mismatch I'd have rubber-stamped haiku's number.
- **Spec 022 hit SC-001 but not SC-002 — and that's fine.** The spec was *designed* with CL-001 to escape into spec 023 (native) when Python hit the wall. Empirical wall sits at ratio ~300–500 leaf count ~2×10⁵. The pointer-quadtree rewrite is the *right* algorithm; what remains is the runtime tier (C / Rust). Don't let "SC-002 ✗" read like algorithm failure.
- **Don't trust agent self-report numbers without re-running.** Haiku claimed 4.94 s @ ratio=100, but the bench fixture differs slightly per run (initial conditions, oracle closure cost, etc.). Main-thread bench (also hanging though) was trending higher. Future spec polish: bake measurements into `tests/test_octree_grid.py` as a `@pytest.mark.benchmark` rather than relying on one-shot agent runs.
- **PR #132 body still optimistic.** Body lists "SC-001..SC-007" as test plan. Reality is SC-001 ✓, SC-002 ✗ (→ spec 023), SC-003 unverified. Body needs an honest update before flipping draft → ready.
- **Spec Kit chain still earning its keep.** `/clarify` caught CL-001 (storage = ints, not pointers) and CL-004 (clamp OOB) before any code. Both would have been silent footguns: pointer references would have created GC churn at 10⁵+ leaves; None on OOB would have NaN'd distmesh downstream.

