# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [1.0.0b1] — 2026-10-01

First 1.0 pre-release. The public API in `admesh.__all__` is fixed for 1.x.

### Changed
- Version 1.0.0b1, with the `Development Status :: 4 - Beta` classifier.
- The 14 `admesh.<stage>` compatibility modules are kept for all of 1.x; removal is no earlier than 2.0. The canonical import path is `admesh._stages.<stage>`.
- `docs/api` now documents every name in `admesh.__all__`, including `triangulate_batch` and the Gmsh I/O functions. `tests/test_public_api_docs.py` keeps `__all__`, the README and `docs/api` in agreement.

### Added
- `triangulate(..., medial_method=None)` adds an optional channel-width size contribution. `"grid"` uses the medial-axis grid method of the 2012 port, `"octree"` the octree leaf graph, and `"vdt"` the vector distance transform with corner pruning of Kang and Kubatko (2024, https://doi.org/10.5194/gmd-17-1603-2024), in the new module `admesh.medial_vdt`. The default `None` leaves output unchanged, and the locked stage modules are not modified. `scripts/bench_medial.py` compares the three methods on WNAT and ENPAC; `"vdt"` stays opt-in because it does not beat both baselines on every criterion (results in `benchmarks/medial_vdt.{json,md}`).
- A registry mesh that is registered but not hosted (for example, a license that does not allow a hosted copy) now fails with `valence_domains.MeshNotHostedError` before any download is attempted, on `valence-domains` releases that define it. Its message names the mesh and says it is not hosted. Older releases keep their behaviour.
- Valence manifest 0.4-ready; 0.3 still supported. Registry lookups run through `admesh._valence_compat`, which picks the group API, the manifest object or the Domain-only API by feature detection. `list_available_domains()` now also lists Collections, and aliases and Collections load by name. Domain metadata reports both `continent` and `region`, and mesh metadata both `format` and `type`.
- `triangulate_batch(domains, n_jobs=None, **kwargs)` meshes several domains on a process pool (#99 P2). Results come back in input order and are bit-identical to a serial `triangulate` loop. On 8 WNAT meshes (94,777 nodes each) 8 workers run 5.09x faster than the serial loop; small meshes gain less because each worker takes about 0.5 s to start.
- `scripts/bench_batch.py --wnat` runs the P2 gate: at least 4.0x at 8 workers on 8 WNAT meshes. Results and figure in `benchmarks/results/batch_wnat.{json,png}`.

### Fixed
- `scripts/bench_batch.py` warms the Numba cache before timing the serial baseline. A cold baseline had inflated the speedup reported in 8f1e67b (2.91x).

## [0.6.1] — 2026-07-14

Packaging and CI patch on 0.6.0. No change under `src/`.

### Fixed
- Distributed wheel builds no longer pass `-march=native` (#195).
- The cibuildwheel test environment installs binary numba and llvmlite (#196) and no longer builds scipy from source (#190).
- `publish.yml` has a single top-level permissions block (#193) and accepts a manual `workflow_dispatch` (#191).

### Added
- `SECURITY.md` (#194).
- A viz-interop CI lane, so the CHILmesh and Matplotlib tests run (#197).

### Documentation
- README benchmark figure corrected from 26.7x to 26.6x (#189).

## [0.6.0] — 2026-07-05

### Added
- Octree size-field production (spec-029): vectorized SoA octree backend, leaf-graph gradient limiting, IDW smooth interpolation for curvature/medial-axis fallback, WNAT/ENPAC benchmark integration.

### Changed
- Benchmark standard migration: WNAT → ENPAC 2003 (#154) for Tier-2 evaluation; ENPAC timing baseline, quality targets, and fixture set now canonical.
- Documentation: parallel-branches lineage corrected (#185); rolling PR `development → main` formalized (#182).

### Fixed
- Test suite: consolidate additive-layer tests, resolve skip debt (#184); correct `inpaint_nans` 1-D Laplacian column alignment (#155).

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
- Cross-repo sync contract + session-start hook plugin auto-install

  > Correction (2026-09-26): `TEST-AUDIT.md` is no longer in this repository; audit records are kept outside this repository. The session-start hook and its script were untracked on 2026-09-24 and are local tooling, not part of the package.

### Fixed
- 1D boundary seeding for `Domain` path on notched-rectangle geometry — issue #2
- `h_min` / `h_max` parameters now propagate into the size field even when no user contributions are supplied — issue #37
- `Domain.from_mesh()` produces a proper SDF for real-world ADCIRC meshes — issues #38, #39

### Documentation
- `pfix` bit-exact preservation contract — issue #46
- Planning artifacts for Gmsh I/O integration (spec 008) — issue #5
- Planning for PyPI namespace claim — issue #13
- `CONSTITUTION.md` covering specs 001-008 — issue #57
- Scripts audit + cleanup recommendations — issue #42

### Infrastructure
- Single-branch policy: all routine fixes land on `daily-issue-fixing`
- Synced governance pin to the v2.1 manifest

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
