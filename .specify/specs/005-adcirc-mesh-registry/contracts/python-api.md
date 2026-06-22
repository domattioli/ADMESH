# Contract: Python Loader API

The public API surface of `adcirc_mesh_registry`. Consumers (ADMESH,
other simulation tools, notebooks) depend on this; breaking changes
require a MAJOR version bump.

## Top-level imports

```python
from adcirc_mesh_registry import (
    find,                  # query function
    load_manifest,         # explicit manifest load (advanced)
    Mesh,                  # entity model
    SCHEMA_VERSION,        # str, e.g., "1.0"
    __version__,           # str, package version (independent of SCHEMA_VERSION)
)
```

## `find(...)` — primary query

```python
def find(
    *,
    bbox:           tuple[float, float, float, float] | None = None,
    features:       list[str] | None = None,
    min_size:       int | None = None,
    max_size:       int | None = None,
    license:        str | list[str] | None = None,
    namespace:      str | None = None,
    contributor:    str | None = None,
    include_deprecated: bool = False,
    manifest:       str | Path | None = None,   # default: cached HF download
) -> list[Mesh]:
    ...
```

**Semantics**:

- All filter args are AND-combined; passing none returns all
  non-deprecated meshes.
- `bbox` semantics: returns meshes whose `bounding_box` intersects
  the query bbox (R5; antimeridian-safe).
- `features` semantics: returns meshes whose `features` is a
  superset of the query list (must contain ALL).
- `min_size`/`max_size`: inclusive bounds on `num_triangles`.
- `license` accepts a single identifier or a list (OR-combined within
  the list).
- `include_deprecated=True` opts into surfacing tombstones (FR-015).
- `manifest=None` triggers download from the HF Datasets mirror
  (cached under XDG cache, R10). Pass an explicit path for offline
  or testing use.

**Performance contract**: For a manifest of 10K entries with all
filters set, returns in under 1 second on a modern laptop CPU when
the manifest is locally cached (FR-014, SC-009).

**Errors**:

- `ManifestNotFoundError` — no manifest at the given path or HF mirror unreachable.
- `SchemaVersionError` — manifest's `schema_version` MAJOR exceeds loader's.
- `ManifestValidationError` — manifest fails schema validation
  (raised by underlying `load_manifest`, propagated).

## `Mesh` class

```python
@dataclass
class Mesh:
    id:                 str
    namespace:          str
    name:               str
    version:            str
    source_url:         str
    content_hash:       str
    num_triangles:      int
    license:            str
    mirror_eligible:    bool
    bounding_box:       BoundingBox
    features:           list[str]
    created_by:         str
    created_date:       datetime
    review_state:       str
    deprecation_reason: str | None
    deprecated_date:    datetime | None
    derived_from:       str | None
    provenance_history: list[MeshOperation]
    authoritative:      bool

    def load(self, *, cache_dir: Path | None = None) -> Path:
        """Download the mesh file (if needed) and return a local path."""

    def lineage(self, *, manifest: Manifest | None = None) -> list["Mesh"]:
        """Return the chain of ancestors, root-first. Empty if no parent."""

    def to_fort14(self) -> str:
        """Return the mesh content as fort.14 ASCII (loads if needed)."""
```

### `Mesh.load()` semantics

- For `mirror_eligible=True` meshes: fetches from HuggingFace
  Datasets at `data/<namespace>/<name>/<version>.fort.14`.
- For `mirror_eligible=False`: fetches from `source_url`.
- Caches under `$XDG_CACHE_HOME/adcirc-mesh-registry/<namespace>/<name>/<version>/`
  (R10). Re-validates `content_hash` on every load; rejects on
  mismatch with `ContentHashMismatchError`.
- Returns `Path` to the local cached file; does NOT parse the
  fort.14 (that's `to_fort14()` or a downstream tool's job).

### `Mesh.lineage()` semantics

- Walks `derived_from` until hitting a root.
- Returns `[root, ..., parent]` (excludes `self`).
- Tombstoned ancestors are included (FR-015 lineage integrity).
- Raises `LineageCycleError` if a cycle is detected (defense in
  depth; the manifest validator should catch this at PR time).

## `load_manifest(...)` — advanced

```python
def load_manifest(path: str | Path) -> Manifest:
    """Load a TOML manifest (single file or sharded directory) and
    return a validated Manifest object."""
```

`Manifest` exposes `.meshes: list[Mesh]`, `.schema_version: str`,
and helper methods (`.by_id(id)`, `.by_namespace(ns)`).

## Exceptions

| Exception | Raised when |
|---|---|
| `ManifestNotFoundError` | Manifest path does not exist or HF mirror unreachable |
| `SchemaVersionError` | Manifest schema_version MAJOR exceeds loader |
| `ManifestValidationError` | Schema or invariant violation; carries a list of structured errors |
| `MeshNotFoundError` | `find` query returned an empty list AND caller used `find_one` strict variant (TBD if we add this in Phase 2) |
| `ContentHashMismatchError` | Downloaded file hash != expected hash |
| `LineageCycleError` | `Mesh.lineage()` detected a cycle |

All exceptions inherit from `RegistryError` for catch-all use.

## CLI surface (separate from library API)

```bash
mesh-registry validate manifest.toml          # exit 0 = valid, 1 = errors
mesh-registry find --bbox=-97,25,-80,30      # JSON output to stdout
mesh-registry publish --to=huggingface       # CI use; reads $HF_TOKEN
```

CLI is a thin wrapper around the library; non-trivial logic lives in
the library so it's testable without subprocess machinery.
