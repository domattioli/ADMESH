# MIGRATED — Mesh Registry has moved

> **This feature was extracted to its own repository on 2026-04-26.**
>
> **New home**: [github.com/domattioli/ADMESH-Domains](https://github.com/domattioli/ADMESH-Domains)
>
> All future development happens there. This directory is preserved as a
> historical record only.

## What happened

This spec (`005-adcirc-mesh-registry`) was developed inside the ADMESH repo
between 2026-04-25 and 2026-04-26 as a dictator-approved exception to the
constitution's Principle I (faithful-port-first). The implementation
delivered a v0.1.0 MVP with:

- Three core user stories implemented (US1 Discovery, US2 Lineage, US3 PR Workflow)
- 43 passing contract tests
- 5 seed meshes (NOAA HSOFS, USACE Galveston, academic examples)
- Full Python package + CLI
- Comprehensive documentation

On 2026-04-26 (same day the MVP shipped), the registry was migrated to
its own repository **earlier than the original migration target** (≥20
contributed meshes or ≥3 external dependents). The dictator approved
the early migration to keep ADMESH narrowly focused on the faithful
port and to give the registry its own contribution surface.

## Migration mapping

| Original location in ADMESH | New location in ADMESH-Domains |
|---|---|
| `mesh_registry/` (Python package) | `admesh_domains/` |
| `registry_data/manifest.toml` | `registry_data/manifest.toml` |
| `tests/test_registry_*.py` (3 files) | `tests/test_registry_*.py` |
| `tests/fixtures/registry/` | `tests/fixtures/registry/` |
| `docs/registry/` | `docs/` |
| `.github/workflows/validate-pr.yml` | `.github/workflows/validate-pr.yml` |
| `.github/workflows/publish-hf.yml` | `.github/workflows/publish-hf.yml` |
| `.importlinter` | (deleted — no longer needed) |
| `pyproject.toml` `[registry]` extra | (deleted — now main deps) |
| All spec docs (`spec.md`, `plan.md`, etc.) | `specs/005-adcirc-mesh-registry/` |

**Module rename**: `mesh_registry` → `admesh_domains` to match the new
repo name. All imports updated automatically; PyPI distribution name
is `admesh-domains`.

## What was removed from ADMESH

- All of `mesh_registry/` (the Python package)
- All of `registry_data/` (the seed manifest)
- The three registry test files and their fixtures
- All of `docs/registry/`
- Both registry GitHub Actions workflows
- The `.importlinter` configuration (only needed when both packages co-existed)
- The `[registry]` optional extra and `mesh_registry*` package include from `pyproject.toml`
- The registry-only dev dependencies (`pytest-asyncio`, `responses`, `respx`, `import-linter`)

## What was kept in ADMESH

- This entire `specs/005-adcirc-mesh-registry/` directory (historical record)
- The link to ADMESH-Domains in `pyproject.toml` `[project.urls]`
- The reference to ADMESH-Domains in `CLAUDE.md`
- An entry in `README.md` pointing users at the registry

## Why early migration was approved

Originally (`plan.md` Migration Notes), migration was planned to happen
when the registry reached ≥20 contributed meshes or ≥3 external
dependents. The dictator approved earlier migration because:

1. **Cleaner ADMESH boundary**: ADMESH stays focused on the faithful
   port; no need to maintain segregation rules (cross-import bans,
   import-linter) for code that's no longer here.
2. **Independent contribution surface**: The registry can grow its own
   issue tracker, PR workflow, and release cadence without conflating
   with ADMESH's port milestones.
3. **Domain-specific naming**: The new repo name (`ADMESH-Domains`)
   uses the more accurate term "domains" rather than "meshes" — better
   aligned with how coastal modelers describe these artifacts.
4. **Working state at migration time**: The MVP was complete, tested,
   and documented; there was no half-finished work to disrupt.

## Pointers

- **Use the registry**: Visit [domattioli/ADMESH-Domains](https://github.com/domattioli/ADMESH-Domains)
- **Contribute a mesh**: See `domattioli/ADMESH-Domains/docs/CONTRIBUTING.md`
- **Reference the spec**: This directory contains the original specification
  artifacts (`spec.md`, `plan.md`, `data-model.md`, `contracts/`, `tasks.md`,
  `quickstart.md`, `research.md`); they are also mirrored in the new repo's
  `specs/` directory.

## Original migration plan (for the record)

The pre-migration `MIGRATION.md` in this directory described the
intended extraction process. It was not executed verbatim — the actual
migration used a simpler file-copy approach (preserving the spec docs
in both repos as historical record), but the principles were the same:

- Clean separation of `mesh_registry/` from `admesh/`
- Revert all ADMESH-side changes (`pyproject.toml` extra, package
  discovery include, `.importlinter`, GitHub Actions workflows)
- Preserve the spec directory as historical record
- Update `CLAUDE.md` to remove "active feature" status

The original `MIGRATION.md` is also kept in this directory for context.
