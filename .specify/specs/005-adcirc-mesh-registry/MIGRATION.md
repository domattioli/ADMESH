# Migration Plan: Extract mesh_registry to Standalone Repo

**Status**: Deferred (target: ≥20 contributed meshes or ≥3 external dependents)  
**Created**: 2026-04-26

## Overview

The `mesh_registry/` implementation currently lives inside the ADMESH repo as an interim arrangement (dictator-approved exception, 2026-04-25). This document describes how to cleanly extract it to a standalone `domattioli/adcirc-mesh-registry` repo when the time comes.

## Changes to ADMESH Documents (Must Prune)

The following changes to ADMESH core documents **must be reverted or removed** when extracting:

### 1. `pyproject.toml`

**Added**: `[project.optional-dependencies]` `registry` extra

```toml
registry = [
    "pydantic>=2.0",
    "shapely>=2.0",
    "httpx>=0.25",
    "huggingface_hub>=0.20",
    "click>=8.1",
    "tomli-w>=1.0",
]
```

**Action on extraction**: Delete this entire section. The registry will have its own `pyproject.toml` with these as main dependencies.

**Modified**: `[tool.setuptools.packages.find]` `include` field

```toml
include = ["admesh*", "mesh_registry*"]  # Added "mesh_registry*"
```

**Action on extraction**: Revert to `include = ["admesh*"]`.

**Added to `[project.optional-dependencies]` `dev`**: Test/CI dependencies

```python
"pytest-asyncio",
"responses",
"respx",
"import-linter",
```

**Action on extraction**: These can stay in ADMESH dev deps (they're useful for the admesh test suite too). Alternatively, remove them if they're only used by registry tests.

### 2. `CLAUDE.md`

**Added**: SPECKIT marker notes about mesh_registry

Lines referring to:
- "Active spec-kit feature: `005-adcirc-mesh-registry`"
- "Implementation lives **inside ADMESH** under... `mesh_registry/`"
- "Cross-imports between `admesh.*` and `mesh_registry.*` are forbidden"
- "Migration to... `domattioli/adcirc-mesh-registry` repo is planned but deferred"

**Action on extraction**: Delete or replace with reference to separate repo. The ADMESH project should no longer mention mesh_registry.

### 3. `.importlinter` (NEW FILE)

**Action on extraction**: Delete entirely. This file enforces the cross-import ban between admesh and mesh_registry; it's only needed while they're in the same repo.

### 4. `.github/workflows/validate-pr.yml` and `publish-hf.yml` (NEW FILES)

**Action on extraction**: Delete from ADMESH. These workflows will move to the new repo.

### 5. `README.md` (if modified)

**Expected**: Future modification to add a link to the registry. E.g., "See the [mesh registry](https://github.com/domattioli/adcirc-mesh-registry) for discovering and managing ADCIRC meshes."

**Action on extraction**: Keep the link; just update the link target if the new repo slug changes.

## Extraction Steps

When ≥20 meshes exist or ≥3 external dependents adopt the registry:

1. **Create new repo**:
   ```bash
   gh repo create domattioli/adcirc-mesh-registry --public --clone --template=...
   ```

2. **Extract mesh_registry subtree** (uses git-subtree):
   ```bash
   cd /path/to/ADMESH
   git subtree split --prefix=mesh_registry/ -b registry-extract
   cd /path/to/new/adcirc-mesh-registry
   git merge --allow-unrelated-histories registry-extract
   ```

3. **Move supporting files**:
   ```bash
   # From ADMESH to new repo:
   git subtree split --prefix=registry_data/ -b registry-data-extract
   git subtree split --prefix=tests/fixtures/registry/ -b registry-fixtures-extract
   git subtree split --prefix=docs/registry/ -b registry-docs-extract
   git subtree split --prefix=.github/workflows/validate-pr.yml -b registry-ci-extract
   git subtree split --prefix=.github/workflows/publish-hf.yml -b registry-ci-extract
   ```

4. **Clean up ADMESH**:
   ```bash
   # Revert pyproject.toml changes
   git checkout main -- pyproject.toml
   
   # Delete files
   rm -rf mesh_registry/ registry_data/ tests/fixtures/registry/ .importlinter
   rm .github/workflows/validate-pr.yml .github/workflows/publish-hf.yml
   
   # Revert CLAUDE.md
   git checkout main -- CLAUDE.md
   
   # Update README.md link if needed
   # Update specs/005-adcirc-mesh-registry/ → archive or remove
   ```

5. **Create final cleanup commit**:
   ```bash
   git commit -m "Extract mesh_registry to separate repo; clean up interim implementation"
   ```

6. **Set up CI/CD in new repo**:
   - Copy validated `.github/workflows/validate-pr.yml` from ADMESH
   - Copy validated `.github/workflows/publish-hf.yml` from ADMESH
   - Create `pyproject.toml` with registry deps as main dependencies
   - Set up HuggingFace Datasets publishing (HF_TOKEN secret)

7. **Update cross-references**:
   - ADMESH `README.md`: Link to new repo
   - ADMESH `CLAUDE.md`: Note that mesh_registry has moved
   - This spec: Update to mark as MIGRATED

## Why This Approach

- **Minimal ADMESH changes**: Only the `[registry]` extra and package discovery; no core ADMESH code affected
- **Clean extraction**: `git subtree split` preserves history and makes the subtree move auditable
- **Import-linter boundary**: Prevents entanglement; if violated, extraction becomes painful (and the linter will catch it in CI)
- **Deferral target**: ~20 meshes or 3 dependents is ~3–6 months of community adoption; enough runway to validate the design

## Checklist for Extraction Day

- [ ] ≥20 contributed meshes in registry OR ≥3 external dependents confirmed
- [ ] All ADMESH tests pass after subtree split
- [ ] New repo created and initialized with basic CI
- [ ] pyproject.toml reverted in ADMESH
- [ ] `.importlinter` file deleted
- [ ] Workflows (validate-pr.yml, publish-hf.yml) deleted from ADMESH (only in new repo)
- [ ] CLAUDE.md updated or reverted
- [ ] README.md links updated
- [ ] specs/005-adcirc-mesh-registry marked as MIGRATED
- [ ] Final cleanup commit pushed to ADMESH main
- [ ] New repo first release tagged (v0.1.0 or v1.0.0)
- [ ] Cross-project tests confirm old ADMESH still works without mesh_registry

## References

- Original spec: `specs/005-adcirc-mesh-registry/spec.md`
- Implementation plan: `specs/005-adcirc-mesh-registry/plan.md`
- Constitution Principle I deviation: `specs/005-adcirc-mesh-registry/plan.md` (Complexity Tracking section)
