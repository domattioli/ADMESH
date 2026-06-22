# Implementation Plan: Octree Size-Field O(log N) Scalability

**Branch**: `daily-maintenance` (plan) → `021-octree-size-field-perf` (impl) | **Date**: 2026-06-02 | **Spec**: [spec.md](spec.md)
**Input**: `specs/021-octree-size-field-perf/spec.md` | **Issue**: [#115](https://github.com/domattioli/ADMESH/issues/115)

## Summary

Replace the O(N²)/O(N³) flat-list octree prototype in `admesh/_stages/octree_grid.py` (PR #113) with a pointer-based tree using: (1) O(log N) point location via recursive descent, (2) O(N) adjacency via parent/sibling links set during subdivision, (3) work-queue 2:1 balancing. Numba vectorization of per-leaf loops is P1 (optional). Target: build + query for feature-size ratio ≥ 1000 completes in < 10 s on a workstation.

## Technical Context

**Language/Version**: Python 3.10+  
**Primary Dependencies**: NumPy ≥ 1.24, Numba ≥ 0.57 (P1 only), `collections.deque` (stdlib)  
**Storage**: N/A (in-memory tree structure)  
**Testing**: pytest, `tests/test_octree_grid.py` (new scalability + parity tests)  
**Target Platform**: Linux/macOS workstation; CI on ubuntu-latest  
**Project Type**: Scientific Python library  
**Performance Goals**: Build + query < 10 s for feature-size ratio 1000; leaf count ≥ 10× below uniform-at-finest baseline  
**Constraints**: Numerical parity with prototype within `atol=1e-10`; Constitution Principle I — no changes to 13 locked faithful-port stage modules outside `octree_grid.py` / `octree_medial.py`  
**Scale/Scope**: `octree_grid.py` (~300 LOC) + `octree_medial.py` (P1 Numba loops); 5 new tests

## Constitution Check

**ADMESH Constitution Principles — pre-design gate:**

| Principle | Relevant Constraint | Status |
|---|---|---|
| Faithful-port lock | `octree_grid.py` is NOT one of the 13 locked MATLAB-port stages — it is new Python-only code | ✅ No lock applies |
| Numerical identity | `size_field_octree(pts)` must match the prototype within `atol=1e-10` | ✅ Enforced by `test_parity_vs_prototype` |
| No silent algorithm swaps | Pointer-tree swap documented in this plan + PR description | ✅ Explicit |
| Domain correctness | Size-field callable contract `fh(pts) → h` is unchanged; only internals change | ✅ Interface preserved |
| Mesh validity | Size field feeds distmesh; if `fh` is numerically identical, mesh output unchanged | ✅ Covered by parity test |

No violations. Proceed.

## Project Structure

### Documentation (this feature)

```text
specs/021-octree-size-field-perf/
├── spec.md              # Specification (complete)
├── plan.md              # This file
├── research.md          # Phase 0 findings
├── data-model.md        # OctreeNode data model
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
admesh/_stages/
├── octree_grid.py       # PRIMARY: OctreeNode rewrite (pointer tree)
└── octree_medial.py     # P1: Numba @njit wrapping of per-leaf loops

tests/
└── test_octree_grid.py  # 5 new tests (see spec §6 test plan)

scripts/
└── render_scalability.py  # Extend to ratio 1000; regenerate output/octree_scalability.png

docs/
└── PORTING_NOTES.md     # Stage-02 data-structure change record
```

**Structure Decision**: Single-file rewrite. No new modules needed; `octree_grid.py` is the sole change surface. `octree_medial.py` touched only for P1 Numba loops.

## Implementation Phases

### Phase P0 — Node data model (OctreeNode rewrite)

**Goal:** Replace flat leaf list with pointer tree.

**Changes to `OctreeNode`:**
- Add fields: `parent: OctreeNode | None`, `children: list[OctreeNode]` (length 4 or 0), `neighbours: dict[str, OctreeNode | None]` (keys `N/S/E/W`)
- `is_leaf()` → `len(self.children) == 0`
- `split()` → create 4 children, set `child.parent = self`, set sibling links among children, wire cross-parent neighbours via parent's neighbour dict

**Test gate:** `test_adjacency_sibling_links` (unit-square 3-level; all neighbour dicts consistent after 2 splits)

### Phase P1 — O(log N) locate + interpolate

**Goal:** Remove O(N) linear scan from `locate()` / `interpolate()`.

**Algorithm:**
```python
def locate(self, pt):
    if self.is_leaf():
        return self
    mid = (self.bbox[0] + self.bbox[1]) / 2
    ix = int(pt[0] >= mid[0])
    iy = int(pt[1] >= mid[1])
    return self.children[2*iy + ix].locate(pt)
```

Depth bounded by `max_depth`; O(max_depth) = O(log N). `interpolate()` calls `locate()` once per query point.

**Test gate:** `test_locate_descent` (100 random points; call count ≤ `max_depth + 1`)

### Phase P2 — O(N) adjacency + work-queue balancing

**Goal:** Eliminate O(N²) `_build_adjacency` and O(N³) `_balance_2to1`.

**Adjacency:** Set during `split()` via parent/sibling links — O(1) per split. No post-hoc all-pairs comparison needed.

**Balancing:**
```python
def balance_2to1(root):
    queue = deque(leaves_violating_2to1(root))
    while queue:
        leaf = queue.popleft()
        if leaf.is_leaf() and violates_2to1(leaf):
            leaf.split()
            queue.extend(new_violation_candidates(leaf))
```

Safety cap: assert `iteration_count < 10 * len(leaves)`.

**Test gate:** `test_balance_2to1_queue` (river-into-bay ratio=20; timing < 1 s)

### Phase P3 — Scalability + parity validation

**Goal:** Confirm O(log N) build/query at ratio 1000; confirm numerical parity.

- Extend `scripts/render_scalability.py` to ratio 1000; regenerate `output/octree_scalability.png`
- `test_scalability_ratio_1000`: build + query < 10 s; leaf count ≥ 10× below uniform baseline
- `test_parity_vs_prototype`: `atol=1e-10` against reference output from `tests/fixtures/octree/`

### Phase P4 (optional) — Numba vectorization

- Wrap per-leaf loops in `octree_medial.py` with `@njit`
- Gated behind `ADMESH_NUMBA=1` env var (same pattern as `_solve_iter_nb`)
- `test_numba_parity`: `atol=1e-12` between `@njit` and pure-Python paths

## Risk Register

| Risk | Mitigation |
|---|---|
| Sibling-link correctness at tree boundaries | Unit-test exhaustively on hand-constructed 3-level tree (Phase P0 gate) |
| Numba first-run latency 1–3 s | Gate behind `ADMESH_NUMBA=1`; default off in CI |
| Float tie-breaking changes locate output | Use `< mid` consistently (prototype rule); assert `atol=1e-10` not `==` |
| 2:1 work-queue cycle | Safety counter cap at `10 * len(leaves)` |
| PR #113 branch still open | This plan targets the `021-octree-size-field` branch; coordinate with PR |

## Out of Scope

- GPU offload (#8)
- 13 locked faithful-port stage modules (Constitution Principle I)
- 3D octree extension
- Grid-agnostic boundary seeding (spec 024 / issue #114 — orthogonal)
