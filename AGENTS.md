# ADMESH

ADMESH is a Python port of `01_ADMESH_Library` from
[`domattioli/QuADMesh-MATLAB`](https://github.com/domattioli/QuADMesh-MATLAB)
at commit `19b2eb9f078a648daec3fd40d5d4c6e072f467ac`. The package is published as
`admesh2D` and imported as `admesh`. It generates triangular meshes for 2D
shallow-water models and reads and writes ADCIRC `fort.14` and Gmsh 2.2 files.

## Hard rules

1. The 13 original stage modules under `src/admesh/_stages/` are locked faithful
   ports. They must remain numerically equivalent to the pinned MATLAB source.
   Any change needs a Constitution Principle I justification and MATLAB reference
   tests. New behavior belongs in the additive API layer.
2. Python uses 0-based indices. Convert MATLAB indexing explicitly and record
   non-obvious substitutions in `docs/PORTING_NOTES.md`.
3. MATLAB column-major behavior matters only at input and output boundaries.
   Internal arrays use normal NumPy layout.
4. MATLAB reference fixtures are read-only in Python. Regenerate them only from
   the pinned MATLAB source with `scripts/export_matlab_fixtures.m`.
5. The supported path must work without a C++ toolchain. `src/admesh/_cpp/` is an
   optional accelerator and falls back to the Python and Numba implementation.
6. Do not delete mesh fixtures or reference data.

## Repository layout

```text
src/admesh/
├── _stages/              # locked MATLAB-faithful numerical stages
├── _cpp/                 # optional C++ distmesh accelerator
├── api.py                # Domain, Mesh, BoundarySegment, triangulate
├── fort14.py             # ADCIRC fort.14 I/O
├── gmsh.py               # Gmsh 2.2 ASCII I/O
├── loaders.py            # TOML, JSON, fort.14, and registry domains
├── size_field.py         # size-field composition
├── octree.py             # adaptive background grid
├── quad_prep.py          # triangle preparation for quadrangulation
├── registry.py           # external domain registry adapter
├── valence.py            # triangle valence balancing
└── <stage>.py            # compatibility shims for _stages modules
tests/
├── test_<stage>.py
├── fixtures/<stage>/*.npz
└── fixtures/fort14/
scripts/
├── export_matlab_fixtures.m
├── bench_*.py
└── render_*.py
docs/
├── governance/
├── PORTING_NOTES.md
├── DOMAIN_IO.md
└── adr/
```

## Install, test, and run

```bash
# Development install
pip install -e ".[dev]"

# Default suite. Slow tests are excluded by pyproject.toml.
pytest tests/ -q

# One faithful-port stage
pytest tests/test_distance.py -v

# Include slow tests
pytest tests/ -q -m slow

# Benchmarks
python scripts/bench_mesh_size.py
python scripts/bench_pipeline.py

# Refresh MATLAB fixtures. Requires MATLAB.
matlab -batch "run('scripts/export_matlab_fixtures.m')"
```

`triangulate()` accepts a `Domain`, a TOML or JSON polygon file, an existing
`fort.14`, or a registry slug. Removed v0.1 helpers such as
`domain_from_polygon()` and `domain_from_sdf()` must not be restored as public
API. Construct a `Domain` directly or use the loaders documented in
`docs/DOMAIN_IO.md`.

## Porting conventions

- Map one MATLAB function to one snake-case Python function. Keep private helpers
  structurally recognizable.
- Every ported function docstring cites its MATLAB path and pinned source commit.
- Replace toolbox functions with SciPy, Shapely, or NumPy equivalents and record
  behavior differences such as boundary inclusion, ordering, and tie-breaking.
- Translate MATLAB `end` to `-1` or `len(x) - 1`. Translate inclusive
  `x(i:j)` to the correct half-open Python slice after subtracting one.
- Treat numerical divergence as a defect. Do not widen tolerances to hide it.
- Add third-party dependencies to `pyproject.toml` explicitly.

Common substitutions:

| MATLAB | Python |
|---|---|
| `inpolygon(...)` | `admesh.in_polygon.in_polygon(...)` |
| `delaunay(x, y)` | `scipy.spatial.Delaunay(np.c_[x, y]).simplices` |
| `griddata(...)` | `scipy.interpolate.griddata(...)` |
| `bwdist(...)` | `scipy.ndimage.distance_transform_edt(...)` |
| `struct(...)` | dataclass or dictionary, chosen per module |
| varying-length cell array | `list[np.ndarray]` |

`src/admesh/_stages/mesh_size.py` keeps a readable `_solve_iter_py()` and a
Numba `_solve_iter_nb()`. They must agree to `atol=1e-10` on fixed input.
`solve_iter()` uses Numba by default and accepts `use_numba=False` for debugging.

## Testing

- Keep one `tests/test_<stage>.py` file per faithful-port stage.
- Store MATLAB inputs and expected outputs in named arrays under
  `tests/fixtures/<stage>/`. Keep each fixture below 1 MB where practical.
- Default reference tolerance is `atol=1e-8, rtol=1e-6`. Document any exception.
- The binding mesh gate is structural validity: positive-area triangles, points
  inside the domain, and a watertight boundary.
- `quality_gate=(0.30, 0.60)` is an advisory smoke default, not an invariant.
  Size-field choices can legitimately lower quality. Use `(0.0, 0.0)` when a
  design requires disabling the check.
- `fort.14` is the only boundary where ADCIRC 1-based node IDs and positive-down
  depth are converted. Internal mesh indices are 0-based and elevations are
  positive-up.

## Branch workflow

The working branch is `development`. Releases go through a pull request from
`development` to `main`. Never push directly to `main` and never force-push a
shared branch. Feature branches are created only by the spec-kit workflow after
checking existing local and remote branches. Do not create duplicate task
branches.

## Governance

This repo is a downstream consumer of [`domattioli/DomI`](https://github.com/domattioli/DomI). Universal git, coding-dispatch, secrets, session-lifecycle, and communication rules live in DomI `.claude/policies/`.
`.domi-pin` drift is checked at session start by `scripts/instructions_on_start.sh`.
Spec-kit artifacts live in DomI `specs/consumers/ADMESH/`, never in a local `.specify/` directory.
Repo-specific rules in `docs/governance/CONSTITUTION.md` override universal defaults only where they do not conflict with the branch policy above.

## Project references

- `docs/governance/CONSTITUTION.md`: binding project principles.
- `docs/governance/PROJECT_PLAN.md`: roadmap and current state.
- `docs/PORTING_NOTES.md`: MATLAB substitutions and behavior differences.
- `docs/DOMAIN_IO.md`: domain formats and loading API.
- `docs/adr/`: architecture decisions, including the CHILmesh boundary.
- `.github/labels.yml`: active label taxonomy. `domi-sync` is retained for
  automated downstream sync issues.

Related repositories are
[`QuADMesh-MATLAB`](https://github.com/domattioli/QuADMesh-MATLAB),
[`CHILmesh`](https://github.com/domattioli/CHILmesh),
[`ADMESH-Domains`](https://github.com/domattioli/ADMESH-Domains), and
[`DomI`](https://github.com/domattioli/DomI).
