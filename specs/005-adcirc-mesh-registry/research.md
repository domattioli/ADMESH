# Phase 0 Research: ADCIRC Mesh Registry

Resolves the design unknowns from `plan.md` Technical Context. Format
per topic: **Decision** / **Rationale** / **Alternatives considered**.

---

## R1 — TOML schema layout for the manifest

**Decision**: Use TOML **array-of-tables** (`[[meshes]]`), one block
per mesh, with nested sub-tables for `bounding_box` and arrays for
`features` and `provenance_history`.

```toml
[[meshes]]
id          = "noaa/hsofs@v2021"
namespace   = "noaa"
name        = "hsofs"
version     = "v2021"
source_url  = "https://example.org/hsofs.fort.14"
content_hash = "sha256:abc123..."
num_triangles = 1813443
license     = "public-domain"
features    = ["open_ocean", "estuary"]
created_by  = "Jane Doe <jane@example.org>"
created_date = 2021-08-15T00:00:00Z
review_state = "approved"

  [meshes.bounding_box]
  min_lon = -98.0
  min_lat = 8.5
  max_lon = -60.0
  max_lat = 46.0

  [[meshes.provenance_history]]
  operation_type = "refine_box"
  applied_date   = 2022-03-10T00:00:00Z
  applied_by     = "Jane Doe <jane@example.org>"
    [meshes.provenance_history.parameters]
    bbox = [-90.0, 28.0, -88.0, 30.0]
```

**Rationale**: Array-of-tables is TOML's idiomatic "list of records"
pattern (same as `[[tool.poetry.dependencies]]`-style usage). It
preserves order, plays well with diff tools (one mesh = one block of
adjacent lines), and is the format `tomllib`/`tomli-w` round-trip
without surprises.

**Alternatives considered**:
- *Flat top-level table per mesh keyed by ID* (`[noaa/hsofs@v2021]`) —
  rejected because slashes in TOML keys require quoting, which breaks
  syntax highlighting in most editors.
- *One file per mesh in a directory* — rejected for the bootstrap
  (5–500 entries); 5K+ entries triggers the namespace-shard layout
  defined in FR-013, which is a coarser split than per-mesh.

---

## R2 — Manifest sharding strategy at scale

**Decision**: At ≥5K entries, split into one file per namespace under
`manifests/<namespace>.toml`. The loader resolves all shards by
globbing `manifests/*.toml` and concatenating the `[[meshes]]` arrays
in memory. A single root `manifest.toml` is retained for ≤5K entries
during bootstrap.

**Rationale**: Namespace is the natural unit of contributor authority
(NOAA edits NOAA's meshes; an academic group edits theirs). Sharding
by namespace keeps PR diffs minimal and avoids cross-contributor
merge conflicts on a monolithic file. Namespaces are bounded
(realistically 10–100), so namespace-count never explodes to where
file-per-namespace becomes the wrong unit.

**Alternatives considered**:
- *Shard by entry count (e.g., 1K per file)* — rejected because it
  breaks PR locality (one contributor's edits land across multiple
  shards).
- *Parquet sidecar* — deferred to Phase 2; the PDF flagged it for
  queryability, but for Phase 1 a Python in-memory scan is fast
  enough at 10K rows.

---

## R3 — HuggingFace Datasets for non-tabular mesh files

**Decision**: Publish the manifest as a Parquet sidecar (one row per
mesh, flattened metadata) AND publish the mesh files themselves under
`data/<namespace>/<name>/<version>.fort.14` for entries with
`mirror_eligible=true`. Use the `huggingface_hub` Python API in CI to
push, with `commit_message` referencing the source release tag.

**Rationale**: HF Datasets is row-oriented (Parquet/Arrow) by
default. A Parquet sidecar gives users free filterable previews in
the HF web UI; the raw mesh files remain accessible via the dataset
repo's file tree. This is the documented "raw-files-with-loader"
pattern HF supports for media datasets, and the PDF explicitly
suggested it.

**Alternatives considered**:
- *Mesh files only, no Parquet* — rejected because users lose the HF
  web search UI (per FR-010 requirement).
- *Custom `loading_script.py` for `datasets.load_dataset(...)` to
  parse fort.14 on the fly* — rejected for Phase 1 (deferred to
  Phase 2 polish); too much logic for limited Phase 1 value.

---

## R4 — GitHub Actions PR validation workflow

**Decision**: Two workflows under `.github/workflows/`:

1. `validate-pr.yml` — runs on every PR touching `manifest.toml` or
   `manifests/**.toml`. Steps: install package (editable), run
   `mesh-registry validate manifest.toml`, fail on any schema or
   sanity error. Posts a summary comment with diff (added/removed/
   changed entries).
2. `publish-hf.yml` — runs on release tag push (`v*`). Steps:
   install package, run `mesh-registry publish --to=huggingface
   --dataset=adcirc-meshes` (uses `HF_TOKEN` secret).

**Rationale**: Splits validation (cheap, runs on every PR) from
publication (expensive, runs only on tagged releases). Single-action
files are easier to audit than reusable workflows for a small repo.

**Alternatives considered**:
- *Continuous push to HF on every merge to main* — rejected; produces
  noisy HF dataset version history and risks publishing unreviewed
  state.
- *Pre-commit hook for schema validation* — kept as a CONTRIBUTING.md
  recommendation but not enforced; CI is the binding gate.

---

## R5 — Bounding box overlap algorithm

**Decision**: Use `shapely.box(...).intersects(other_box)` for
spatial overlap queries. Wrap in a tiny helper that handles
antimeridian crossing (when `min_lon > max_lon`).

**Rationale**: Shapely v2 ships pure-Python wheels for all supported
platforms, has an O(1) bbox-vs-bbox intersection, and is already
familiar to scientific Python users. For 10K entries with linear scan
the total query time is sub-millisecond in pure C-extension paths.

**Alternatives considered**:
- *Manual implementation* (4 inequality comparisons) — equivalent in
  speed but loses the antimeridian helper and the well-known API.
- *R-tree index (`shapely.STRtree` or `rtree`)* — overkill at 10K
  entries; revisit if catalog grows past 100K (deferred).

---

## R6 — License identifiers

**Decision**: Use a curated enum aligned with SPDX identifiers where
SPDX has a match: `public-domain` (= SPDX `CC-PDDC` or
`LicenseRef-public-domain`), `MIT`, `CC-BY-4.0`, `CC-BY-SA-4.0`,
`CC0-1.0`, `proprietary`, `unknown`. The validator coerces common
synonyms (`CC-BY` → `CC-BY-4.0`, `MIT-0` → `MIT`) at PR time.

**Rationale**: Pure SPDX enum (~600 identifiers) is overkill for a
mesh registry where 95% of entries fall in 5 categories. A curated
enum keeps the validator small and the HF dataset card readable. SPDX
alignment preserves interoperability with broader tooling
(`pip-licenses`, GitHub's license detection).

**Alternatives considered**:
- *Free-form license string* — rejected; defeats the FR-009 validation
  goal.
- *Full SPDX enum* — deferred until a real-world contributor needs an
  identifier outside the curated set.

---

## R7 — Composite slug parsing & validation

**Decision**: ID grammar is
`<namespace>/<name>@<version>` where:
- `namespace`: `[a-z0-9][a-z0-9-]{0,38}` (DNS-label-like, 39 chars max)
- `name`: same as namespace
- `version`: `[A-Za-z0-9._-]{1,64}` (free-form revision tag)

Implemented as a pydantic field validator; rejects IDs that don't
match the regex with a structured error pointing at the offending
character.

**Rationale**: DNS-label semantics keep IDs URL-safe (HuggingFace
dataset paths) and filesystem-safe (mirror layout). The 39-char limit
matches GitHub username constraints, which is the most likely
namespace authority. Version is permissive because real-world mesh
versions look like `v2021`, `2024-Q1`, `hurricane-ian-rev3`.

**Alternatives considered**:
- *UUIDs* — rejected in spec clarification Q2.
- *Free-form strings* — rejected; precludes URL/filesystem safety.

---

## R8 — Default conflict resolution for duplicate content hashes

**Decision**: Authoritative entry = oldest `created_date` among all
entries sharing a content hash. Maintainers can override by setting
`authoritative = true` on a single entry (validator enforces at most
one such override per hash group).

**Rationale**: "First registered wins" is unambiguous and stable
(re-running the validator gives the same answer). Overrides handle
the case where the official source registered late.

**Alternatives considered**:
- *Lexicographic-ID tiebreaker* — opaque to humans; doesn't reflect
  actual provenance.
- *No default, force manual override always* — too much friction for
  the common case where a duplicate is genuinely incidental.

---

## R9 — Version policy for the loader package

**Decision**: SemVer. MAJOR for breaking schema changes (a
non-additive change to the TOML format). MINOR for new optional
fields, new query filters, new `Mesh` methods. PATCH for bug fixes
and validator improvements. The schema version is encoded in
`pyproject.toml` under `[tool.adcirc-mesh-registry]
schema_version = "1.0"` and surfaced via
`adcirc_mesh_registry.SCHEMA_VERSION`.

**Rationale**: Decouples the loader's runtime version (whatever
ships) from the manifest schema version (what the loader can parse).
This matches the spec's "Schema Stability" assumption and avoids
forcing a new package release every time the manifest grows an
optional field.

**Alternatives considered**:
- *Single version (loader + schema)* — couples concerns; every
  optional-field addition forces a release.
- *Date-based versioning* — incompatible with PyPI dependency
  resolvers' SemVer expectations.

---

## R10 — Local cache for the loader

**Decision**: Loader caches downloaded mesh files under
`$XDG_CACHE_HOME/adcirc-mesh-registry/<namespace>/<name>/<version>/`
(falling back to `~/.cache/...` on systems without XDG). Cache key is
the content hash from the manifest; mismatched downloads are
rejected.

**Rationale**: Standard XDG paths are user-discoverable and respect
shared-cache conventions. Hash-based cache validity protects against
silent corruption.

**Alternatives considered**:
- *No cache, fetch every call* — wastes bandwidth on repeated
  `Mesh.load()` in the same session.
- *Project-local cache (`./.mesh-cache/`)* — multiplies storage
  across project directories.

---

## Outstanding for Phase 2+ (deferred, not blocking Phase 1)

- Schema versioning negotiation in the loader (forward-compat reads).
- AI-assisted bundle generation (clustering / NL queries).
- Custom `datasets.load_dataset(...)` script for streaming mesh
  parses.
- Zenodo cross-publication for DOI minting.
- Observability (loader telemetry, query metrics) — not needed at
  Phase 1 traffic levels.
