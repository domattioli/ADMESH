# DomI Issue Draft — `sync-from-domi` hard-depends on authenticated `gh` CLI

**Intended destination**: new issue on `domattioli/DomI`
**Authored from**: ADMESH session `claude/resolve-merge-conflicts-78X82`, 2026-05-15
**Status**: draft for human review before posting

---

## Title

`sync-from-domi: update_pin.sh / check_pin.sh hardcoded to gh CLI; breaks in environments without authenticated gh`

## Body

### From: ADMESH (downstream consumer)

### Problem

`sync-from-domi`'s `update_pin.sh` (and `check_pin.sh`) require an
authenticated `gh` CLI to fetch the upstream SHA and `MANIFEST.md`. The
guard in `plugins/sync-from-domi/skills/sync-from-domi/scripts/update_pin.sh`
reads:

```bash
if ! command -v gh &>/dev/null || ! gh auth status &>/dev/null; then
  echo "ERROR: gh not authenticated; cannot fetch upstream SHA" >&2
  exit 1
fi

UPSTREAM_SHA=$(gh api "repos/${UPSTREAM_OWNER}/${UPSTREAM_REPO}/commits/${UPSTREAM_BRANCH}" --jq '.sha')
MANIFEST_CONTENT=$(gh api "repos/${UPSTREAM_OWNER}/${UPSTREAM_REPO}/contents/MANIFEST.md?ref=${UPSTREAM_SHA}" --jq '.content' | base64 -d)
```

In remote Claude Code environments (Claude Code on the web, GitHub Actions
runners, ephemeral containers), `gh` is typically not installed or not
authenticated, so the sync aborts even when the plugin itself installs
cleanly via `claude plugin install sync-from-domi@DomI`.

### Reproduction (ADMESH session 2026-05-15)

1. Fresh remote Claude Code session, container cloned ADMESH at `daily-maintenance`.
2. `scripts/instructions_on_start.sh` reports `sync-from-domi not installed`.
3. `claude plugin marketplace add domattioli/DomI` → success.
4. `claude plugin install sync-from-domi@DomI` → success.
5. Re-run SessionStart hook → `gh not authenticated — DomI drift check skipped`.
6. End-to-end sync (e.g. closing ADMESH#62) impossible without leaving the remote env.

### Impact

- Drift-sync issues (the `domi-sync` label) open across all downstream consumers
  cannot be closed from a remote/web session, even though plugin install works.
- Downstream CLAUDE.md files document the DomI sync contract as "hard stop on
  drift", which silently degrades to "skipped" in remote envs. Operators may not
  realize they're working off stale shared skills.
- Net effect: the "downstream = pull-only" contract has a missing rail —
  there's no remote-friendly path to actually pull.

### Proposed fix

Drop the hard dependency on `gh` for the read-only operations (SHA + MANIFEST
content). Both are reachable unauthenticated via plain `git`:

```bash
# Upstream SHA — no auth, no rate limit
UPSTREAM_SHA=$(git ls-remote \
  "https://github.com/${UPSTREAM_OWNER}/${UPSTREAM_REPO}.git" \
  "refs/heads/${UPSTREAM_BRANCH}" | awk '{print $1}')

# MANIFEST.md at that SHA — shallow clone or git archive
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT
git clone --depth 1 --branch "${UPSTREAM_BRANCH}" --quiet \
  "https://github.com/${UPSTREAM_OWNER}/${UPSTREAM_REPO}.git" "$TMPDIR"
MANIFEST_CONTENT=$(cat "$TMPDIR/MANIFEST.md")
```

Use `gh api` only when an authenticated upstream call is genuinely required
(e.g. private-repo support, future API features). The pin-check + pin-update
read path doesn't need it.

`check_pin.sh` should also report its existing exit code 4 ("infra failure,
session continues") when neither `gh` nor `git` outbound can reach the
upstream, so SessionStart hooks degrade gracefully rather than erroring.

### Evidence

| Check | Result | Conclusion |
|---|---|---|
| `claude plugin install sync-from-domi@DomI` in remote env | ✓ success | Plugin install path works in remote envs |
| `gh auth status` in same env | ✗ not authenticated | No token mounted in the container |
| `gh api repos/domattioli/DomI/commits/main` | ✗ fails on auth | API path is blocked |
| `git ls-remote https://github.com/domattioli/DomI.git refs/heads/main` | ✓ returned `b8efc4efa91efab75e10519192d811f19e90572a` | Unauthenticated git access works and matches ADMESH#62's expected SHA |
| Anonymous `curl https://api.github.com/repos/domattioli/DomI/commits/main` | ✗ `API rate limit exceeded for 35.238.245.102` | Shared-IP anon API isn't a reliable fallback |

### Acceptance criteria

- [ ] `update_pin.sh` and `check_pin.sh` work in `gh`-less environments using `git`.
- [ ] Existing authenticated `gh` path preserved (no regression for local-CLI users).
- [ ] CLAUDE.md downstream sync-contract snippet updated to note the relaxed dependency.
- [ ] One downstream repo (e.g. ADMESH) verified to close a drift issue from a
      remote Claude Code session after the change lands.

### Related

- Downstream tracking: `domattioli/ADMESH#62`
- Skill source: `plugins/sync-from-domi/skills/sync-from-domi/scripts/{update_pin.sh,check_pin.sh}`
