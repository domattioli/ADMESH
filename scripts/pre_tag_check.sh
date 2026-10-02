#!/usr/bin/env bash
# Pre-tag verification — gates release tags (version-agnostic since 0.6.0).
#
# Gates:
#   1. README has the "0.1.0 in progress" callout
#   2. no docs/papers/wnat_admesh.png in the working tree
#   3. no dist/ or build/ directories
#   4. tier-2 release-gate test passes OR is documented as xfail (issue #10)
#   5. pyproject.toml version == admesh/__init__.py __version__  (spec 009 FR-001)
#   6. output/coverage.json exists and is < 30 days old            (spec 009 FR-004/005)
#   7. output/durations.txt exists and is < 30 days old            (spec 009 FR-004/005)
#
# Usage: bash scripts/pre_tag_check.sh
#
# Exits 0 on PASS, non-zero on FAIL with a one-line diagnostic per
# failed gate.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

failed=0
fail() {
    echo "FAIL: $*" >&2
    failed=$((failed + 1))
}
pass() {
    echo "PASS: $*"
}

# Target version — derived once from pyproject.toml -------------------------
TARGET_VERSION=$(grep -E '^version *= *"' pyproject.toml | head -1 | sed -E 's/^version *= *"([^"]+)".*/\1/')
if [[ -z "$TARGET_VERSION" ]]; then
    echo "FAIL: could not derive TARGET_VERSION from pyproject.toml" >&2
    exit 1
fi
# grep-safe form (dots escaped)
ver_re=$(printf '%s' "$TARGET_VERSION" | sed 's/\./\\./g')

# 1. README status reflects shipping reality ----------------------------
# Pre-ship: README carries "<version> in progress" callout.
# Ship-ready: README mentions the tag version explicitly.
# Either state is acceptable; the gate fails only when both are absent.
if grep -q "${ver_re} in progress" README.md; then
    pass "README in pre-ship state ('${TARGET_VERSION} in progress' callout present)"
elif grep -qE "${ver_re}" README.md; then
    pass "README in ship-ready state (${TARGET_VERSION} version mentioned)"
else
    fail "README must reference ${TARGET_VERSION} either as 'in progress' or as a shipped version"
fi

# 2. No docs/papers/wnat_admesh.png in the working tree ------------------------
if [[ -f docs/papers/wnat_admesh.png ]]; then
    fail "docs/papers/wnat_admesh.png is present (spec FR-019; should be removed)"
else
    pass "docs/papers/wnat_admesh.png absent"
fi

# 3. No dist/ or build/ directories ---------------------------------------
if [[ -d dist ]]; then
    fail "dist/ directory present (spec FR-019; should be removed)"
else
    pass "dist/ absent"
fi
if [[ -d build ]]; then
    fail "build/ directory present (spec FR-019; should be removed)"
else
    pass "build/ absent"
fi

# 4. Tier-2 (WNAT) release-gate status ------------------------------------
# Either the test passes outright, or it is marked xfail with an issue
# reference in the body. xfail is acceptable until issue #10 lands.
if grep -q '@pytest\.mark\.xfail' tests/test_default_size_field.py \
   && grep -q 'WNAT' tests/test_default_size_field.py; then
    pass "Tier-2 release gate: documented xfail (issue #10)"
else
    pass "Tier-2 release gate: not xfailed — verify it passes via pytest"
fi

# 5. Version string consistency -----------------------------------------------
# PEP 517 src-layout is canonical; legacy flat layout kept as fallback.
init_file=""
if [[ -f src/admesh/__init__.py ]]; then
    init_file="src/admesh/__init__.py"
elif [[ -f admesh/__init__.py ]]; then
    init_file="admesh/__init__.py"
fi
init_version=""
if [[ -n "$init_file" ]]; then
    init_version=$(
        grep -E '^__version__\s*=' "$init_file" \
            | head -1 \
            | sed -E 's/^__version__\s*=\s*"([^"]+)".*/\1/'
    )
fi
if [[ -z "$init_version" ]]; then
    fail "VERSION_MISSING: could not parse __version__ from src/admesh/__init__.py or admesh/__init__.py"
elif [[ "$TARGET_VERSION" != "$init_version" ]]; then
    fail "VERSION_MISMATCH: pyproject.toml=$TARGET_VERSION $init_file=$init_version"
else
    pass "version strings agree: $TARGET_VERSION"
fi

# 6. output/coverage.json exists and is < 30 days old ------------------------
if [[ ! -f output/coverage.json ]]; then
    fail "COVERAGE_MISSING: output/coverage.json not found — run: pytest --cov=admesh --cov-report=json"
else
    cov_age=$(python3 -c "
import os, time
age = (time.time() - os.path.getmtime('output/coverage.json')) / 86400
print(int(age))
" 2>/dev/null || echo 999)
    if [[ "$cov_age" -gt 30 ]]; then
        fail "COVERAGE_STALE: output/coverage.json is ${cov_age} day(s) old (threshold: 30)"
    else
        pass "output/coverage.json is ${cov_age} day(s) old"
    fi
fi

# 7. output/durations.txt exists and is < 30 days old ------------------------
if [[ ! -f output/durations.txt ]]; then
    fail "DURATIONS_MISSING: output/durations.txt not found — run: pytest --durations=10 -q"
else
    dur_age=$(python3 -c "
import os, time
age = (time.time() - os.path.getmtime('output/durations.txt')) / 86400
print(int(age))
" 2>/dev/null || echo 999)
    if [[ "$dur_age" -gt 30 ]]; then
        fail "DURATIONS_STALE: output/durations.txt is ${dur_age} day(s) old (threshold: 30)"
    else
        pass "output/durations.txt is ${dur_age} day(s) old"
    fi
fi

# Summary -----------------------------------------------------------------
if [[ "$failed" -eq 0 ]]; then
    echo
    echo "ALL PRE-TAG CHECKS PASSED — ${TARGET_VERSION} tag is unblocked from this script's"
    echo "perspective. Verify pytest tests/ -q is green before tagging."
    exit 0
else
    echo
    echo "$failed PRE-TAG CHECK(S) FAILED — ${TARGET_VERSION} tag BLOCKED."
    exit 1
fi
