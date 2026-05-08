#!/bin/bash
# instructions_on_start.sh — ADMESH session startup hook.
#
# Runs at the start of every Claude Code session in this repo. Validates
# repo health and enforces the DomI sync contract before any write work.
#
# USAGE: bash "$(git rev-parse --show-toplevel)"/scripts/instructions_on_start.sh

set -euo pipefail

# --- locate sync-from-domi ---
# Search order:
#   1. Plugin cache (after `claude plugin install sync-from-domi@DomI`)
#      Path pattern: ~/.claude/plugins/cache/DomI/sync-from-domi/<version>/skills/sync-from-domi
#   2. Plugin marketplace clone
#   3. Vendored copy in this repo
#   4. Global ~/.claude/skills
DOMI_SKILL_PATH="${DOMI_SKILL_PATH:-}"
if [ -z "$DOMI_SKILL_PATH" ]; then
  # Glob-match the versioned cache path first (preferred)
  for cached in "${HOME}"/.claude/plugins/cache/DomI/sync-from-domi/*/skills/sync-from-domi; do
    if [ -f "${cached}/scripts/check_pin.sh" ]; then
      DOMI_SKILL_PATH="$cached"
      break
    fi
  done
fi
if [ -z "$DOMI_SKILL_PATH" ]; then
  for candidate in \
    "${HOME}/.claude/plugins/marketplaces/domattioli/DomI/plugins/sync-from-domi/skills/sync-from-domi" \
    "./plugins/sync-from-domi/skills/sync-from-domi" \
    "./skills/sync-from-domi" \
    "${HOME}/.claude/skills/sync-from-domi"; do
    if [ -f "${candidate}/scripts/check_pin.sh" ]; then
      DOMI_SKILL_PATH="$candidate"
      break
    fi
  done
fi

if [ -z "$DOMI_SKILL_PATH" ] || [ ! -f "${DOMI_SKILL_PATH}/scripts/check_pin.sh" ]; then
  echo "⚠ sync-from-domi skill not found locally; skipping DomI drift check"
  echo "  → install via: claude plugin marketplace add domattioli/DomI && claude plugin install sync-from-domi@DomI"
else
  set +e
  bash "${DOMI_SKILL_PATH}/scripts/check_pin.sh"
  DOMI_DRIFT_RC=$?
  set -e

  case $DOMI_DRIFT_RC in
    0)
      : # synced; continue
      ;;
    1)
      echo ""
      echo "============================================================"
      echo "🛑 HARD STOP: downstream is BEHIND DomI"
      echo "============================================================"
      echo "Invoke the sync-from-domi skill before any write work:"
      echo "  > sync from DomI"
      echo "Or run manually:"
      echo "  bash ${DOMI_SKILL_PATH}/scripts/update_pin.sh"
      echo "  (then commit .domi-pin and any updated skills)"
      echo "============================================================"
      if [ "${DOMI_BLOCK_ON_DRIFT:-1}" = "1" ]; then
        exit 1
      fi
      ;;
    2)
      echo "ⓘ First-time DomI pin needed; will create on next sync"
      ;;
    3)
      echo ""
      echo "============================================================"
      echo "🛑 HARD STOP: DomI pin FORKED (manifest hash mismatch)"
      echo "============================================================"
      echo "Local edits to vendored DomI artifacts suspected."
      echo "Operator must resolve manually before continuing."
      echo "============================================================"
      exit 1
      ;;
    4)
      echo "⚠ DomI drift check skipped (gh unavailable); continuing"
      ;;
  esac
fi
# --- end DomI drift check ---

# --- repo health checks ---
echo "✓ ADMESH startup checks complete"
