#!/bin/bash
# scripts/instructions_on_start.sh — session startup health check
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")" 
cd "$REPO_ROOT" || exit 1

echo "=== Session Start: ADMESH ==="
echo "Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null) | Dirty: $(git status --porcelain 2>/dev/null | wc -l | tr -d ' ') files"
echo ""

# Bootstrap DomI contract plugins (idempotent; fast no-op on warm containers)
if command -v claude &>/dev/null; then
  set +e
  if [ ! -d "$HOME/.claude/plugins/marketplaces/DomI" ]; then
    echo "Adding DomI marketplace..."
    claude plugin marketplace add domattioli/DomI >/dev/null 2>&1 \
      && echo "  ✓ DomI marketplace added" \
      || echo "  ✗ DomI marketplace add failed (network?)"
  fi
  for plugin in sync-from-domi introspect request-from-domi; do
    if [ ! -d "$HOME/.claude/plugins/cache/DomI/$plugin" ]; then
      echo "Installing $plugin@DomI..."
      claude plugin install "$plugin@DomI" >/dev/null 2>&1 \
        && echo "  ✓ $plugin@DomI installed" \
        || echo "  ✗ $plugin@DomI install failed"
    fi
  done
  set -e
fi
echo ""

# DomI drift check (plugin cache → skills marketplace → vendored)
_find_check_pin() {
  for d in "$HOME/.claude/plugins/cache/DomI/sync-from-domi" \
            "$HOME/.claude/skills/sync-from-domi" \
            "$REPO_ROOT/plugins/sync-from-domi"; do
    local f; f=$(find "$d" -name "check_pin.sh" -maxdepth 5 2>/dev/null | head -1)
    [ -n "$f" ] && echo "$f" && return 0
  done; return 1
}

# Offline sibling-clone drift fallback (#147 pattern). Used when the network
# check_pin path is absent (plugin not installed in cloud containers) or
# returns exit 4 (api.github.com 403). Compares the pinned DomI sha against a
# local DomI checkout (#230/#223; mirrors update_pin.sh). Echoes status.
# Returns: 0 = current, 1 = behind/forked (hard stop), 2 = inconclusive.
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

CHECK_PIN=$(_find_check_pin 2>/dev/null || true)
if [ -n "$CHECK_PIN" ]; then
  set +e; bash "$CHECK_PIN"; rc=$?; set -e
  case $rc in
    0) echo "✓ DomI pin current" ;;
    1|3) echo "HARD STOP: DomI drift (exit $rc). Run '/sync-from-domi' before write work." >&2; exit 1 ;;
    2) echo "⚠ .domi-pin absent — run update_pin.sh to initialize" ;;
    4) # network path skipped (gh/api unavailable) — try offline sibling clone
       set +e; _sibling_clone_drift; src=$?; set -e
       case $src in
         0) : ;;
         1) exit 1 ;;
         *) echo "⚠ gh unavailable + no sibling DomI clone — DomI drift check skipped" ;;
       esac ;;
  esac
else
  # plugin absent (typical in cloud containers) — try offline sibling clone
  set +e; _sibling_clone_drift; src=$?; set -e
  case $src in
    0) : ;;
    1) exit 1 ;;
    *) echo "⚠ sync-from-domi not installed + no sibling DomI clone. Run: claude plugin install sync-from-domi@DomI" ;;
  esac
fi
echo ""

echo "=== ✓ Health check passed ==="
