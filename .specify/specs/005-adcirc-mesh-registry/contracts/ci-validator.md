# Contract: CI Validator

The validator runs in `.github/workflows/validate-pr.yml` on every PR
that touches `manifest.toml` or `manifests/**.toml`. It is also
exposed as `mesh-registry validate` for local pre-commit use.

## Inputs

- One or more TOML manifest files (or a sharded directory).
- Implicit: the previous `main` state of the same files (for diff
  generation in the PR comment).

## Behavior

### 1. Schema validation (per file)

Run pydantic validation of every `[[meshes]]` entry against the
`Mesh` model. Collect ALL errors before exiting (don't stop on
first); report them as a structured list.

### 2. Manifest-level invariants (per file or merged dir)

In order:

1. **Unique IDs** across all entries (within a single file or
   merged across all shards).
2. **No dangling `derived_from`** — every parent ID exists
   (deprecated parents allowed).
3. **No DAG cycles** in `derived_from` chains.
4. **At most one `authoritative=True`** per `content_hash` group.
5. **Tombstone consistency**: `review_state==deprecated` ⇒ both
   `deprecation_reason` and `deprecated_date` set.
6. **Schema version compatibility**: file's `schema_version` MAJOR
   ≤ validator's supported version.

### 3. Sanity checks (per new entry only — diff-based)

For each NEWLY added or MODIFIED `[[meshes]]` entry compared to
`main`:

- **URL reachability**: `HEAD` request to `source_url`; warn
  (not error) on 4xx/5xx or timeout. Mirror-eligible meshes whose
  `source_url` is unreachable still pass — the mirror is the
  fallback.
- **Hash consistency check**: if `source_url` is reachable AND the
  file is small (<10 MB), download and verify `content_hash`. For
  larger files, trust the contributor's declared hash.
- **Bounding-box plausibility**: warn if bbox area is suspiciously
  small (< 1 km²) or spans >180° in longitude (likely a sign
  error).
- **Triangle-count plausibility**: warn if `num_triangles` is < 100
  or > 50,000,000.

### 4. Diff summary

Generate a Markdown summary of changes for the PR comment:

```markdown
## Manifest changes in this PR

**Added** (2):
- `noaa/hsofs@v2024` (Atlantic + Gulf, 2.1M triangles, public-domain)
- `usace/galveston-bay@2024-Q1` (Galveston Bay, 89K triangles, CC-BY-4.0)

**Modified** (1):
- `noaa/hsofs@v2021`: `review_state` changed `approved` → `deprecated`

**Removed** (0): none.
```

## Outputs

- **Exit code**: 0 = all checks pass (warnings allowed); 1 = at
  least one error.
- **stdout** (CLI): JSON with `{errors: [...], warnings: [...],
  summary: "..."}`.
- **GitHub PR comment** (CI): the diff summary (above) + a
  collapsible `<details>` block with full error/warning lists.

## Error format

Each error/warning is a structured object:

```json
{
  "level": "error",
  "code": "INVARIANT_DANGLING_REF",
  "message": "derived_from points to a non-existent mesh",
  "location": {
    "file": "manifest.toml",
    "entry_id": "noaa/foo@v2024",
    "field": "derived_from",
    "value": "noaa/missing@v2020"
  }
}
```

## Error codes (initial set)

| Code | Level | Trigger |
|---|---|---|
| `SCHEMA_INVALID_FIELD` | error | Pydantic per-field validation failure |
| `INVARIANT_DUPLICATE_ID` | error | Two entries with the same `id` |
| `INVARIANT_DANGLING_REF` | error | `derived_from` resolves nowhere |
| `INVARIANT_LINEAGE_CYCLE` | error | Cycle in `derived_from` graph |
| `INVARIANT_MULTIPLE_AUTHORITATIVE` | error | More than one `authoritative=True` per content_hash |
| `INVARIANT_TOMBSTONE_INCOMPLETE` | error | `deprecated` state without reason or date |
| `SCHEMA_VERSION_INCOMPATIBLE` | error | Manifest MAJOR > validator MAJOR |
| `SANITY_URL_UNREACHABLE` | warning | `source_url` returned non-2xx |
| `SANITY_HASH_MISMATCH` | error | Downloaded file hash ≠ declared hash (small-file check) |
| `SANITY_BBOX_DEGENERATE` | warning | Bbox area implausibly small or spans wrong sign |
| `SANITY_TRIANGLE_COUNT_OUTLIER` | warning | `num_triangles` outside [100, 5×10⁷] |

New codes added in MINOR releases.

## Performance contract

For a 10K-entry manifest, validator completes in under 30 seconds
(SC-004 supports a 30-minute review-and-merge target; the validator
is a small fraction of that).

## Determinism

Validator output (set of errors/warnings, summary text) is
deterministic for a given input — no time-of-day, hostname, or
random ordering dependencies. This makes CI failures reproducible
locally via the same `mesh-registry validate` command.
