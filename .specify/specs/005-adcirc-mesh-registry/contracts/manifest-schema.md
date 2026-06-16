# Contract: TOML Manifest Schema

The on-disk format for the registry. Producers (humans editing PRs,
publishing scripts) and consumers (the loader, CI validator, HF
publisher) agree on this contract.

## Top-level structure

```toml
schema_version = "1.0"            # optional; default "1.0"

[[meshes]]
# ... mesh entry (see below)

[[meshes]]
# ... another mesh entry
```

`schema_version` follows SemVer for the schema (R9). Loader rejects
manifests whose MAJOR exceeds its supported version. New optional
fields are MINOR; new required fields or removed fields are MAJOR.

## Mesh entry

```toml
[[meshes]]
# Identity (required)
id            = "noaa/hsofs@v2021"           # composite slug, see ID grammar
source_url    = "https://example.org/x.fort.14"
content_hash  = "sha256:abc123..."           # 64-char hex after prefix

# Classification (required)
num_triangles = 1813443                       # integer >= 0
license       = "public-domain"               # see LicenseId enum
features      = ["open_ocean", "estuary"]    # list (may be empty) of FeatureTag

# Provenance (required for created_by/date; optional otherwise)
created_by    = "Jane Doe <jane@example.org>"
created_date  = 2021-08-15T00:00:00Z
review_state  = "approved"                    # draft|approved|deprecated

# Geographic (required)
[meshes.bounding_box]
min_lon = -98.0
min_lat =   8.5
max_lon = -60.0
max_lat =  46.0

# Lineage (optional — derived meshes only)
derived_from = "noaa/hsofs@v2018"            # parent ID

[[meshes.provenance_history]]
operation_type = "refine_box"
applied_date   = 2022-03-10T00:00:00Z
applied_by     = "Jane Doe <jane@example.org>"
  [meshes.provenance_history.parameters]
  bbox = [-90.0, 28.0, -88.0, 30.0]
  target_resolution = 50.0

# Tombstone (required when review_state == "deprecated")
# deprecation_reason = "License retracted by source"
# deprecated_date    = 2026-01-15T00:00:00Z

# Conflict-resolution override (optional)
# authoritative = true                        # at most one per content_hash
```

## Field constraints (summary; full rules in `data-model.md`)

| Field | Constraint |
|---|---|
| `id` | Matches `<namespace>/<name>@<version>`; namespace and name are DNS-label-like (≤39 chars); version ≤64 chars |
| `source_url` | Valid HTTP(S) URL |
| `content_hash` | Format `sha256:<64-hex>` |
| `num_triangles` | Integer ≥ 0 |
| `license` | One of: `public-domain`, `CC0-1.0`, `CC-BY-4.0`, `CC-BY-SA-4.0`, `MIT`, `proprietary`, `unknown` |
| `features[*]` | One of: `open_ocean`, `inlet`, `estuary`, `tidal_flat`, `barrier_island`, `levee`, `breakwater`, `wetland`, `shipping_channel`, `river_outflow`, `bay`, `lagoon`, `reef` |
| `created_by` | `Name <email>` format |
| `bounding_box.min_lat` ≤ `max_lat` | enforced |
| `bounding_box.min_lon > max_lon` | permitted (antimeridian) |
| `review_state` | `draft` \| `approved` \| `deprecated` |
| `derived_from` | If set, must resolve to another mesh's `id` |
| Tombstone fields | Required iff `review_state == deprecated` |

## Sharded layout (≥5K entries)

When entry count crosses 5K, replace `manifest.toml` with:

```text
manifests/
├── noaa.toml                # all entries with namespace=noaa
├── usace.toml               # all entries with namespace=usace
└── ...
```

Each shard has the same top-level `schema_version` and `[[meshes]]`
structure. Loader concatenates shards in alphabetical order; entry
order within a shard is preserved.

## Forward compatibility

- **Adding optional fields** (e.g., a new `tags` array) is a MINOR
  schema change. Older loaders ignore unknown fields.
- **Adding required fields** is MAJOR; older loaders reject the
  manifest with a clear error.
- **Removing fields** is MAJOR; downstream tools that depended on
  them break visibly.
- **Renaming fields** is MAJOR; aliases are not provided (one canonical
  name at any time).
