# Testing ADMESH

This document covers how the ADMESH test suite is organized, what each
marker means, and how to run the suite in the same way CI does.

## Quick reference

```bash
# Standard CI lane (matches .github/workflows/tests.yml)
pytest -m "not slow" -q

# Full suite (matches .github/workflows/tests-slow.yml)
pytest -q

# Coverage report (matches the artifact committed to output/coverage.json)
pytest --cov=admesh --cov-report=json --cov-report=term-missing -q

# Slowest 10 tests (matches the artifact committed to output/durations.txt)
pytest --durations=10 -q

# Single file or test
pytest tests/test_api_triangulate.py -v
pytest tests/test_distmesh.py::test_distmesh2d_basic -v

# Run all tests EXCEPT a marker
pytest -m "not slow and not requires_matlab" -q
```

## Markers

| Marker             | Meaning                                                                  | CI behavior |
|--------------------|--------------------------------------------------------------------------|-------------|
| `slow`             | Tests requiring real coastal fixtures (≥1 MB) or long wall-clock         | Standard lane SKIPS; slow lane includes |
| `requires_matlab`  | Tests requiring MATLAB-derived `.npz` fixtures (not committed by default)| Self-skip via `pytest.skip` when fixture missing |
| `requires_chilmesh`| Tests requiring `chilmesh` Python package                                | Self-skip via `pytest.importorskip` when absent |

Tests not tagged with any marker run in every CI lane.

`slow` is declared in `pyproject.toml` under `[tool.pytest.ini_options].markers`.
`requires_matlab` and `requires_chilmesh` are conventional names used by the
existing `skip`/`importorskip` patterns — they are documentation, not formal
markers (a future cleanup may promote them).

## Fixture data layout

```
tests/
├── conftest.py                          # shared parametrize + helpers
├── _structural_validity.py              # assert_structurally_valid()
├── fixtures/
│   ├── fort14/
│   │   ├── adcirc_examples/             # real ADCIRC v55 distribution
│   │   │   ├── wetting_and_drying_test.14  # ~60×65 km, paired-edge weirs (Tier-1)
│   │   │   └── wnat_test.14                # ~10K nodes, US East Coast (Tier-2)
│   │   ├── synthetic/                   # generated polygons
│   │   └── README.md                    # fixture provenance
│   ├── matlab/                          # MATLAB golden fixtures (gitignored;
│   │                                    # generate via scripts/export_matlab_fixtures.m)
│   └── quad_prep/                       # synthetic right-iso targets
└── test_*.py
```

Real coastal fixtures (`wnat_test.14`, `wetting_and_drying_test.14`) are
committed under `tests/fixtures/fort14/adcirc_examples/`. Tests that use
them carry `@pytest.mark.slow`.

MATLAB fixtures are NOT committed. Tests that need them call
`pytest.skip` automatically when the `.npz` file is absent. To regenerate:

```matlab
% In MATLAB, from /workspace/QuADMesh-MATLAB
addpath('/path/to/ADMESH/scripts')
export_matlab_fixtures  % writes .mat files
```

then `python scripts/mat_to_npz.py` to convert to `.npz`.

## Parity-test pattern (port-correctness)

The 13 faithful-port stage modules (`admesh/curvature.py`, `admesh/medial_axis.py`,
etc.) are tested in two ways:

1. **Hand-derived port-correctness tests** — assert mathematical invariants
   of the MATLAB algorithm (e.g. apply_curvature on-boundary formula).
   These run without MATLAB fixtures.
2. **MATLAB-fixture parity tests** — assert numerical parity to the MATLAB
   reference output at `atol=1e-10` (or tighter). These skip when fixtures
   are absent.

Both live in `tests/test_matlab_port.py` and a per-stage `tests/test_<stage>.py`.

## Helpers

- `tests/_structural_validity.py` exposes `assert_structurally_valid(mesh, domain)`:
  asserts every node satisfies `domain.sdf(p) <= bbox_diag * 1e-2`, no
  duplicate triangles, every triangle has positive area. Used by Tier-0/1/2
  acceptance tests.
- `tests/conftest.py` exposes shared `assert_valid_mesh(mesh)` (positional and
  topological validity) and the 5 MVP domain parametrize fixture.

## Cold-clone recipe

To replicate exactly what CI does:

```bash
git clone https://github.com/domattioli/ADMESH.git
cd ADMESH
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
pytest -m "not slow" -q --tb=short
```

Expected: ~30 seconds wall-clock on a 4-core laptop, all tests passing or
explicitly skipped (matlab/chilmesh/registry-error skips are expected when
their respective optional dependencies are absent).

## CI parity

- Standard CI lane: `.github/workflows/tests.yml`. Triggers on every push
  and PR. Matrix: Python 3.10 / 3.11 / 3.12 on `ubuntu-latest`. Runs
  `pytest -m "not slow" -q --tb=short`.
- Slow CI lane: `.github/workflows/tests-slow.yml`. Triggers on Monday
  04:00 UTC, on `v*` tag pushes, and on manual dispatch. Same matrix.
  Runs the full suite (no `-m` filter).

If you see CI behavior diverge from your local run, the most common cause
is a missing optional dependency. `pip install -e ".[dev]"` should give
you everything CI sees.

## Issue #10 status (Tier-1 / Tier-2 release-gate tests)

`tests/test_default_size_field.py::test_tier1_wetting_and_drying_round_trip`
and `::test_tier2_wnat_release_gate` are currently `@pytest.mark.xfail`,
blocked by [issue #10](https://github.com/domattioli/ADMESH/issues/10).
They will be un-`xfail`ed when spec 009 R4 lands. See
`specs/009-release-readiness-for-0.1.0/spec.md` for the release-readiness
plan.
