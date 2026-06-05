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

- All in-progress work lives on `daily-maintenance`. Open issues directly
  against that branch; do not push directly to `main`.
- Feature specs (`specs/NNN-name/`) may live on their own short-lived
  `NNN-name` branches and merge back to `daily-maintenance` when complete.
- Never push to `main` from a fork or local clone.
- Never force-push to `main`, `daily-maintenance`, or any branch with an
  open pull request from another contributor.
- Never use `--no-verify`, `--no-gpg-sign`, or any other flag that skips
  configured git hooks unless explicitly approved by a maintainer in a
  comment on the PR.

## DomI sync (governance / skill marketplace)

ADMESH consumes shared skills, hooks, and policies from the upstream
[DomI](https://github.com/domattioli/DomI) repository. The pinned upstream
commit is recorded in `.domi-pin` at the repo root. Before starting a
write session, verify the pin matches DomI HEAD by either:

- Running `bash skills/sync-from-domi/scripts/check_pin.sh` (exit 0 = synced),
  or
- Saying "sync from DomI" in a Claude Code session — the `sync-from-domi`
  skill will refresh the pin and update installed skills if drift is detected.

A `chore: sync DomI@<sha>` issue auto-opens on this repo whenever DomI
ships a new commit. Close the issue by running the sync.

## Filing an issue

- ADMESH bug, feature, or doc gap → file at
  [github.com/domattioli/ADMESH/issues](https://github.com/domattioli/ADMESH/issues).
  Include: minimal repro, expected vs. actual, ADMESH version
  (`python -c "import admesh; print(admesh.__version__)"`),
  and OS / Python version.
- Cross-repo / governance concern → file at
  [github.com/domattioli/DomI/issues](https://github.com/domattioli/DomI/issues)
  with a `From: ADMESH` line in the body.

## Code style

- Run `ruff check admesh tests` and `ruff format admesh tests` before committing.
- Run `mypy admesh` for type-check signal (not gating yet, but soon).
- Numeric code follows the Constitution (`docs/governance/CONSTITUTION.md`):
  faithful ports of MATLAB `01_ADMESH_Library` modules live under
  `admesh/_stages/` (once spec 009 R3 lands) or directly under `admesh/`
  today, and must produce results bit-equivalent to the MATLAB reference
  within documented tolerances. Any divergence requires a
  `docs/PORTING_NOTES.md` entry.

## Commit messages

- Conventional-commits style preferred: `feat: ...`, `fix: ...`, `chore: ...`,
  `docs: ...`, `test: ...`, `refactor: ...`.
- Reference the issue: `Resolve #NN: ...` or `Refs #NN: ...`.
- Spec-kit commits: `spec NNN ${PHASE}: ...` (e.g. `spec 009 R1: ...`).

## Pull requests

- Target `daily-maintenance`, not `main`.
- Mark as draft until CI is green.
- Include a "Test plan" section in the body. If the PR is documentation-only,
  say so explicitly.
- Link the issue with `Closes #NN` in the description.
