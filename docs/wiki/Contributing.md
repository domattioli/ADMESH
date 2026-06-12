# Contributing

ADMESH is a focused port. Contributions are welcome — keep them
small, well-tested, and aligned with the
[constitution](https://github.com/domattioli/ADMESH/blob/main/docs/governance/CONSTITUTION.md).
For the conceptual primer before touching code, read
[Concepts](Concepts.md).

## Getting set up

```bash
git clone https://github.com/domattioli/ADMESH.git
cd ADMESH
pip install -e ".[dev]"
pytest tests/ -q   # should be all green or only known xfails
```

Requires Python ≥ 3.10. Core deps: NumPy, SciPy, Numba, Shapely.

## How work is organised

ADMESH uses **spec-kit** for non-trivial features. Each spec lives
in its own directory:

- [`specs/001-pythonize-and-fort14-integration/`](https://github.com/domattioli/ADMESH/tree/main/specs/001-pythonize-and-fort14-integration) — shipped foundation
- [`specs/002-size-field-defaults/`](https://github.com/domattioli/ADMESH/tree/main/specs/002-size-field-defaults) — active (default size-field stack + paired-edge BCs)
- [`specs/003-fix-outer-ring-sorting/`](https://github.com/domattioli/ADMESH/tree/main/specs/003-fix-outer-ring-sorting) — release-blocker fix
- [`specs/004-quad-prep-smoother/`](https://github.com/domattioli/ADMESH/tree/main/specs/004-quad-prep-smoother) — scoped (post-v1 sequencing)
- [`specs/005-adcirc-mesh-registry/`](https://github.com/domattioli/ADMESH/tree/main/specs/005-adcirc-mesh-registry) — migrated to [ADMESH-Domains](https://github.com/domattioli/ADMESH-Domains)
- [`specs/006-verify-h-parameter-usage/`](https://github.com/domattioli/ADMESH/tree/main/specs/006-verify-h-parameter-usage) — diagnostic investigation
- [`specs/007-1d-boundary-seeding/`](https://github.com/domattioli/ADMESH/tree/main/specs/007-1d-boundary-seeding) — scoped
- [`specs/008-gmsh-io-integration/`](https://github.com/domattioli/ADMESH/tree/main/specs/008-gmsh-io-integration) — scoped

A spec contains: `plan.md`, `research.md`, `data-model.md`,
`contracts/*.md`, `quickstart.md`, `tasks.md`. Tasks are worked one
at a time, with one commit per task and tests landing alongside the
implementation.

For tiny changes (typo fixes, doc tweaks, single-bug fixes) a spec
is overkill — open a PR directly.

## Branch + commit conventions

- **Branch name**: `NNN-short-feature-slug` for spec-kit work,
  `fix/short-description` for bug fixes.
- **Commit message**: prefix with the spec number when applicable —
  `feat(002): wire bathymetry stage into default stack`,
  `fix(api): outer-ring picker should sort by signed area`.
- One logical change per commit. Small commits are easier to review
  and to revert.

## Tests are non-negotiable

Every change ships with tests that prove it. The test ladder:

| Tier | Where | When it runs |
|---|---|---|
| 0 — synthetic | `tests/test_*.py` | every PR |
| 1 — small ADCIRC fixture | `tests/test_default_size_field.py::test_tier1_*` | every PR |
| 2 — WNAT release gate | `tests/test_default_size_field.py::test_tier2_*` | every PR (≤ 60 s wall-clock) |

If you're touching the 13 stage modules in `admesh/*.py`, the bar is
*numerical equivalence to the MATLAB reference* — fixtures live in
`tests/fixtures/<stage>/` as `.npz` files. Regenerating those
requires MATLAB; see `scripts/export_matlab_fixtures.m`.

## Constitutional invariants (please read before touching code)

From
[`docs/governance/CONSTITUTION.md`](https://github.com/domattioli/ADMESH/blob/main/docs/governance/CONSTITUTION.md)
Article II:

1. **The 13 stage modules in `admesh/*.py` stay numerically identical
   to the MATLAB reference.** Improvements happen via the additive
   surface (`api.py`, `fort14.py`, `size_field.py`, `viz.py`,
   `quad_prep.py`, …), not by editing stages. See the
   [Architecture overview](Architecture-Overview.md) for the two-layer
   structure.
2. **No C extensions in v1.** Numba is fine; `ctypes` bindings to
   `MeshSizeIterativeSolver.c` are not.
3. **0-based indexing throughout.** When porting from MATLAB,
   subtract 1 wherever the source indexes into arrays.

If your change requires bending one of these, open an issue first
to discuss — don't slip it into a PR.

## What we look for in a PR

- A clear description of *what* changed and *why*.
- Tests that fail without the change and pass with it.
- For ports of MATLAB code: a one-line note in
  [`docs/PORTING_NOTES.md`](https://github.com/domattioli/ADMESH/blob/main/docs/PORTING_NOTES.md)
  for any non-obvious substitution.
- Green CI.
- No unrelated drive-by edits — reformat-only commits muddy the
  review.

## Reporting bugs

[Open an issue](https://github.com/domattioli/ADMESH/issues/new). If
the bug touches mesh output, include:

- A minimal `fort.14` (or the call sequence with synthetic inputs)
  that reproduces.
- The failing assertion + traceback.
- Your Python + NumPy + Numba versions (`pip list | grep -iE "numpy|numba|scipy"`).

## Getting help

- **Theory** (algorithm, size-field formulation, ADCIRC integration):
  Ethan J. Kubatko — kubatko.3@osu.edu
- **Code** (this repo): Dominik Mattioli —
  [github.com/domattioli](https://github.com/domattioli)
