# Contract: HuggingFace Publisher

The publisher runs in `.github/workflows/publish-hf.yml` on every
release tag (`v*`) push. It is also exposed as
`mesh-registry publish` for ops use.

## Inputs

- A validated manifest (single file or sharded dir) at the release
  tag's commit.
- Environment variable `HF_TOKEN` with write access to
  `huggingface.co/datasets/adcirc-meshes` (or the configured
  dataset slug).
- Release tag string (e.g., `v1.0.0`) for the HF commit message and
  dataset card revision label.

## Behavior

### 1. Pre-flight

- Re-run the CI validator against the manifest. Hard fail if any
  errors. (Defense in depth — `validate-pr.yml` should have caught
  these, but releases must not push invalid state.)
- Verify `HF_TOKEN` is set and authenticates against the target
  dataset.

### 2. Mesh file mirroring (one file per `mirror_eligible=True` mesh)

For every entry with `mirror_eligible == True`:

- If a file already exists at the target HF path with the same
  `content_hash`, skip (idempotent).
- Otherwise, download from `source_url`, verify hash, then upload
  to `data/<namespace>/<name>/<version>.fort.14` in the HF dataset
  repo using `huggingface_hub.upload_file`.

For entries with `mirror_eligible == False`: do NOT upload.
Metadata still appears in the manifest sidecar (next step), with a
note that the file lives at `source_url`.

### 3. Tombstone cleanup

For every entry with `review_state == "deprecated"` that previously
had a mirrored file:

- Delete the file from the HF dataset repo via
  `huggingface_hub.delete_file`.
- Retain the metadata row in the Parquet sidecar (with
  `review_state=deprecated` flag visible in the HF web UI).

### 4. Parquet sidecar generation

Flatten every entry (including deprecated) into one row of a
Parquet table, written to `manifest.parquet` in the HF dataset
repo. Columns mirror the `Mesh` model with these flatten rules:

- `bounding_box` → 4 columns: `bbox_min_lon`, `bbox_min_lat`,
  `bbox_max_lon`, `bbox_max_lat`.
- `features` → kept as `list<string>`.
- `provenance_history` → serialized to a JSON string in column
  `provenance_history_json` (Parquet structs of variable-schema
  dicts are awkward; JSON is sufficient and HF UI renders it).

Schema is documented in the dataset card.

### 5. Dataset card generation

Render `README.md` (the HF dataset card) from a Jinja template
filled with:

- Total mesh count, breakdown by license and namespace.
- Geographic coverage map (top-10 bbox extents).
- Citation block (BibTeX referencing the GitHub repo + tag).
- Schema reference (link to the `manifest-schema.md` contract).
- Quickstart code block (Python `find()` example).

### 6. Atomic commit

All file uploads, the Parquet write, and the README write happen
in a single HF API commit (via
`huggingface_hub.create_commit(operations=[...])`) so partial
failures don't leave the dataset in a half-published state.

Commit message format:

```
release <release_tag>: <N_added> added, <N_modified> modified, <N_deprecated> deprecated

Source: github.com/domattioli/adcirc-mesh-registry@<release_tag>
Schema: <schema_version>
```

## Idempotency

Running publish twice for the same release tag is safe. The HF API's
SHA-based content addressing means re-uploading identical files is a
no-op; the sidecar/README are overwritten with byte-identical
content (deterministic generation from the same manifest), producing
either a no-op commit or a single commit collapsing both runs.

## Failure modes

| Failure | Behavior |
|---|---|
| Manifest validation fails pre-flight | Abort, exit 1, no HF state changes |
| `HF_TOKEN` invalid or missing | Abort, exit 1 |
| Source URL unreachable for a `mirror_eligible` entry | Skip that entry's file upload, log warning, continue (entry still appears in sidecar with `mirror_status=fallback_to_source_url`) |
| HF API rate limit hit | Backoff (exponential, 4 retries: 2s, 4s, 8s, 16s); abort after exhaustion |
| Hash mismatch on download (small-file path) | Abort, exit 1 — refuse to mirror tampered content |

## Outputs

- HF dataset commit (one) containing: 0+ new mesh files, 0+
  deletions, 1 updated `manifest.parquet`, 1 updated `README.md`.
- Workflow log with: per-entry mirror status, total upload size,
  total wall time.
- Optional: GitHub release annotation (comment on the release tag)
  with a link to the HF dataset commit.

## Performance contract

For a 10K-entry manifest with ~7K mirror-eligible (estimated 50
GB total file size), publish completes in under 1 hour on the
default GitHub Actions runner. Re-publish (idempotent no-op case)
completes in under 5 minutes.

## Security & secrets

- `HF_TOKEN` stored as a GitHub repo secret, accessed only by
  `publish-hf.yml` (the validator workflow does NOT need it).
- Token scope: write access to a single HF dataset repo. No org-
  or account-level write access.
- Token rotation: documented in CONTRIBUTING.md; recommended every
  90 days.
