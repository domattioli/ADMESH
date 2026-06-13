#!/bin/bash
# Smoke test for the offline sibling-clone DomI-drift fallback (#147 pattern)
# in scripts/instructions_on_start.sh. Exercises synced / behind / no-sibling.
set -euo pipefail

# Embedded helper functions (extracted from scripts/instructions_on_start.sh)
_find_sibling_domi() {
  local d
  for d in "${DOMI_SIBLING:-}" "$HOME/DomI" "$REPO_ROOT/../DomI" "/home/user/DomI"; do
    [ -n "$d" ] && [ -f "$d/MANIFEST.md" ] \
      && git -C "$d" rev-parse --git-dir >/dev/null 2>&1 \
      && echo "$d" && return 0
  done
  return 1
}

_sibling_clone_drift() {
  local sib pin ref head
  sib=$(_find_sibling_domi) || return 2
  [ -f "$REPO_ROOT/.domi-pin" ] || return 2
  pin=$(awk '/^sha:/{print $2}' "$REPO_ROOT/.domi-pin")
  [ -n "$pin" ] || return 2
  # Prefer origin/main, then main, then HEAD as the upstream reference.
  for ref in origin/main main HEAD; do
    head=$(git -C "$sib" rev-parse --verify "$ref" 2>/dev/null) && break
  done
  [ -n "$head" ] || return 2
  if [ "$pin" = "$head" ]; then
    echo "✓ DomI pin current (offline sibling clone $sib @ $ref)"
    return 0
  fi
  # Pinned sha must exist in the sibling history to draw a conclusion.
  git -C "$sib" cat-file -e "${pin}^{commit}" 2>/dev/null || return 2
  if git -C "$sib" merge-base --is-ancestor "$pin" "$head" 2>/dev/null; then
    echo "HARD STOP: DomI drift (offline: pin $pin behind sibling $ref $head). Run '/sync-from-domi' before write work." >&2
  else
    echo "HARD STOP: DomI drift (offline: pin $pin diverged from sibling $ref — forked). Resolve manually." >&2
  fi
  return 1
}

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
SIB="$TMP/DomI"; PINREPO="$TMP/consumer"
mkdir -p "$SIB" "$PINREPO"

git -C "$SIB" init -q
echo "# manifest" > "$SIB/MANIFEST.md"
git -C "$SIB" add -A && git -C "$SIB" -c user.email=t@t -c user.name=t -c commit.gpgsign=false commit -qm c1
OLD=$(git -C "$SIB" rev-parse HEAD)
echo "change" >> "$SIB/MANIFEST.md"
git -C "$SIB" add -A && git -C "$SIB" -c user.email=t@t -c user.name=t -c commit.gpgsign=false commit -qm c2
HEAD=$(git -C "$SIB" rev-parse HEAD)

export REPO_ROOT="$PINREPO" DOMI_SIBLING="$SIB"

# Scenario 1: synced (pin == HEAD) -> 0
printf 'sha: %s\n' "$HEAD" > "$PINREPO/.domi-pin"
set +e; _sibling_clone_drift >/dev/null 2>&1; rc=$?; set -e
[ "$rc" -eq 0 ] || { echo "FAIL synced expected 0 got $rc"; exit 1; }

# Scenario 2: behind (pin == ancestor) -> 1
printf 'sha: %s\n' "$OLD" > "$PINREPO/.domi-pin"
set +e; _sibling_clone_drift >/dev/null 2>&1; rc=$?; set -e
[ "$rc" -eq 1 ] || { echo "FAIL behind expected 1 got $rc"; exit 1; }

# Scenario 3: no pin file -> 2 (inconclusive)
EMPTY="$TMP/empty"; mkdir -p "$EMPTY"; export REPO_ROOT="$EMPTY"
set +e; _sibling_clone_drift >/dev/null 2>&1; rc=$?; set -e
[ "$rc" -eq 2 ] || { echo "FAIL nopin expected 2 got $rc"; exit 1; }

echo "SMOKE PASS"
