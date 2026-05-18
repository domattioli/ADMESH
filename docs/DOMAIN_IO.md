# Domain I/O and Registry Integration

Guide for loading mesh domains from files and the ADMESH-Domains registry.

## Quick Start

### Load from File

```python
import admesh

# Load from TOML (ADMESH-Domains native format)
mesh = admesh.triangulate("my_domain.toml", h0=0.1)

# Load from JSON
mesh = admesh.triangulate("my_domain.json", h0=0.1)

# Extract boundary from existing mesh
mesh = admesh.triangulate("existing_mesh.14", h0=0.05)
```

### Load from Registry

```python
import admesh

# List available domains
domains = admesh.list_available_domains()
for mesh_id, desc in domains.items():
    print(f"{mesh_id}: {desc}")

# Load by mesh_id (auto-detects registry)
mesh = admesh.triangulate("noaa-hsofs-v20", h0=0.1)

# Or use explicit registry loader
domain = admesh.load_domain_from_registry("noaa-hsofs-v20")
mesh = admesh.triangulate(domain, h0=0.1)
```

## File Format Specifications

### TOML Format (Recommended)

Native format for ADMESH-Domains. Human-readable, widely supported.

**File: `domain.toml`**

```toml
[domain]
name = "noaa-hsofs-v20"
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
source_url = "https://github.com/domattioli/ADMESH-Domains"
```

**Loading:**
```python
domain = admesh.load_domain_from_toml("domain.toml")
mesh = admesh.triangulate(domain, h0=0.1)
```

### JSON Format

Universal, portable format. Identical structure to TOML without metadata section.

**File: `domain.json`**

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

**Loading:**
```python
domain = admesh.load_domain_from_json("domain.json")
mesh = admesh.triangulate(domain, h0=0.1)
```

### Fort.14 Format

Extract domain boundary from ADCIRC v55 fort.14 mesh files. Useful for re-triangulating at different resolutions, refining/coarsening, domain validation.

**Loading:**
```python
# Extract boundary from existing mesh
domain = admesh.load_domain_from_fort14("existing_mesh.14")

# Re-triangulate at coarser resolution
coarse_mesh = admesh.triangulate(domain, h0=0.5)

# Or at finer resolution
fine_mesh = admesh.triangulate(domain, h0=0.02)
```

**What gets extracted:**
- Outer boundary polygon from first land boundary segment
- Interior islands (holes) from additional segments
- Bounding box computed from node coordinates
- Corner vertices marked as fixed points

## Registry Integration

Requires `admesh-domains` package:

```bash
pip install admesh-domains
```

### Discovering Domains

```python
import admesh

# List all available mesh IDs
domains = admesh.list_available_domains()
print(f"Available meshes: {len(domains)}")

# Fetch domain metadata
domain, meta = admesh.load_domain_with_metadata("noaa-hsofs-v20")
print(f"Version: {meta.get('version')}")
print(f"Contributor: {meta.get('contributed_by')}")
print(f"License: {meta.get('license')}")
```

### Loading from Registry

```python
import admesh

# Method 1: Direct registry load
domain = admesh.load_domain_from_registry("noaa-hsofs-v20")
mesh = admesh.triangulate(domain, h0=0.1)

# Method 2: Auto-detect (string without path separators)
mesh = admesh.triangulate("noaa-hsofs-v20", h0=0.1)

# Method 3: With metadata
domain, meta = admesh.load_domain_with_metadata("noaa-hsofs-v20")
mesh = admesh.triangulate(domain, h0=0.1)
print(f"Mesh ID: {meta.get('mesh_id')}")
```

## Complete Example

```python
import admesh
import numpy as np

# Load domain from registry
domain = admesh.load_domain_from_registry("noaa-hsofs-v20")

# Triangulate with custom parameters
mesh = admesh.triangulate(
    domain,
    h0=0.15,  # Target edge length
    seed=42,  # Reproducible randomness
)

# Save the mesh
admesh.write_fort14(mesh, "output_mesh.14")

# Inspect mesh quality
print(f"Nodes: {mesh.n_nodes}")
print(f"Elements: {mesh.n_elements}")
print(f"Quality: {mesh.quality}")

# Re-triangulate boundary at finer resolution
finer_mesh = admesh.triangulate(domain, h0=0.05)
print(f"Finer mesh: {finer_mesh.n_nodes} nodes")
```

## Conventions

### Coordinate System
- **Coordinates**: (x, y) pairs, typically longitude/latitude for geographic domains
- **Indexing**: 0-based (Python convention, not MATLAB 1-based)
- **Bbox format**: (xmin, ymin, xmax, ymax)

### Signed Distance Function (SDF)
- **Negative**: Inside domain
- **Positive**: Outside domain
- **Zero**: On boundary
- Constructed from polygon rings using Shapely

### Fixed Points
- Pinned vertices the triangulator must preserve
- Useful for re-entrant corners, domain features
- Optional; omit if not needed

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
except ImportError:
    print("admesh-domains not installed")
except ValueError:
    print("Mesh not found in registry")
```

## Migration from admesh.domains

Old hardcoded test domains still available:

```python
import admesh.domains

# Legacy access
domain_obj = admesh.domains.UNIT_SQUARE
# Convert to new format
from admesh.api import domain_from_sdf
domain = domain_from_sdf(domain_obj.fd, bbox=domain_obj.bbox)
```

For new code, prefer file-based or registry-based loaders.

## See Also

- `ADMESH-Domains` repository: https://github.com/domattioli/ADMESH-Domains
- `admesh.api.Domain` — Domain dataclass documentation
- `admesh.triangulate()` — Main triangulation function
