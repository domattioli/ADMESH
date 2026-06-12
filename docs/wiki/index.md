# ADMESH Wiki

<p align="center">
  <img src="https://raw.githubusercontent.com/domattioli/ADMESH/main/papers/fig8_admesh_wnat.png" alt="ADMESH mesh of the Western North Atlantic" width="80%">
</p>

Python port of [`QuADMesh-MATLAB`](https://github.com/domattioli/QuADMesh-MATLAB)
`01_ADMESH_Library` (commit `19b2eb9`) — an automatic unstructured-triangle
mesh generator for 2D shallow-water models, with native ADCIRC `fort.14` I/O.

This wiki is the **navigation, concepts, roadmap, and ecosystem** layer.
The repository itself is the source of truth for code, specs, and
governance. **If a wiki page contradicts the repo, the repo wins.**

## Start here

| You want… | Look at… |
|---|---|
| Conceptual primer | [Concepts](Concepts.md) — distmesh, size field, SDF, medial axis, BC types |
| End-to-end walkthrough | [Pipeline](Pipeline.md) — `domain → triangulate → fort.14 → ADCIRC` |
| Module map | [Architecture overview](Architecture-Overview.md) |
| Where the project is going | [Roadmap](Roadmap.md) — 0.1.0 gate + post-v1 |
| Where ADMESH fits | [Ecosystem](Ecosystem.md) — CHILmesh, MADMESHR, ADMESH-Domains, ADCIRC |
| Question that comes up often | [FAQ](FAQ.md) |
| Contributing | [Contributing](Contributing.md) |

## Look at the repo for…

| Artifact | Path |
|---|---|
| Install + quickstart | [`README.md`](https://github.com/domattioli/ADMESH/blob/main/README.md) |
| Active feature spec | [`specs/002-size-field-defaults/`](https://github.com/domattioli/ADMESH/tree/main/specs/002-size-field-defaults) |
| Shipped foundation spec | [`specs/001-pythonize-and-fort14-integration/`](https://github.com/domattioli/ADMESH/tree/main/specs/001-pythonize-and-fort14-integration) |
| Scoped follow-up specs | [`specs/003-008/`](https://github.com/domattioli/ADMESH/tree/main/specs) — outer-ring sort, quad-prep smoother, mesh registry, h-param audit, 1D boundary seeding, Gmsh I/O |
| Active project plan | [`docs/governance/PROJECT_PLAN.md`](https://github.com/domattioli/ADMESH/blob/main/docs/governance/PROJECT_PLAN.md) |
| Constitution + rules | [`docs/governance/CONSTITUTION.md`](https://github.com/domattioli/ADMESH/blob/main/docs/governance/CONSTITUTION.md) |
| Operational notes for AI sessions | [`CLAUDE.md`](https://github.com/domattioli/ADMESH/blob/main/CLAUDE.md) |
| MATLAB → Python substitutions log | [`docs/PORTING_NOTES.md`](https://github.com/domattioli/ADMESH/blob/main/docs/PORTING_NOTES.md) |
| Session artifacts | [`docs/sessions/`](https://github.com/domattioli/ADMESH/tree/main/docs/sessions) |
| Open issues | [Issues](https://github.com/domattioli/ADMESH/issues) |

## What the wiki never duplicates

PR-reviewed, version-locked to the code — read in the repo only:

- `docs/governance/CONSTITUTION.md` (governance, immutable invariants)
- `docs/governance/PROJECT_PLAN.md` (active roadmap, session log)
- `CLAUDE.md` (session operational reference)
- `specs/` (feature specifications + contracts + plans)
- `docs/PORTING_NOTES.md` (MATLAB substitutions log)

## Status

**0.1.0 in progress.** First PyPI tag follows when the Tier-2 / WNAT
structural-validity gate is green and the three open release-blockers
([#10](https://github.com/domattioli/ADMESH/issues/10),
 [#11](https://github.com/domattioli/ADMESH/issues/11),
 [#12](https://github.com/domattioli/ADMESH/issues/12)) close. See
[Roadmap](Roadmap.md) for detail.
