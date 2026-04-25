# CLAUDE.md

Operational reference for Claude Code sessions on ADMESH.

**Read these three at every session start (in order):**
`CONSTITUTION.md` → `PROJECT_PLAN.md` → `CLAUDE.md`.

If CLAUDE.md contradicts the constitution, the constitution wins.

---

## Project overview

Python port of `01_ADMESH_Library` from
[`domattioli/QuADMesh-MATLAB`](https://github.com/domattioli/QuADMesh-MATLAB)
at commit `19b2eb9f078a648daec3fd40d5d4c6e072f467ac`. See
`CONSTITUTION.md` Article I for the north star; Article II for hard
rules (faithful port, no C extensions in first cut, 0-based indexing).

Local MATLAB reference clone: `/workspace/QuADMesh-MATLAB` (branch
`main`). Source tree of interest: `01_ADMESH_Library/`.

---

## Commands

```bash
# Install for development
pip install -e ".[dev]"

# Run all tests
pytest tests/ -q

# Run a single stage's tests
pytest tests/test_distance.py -v

# Benchmark the Numba mesh_size solver vs. the C baseline
python scripts/bench_mesh_size.py

# Export fresh reference fixtures from MATLAB (requires MATLAB)
matlab -batch "run('scripts/export_matlab_fixtures.m')"
```

---

## Architecture

```
admesh/
  __init__.py          # package entry, re-exports public API
  routine.py           # 01 — top-level driver (ADmeshRoutine, ADmeshSubMeshRoutine)
  background_grid.py   # 02 — CreateBackgroundGrid
  distance.py          # 03 — SignedDistanceFunction, PTS2PointList
  curvature.py         # 04 — CurvatureFunction
  medial_axis.py       # 05 — MedialAxisFunction, TriMedialAxisFunction, medial_distance_FMM
  bathymetry.py        # 06 — BathymetryFunction
  dominate_tide.py     # 07 — DominateTideFunction
  boundary.py          # 08 — EnforceBoundaryConditions, create_polygon_structure
  mesh_size.py         # 09 — MeshSizeFunction + Numba-JIT iterative solver
  distmesh.py          # 10 — distmesh2d + fixmesh (triangulation only; tri2quad is out of scope)
  quality.py           # 11 — MeshQuality
  in_polygon.py        # 12 — InPolygon
  inpaint.py           # 13 — inpaint_nans

tests/
  test_<stage>.py      # one per stage
  fixtures/<stage>/    # .npz inputs+outputs captured from MATLAB

scripts/
  export_matlab_fixtures.m   # MATLAB-side fixture emitter
  bench_mesh_size.py         # Numba vs. C solver benchmark

docs/
  PORTING_NOTES.md     # running log of MATLAB → Python substitutions
```

---

## MATLAB → Python conventions

**Naming**
- `CreateBackgroundGrid.m` → `create_background_grid()` in
  `admesh/background_grid.py`.
- Private helpers keep their MATLAB name in snake_case, leading
  underscore if they're module-private.

**Indexing**
- MATLAB 1-based → Python 0-based. Subtract 1 wherever the MATLAB
  source indexes into arrays.
- MATLAB `end` → Python `-1` or `len(x) - 1`.
- MATLAB `x(i:j)` inclusive → Python `x[i-1:j]` (half-open, remember
  the upper bound doesn't shift).

**Common substitutions**
| MATLAB | Python |
|---|---|
| `inpolygon(xq, yq, xv, yv)` | `admesh.in_polygon.in_polygon(xq, yq, xv, yv)` (our port) |
| `delaunay(x, y)` | `scipy.spatial.Delaunay(np.c_[x, y]).simplices` |
| `griddata` | `scipy.interpolate.griddata` |
| `bwdist` | `scipy.ndimage.distance_transform_edt` |
| `struct` | `dataclasses.dataclass` or dict — pick per-module |
| cell array of varying-length vectors | `list[np.ndarray]` |

Document each non-obvious substitution in `docs/PORTING_NOTES.md` with
a one-line note on any behavior difference (closed-vs-open boundary,
tie-breaking, ordering).

**Docstring template**
```python
def create_background_grid(domain, params):
    """Build a structured background grid over the domain.

    Port of ``01_ADMESH_Library/02_Create_Background_Grid/CreateBackgroundGrid.m``
    from QuADMesh-MATLAB @ 19b2eb9.

    Parameters
    ----------
    domain : ...
    params : ...

    Returns
    -------
    grid : ...
    """
```

---

## Numba conventions

`admesh/mesh_size.py` hosts the iterative PDE solver ported from
`MeshSizeIterativeSolver.c`. Keep two implementations in-module:

1. `_solve_iter_py(...)` — pure NumPy, readable, the reference.
2. `_solve_iter_nb(...)` — `@njit(cache=True)`, optimized.

A test in `tests/test_mesh_size.py` asserts they agree to `atol=1e-10`
on a fixed input. The public `solve_iter(...)` dispatches to the Numba
path by default, with a `use_numba=False` kwarg for debugging.

---

## Testing

- One test file per stage: `tests/test_<stage>.py`.
- Fixtures: `.npz` under `tests/fixtures/<stage>/<case>.npz` with
  named arrays for inputs and expected outputs.
- Load pattern:
  ```python
  data = np.load("tests/fixtures/distance/square.npz")
  out = admesh.distance.signed_distance(data["x"], data["y"], data["poly"])
  np.testing.assert_allclose(out, data["expected"], atol=1e-8)
  ```
- Keep fixtures small (< 1 MB per file ideally) so the repo stays
  lightweight.

---

## Session cadence (lightweight)

Each working session:
1. **Orient** — read `CONSTITUTION.md`, `PROJECT_PLAN.md`, this file.
2. **Pick a stage** from the current phase in `PROJECT_PLAN.md`.
3. **Port** the MATLAB source, committing per file/function.
4. **Test** against fixtures; iterate until green.
5. **Commit + push.** Update `PROJECT_PLAN.md` "Where we are today" if
   a phase milestone landed.

No mandatory session reports, no 4-agent planning, no dispatch queue —
this is a port, not a research project. Keep it simple.

---

## Related repos on disk

| Path | What it is |
|---|---|
| `/workspace/QuADMesh-MATLAB` | MATLAB source (read-only reference) |
| `/workspace/MADMESHR` | Sibling RL-meshing project — **not related to ADMESH**, do not cross-contaminate |
| `/workspace/ADMESH` | This repo |

<!-- SPECKIT START -->
Active spec-kit feature: `002-size-field-defaults` (branch
`002-size-field-defaults`). **MVP slice shipped** (T001-T015 +
T018-T028 + T032-T037, 252 → 259 tests passing). Default Phase-1
stack wired into `admesh.triangulate()`; fort.14 I/O extended for
paired-edge BC records (IBTYPE 3 / 4 / 13 / 24); constitution walked
back to v1.0.2; pre-tag verification script in place. Tier-1 / Tier-2
acceptance tests are `xfail` pending issue #10 (default-stack
overshoot on real-world coastal fixtures) and issue #11
(Domain.from_mesh outer-ring picker). 0.1.0 tag is gated on those
two.

For technical context, the API extensions (`Domain.bathymetry`,
`Domain.tide_period`, `Domain.from_mesh`, the new `BoundaryType`
members), the structural-validity test gate, and the test fixture
ladder, read:

- `specs/002-size-field-defaults/plan.md`
- `specs/002-size-field-defaults/research.md`
- `specs/002-size-field-defaults/data-model.md`
- `specs/002-size-field-defaults/contracts/python-api-default-stack.md`
- `specs/002-size-field-defaults/contracts/fort14-paired-edge.md`
- `specs/002-size-field-defaults/quickstart.md`

Spec 001 (`001-pythonize-and-fort14-integration`) is shipped on its
branch and remains the foundation; its plan/data-model/contracts are
still authoritative for the spec-001 surface. Constitution Principle I
still applies: the 13 faithful-port stage modules in `admesh/*.py`
MUST stay numerically identical. Spec-002 changes live in `api.py`,
`fort14.py`, `boundary_types.py` (extending), `_structural_validity.py`
(test helper), and three new test modules
(`tests/test_default_size_field.py`, `tests/test_fort14_paired.py`,
`tests/test_backward_compat.py`); all strictly additive.

**Open follow-up issues** (`gh issue list --repo domattioli/ADMESH`):
- #6 — domain/mesh registry concept (low, post-v1)
- #8 — GPU + CPU-parallel acceleration (low, post-v1)
- #9 — admesh-segmenter sibling project (low, post-v1)
- #10 — default-stack domain overshoot on real-world coastal fixtures (high; release-blocker for 0.1.0)
- #11 — Domain.from_mesh outer-ring picker (high; mechanical fix)
<!-- SPECKIT END -->
