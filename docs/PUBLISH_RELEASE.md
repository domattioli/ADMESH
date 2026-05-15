# Publish Release Guide

Automated GitHub release and PyPI publication for ADMESH.

## Quick Start

```bash
# Publish new release (auto-detect version from pyproject.toml)
python scripts/publish_release.py

# Publish with explicit version
python scripts/publish_release.py --version 0.2.0

# Create draft release (for testing)
python scripts/publish_release.py --draft

# Skip PyPI upload
python scripts/publish_release.py --no-pypi
```

## Features

- **Auto-detect version** from `pyproject.toml` if not specified
- **Extract release notes** from `CHANGELOG.md` automatically
- **Create GitHub release** via `gh` CLI with release notes
- **Upload to PyPI** via `twine`
- **Validate prerequisites**: checks for `gh`, `twine`, `dist/`, clean git state
- **Support flags** for testing and customization:
  - `--version`: explicit version number
  - `--draft`: create draft release on GitHub
  - `--no-pypi`: skip PyPI upload
  - `--repo`: custom GitHub repository (format: `owner/repo`)
- **Report final URLs** for release and PyPI package

## Prerequisites

1. **gh CLI installed**
   ```bash
   brew install gh        # macOS
   sudo apt-get install gh  # Ubuntu/Debian
   ```

2. **twine installed**
   ```bash
   pip install twine
   ```

3. **Build artifacts in dist/**
   ```bash
   python -m build
   ```

4. **Clean git state** (all changes committed)

5. **Version in pyproject.toml**
   ```toml
   [project]
   version = "0.2.0"
   ```

6. **Release notes in CHANGELOG.md**
   ```markdown
   ## 0.2.0 (2026-04-27)

   - Feature 1 description
   - Bug fix description
   ```

## How It Works

### 1. Prerequisites Validation

Checks for: `gh` CLI, `twine`, `dist/` directory, clean git state. Exits with error if any prerequisite fails.

### 2. Version Detection

1. Use `--version` flag if provided
2. Auto-detect from `pyproject.toml`: looks for `version = "X.Y.Z"` in `[project]` section

### 3. Release Notes Extraction

Reads `CHANGELOG.md` and extracts section matching version:
- Patterns supported: `## v1.0.0`, `## [1.0.0]`, `## 1.0.0`
- Extracts everything until next section header or EOF

### 4. GitHub Release Creation

Uses `gh release create` to create release tag (auto-prefixed with `v`), attach release notes, support draft mode + custom repository.

### 5. PyPI Upload

Uses `twine upload dist/`, skip if `--no-pypi` flag used.

### 6. Report Results

Displays GitHub release URL and PyPI package URL.

## Exit Codes

- `0`: Success
- `1`: Validation or execution failure

## Troubleshooting

### "gh CLI not found"
```bash
brew install gh    # macOS
# or see https://github.com/cli/cli#installation
```

### "twine not found"
```bash
pip install twine
```

### "dist/ directory not found"
```bash
python -m build
```

### "Git working directory has uncommitted changes"
```bash
git add -A && git commit -m "Release preparation"
```

### "Could not determine version"
Add version to `pyproject.toml` or use `--version` flag.

### "No release notes found in CHANGELOG.md"
Add section matching `## [v]VERSION [...]` pattern.

## Integration with Claude Code

```bash
/publish-release                    # Auto-detect version
/publish-release --version 0.2.0   # Explicit version
/publish-release --draft           # Draft mode
/publish-release --no-pypi         # Skip PyPI
```

## Release Workflow

```bash
# 1. Prepare
# Update version in pyproject.toml
# Update CHANGELOG.md
pytest

# 2. Build
python -m build

# 3. Publish
python scripts/publish_release.py

# 4. Verify
# GitHub: https://github.com/domattioli/ADMESH/releases
# PyPI: https://pypi.org/project/admesh/
```

## See Also

- [CHANGELOG.md](../CHANGELOG.md)
- [pyproject.toml](../pyproject.toml)
- [gh CLI documentation](https://cli.github.com/manual/)
- [twine documentation](https://twine.readthedocs.io/)
