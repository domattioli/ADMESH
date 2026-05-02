# Publish Release Guide

Automated GitHub release and PyPI publication for ADMESH.

## Quick Start

```bash
# Publish a new release (auto-detect version from pyproject.toml)
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
- **Graceful error handling** with clear, actionable error messages
- **Report final URLs** for release and PyPI package

## Prerequisites

Before publishing a release, ensure:

1. **gh CLI installed**
   ```bash
   # macOS
   brew install gh

   # Ubuntu/Debian
   sudo apt-get install gh

   # Or from GitHub: https://github.com/cli/cli
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
   ```bash
   git status
   ```

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
   - Other changes
   ```

## Usage Examples

### Publish a new release

```bash
# Automatic version detection
python scripts/publish_release.py

# With explicit version
python scripts/publish_release.py --version 0.2.0
```

### Test release (draft mode)

```bash
python scripts/publish_release.py --draft
```

Allows testing the GitHub release creation without publishing to PyPI. The draft release can be reviewed and published manually on GitHub.

### Release without PyPI

```bash
python scripts/publish_release.py --no-pypi
```

Useful if you want to create the GitHub release but handle PyPI publication separately.

### Custom repository

```bash
python scripts/publish_release.py --repo myorg/admesh
```

For releases to fork or alternate repositories.

## How It Works

### 1. Prerequisites Validation

Checks for:
- `gh` CLI availability
- `twine` availability
- `dist/` directory with build artifacts
- Clean git state (no uncommitted changes)

Exits with error if any prerequisite fails.

### 2. Version Detection

1. Use `--version` flag if provided
2. Auto-detect from `pyproject.toml`:
   - Looks for `version = "X.Y.Z"` in `[project]` section
   - Supports quoted values

### 3. Release Notes Extraction

Reads `CHANGELOG.md` and extracts section matching version:
- Patterns supported: `## v1.0.0`, `## [1.0.0]`, `## 1.0.0`
- Extracts everything until next section header or EOF
- Uses extracted notes in GitHub release

### 4. GitHub Release Creation

Uses `gh release create` to:
- Create release tag (automatically prefixed with `v`)
- Attach release notes
- Support draft mode (`--draft`)
- Support custom repository (`--repo`)

### 5. PyPI Upload

Uses `twine upload` to:
- Upload distributions from `dist/`
- Support non-interactive mode
- Skip if `--no-pypi` flag used

### 6. Report Results

Displays:
- GitHub release URL: `https://github.com/{owner}/{repo}/releases/tag/v{version}`
- PyPI package URL: `https://pypi.org/project/admesh/{version}/`

## Exit Codes

- `0`: Success (release published)
- `1`: Validation or execution failure (see error messages for details)

## Troubleshooting

### "gh CLI not found"

Install GitHub CLI:
```bash
# macOS
brew install gh

# Ubuntu/Debian
sudo apt-get install gh

# Or see https://github.com/cli/cli#installation
```

### "twine not found"

Install twine:
```bash
pip install twine
```

### "dist/ directory not found"

Build distribution artifacts:
```bash
python -m build
```

### "Git working directory has uncommitted changes"

Commit all changes before publishing:
```bash
git add -A
git commit -m "Release preparation"
```

### "Could not determine version"

Add version to `pyproject.toml`:
```toml
[project]
version = "0.2.0"
```

Or use explicit `--version` flag:
```bash
python scripts/publish_release.py --version 0.2.0
```

### "No release notes found in CHANGELOG.md"

Add section for your version in `CHANGELOG.md`:
```markdown
## 0.2.0 (2026-04-27)

- Feature 1
- Feature 2
- Bug fixes
```

Pattern must match: `## [v]VERSION [...]`

## Integration with Claude Code

### Using as a Skill

This utility can be integrated as a `/publish-release` skill in Claude Code:

```bash
/publish-release                    # Auto-detect version
/publish-release --version 0.2.0   # Explicit version
/publish-release --draft           # Draft mode
/publish-release --no-pypi         # Skip PyPI
```

### Using from Terminal

```bash
cd /workspace/ADMESH
python scripts/publish_release.py [options]
```

## Release Workflow

Standard release process:

1. **Prepare**
   ```bash
   # Update version in pyproject.toml
   # Update CHANGELOG.md with release notes
   # Run tests
   python -m pytest
   ```

2. **Build**
   ```bash
   python -m build
   ```

3. **Publish**
   ```bash
   python scripts/publish_release.py
   ```

4. **Verify**
   - Check GitHub: https://github.com/domattioli/ADMESH/releases
   - Check PyPI: https://pypi.org/project/admesh/

## See Also

- [CHANGELOG.md](../CHANGELOG.md) - Release notes format
- [pyproject.toml](../pyproject.toml) - Version configuration
- [gh CLI documentation](https://cli.github.com/manual/)
- [twine documentation](https://twine.readthedocs.io/)
