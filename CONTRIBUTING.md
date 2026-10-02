# Contributing to ADMESH

ADMESH is an automatic unstructured mesh generator for 2D shallow-water domains.
This guide covers what you need to make changes locally and open a pull request.

## Dev setup

```bash
git clone https://github.com/domattioli/ADMESH.git
cd ADMESH
pip install -e ".[dev]"
```

Requirements: Python ≥ 3.10. Core deps (NumPy, SciPy, Numba, Shapely,
`admesh-domains`) install automatically. Optional viz extras via `pip install -e ".[dev,viz]"`.

## Running tests

```bash
# Standard lane (matches CI; ~30s on a laptop)
pytest -m "not slow" -q

# Full suite including slow real-world fixtures
pytest -q

# Specific file or test
pytest tests/test_api_triangulate.py -v
pytest tests/test_distmesh.py::test_distmesh2d_basic -v

# With coverage
pytest --cov=admesh --cov-report=term-missing
```

See `TESTING.md` for the full marker reference and fixture-data layout.

## Branch contract

- All in-progress work lives on `development`. Open issues directly
  against that branch; do not push directly to `main`.
- Feature specs (`specs/NNN-name/`) may live on their own short-lived
  `NNN-name` branches and merge back to `development` when complete.
- Never push to `main` from a fork or local clone.
- Never force-push to `main`, `development`, or any branch with an
  open pull request from another contributor.
- Never use `--no-verify`, `--no-gpg-sign`, or any other flag that skips
  configured git hooks unless explicitly approved by a maintainer in a
  comment on the PR.

## Filing an issue

- ADMESH bug, feature, or doc gap → file at
  [github.com/domattioli/ADMESH/issues](https://github.com/domattioli/ADMESH/issues).
  Include: minimal repro, expected vs. actual, ADMESH version
  (`python -c "import admesh; print(admesh.__version__)"`),
  and OS / Python version.

## Code style

- Run `ruff check admesh tests` and `ruff format admesh tests` before committing.
- Run `mypy admesh` for type-check signal (not gating yet, but soon).
- Numeric code stays faithful to the MATLAB `01_ADMESH_Library` reference:
  the 13 locked stage modules under `src/admesh/_stages/` must remain
  numerically equivalent to the pinned MATLAB source. Any divergence needs a
  `docs/PORTING_NOTES.md` entry.

## Porting rules

ADMESH is a Python port of `01_ADMESH_Library` from
[`domattioli/QuADMesh-MATLAB`](https://github.com/domattioli/QuADMesh-MATLAB)
at commit `19b2eb9f078a648daec3fd40d5d4c6e072f467ac`. These rules apply to
every change:

- The 13 original stage modules under `src/admesh/_stages/` are locked
  faithful ports. A change to one needs a written numerical justification and
  passing MATLAB reference tests. New behavior goes in the additive API layer.
  `domains.py`, `octree_grid.py` and `octree_medial.py` in that directory are
  Python-only and are not locked.
- Map one MATLAB function to one snake-case Python function. Each ported
  function's docstring cites its MATLAB path and the pinned commit.
- Python uses 0-based indices. Convert MATLAB indexing explicitly and record
  non-obvious substitutions in `docs/PORTING_NOTES.md`.
- MATLAB column-major order matters only at input and output boundaries.
  Internal arrays use normal NumPy layout.
- Treat numerical divergence from the MATLAB reference as a defect. Do not
  widen tolerances to hide it. The default reference tolerance is
  `atol=1e-8, rtol=1e-6`.
- MATLAB reference fixtures under `tests/fixtures/` are read-only. Regenerate
  them only from the pinned MATLAB source with
  `scripts/export_matlab_fixtures.m`. Never delete mesh fixtures or reference
  data.
- The supported install path must work without a C++ toolchain. The C++
  accelerator in `src/admesh/_cpp/` is optional and falls back to Python and
  Numba.
- `fort.14` is the only boundary where ADCIRC 1-based node IDs and
  positive-down depth are converted. Internal mesh indices are 0-based and
  elevations are positive-up.

## Commit messages

- Conventional-commits style preferred: `feat: ...`, `fix: ...`, `chore: ...`,
  `docs: ...`, `test: ...`, `refactor: ...`.
- Reference the issue: `Resolve #NN: ...` or `Refs #NN: ...`.
- Feature-spec commits: `spec NNN ${PHASE}: ...` (e.g. `spec 009 R1: ...`).

## Pull requests

- Target `development`, not `main`.
- Mark as draft until CI is green.
- Include a "Test plan" section in the body. If the PR is documentation-only,
  say so explicitly.
- Link the issue with `Closes #NN` in the description.
