# `admesh-domains` Contract

This document specifies the public surface ADMESH consumes from its sibling
package, [`admesh-domains`](https://github.com/domattioli/ADMESH-Domains).
Changes to this contract require a coordinated update of both packages.

## Supported version range

```toml
admesh-domains>=0.3.0,<0.4
```

The pin is declared in `pyproject.toml` under `[project].dependencies`.
ADMESH 0.1.0 is validated against `admesh-domains` 0.3.2. Future minor
bumps within `0.3.x` (`>=0.3.0,<0.4`) are accepted; `0.4.x` requires a
coordinated update and a new contract revision.

## Consumed API surface

ADMESH imports from `admesh_domains` lazily inside `admesh/registry.py`
so a missing install raises a friendly `ImportError` at first registry
use rather than at `import admesh` time.

### Top-level functions

| Symbol                                  | Used by                  | Notes                                       |
|-----------------------------------------|--------------------------|---------------------------------------------|
| `admesh_domains.get_domain(name, *)`    | `load_domain_from_registry` | Returns a `Domain` (see below)             |
| `admesh_domains.list_domains(*)`        | `list_available_domains` | Returns `list[Domain]`                      |

### Data classes

| Class                              | Attributes ADMESH reads                                         |
|------------------------------------|-----------------------------------------------------------------|
| `admesh_domains.Domain`            | `name`, `full_name`, `description`, `category`, `region`, `bounding_box`, `meshes` |
| `admesh_domains.Mesh`              | `id`, `filename`, `bounding_box`, `path`, `exists()`, `load()`  |
| `admesh_domains.BoundingBox`       | `min_lon`, `min_lat`, `max_lon`, `max_lat`                      |

`Mesh.path` is a `pathlib.Path` pointing to the expected local file location
inside the `admesh-domains` install directory. `Mesh.exists()` returns
whether the file is currently on disk; `Mesh.load()` downloads the file
from the upstream HuggingFace mirror if missing (requires the optional
`huggingface_hub` extra).

## Upgrade policy

When `admesh-domains` ships a new version:

1. **Patch** (`0.3.x` → `0.3.y`): no action required; pin already accepts.
   Run `pytest tests/test_admesh_domains_contract.py -v` to confirm.
2. **Minor** (`0.3.x` → `0.4.0`): coordinated update.
   - Run the contract test against `0.4.0` to identify which symbols
     changed.
   - Update `admesh/registry.py` adapter to match the new surface.
   - Update this document and the pin in `pyproject.toml`.
   - Open a PR with both changes; do not bump the pin alone.
3. **Major** (`0.x` → `1.0`): treat as a minor bump; the contract may
   stabilize entirely.

## Network fetch

`admesh_domains.Mesh.load()` downloads the underlying fort.14 from the
upstream HuggingFace mirror. ADMESH treats this as opt-in: install with
`pip install admesh2D[registry]` to pull in `huggingface_hub>=0.20`.
Without the extra, `admesh.load_domain_from_registry` raises a clear
`ImportError` before any network call is made — only the local
`list_available_domains()` path stays usable.

The slow CI lane (`pytest -m slow`) exercises the full chain on the
smallest fixture (`BaranjaHill`, ~0.08 MB), covering
`load_domain_from_registry`, `load_domain_with_metadata`, and the
end-to-end contract test below.

## Contract validation

`tests/test_admesh_domains_contract.py` asserts:

1. `admesh_domains` is importable.
2. `admesh_domains.__version__` satisfies the pin.
3. Every symbol in the "Consumed API surface" table above resolves.
4. `admesh_domains.list_domains()` runs without raising.
5. Each `Domain` returned exposes the attributes ADMESH reads.
6. `test_end_to_end_load_domain_from_registry` (slow lane) exercises
   the full ``get_domain → Mesh.load → read_fort14 → Domain.from_mesh``
   chain.

This test is part of the standard CI lane. A contract drift caught by
this test is a release-blocking signal.
