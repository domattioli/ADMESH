# Quickstart: ADCIRC Mesh Registry

This document is the user-facing onboarding for the registry. It
covers the three audiences from the spec:

1. **Researchers** finding and loading meshes (User Stories 1 & 4).
2. **Contributors** submitting new meshes (User Story 3).
3. **Maintainers** publishing releases.

It will be promoted to the new repo's `README.md` and adapted as the
HuggingFace dataset card.

---

## For researchers — find and load a mesh

```bash
pip install adcirc-mesh-registry
```

```python
from adcirc_mesh_registry import find

# Find meshes covering the western Gulf of Mexico,
# with levee features, ≤ 50K triangles, public-domain licensed.
meshes = find(
    bbox=(-97, 25, -88, 30),
    features=["levee"],
    max_size=50_000,
    license="public-domain",
)

for m in meshes:
    print(f"{m.id}: {m.num_triangles} triangles, {m.license}")

# Download and use one
mesh = meshes[0]
fort14_path = mesh.load()      # cached under ~/.cache/adcirc-mesh-registry/
print(f"Mesh file: {fort14_path}")

# Trace lineage
for ancestor in mesh.lineage():
    print(f"  ← {ancestor.id}")
```

**Cache location**: `$XDG_CACHE_HOME/adcirc-mesh-registry/` or
`~/.cache/adcirc-mesh-registry/`. Files are validated against the
manifest's `content_hash` on every load.

**Offline use**: pass an explicit manifest path:

```python
meshes = find(bbox=..., manifest="./local-manifest.toml")
```

---

## For contributors — submit a new mesh

### Prerequisites

- Your mesh in fort.14 ASCII format (or equivalent).
- A public URL where it lives (your S3 bucket, GitHub release
  asset, institutional archive, etc.).
- Familiarity with GitHub PR workflow.

### Steps

1. **Fork** `domattioli/adcirc-mesh-registry`.
2. **Compute the content hash**:
   ```bash
   sha256sum your-mesh.fort.14
   ```
3. **Add an entry to `manifest.toml`** (or `manifests/<your-namespace>.toml`
   if the repo is sharded). Use this template:

   ```toml
   [[meshes]]
   id            = "your-namespace/your-mesh@v2026"
   source_url    = "https://your-host/your-mesh.fort.14"
   content_hash  = "sha256:abc123..."
   num_triangles = 12345
   license       = "CC-BY-4.0"
   features      = ["estuary", "levee"]
   created_by    = "Your Name <you@example.org>"
   created_date  = 2026-04-25T00:00:00Z
   review_state  = "draft"

     [meshes.bounding_box]
     min_lon = -97.0
     min_lat =  25.0
     max_lon = -88.0
     max_lat =  30.0
   ```

4. **Validate locally** (optional but recommended):
   ```bash
   pip install adcirc-mesh-registry
   mesh-registry validate manifest.toml
   ```
5. **Open a PR**. CI will run `validate-pr.yml` and post a summary
   comment within ~30 seconds.
6. **Address feedback**. A maintainer will review and either
   approve (changing your entry's `review_state` to `approved`) or
   request edits.
7. **Merge**. Your mesh appears in the registry on the next
   release tag (typically within a week).

### Common validation failures

- **Hash mismatch** — your `content_hash` doesn't match the file at
  `source_url`. Re-run `sha256sum` and update the entry.
- **Dangling `derived_from`** — you cited a parent mesh that
  doesn't exist in the manifest. Verify the parent ID.
- **Bbox spans wrong sign** — likely a longitude sign error
  (`-97` vs `97`).
- **Unknown feature tag** — your `features` list contains a tag not
  in the controlled vocabulary. Either pick an existing tag or
  open a separate PR adding the new tag with a description.

---

## For derived meshes — record provenance

When your mesh is a refinement or modification of an existing one:

```toml
[[meshes]]
id           = "your-namespace/galveston-refined@v2026"
derived_from = "noaa/hsofs@v2021"      # the parent
# ... other fields ...

  [[meshes.provenance_history]]
  operation_type = "refine_box"
  applied_date   = 2026-04-20T00:00:00Z
  applied_by     = "Your Name <you@example.org>"
    [meshes.provenance_history.parameters]
    bbox = [-95.5, 28.5, -94.0, 29.5]
    target_resolution = 25.0

  [[meshes.provenance_history]]
  operation_type = "add_levee"
  applied_date   = 2026-04-22T00:00:00Z
  applied_by     = "Your Name <you@example.org>"
    [meshes.provenance_history.parameters]
    polyline        = [[-94.8, 29.3], [-94.7, 29.35], [-94.6, 29.4]]
    crest_elevation = 4.5
```

See `contracts/manifest-schema.md` for the full operation vocabulary.

---

## For maintainers — publish a release

```bash
# Tag the validated state of main
git tag -a v1.2.0 -m "Add Texas Gulf coast bundle (5 meshes)"
git push origin v1.2.0
```

The `publish-hf.yml` workflow runs automatically on tag push:

1. Re-validates the manifest (defense in depth).
2. Mirrors `mirror_eligible=True` mesh files to HuggingFace.
3. Removes any newly-deprecated meshes from the HF mirror.
4. Regenerates the Parquet sidecar and dataset card.
5. Commits everything to the HF dataset in a single atomic commit.

Wall-clock time: ~5 min for an incremental release, ~1 hour for a
full re-publish (10K entries / ~50 GB).

### Tombstoning a mesh

To deprecate (license retraction, source request, or quality issue):

```toml
[[meshes]]
id                 = "namespace/name@version"
# ... unchanged metadata ...
review_state       = "deprecated"
deprecation_reason = "Source archive requested takedown"
deprecated_date    = 2026-04-25T00:00:00Z
```

The next release removes the file from HF; the entry remains in
the manifest (for lineage integrity) but is excluded from default
queries.

---

## Troubleshooting

**"ManifestNotFoundError"**: check that `pip install` was successful
and your network can reach `huggingface.co`. To use offline:
download the manifest manually and pass `manifest=path/to/file.toml`
to `find()`.

**"ContentHashMismatchError"**: a downloaded file's hash didn't match
the manifest. Either the source was tampered with, or the manifest
hash is stale. File an issue on the registry repo.

**"SchemaVersionError"**: your installed loader is older than the
manifest's schema. Run `pip install -U adcirc-mesh-registry`.
