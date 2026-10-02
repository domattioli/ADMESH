# `valence-domains` Contract

This document specifies the public surface ADMESH consumes from the
[`valence-domains`](https://github.com/domattioli/Valence) registry package.
The package was formerly published as `admesh-domains`.

## Supported versions

```toml
valence-domains>=0.4.2
```

The pin is declared in `pyproject.toml` under `[project].dependencies`. It has
no upper cap. ADMESH supports both registry manifest schemas:

| Manifest schema | Example package release | Lookup route used by ADMESH |
|-----------------|-------------------------|-----------------------------|
| 0.3             | `valence-domains` 0.4.2 | Domain-only API (route c)   |
| 0.4             | `valence-domains` 0.9.0 and later | group API (route a), or the manifest object (route b) |

In CI, the `valence-schema-03` job (shown as "valence-schema-0.3") pins `valence-domains==0.4.2`, and the
main job installs the newest published release. Until a schema-0.4 release is
published, schema 0.4 is checked against a Valence source checkout through
`ADMESH_VALENCE_SRC` (see "Contract validation").

## The compatibility layer

`admesh/registry.py` never calls `valence_domains` lookup functions directly.
It goes through `admesh/_valence_compat.py`, which picks one of three routes by
feature detection (`getattr` / `hasattr`). It never compares version numbers.

| Route | Detected by | Lookup | Listing |
|-------|-------------|--------|---------|
| a. group API | callable `get_group` and `list_collections` | `get_group(name, manifest=None)` | `list_domains()` plus `list_collections()` |
| b. manifest object | `load_manifest()` returns an object with `get_group`, `collections` and `primary_domains` | `Manifest.get_group(name)`, then `resolve_alias` | `primary_domains` plus `collections` |
| c. Domain-only API | fallback | `get_domain(name)` | `list_domains()` |

Routes a and b resolve a Domain, a Domain alias (to its primary Domain) or a
Collection. Route c has no aliases and no Collections. An unknown name raises
`KeyError`, which the registry functions turn into `ValueError`.

## Consumed data

| Object | Attributes ADMESH reads |
|--------|-------------------------|
| Domain | `name`, `full_name`, `description`, `category`, `continent` (schema 0.4) or `region` (schema 0.3), `bounding_box`, `meshes`, `get_mesh()` |
| Collection | `name`, `full_name`, `description`, `meshes`, `get_mesh()` |
| Mesh | `id`, `filename`, `bounding_box`, `license`, `contributor`, `contributed_by`, `version`, `format` (schema 0.4) or `type` (schema 0.3), `path`, `exists()`, `load()` |

Schema 0.4 renamed `region` to `continent` and `type` to `format`.
`load_domain_with_metadata()` reports both names of each pair with the same
value, so callers written against either schema keep working.

## Network fetch

`Mesh.load()` downloads the underlying fort.14 from the upstream mirror.
ADMESH treats this as opt-in: install with `pip install admesh2D[registry]` to
pull in `huggingface_hub`. Without the extra, `load_domain_from_registry`
raises a clear `ImportError` before any network call. Only the local
`list_available_domains()` path stays usable.

Some registered meshes have no hosted copy, because their license does not
allow one. On `valence-domains` releases that define `MeshNotHostedError`,
ADMESH raises that error before checking for `huggingface_hub` and before any
network call. The check is feature-detected through `license_eligible`, and
releases without the class keep their old behaviour.

The slow test lane (`pytest -m slow`) exercises the full chain on the smallest
fixture (`BaranjaHill`, about 0.08 MB).

## Contract validation

- `tests/test_valence_domains_contract.py` runs against the installed package.
  It checks the version floor, that at least one lookup route exists, that
  listing returns entries, and that entries and meshes expose the attributes
  above.
- `tests/test_valence_compat.py` injects one stand-in module per route and
  checks that the registry reports the same names and metadata for the same
  content. When `ADMESH_VALENCE_SRC` points at a Valence source checkout, one
  more test resolves a Domain, an alias and a Collection from that checkout's
  `tests/fixtures/manifest_v04_minimal.toml`.

A contract drift caught by these tests blocks a release.
