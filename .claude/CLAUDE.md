# CLAUDE.md — Operational Reference

**Read in order**: `docs/governance/CONSTITUTION.md` → `docs/governance/PROJECT_PLAN.md` → `CLAUDE.md`

## Project

Python port of MATLAB ADMESH (`github.com/domattioli/QuADMesh-MATLAB`, commit `19b2eb9`).
Two layers: **faithful-port stage modules** (locked, identical to MATLAB) + **Pythonic API** (spec-001+, strictly composes stages).

Reference MATLAB clone: `/workspace/QuADMesh-MATLAB`, source: `01_ADMESH_Library/`.

## Quick Start

```bash
pip install -e ".[dev]"
pytest tests/ -q
python scripts/bench_mesh_size.py
```

## Code Structure

**Stage modules** (locked):
- `routine.py` (01), `background_grid.py` (02), `distance.py` (03), `curvature.py` (04), `medial_axis.py` (05), `bathymetry.py` (06), `dominate_tide.py` (07), `boundary.py` (08), `mesh_size.py` (09), `distmesh.py` (10), `quality.py` (11), `in_polygon.py` (12), `inpaint.py` (13)

**API layer** (additive):
- `api.py` (Domain/Mesh/triangulate), `fort14.py` (I/O), `loaders.py` (domain loaders), `size_field.py`, `quad_prep.py` (spec-004), `registry.py` (spec-005)

## Domain Loading (v0.2+)

```python
from admesh import triangulate
mesh = triangulate("domain.toml", h0=0.1)  # TOML, JSON, or fort.14
```

Breaking change from v0.1: `domain_from_polygon()` removed. Use file-based loading.

## MATLAB → Python

| MATLAB | Python |
|--------|--------|
| `inpolygon(xq, yq, xv, yv)` | `admesh.in_polygon.in_polygon(...)` |
| `delaunay(x, y)` | `scipy.spatial.Delaunay(...).simplices` |
| `griddata` | `scipy.interpolate.griddata` |
| `bwdist` | `scipy.ndimage.distance_transform_edt` |
| `struct` | `dataclasses.dataclass` or dict |

**Indexing**: MATLAB 1-based → Python 0-based. `x(i:j)` inclusive → `x[i-1:j]`.

## Testing

- One test file per stage: `tests/test_<stage>.py`
- Reference fixtures: `tests/fixtures/<stage>/*.npz` (from MATLAB)
- Default tolerance: `atol=1e-8, rtol=1e-6` (override in docstring if needed)
- End-to-end: MVP 5 domains, quality gates `min_q ≥ 0.30`, `mean_q ≥ 0.60`

## Numba Path

`admesh/mesh_size.py` has two solvers:
1. `_solve_iter_py(...)` — NumPy reference
2. `_solve_iter_nb(...)` — `@njit` optimized

Test asserts parity to `atol=1e-10`. Public `solve_iter()` dispatches to Numba by default; `use_numba=False` to debug.

## Stream Timeout Prevention

1. One task per turn; confirm before next.
2. Max 150 lines per file write; split if longer.
3. Grep short; use `-l`, `--include` flags.
4. If timeout: retry same step, shorter form.
5. >20 tool calls → start fresh session.

## Spec-Kit Integration

Active feature spec tracked in docs. All specs live under `specs/NNN-feature-name/` with: spec.md, plan.md, research.md, data-model.md, quickstart.md, tasks.md.

Constitution Principle I: 13 faithful-port modules stay numerically identical. Specs 001–005 are additive.

---

## Skills & Tools

All Claude Code skills managed by parent **DomI** repository:
- Single-branch policy enforcement (`daily-issue-fixing`)
- Pre-commit hooks
- Session startup configuration

Skill updates → https://github.com/domattioli/DomI

## Coding dispatch — Haiku subagent default

All coding work (writing or editing source code) MUST be dispatched to a subagent running the Haiku model (`claude-haiku-4-5`) — not written inline by the main session. The orchestrator session plans, reviews, and integrates; implementation is delegated to the Haiku subagent.

- **Default**: for any code-writing/editing task, spawn a subagent with `model: haiku`.
- **Exception**: only when the operator explicitly directs otherwise (e.g. "do it inline", "use Sonnet/Opus for this"). Explicit operator instruction only — never assumed.
- **Scope**: applies to code. Non-coding work (planning, research, docs, git/PR orchestration, review) stays on the main session.
