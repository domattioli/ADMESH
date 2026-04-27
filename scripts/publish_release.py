#!/usr/bin/env python3
"""Automated GitHub release and PyPI publication.

Usage:
  python scripts/publish_release.py [--version VERSION] [--no-pypi] [--draft] [--repo REPO]

Features:
  - Auto-detect version from pyproject.toml if not specified
  - Extract release notes from CHANGELOG.md
  - Create GitHub release via gh CLI
  - Upload to PyPI via twine
  - Validate prerequisites (gh, twine, dist/, clean git)
  - Support flags for testing and customization
  - Graceful error handling with clear messages
  - Report final release URLs

Exit codes:
  0 = success
  1 = validation or execution failure
"""

import argparse
import subprocess
import sys
import re
from pathlib import Path
from typing import Optional, Tuple


def run_command(cmd: list[str], check: bool = True) -> Tuple[int, str, str]:
    """Execute a command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def validate_prerequisites() -> Tuple[bool, list[str]]:
    """Check that gh CLI, twine, and git are available."""
    errors = []

    # Check gh CLI
    rc, _, _ = run_command(["gh", "--version"], check=False)
    if rc != 0:
        errors.append("❌ gh CLI not found (install: brew install gh or apt-get install gh)")

    # Check twine
    rc, _, _ = run_command(["twine", "--version"], check=False)
    if rc != 0:
        errors.append("❌ twine not found (install: pip install twine)")

    # Check git
    rc, _, _ = run_command(["git", "--version"], check=False)
    if rc != 0:
        errors.append("❌ git not found (required for release validation)")

    # Check dist/ directory
    if not Path("dist").exists():
        errors.append("❌ dist/ directory not found (run: python -m build)")

    # Check for uncommitted changes
    rc, stdout, _ = run_command(["git", "status", "--porcelain"], check=False)
    if rc == 0 and stdout.strip():
        errors.append("❌ Git working directory has uncommitted changes (commit or stash them)")

    return len(errors) == 0, errors


def extract_version_from_pyproject() -> Optional[str]:
    """Extract version from pyproject.toml."""
    try:
        with open("pyproject.toml") as f:
            content = f.read()
        match = re.search(r'version\s*=\s*["\']([^"\']+ )["\']', content)
        return match.group(1) if match else None
    except Exception as e:
        print(f"⚠️  Could not read pyproject.toml: {e}")
        return None


def extract_release_notes(version: str) -> Optional[str]:
    """Extract release notes for a specific version from CHANGELOG.md."""
    try:
        with open("CHANGELOG.md") as f:
            content = f.read()

        # Look for section matching the version
        # Patterns: ## v1.0.0, ## [1.0.0], ## Version 1.0.0
        pattern = rf"^##\s+(?:\[?v?)?{re.escape(version)}(?:\])?.*?(?=^##\s|$)"
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

        if match:
            notes = match.group(0).strip()
            # Remove the header line, keep the content
            lines = notes.split('\n', 1)
            return lines[1].strip() if len(lines) > 1 else ""
        return None
    except Exception as e:
        print(f"⚠️  Could not read CHANGELOG.md: {e}")
        return None


def create_github_release(
    version: str,
    release_notes: str,
    draft: bool = False,
    repo: Optional[str] = None,
) -> Tuple[bool, str]:
    """Create a GitHub release using gh CLI."""
    cmd = ["gh", "release", "create", f"v{version}"]

    if draft:
        cmd.append("--draft")

    if repo:
        cmd.extend(["--repo", repo])

    # Add release notes
    if release_notes:
        cmd.extend(["--notes", release_notes])
    else:
        cmd.extend(["--notes", f"Release {version}"])

    print(f"📝 Creating GitHub release v{version}...")
    rc, stdout, stderr = run_command(cmd, check=False)

    if rc == 0:
        # Extract release URL from output
        url = None
        for line in stdout.split('\n'):
            if 'github.com' in line and 'releases' in line:
                url = line.strip()
                break
        return True, url or stdout.strip()
    else:
        return False, f"Failed to create release: {stderr}"


def upload_to_pypi(no_pypi: bool = False) -> Tuple[bool, str]:
    """Upload distribution to PyPI using twine."""
    if no_pypi:
        print("⏭️  Skipping PyPI upload (--no-pypi flag set)")
        return True, "PyPI upload skipped"

    print("📦 Uploading to PyPI...")
    cmd = ["twine", "upload", "dist/*", "--non-interactive"]

    rc, stdout, stderr = run_command(cmd, check=False)

    if rc == 0:
        return True, stdout.strip()
    else:
        return False, f"Failed to upload to PyPI: {stderr}"


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Publish a release to GitHub and PyPI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--version",
        help="Release version (auto-detect from pyproject.toml if omitted)",
    )
    parser.add_argument(
        "--no-pypi",
        action="store_true",
        help="Skip PyPI upload",
    )
    parser.add_argument(
        "--draft",
        action="store_true",
        help="Create as draft release on GitHub",
    )
    parser.add_argument(
        "--repo",
        help="GitHub repository (owner/repo format)",
    )

    args = parser.parse_args()

    # Step 1: Validate prerequisites
    print("🔍 Validating prerequisites...")
    valid, errors = validate_prerequisites()
    for error in errors:
        print(f"  {error}")

    if not valid:
        return 1

    print("✅ Prerequisites validated\n")

    # Step 2: Determine version
    version = args.version or extract_version_from_pyproject()
    if not version:
        print("❌ Could not determine version. Use --version or add version to pyproject.toml")
        return 1

    print(f"📌 Release version: {version}\n")

    # Step 3: Extract release notes
    release_notes = extract_release_notes(version)
    if release_notes:
        print(f"📄 Found release notes in CHANGELOG.md")
    else:
        print(f"⚠️  No release notes found in CHANGELOG.md")
        release_notes = ""

    # Step 4: Create GitHub release
    print()
    success, message = create_github_release(
        version,
        release_notes,
        draft=args.draft,
        repo=args.repo,
    )
    if not success:
        print(f"  ❌ {message}")
        return 1
    print(f"  ✅ Release created: {message}\n")

    # Step 5: Upload to PyPI
    success, message = upload_to_pypi(no_pypi=args.no_pypi)
    if not success:
        print(f"  ❌ {message}")
        return 1
    print(f"  ✅ {message}\n")

    # Step 6: Report success
    release_url = f"https://github.com/{args.repo or 'domattioli/ADMESH'}/releases/tag/v{version}"
    pypi_url = f"https://pypi.org/project/admesh/{version}/"

    print("=" * 70)
    print("🎉 Release published successfully!")
    print("=" * 70)
    print(f"GitHub Release: {release_url}")
    if not args.no_pypi:
        print(f"PyPI Package:   {pypi_url}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())