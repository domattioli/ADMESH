# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Removed
- **BREAKING:** `admesh.quad_prep` (`smooth_for_quadrangulation`, public since 0.5.1) and the unreleased `admesh.quad_layers` prototype moved to QuADMESH. There is no deprecation shim. `admesh.smooth_for_quadrangulation` no longer exists. New import: `from quadmesh.quad_prep import smooth_for_quadrangulation` (`pip install quadmesh`). `admesh.quality.right_iso_quality` stays in ADMESH. The removal ships in the next minor release after 1.0.6. See ADR-002.

### Changed
- Minimum Python is now 3.11. Python 3.10 reached end of life in October 2026. The `tomli` fallback dependency is removed.
- `Domain.from_mesh` (fort.14 and registry domains) and the TOML/JSON loaders compute the signed distance exactly with vectorized shapely 2. The old fort.14 distance used a resampled ring and was off by up to about diag/1000 near the coast; the inside test ran per point. Full Chesapeake Bay fixed-mode run: 228 s -> 50 s. Free-mode meshes of these domains change slightly.
- `triangulate()` defaults to `boundary="fixed"`. Meshes of polygon domains now differ from 1.0.6 output: every input boundary vertex is kept exactly, the nodes between them are spaced by a 1D relaxation along the boundary that follows the size field, and the boundary nodes of the output are exactly those nodes. Pass `boundary="free"` to reproduce the 1.0.6 behaviour for domains built directly with `pts`. Domains from the TOML, JSON and fort.14 loaders now carry their boundary rings, so in `"free"` mode they also get per-edge boundary seeds, which 1.0.6 did not add.
- Domains from the TOML, JSON and fort.14 loaders carry their outer ring (`Domain.pts`) and inner rings (`Domain.holes`). In fort.14 files, closed land segments of type 1, 11 or 21 after the first become holes.
- Fixed mode warns and falls back to free behaviour when a domain has no boundary ring.
- Registry domains carry the same outer and hole rings as fort.14 domains, so `boundary="fixed"` works on them.
- fort.14 rings come from the mesh boundary loops (largest loop outer, rest holes), not from land-segment flags. A land segment is open where the ocean boundary is, and closing it with a chord pinned nodes inside the water (Baranja Hill fixed-mode min quality 0.000, now 0.369).
- Fixed mode re-adds any pinned ring node the solver drops, so output boundary nodes always equal the ring nodes.

### Added
- `admesh.boundary_relax`: 1D DistMesh relaxation of closed boundary rings (`relax_ring`, `relax_rings`, `ring_arclength`). Corners and input vertices are pinned. `init="random"` starts from a random node layout.
- `Domain.holes`: optional tuple of inner rings, default empty. Fixed mode relaxes and pins each hole ring.
- `triangulate(channel_refine=...)`: in fixed mode with no `size_field`, builds a channel-aware field by default (`build_h` medial + curvature terms, sizes `h_min` (default `h_max/8`) to `h_max`, then `limit_gradient`). Narrow channels get interior nodes instead of bank-to-bank slivers (Chesapeake crop: q<0.3 triangles 114 -> 6). Off when `h_min >= h_max`, with a user size field, or when a cost guard finds the grid too large (warns).
- `triangulate(simplify=tol)`: in fixed mode, thins input boundary vertices before pinning (Douglas-Peucker, then a minimum spacing of `tol`). Kept vertices are a subset of the input. Off by default; fixed mode warns when input edges are shorter than 0.25 h. Block_O min quality 0.03 -> 0.71.
- `triangulate(boundary=...)` accepts `"fixed"` and `"free"`. `"slide"` raises `ValueError` until a benchmark shows it is needed.
- `admesh.size_field.limit_gradient(fh, bbox, g=0.2)`: applies the gradient limit over the whole bounding box. The `build_h` limiter only acts within `4*hmin` of the boundary, so jumps from the medial term escape it. On the demo polygon, min quality rises from 0.19 to 0.68.
- `scripts/render_boundary_relax.py` renders the 1D relaxation and the 2D solve as an MP4.

## [1.0.6] - 2026-10-12

### Fixed
- The sdist now contains the C++ sources in `src/admesh/_cpp/`. The 1.0.5 sdist had none, so `pip install` failed with `no such file or directory: 'src/admesh/_cpp/distmesh_cpp.cpp'` on any platform without a matching wheel, for example Python 3.14 or Windows.
- Wheels are built for Python 3.14 (cp314) on Linux x86_64 and macOS arm64. macOS x86_64 has no cp314 wheel because llvmlite publishes none for it. Windows wheels are still deferred; Windows installs build from the sdist.

### Added
- The publish workflow fails if the sdist does not contain `src/admesh/_cpp/distmesh_cpp.cpp`.

## [1.0.5] - 2026-10-11

### Changed
- The registry client now defaults to the public Valence API (https://valence-api.iqh766c2.workers.dev). `VALENCE_API_URL` is an optional override; only `VALENCE_TOKEN` is required.
- The registry client sends an explicit `User-Agent: admesh-registry/1` header. Cloudflare blocks the default `Python-urllib` agent with error 1010.
- The registry functions call the token-gated Valence HTTP API. Set `VALENCE_TOKEN` (and `VALENCE_API_URL` when no default URL applies). Without a token they raise `RegistryAuthError` and make no network request. An unreachable or failing API raises `RegistryUnavailableError`.
- `load_domain_with_metadata` returns only `name` and `sha256`.
- `list_available_domains` returns names only; every value is an empty string.
- `mesh_id` is ignored and warns when it is not the default.
- `triangulate()` with a bare registry slug now raises the registry error with the slug in the message, instead of falling through to the file loader.

### Removed
- The former registry package dependency and the `registry` extra. Installing admesh2D no longer installs Valence code.
- The "Mesh Registry" project URL.

## [1.0.0] - 2026-10-02

### Added
- `triangulate(..., on_iter=None)` forwards a progress callback to DistMesh. It is called once per iteration with the iteration index, the node positions and the triangles, and it does not change the mesh.
- The browser app draws the mesh live while the points move and reports the iteration and point count.

### Fixed
- The polygon signed-distance function is much faster without Numba, as in the browser. A per-cell table of candidate segments replaces the brute-force search, and cells and sign rows are grouped by candidate count so little work is spent on padding. The output is bit-identical. On WNAT (h_min 0.3, h_max 0.5, uniform) meshing takes 1.2 s natively instead of 24.3 s, and 3.9 s in Pyodide instead of 46.3 s.
- The browser app now grades element size instead of meshing uniformly at h_max. The target edge length is h_min at the boundary and grows by 0.2 per unit distance up to h_max, and `medial_method="grid"` also refines narrow channels. A blank h_min means h_max / 10. The WNAT example now uses h_min 0.2 and h_max 2.0: 8358 elements with edges from 0.23 to 0.72 (10th to 90th percentile), where h_max 2.0 alone gave 378 elements of nearly equal size. The boundary distance for this grading is sampled once on a grid and interpolated, and the example meshes in 7.6 s in Pyodide.

## [1.0.0b1] - 2026-10-01

First 1.0 pre-release. The public API in `admesh.__all__` is fixed for 1.x.

### Changed
- Version 1.0.0b1, with the `Development Status :: 4 - Beta` classifier.
- The 14 `admesh.<stage>` compatibility modules are kept for all of 1.x; removal is no earlier than 2.0. The canonical import path is `admesh._stages.<stage>`.
- `docs/api` now documents every name in `admesh.__all__`, including `triangulate_batch` and the Gmsh I/O functions. `tests/test_public_api_docs.py` keeps `__all__`, the README and `docs/api` in agreement.

### Added
- `triangulate(..., medial_method=None)` adds an optional channel-width size contribution. `"grid"` uses the medial-axis grid method of the 2012 port, `"octree"` the octree leaf graph, and `"vdt"` the vector distance transform with corner pruning of Kang and Kubatko (2024, https://doi.org/10.5194/gmd-17-1603-2024), in the new module `admesh.medial_vdt`. The default `None` leaves output unchanged, and the locked stage modules are not modified. `scripts/bench_medial.py` compares the three methods on WNAT and ENPAC; `"vdt"` stays opt-in because it does not beat both baselines on every criterion (results in `benchmarks/medial_vdt.{json,md}`).
- A registry mesh that is registered but not hosted (for example, a license that does not allow a hosted copy) now fails with a not-hosted error before any download is attempted, on releases of the former registry package that define it. Its message names the mesh and says it is not hosted. Older releases keep their behaviour.
- Valence manifest 0.4-ready; 0.3 still supported. Registry lookups run through `admesh._valence_compat`, which picks the group API, the manifest object or the Domain-only API by feature detection. `list_available_domains()` now also lists Collections, and aliases and Collections load by name. Domain metadata reports both `continent` and `region`, and mesh metadata both `format` and `type`.
- `triangulate_batch(domains, n_jobs=None, **kwargs)` meshes several domains on a process pool (#99 P2). Results come back in input order and are bit-identical to a serial `triangulate` loop. On 8 WNAT meshes (94,777 nodes each) 8 workers run 5.09x faster than the serial loop; small meshes gain less because each worker takes about 0.5 s to start.
- `scripts/bench_batch.py --wnat` runs the P2 gate: at least 4.0x at 8 workers on 8 WNAT meshes. Results and figure in `benchmarks/results/batch_wnat.{json,png}`.

### Fixed
- `scripts/bench_batch.py` warms the Numba cache before timing the serial baseline. A cold baseline had inflated the speedup reported in 8f1e67b (2.91x).

## [0.6.1] - 2026-07-14

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

## [0.6.0] - 2026-07-05

### Added
- Octree size-field production (spec-029): vectorized SoA octree backend, leaf-graph gradient limiting, IDW smooth interpolation for curvature/medial-axis fallback, WNAT/ENPAC benchmark integration.

### Changed
- Benchmark standard migration: WNAT → ENPAC 2003 (#154) for Tier-2 evaluation; ENPAC timing baseline, quality targets, and fixture set now canonical.
- Documentation: parallel-branches history corrected (#185); rolling PR `development → main` formalized (#182).

### Fixed
- Test suite: consolidate additive-layer tests, resolve skip debt (#184); correct `inpaint_nans` 1-D Laplacian column alignment (#155).

## [0.5.1] - 2026-06-15

First PyPI release since 0.2.1, consolidates the unreleased 0.3–0.5 development line.

### Changed
- Dependency pins: the former registry package pin raised to `>=0.4.2`; `[viz]` `chilmesh>=1.1,<2 → >=1.2.1,<2`.
- Source archives (git archive / sdist / GitHub-release tarball / Zenodo) exclude agent + dev-process files via `.gitattributes` `export-ignore`.

### Fixed
- `__version__` corrected `0.2.1 → 0.5.1` (had drifted from `pyproject.toml`).

### Notes
- Consolidated since 0.2.1: octree size-field, registry redirect to its current name, README canonicalization, ENPAC standard-benchmark migration (#154), `bench_wnat.py` canonical-loader fix (#158).

## [0.2.1] - 2026-05-18

### Documentation
- README overhaul (issue #66): Why-ADMESH section, 13-stage pipeline table, `BoundaryType` IBTYPE table, 3-line Status snapshot, single deduplicated badge row, table of contents, absolute image URL for PyPI rendering.
- Quickstart API correction: `admesh.domain_from_polygon(...)` (did not exist) replaced with the real surface, `admesh.domains.UNIT_DISK`, `admesh.api.Domain(sdf=..., bbox=...)`, `Domain.from_mesh(...)`, and the `triangulate("path.14", ...)` string overload.
- `CITATION.cff` added at repo root. Software-release citation via Zenodo DOI `10.5281/zenodo.20264101`; algorithm citation via preferred-citation block pointing at the 2012 Ocean Dynamics paper.
- README Citation section now distinguishes algorithm-paper vs software-release citations.

### Fixed
- Resync `admesh/__init__.py` `__version__` to match `pyproject.toml` (drifted to `0.1.0` during the spec-009 R1 tag-gate hygiene pass).
- `.github/workflows/publish.yml` referenced `secrets.PYPI_TOKEN` but the repo secret is named `PYPI_API_TOKEN`; the empty-password substitution caused twine 403 on the v0.2.0 release. Now references the correct name. (Landed in 0.2.0 hotfix during the release; recorded here for the changelog trail.)

No code changes vs 0.2.0, drop-in safe for existing callers.

## [0.2.0] - 2026-05-18

### Added
- Valence balancing via edge flipping (`admesh/valence.py`): issue #27
- `initial_points` warm-start parameter for `triangulate()`: issue #45
- Convergence diagnostics in `distmesh2d` (oscillation + stagnation detection): issue #47
- Restored ADMESH-variant distmesh code (`MeshOutput`, `SizeFn`, `distmesh2d_admesh`)
- Tier-1 / Tier-2 acceptance tests for size-field stack structural validity: issue #10
- Holistic test suite audit (`TEST-AUDIT.md`): issue #59
- Cross-repo sync contract and dev tooling auto-install

  > Correction (2026-09-26): `TEST-AUDIT.md` is no longer in this repository; audit records are kept outside this repository. The session-start hook and its script were untracked on 2026-09-24 and are local tooling, not part of the package.

### Fixed
- 1D boundary seeding for `Domain` path on notched-rectangle geometry: issue #2
- `h_min` / `h_max` parameters now propagate into the size field even when no user contributions are supplied, issue #37
- `Domain.from_mesh()` produces a proper SDF for real-world ADCIRC meshes: issues #38, #39

### Documentation
- `pfix` bit-exact preservation contract: issue #46
- Planning artifacts for Gmsh I/O integration (spec 008): issue #5
- Planning for PyPI namespace claim: issue #13
- `CONSTITUTION.md` covering specs 001-008: issue #57
- Scripts audit + cleanup recommendations: issue #42

### Infrastructure
- Single-branch policy: all routine fixes land on `daily-issue-fixing`
- Synced governance pin to the v2.1 manifest

## [0.1.0] - 2026-04-27

### Added
- Issue #10 fix: Polygon SDF with winding-number testing for multiply-connected domains
- Convergence detection in distmesh to prevent hanging on pathological size fields
- GitHub release skill with automatic credential and metadata detection
- PyPI publish skill with retry logic and verification
- Diagnostic infrastructure for mesh generation issues
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
