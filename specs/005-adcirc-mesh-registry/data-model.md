# Phase 1 Data Model: ADCIRC Mesh Registry

Concrete pydantic-v2 model definitions, validation rules, and state
transitions for the four entities in the spec
(Mesh, MeshFeature, MeshOperation, License).

These models are the runtime representation; the on-disk
representation is the TOML form (see
`contracts/manifest-schema.md`).

---

## Entity: Mesh

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | `str` | yes | Composite slug, see ID grammar below |
| `namespace` | `str` | yes (derived) | Parsed from `id`; persisted for query speed |
| `name` | `str` | yes (derived) | Parsed from `id` |
| `version` | `str` | yes (derived) | Parsed from `id` |
| `source_url` | `HttpUrl` | yes | Authoritative origin (always recorded, even when mirrored) |
| `content_hash` | `str` | yes | Format `sha256:<hex64>` |
| `num_triangles` | `int` | yes | `>= 0` |
| `license` | `LicenseId` | yes | Enum, see License entity below |
| `mirror_eligible` | `bool` | yes (derived) | Computed from `license`; persisted for query convenience |
| `bounding_box` | `BoundingBox` | yes | See sub-model below |
| `features` | `list[FeatureTag]` | yes | May be empty; tags from controlled vocabulary |
| `created_by` | `str` | yes | Format: `Name <email>` (RFC 5322-ish) |
| `created_date` | `datetime` | yes | UTC ISO-8601 |
| `review_state` | `ReviewState` | yes | `draft`, `approved`, `deprecated` |
| `deprecation_reason` | `str \| None` | conditional | Required iff `review_state == deprecated` |
| `deprecated_date` | `datetime \| None` | conditional | Required iff `review_state == deprecated` |
| `derived_from` | `str \| None` | optional | References another Mesh by `id` |
| `provenance_history` | `list[MeshOperation]` | optional | Empty when not derived |
| `authoritative` | `bool` | optional, default `False` | Override flag for dedup tiebreaker (R8) |

### ID grammar (R7)

```text
id        := <namespace> "/" <name> "@" <version>
namespace := [a-z0-9][a-z0-9-]{0,38}
name      := [a-z0-9][a-z0-9-]{0,38}
version   := [A-Za-z0-9._-]{1,64}
```

The validator parses `id` once and populates `namespace`, `name`,
`version` automatically (pydantic `model_validator(mode="before")`).

### BoundingBox sub-model

| Field | Type | Notes |
|---|---|---|
| `min_lon` | `float` | `[-180.0, 180.0]` |
| `min_lat` | `float` | `[-90.0, 90.0]` |
| `max_lon` | `float` | `[-180.0, 180.0]` |
| `max_lat` | `float` | `[-90.0, 90.0]` |

`min_lat <= max_lat` is required. `min_lon > max_lon` is
**permitted** to denote antimeridian crossing (e.g., a Pacific
basin mesh from `170°` to `-170°`); the overlap algorithm in R5
handles this case.

### Cross-field validation

- If `derived_from` is set, the referenced ID MUST exist in the
  manifest. Validator runs after all entries are loaded; emits a
  structured error pointing at the dangling reference.
- If `review_state == deprecated`, both `deprecation_reason` and
  `deprecated_date` MUST be non-null.
- `mirror_eligible` is computed: `True` iff
  `license in {public-domain, MIT, CC-BY-4.0, CC-BY-SA-4.0, CC0-1.0}`.
  Persisted for query speed; validator overwrites any user-supplied
  value to enforce derivation.

### Relationships

- `Mesh.derived_from` → `Mesh.id` (many-to-one, optional). Forms a
  DAG when transitively followed.
- `Mesh.provenance_history` → `list[MeshOperation]` (1:N composition,
  embedded).

### State transitions (review_state)

```text
       (created)
           │
           ▼
        draft  ──approve──►  approved  ──deprecate──►  deprecated
           ▲                    │                          ▲
           └────reject──────────┘                          │
                                └──────deprecate───────────┘
```

- `draft → approved`: maintainer approval at PR-merge time.
- `approved → deprecated`: tombstone path (FR-015). Sets
  `deprecation_reason`, `deprecated_date`. File removed from HF
  mirror at next release.
- `draft → draft`: edits allowed.
- `deprecated → *`: not permitted. Tombstones are terminal.
- `approved → draft`: not permitted (use `deprecated` instead).

---

## Entity: MeshOperation

A single transformation applied to a parent mesh.

| Field | Type | Required | Notes |
|---|---|---|---|
| `operation_type` | `OperationKind` | yes | Enum (see below) |
| `parameters` | `dict[str, Any]` | yes | Operation-specific args; schema enforced per `operation_type` |
| `applied_date` | `datetime` | yes | UTC ISO-8601 |
| `applied_by` | `str` | yes | Same `Name <email>` format as `Mesh.created_by` |

### OperationKind enum

| Value | Required parameters |
|---|---|
| `refine_box` | `bbox: [min_lon, min_lat, max_lon, max_lat]`, `target_resolution: float (meters)` |
| `coarsen_box` | `bbox: [...]`, `target_resolution: float` |
| `add_island` | `ring: list[[lon, lat]]` (closed polygon ≥ 4 points) |
| `remove_region` | `ring: list[[lon, lat]]` |
| `add_levee` | `polyline: list[[lon, lat]]`, `crest_elevation: float (meters)` |
| `splice` | `from_mesh: <mesh-id>`, `region: ring` |
| `other` | `description: str` (free-form for ops not yet enumerated) |

The enum is open for additions in MINOR releases (new entries don't
break existing manifests).

---

## Entity: MeshFeature

Controlled vocabulary of physical/geographic feature tags.

| Field | Type | Notes |
|---|---|---|
| `name` | `FeatureTag` | Enum value, used as the canonical tag string in `Mesh.features` |
| `description` | `str` | Human-readable, shown in HF dataset card |

### FeatureTag enum (Phase 1 vocabulary)

`open_ocean`, `inlet`, `estuary`, `tidal_flat`, `barrier_island`,
`levee`, `breakwater`, `wetland`, `shipping_channel`,
`river_outflow`, `bay`, `lagoon`, `reef`.

The enum is extended in MINOR releases. New tags require: a
description, an example mesh that uses the tag, and approval in the
PR review.

---

## Entity: License

| Field | Type | Notes |
|---|---|---|
| `identifier` | `LicenseId` | Enum, see below |
| `full_name` | `str` | Human-readable (e.g., "Creative Commons Attribution 4.0 International") |
| `is_open_source` | `bool` | Per OSI definition |
| `allows_redistribution` | `bool` | Drives `Mesh.mirror_eligible` |
| `attribution_required` | `bool` | Surfaced on HF dataset card |

### LicenseId enum (R6)

| Identifier | Open source | Redistributable | Attribution |
|---|---|---|---|
| `public-domain` | yes | yes | no |
| `CC0-1.0` | yes | yes | no |
| `CC-BY-4.0` | yes | yes | **yes** |
| `CC-BY-SA-4.0` | yes | yes | **yes** |
| `MIT` | yes | yes | yes |
| `proprietary` | no | **no** | varies |
| `unknown` | no | **no** | yes (assume strict) |

`mirror_eligible` is `True` for all rows with `Redistributable = yes`.

---

## Manifest-level invariants

These are validated by the CI pipeline at PR time:

1. **Unique IDs**: No two `[[meshes]]` blocks share the same `id`.
2. **No dangling refs**: Every non-null `derived_from` resolves to
   an existing `id` (including deprecated entries).
3. **No DAG cycles**: Following `derived_from` from any mesh
   eventually reaches a root (no parent).
4. **Hash-group authoritative count**: For each unique
   `content_hash`, at most one entry has `authoritative = True`.
5. **Tombstone consistency**: Every `review_state == deprecated`
   entry has both `deprecation_reason` and `deprecated_date` set.
6. **Schema version compatibility**: The optional top-level
   `schema_version` key (default `"1.0"`) is forward-compatible
   with the loader's `SCHEMA_VERSION`.
