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

## Known drift (as of 2026-05-15)

**`admesh/registry.py` is broken against `admesh-domains` 0.3.x.** The
adapter was written against an older API that used a registry-object
pattern (`admesh_domains.load_default_registry().get_domain(...)`); the
0.3.x API uses top-level functions (`admesh_domains.get_domain(...)`)
and returns a different `Domain` shape (no `.rings` or `.fixed_points`
attributes; instead a `.meshes` list of `Mesh` references with downloadable
`.path`).

Calling `admesh.load_domain_from_registry()` against the installed 0.3.2
raises `AttributeError: module 'admesh_domains' has no attribute
'load_default_registry'`.

Tracking issue: [#64](https://github.com/domattioli/ADMESH/issues/64).

The registry-rewrite work is post-spec-009 because it needs:
- A new optional `huggingface_hub` dependency (for `Mesh.load()` downloads).
- A redesigned adapter mapping `admesh_domains.Domain` → `admesh.Domain`
  via `read_fort14(Mesh.path)` + `admesh.Domain.from_mesh()`.
- New end-to-end tests that exercise the download path (likely behind
  a `slow` marker since they hit the network).

## Contract validation

`tests/test_admesh_domains_contract.py` asserts:

1. `admesh_domains` is importable.
2. `admesh_domains.__version__` satisfies the pin.
3. Every symbol in the "Consumed API surface" table above resolves.
4. `admesh_domains.list_domains()` runs without raising.
5. Each `Domain` returned exposes the attributes ADMESH reads.

This test is part of the standard CI lane. A contract drift caught by
this test is a release-blocking signal.
