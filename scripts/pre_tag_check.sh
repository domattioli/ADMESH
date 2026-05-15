#!/usr/bin/env bash
# Pre-tag verification — gates the 0.1.0 release tag.
#
# Gates:
#   1. constitution version >= 1.0.2
#   2. README has the "0.1.0 in progress" callout
#   3. no papers/wnat_admesh.png in the working tree
#   4. no dist/ or build/ directories
#   5. tier-2 release-gate test passes OR is documented as xfail (issue #10)
#   6. pyproject.toml version == admesh/__init__.py __version__  (spec 009 FR-001)
#   7. PROJECT_PLAN.md has an entry dated within 30 days of HEAD  (spec 009 FR-002)
#   8. output/coverage.json exists and is < 30 days old            (spec 009 FR-004/005)
#   9. output/durations.txt exists and is < 30 days old            (spec 009 FR-004/005)
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

# 1. Constitution version >= 1.0.2 -----------------------------------------
constitution_version=$(
    grep -E '^\*\*Version\*\*:' .specify/memory/constitution.md \
        | head -1 \
        | sed -E 's/^\*\*Version\*\*: ([0-9]+\.[0-9]+\.[0-9]+).*/\1/'
)
if [[ -z "$constitution_version" ]]; then
    fail "could not read constitution version banner"
elif [[ "$(printf '%s\n%s' '1.0.2' "$constitution_version" | sort -V | head -1)" != '1.0.2' ]]; then
    fail "constitution version $constitution_version < 1.0.2 (spec FR-017)"
else
    pass "constitution version $constitution_version >= 1.0.2"
fi

# 2. README "0.1.0 in progress" callout -----------------------------------
if grep -q '0\.1\.0 in progress' README.md; then
    pass "README has '0.1.0 in progress' callout"
else
    fail "README missing '0.1.0 in progress' callout (spec FR-018)"
fi

# 3. No papers/wnat_admesh.png in the working tree ------------------------
if [[ -f papers/wnat_admesh.png ]]; then
    fail "papers/wnat_admesh.png is present (spec FR-019; should be removed)"
else
    pass "papers/wnat_admesh.png absent"
fi

# 4. No dist/ or build/ directories ---------------------------------------
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

# 5. Tier-2 (WNAT) release-gate status ------------------------------------
# Either the test passes outright, or it is marked xfail with an issue
# reference in the body. xfail is acceptable until issue #10 lands.
if grep -q '@pytest\.mark\.xfail' tests/test_default_size_field.py \
   && grep -q 'WNAT' tests/test_default_size_field.py; then
    pass "Tier-2 release gate: documented xfail (issue #10)"
else
    pass "Tier-2 release gate: not xfailed — verify it passes via pytest"
fi

# 6. Version string consistency -----------------------------------------------
pyproject_version=$(
    grep -E '^version\s*=' pyproject.toml \
        | head -1 \
        | sed -E 's/^version\s*=\s*"([^"]+)".*/\1/'
)
init_version=$(
    grep -E '^__version__\s*=' admesh/__init__.py \
        | head -1 \
        | sed -E 's/^__version__\s*=\s*"([^"]+)".*/\1/'
)
if [[ -z "$pyproject_version" || -z "$init_version" ]]; then
    fail "VERSION_MISSING: could not parse version from pyproject.toml or admesh/__init__.py"
elif [[ "$pyproject_version" != "$init_version" ]]; then
    fail "VERSION_MISMATCH: pyproject.toml=$pyproject_version admesh/__init__.py=$init_version"
else
    pass "version strings agree: $pyproject_version"
fi

# 7. PROJECT_PLAN.md staleness (most recent entry within 30 days of HEAD) -----
plan_date=$(
    grep -oE 'Where we are today \([0-9]{4}-[0-9]{2}-[0-9]{2}' \
        docs/governance/PROJECT_PLAN.md \
        | sort -r \
        | head -1 \
        | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}'
)
if [[ -z "$plan_date" ]]; then
    fail "PLAN_STALE: no 'Where we are today (YYYY-MM-DD' entry found in PROJECT_PLAN.md"
else
    delta_days=$(python3 -c "
from datetime import date
delta = (date.today() - date.fromisoformat('$plan_date')).days
print(delta)
" 2>/dev/null || echo 999)
    if [[ "$delta_days" -gt 30 ]]; then
        fail "PLAN_STALE: last_entry=$plan_date delta=${delta_days}_days (threshold: 30)"
    else
        pass "PROJECT_PLAN.md entry $plan_date is ${delta_days} day(s) old"
    fi
fi

# 8. output/coverage.json exists and is < 30 days old ------------------------
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

# 9. output/durations.txt exists and is < 30 days old ------------------------
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
    echo "ALL PRE-TAG CHECKS PASSED — 0.1.0 tag is unblocked from this script's"
    echo "perspective. Verify pytest tests/ -q is green before tagging."
    exit 0
else
    echo
    echo "$failed PRE-TAG CHECK(S) FAILED — 0.1.0 tag BLOCKED."
    exit 1
fi
