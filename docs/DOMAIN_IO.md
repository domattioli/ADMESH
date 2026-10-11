# Domain I/O and Registry Integration

ADMESH loads a mesh domain from a TOML file, a JSON file, a fort.14 mesh, or the registry. Each source returns a domain that `admesh.triangulate()` accepts. Meshes come through Valence.

## Quick Start

### Load from a file

```python
import admesh

# Load from TOML (Valence native format)
mesh = admesh.triangulate("my_domain.toml", h_max=0.1)

# Load from JSON
mesh = admesh.triangulate("my_domain.json", h_max=0.1)

# Extract boundary from existing mesh
mesh = admesh.triangulate("existing_mesh.14", h_max=0.05)
```

### Load from the registry

See [Registry Integration](#registry-integration) for setup.

```python
import admesh

# List available domains
domains = admesh.list_available_domains()
for mesh_id, desc in domains.items():
    print(f"{mesh_id}: {desc}")

# Load by mesh_id (auto-detects registry)
mesh = admesh.triangulate("Block_O.14", h_max=0.1)

# Or use explicit registry loader
domain = admesh.load_domain_from_registry("Block_O.14")
mesh = admesh.triangulate(domain, h_max=0.1)
```

## File Format Specifications

### TOML Format (Recommended)

TOML is the native ADMESH format. It is human-readable and widely supported.

File `domain.toml`:

```toml
[domain]
name = "BaranjaHill"
description = "NOAA HSOFS Atlantic Hurricane Surge Model domain"
bbox = [-85.0, 20.0, -60.0, 40.0]

# Outer boundary ring (required)
[[domain.rings]]
coords = [
    [-85.0, 20.0],
    [-60.0, 20.0],
    [-60.0, 40.0],
    [-85.0, 40.0],
]

# Interior islands (optional, repeat for multiple islands)
[[domain.rings]]
coords = [
    [-75.0, 25.0],
    [-70.0, 25.0],
    [-70.0, 30.0],
    [-75.0, 30.0],
]

# Fixed mesh vertices (optional; useful for re-entrant corners)
[[domain.fixed_points]]
coords = [[-85.0, 20.0], [-60.0, 40.0]]

# Metadata (optional)
[metadata]
version = "1"
contributed_by = "NOAA"
license = "CC-BY-4.0"
source_url = "https://example.org/your-domain-source"
```

Load it with:

```python
domain = admesh.load_domain_from_toml("domain.toml")
mesh = admesh.triangulate(domain, h_max=0.1)
```

### JSON Format

JSON is a universal, portable format. Its structure matches TOML, without the metadata section.

File `domain.json`:

```json
{
  "name": "example_domain",
  "bbox": [-1.0, -1.0, 1.0, 1.0],
  "rings": [
    [[-1, -1], [1, -1], [1, 1], [-1, 1]],
    [[-0.25, -0.25], [0.25, -0.25], [0.25, 0.25], [-0.25, 0.25]]
  ],
  "fixed_points": [[-1, -1], [1, 1]]
}
```

Load it with:

```python
domain = admesh.load_domain_from_json("domain.json")
mesh = admesh.triangulate(domain, h_max=0.1)
```

### Fort.14 Format

The loader extracts the domain boundary from ADCIRC v55 fort.14 mesh files. Use it to re-triangulate at a different resolution, to refine or coarsen a mesh, and to validate a domain.

Load it with:

```python
# Extract boundary from existing mesh
domain = admesh.load_domain_from_fort14("existing_mesh.14")

# Re-triangulate at coarser resolution
coarse_mesh = admesh.triangulate(domain, h_max=0.5)

# Or at finer resolution
fine_mesh = admesh.triangulate(domain, h_max=0.02)
```

The loader extracts:

- The outer boundary polygon, from the first land boundary segment.
- Interior islands (holes), from additional segments.
- The bounding box, computed from node coordinates.
- Corner vertices, marked as fixed points.

## Registry Integration

Registry access calls the Valence HTTP API. No extra package is needed.

1. Set `VALENCE_TOKEN` to your access token.
2. Set `VALENCE_API_URL` when the built-in default does not apply.

Without a token, registry calls raise `RegistryAuthError` and make no network request.

### Discovering Domains

```python
import admesh

# List all available mesh names (values are empty strings)
domains = admesh.list_available_domains()
print(f"Available meshes: {len(domains)}")

# Fetch domain metadata
domain, meta = admesh.load_domain_with_metadata("Block_O.14")
# Metadata holds the name and the content hash.
print(f"Name: {meta['name']}")
print(f"sha256: {meta['sha256']}")
```

### Loading from the registry

Three methods load a registry domain.

```python
import admesh

# Method 1: Direct registry load
domain = admesh.load_domain_from_registry("Block_O.14")
mesh = admesh.triangulate(domain, h_max=0.1)

# Method 2: Auto-detect (string without path separators)
mesh = admesh.triangulate("Block_O.14", h_max=0.1)

# Method 3: With metadata
domain, meta = admesh.load_domain_with_metadata("Block_O.14")
mesh = admesh.triangulate(domain, h_max=0.1)
print(f"sha256: {meta['sha256']}")
```

## Complete Example

```python
import admesh
import numpy as np

# Load domain from registry
domain = admesh.load_domain_from_registry("Block_O.14")

# Triangulate with custom parameters
mesh = admesh.triangulate(
    domain,
    h_max=0.15,  # Target edge length
    seed=42,  # Reproducible randomness
)

# Save the mesh
admesh.write_fort14(mesh, "output_mesh.14")

# Inspect mesh quality
print(f"Nodes: {mesh.n_nodes}")
print(f"Elements: {mesh.n_elements}")
print(f"Quality: {mesh.quality}")

# Re-triangulate boundary at finer resolution
finer_mesh = admesh.triangulate(domain, h_max=0.05)
print(f"Finer mesh: {finer_mesh.n_nodes} nodes")
```

## Conventions

### Coordinate system

- Coordinates are (x, y) pairs, typically longitude/latitude for geographic domains.
- Indexing is 0-based (Python convention, not MATLAB 1-based).
- Bbox format is (xmin, ymin, xmax, ymax).

### Signed distance function (SDF)

- Negative: inside the domain.
- Positive: outside the domain.
- Zero: on the boundary.
- Shapely constructs it from the polygon rings.

### Fixed points

- Fixed points are pinned vertices the triangulator must preserve.
- They suit re-entrant corners and domain features.
- They are optional. Omit them if you do not need them.

## Error Handling

```python
import admesh

# File not found
try:
    domain = admesh.load_domain_from_toml("missing.toml")
except FileNotFoundError:
    print("Domain file not found")

# Invalid format
try:
    domain = admesh.load_domain_from_json("bad_domain.json")
except ValueError as e:
    print(f"Invalid domain: {e}")

# Registry not available
try:
    domain = admesh.load_domain_from_registry("some-mesh")
except admesh.registry.RegistryAuthError:
    print("Set VALENCE_TOKEN")
except admesh.registry.RegistryNotFoundError:
    print("Mesh not found in registry")
except admesh.registry.RegistryUnavailableError:
    print("Registry API unavailable")
```

## Migration from admesh.domains

The hardcoded test domains stay available:

```python
import admesh.domains

# Legacy access
domain_obj = admesh.domains.UNIT_SQUARE
# Convert to new format
from admesh.api import domain_from_sdf
domain = domain_from_sdf(domain_obj.fd, bbox=domain_obj.bbox)
```

New code should use the file-based or registry-based loaders.

## See Also

- Meshes and domains come through Valence.
- `admesh.api.Domain`: the Domain dataclass documentation.
- `admesh.triangulate()`: the main triangulation function.
