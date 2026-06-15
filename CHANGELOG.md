# Changelog

All notable changes to this project will be documented in this file.

## [0.5.1] — 2026-06-15

First PyPI release since 0.2.1 — consolidates the unreleased 0.3–0.5 development line.

### Changed
- Dependency pins: `valence-domains>=0.4 → >=0.4.2`; `[viz]` `chilmesh>=1.1,<2 → >=1.2.1,<2`.
- Source archives (git archive / sdist / GitHub-release tarball / Zenodo) exclude agent + dev-process files via `.gitattributes` `export-ignore`.

### Fixed
- `__version__` corrected `0.2.1 → 0.5.1` (had drifted from `pyproject.toml`).

### Notes
- Consolidated since 0.2.1: octree size-field, valence-domains registry redirect (was admesh-domains), README canonicalization, ENPAC standard-benchmark migration (#154), `bench_wnat.py` canonical-loader fix (#158).

## [0.2.1] - 2026-05-18

### Documentation
- README overhaul (issue #66): Why-ADMESH section, 13-stage pipeline table, `BoundaryType` IBTYPE table, 3-line Status snapshot, single deduplicated badge row, table of contents, absolute image URL for PyPI rendering.
- Quickstart API correction: `admesh.domain_from_polygon(...)` (did not exist) replaced with the real surface — `admesh.domains.UNIT_DISK`, `admesh.api.Domain(sdf=..., bbox=...)`, `Domain.from_mesh(...)`, and the `triangulate("path.14", ...)` string overload.
- `CITATION.cff` added at repo root. Software-release citation via Zenodo DOI `10.5281/zenodo.20264101`; algorithm citation via preferred-citation block pointing at the 2012 Ocean Dynamics paper.
- README Citation section now distinguishes algorithm-paper vs software-release citations.

### Fixed
- Resync `admesh/__init__.py` `__version__` to match `pyproject.toml` (drifted to `0.1.0` during the spec-009 R1 tag-gate hygiene pass).
- `.github/workflows/publish.yml` referenced `secrets.PYPI_TOKEN` but the repo secret is named `PYPI_API_TOKEN`; the empty-password substitution caused twine 403 on the v0.2.0 release. Now references the correct name. (Landed in 0.2.0 hotfix during the release; recorded here for the changelog trail.)

No code changes vs 0.2.0 — drop-in safe for existing callers.

## [0.2.0] - 2026-05-18

### Added
- Valence balancing via edge flipping (`admesh/valence.py`) — issue #27
- `initial_points` warm-start parameter for `triangulate()` — issue #45
- Convergence diagnostics in `distmesh2d` (oscillation + stagnation detection) — issue #47
- Restored ADMESH-variant distmesh code (`MeshOutput`, `SizeFn`, `distmesh2d_admesh`)
- Tier-1 / Tier-2 acceptance tests for size-field stack structural validity — issue #10
- Holistic test suite audit (`TEST-AUDIT.md`) — issue #59
- DomI cross-repo sync contract + SessionStart hook plugin auto-install

### Fixed
- 1D boundary seeding for `Domain` path on notched-rectangle geometry — issue #2
- `h_min` / `h_max` parameters now propagate into the size field even when no user contributions are supplied — issue #37
- `Domain.from_mesh()` produces a proper SDF for real-world ADCIRC meshes — issues #38, #39

### Documentation
- `pfix` bit-exact preservation contract — issue #46
- Spec-kit planning artifacts for Gmsh I/O integration (spec 008) — issue #5
- Spec-kit planning for PyPI namespace claim — issue #13
- `CONSTITUTION.md` covering specs 001-008 — issue #57
- Scripts audit + cleanup recommendations — issue #42

### Infrastructure
- Single-branch policy: all routine fixes land on `daily-issue-fixing`
- Synced `.domi-pin` to DomI v2.1 manifest

## [0.1.0] - 2026-04-27

### Added
- Issue #10 fix: Robust polygon SDF with winding-number testing for multiply-connected domains
- Convergence detection in distmesh to prevent hanging on pathological size fields
- GitHub release skill with automatic credential and metadata detection
- PyPI publish skill with retry logic and verification
- Comprehensive diagnostic infrastructure for mesh generation issues
- Support for real-world ADCIRC coastal mesh fixtures (Tier-1, Tier-2)

### Fixed
- Domain.from_mesh() SDF construction for accurate boundary distance computation
- Distmesh oscillation and timeout issues through stagnant iteration detection
- Size-field stack domain overshoot on multiply-connected domains

### Documentation
- Complete specification for issue #10 fix
- Implementation plan and 28-task decomposition
- Diagnostic harness and profiler modules
- Release automation guides

### Technical Details
- Replaced bbox-based SDF heuristic with proper winding-number algorithm
- Added convergence detection with 20-iteration stagnation threshold
- Automated release workflow with non-interactive skill implementations
