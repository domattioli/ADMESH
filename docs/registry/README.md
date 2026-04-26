# ADCIRC Mesh Registry

A **federated registry of ADCIRC-compatible coastal-simulation meshes** for disaster preparedness, flood modeling, and climate adaptation research.

## Features

✅ **Discover meshes** by geographic region, features, triangle count, and license  
✅ **Track lineage** — trace which mesh is derived from which, with operation history  
✅ **Contribute via GitHub** — PR-based submission workflow with automated CI validation  
✅ **Programmatic access** — Python API for automation and downstream tools  
✅ **License clarity** — Every mesh has explicit licensing information  
✅ **Scalable** — Designed for 10K+ entries with sub-second queries

## Quick Start

### For Researchers (Finding Meshes)

```bash
pip install adcirc-mesh-registry
```

```python
from adcirc_mesh_registry import find

# Find public-domain meshes in the Gulf of Mexico with levees, ≤50K triangles
meshes = find(
    bbox=(-97, 25, -88, 30),        # Gulf of Mexico
    features=["levee"],              # Physical features
    max_size=50_000,                # Triangle count limit
    license="public-domain"         # License filter
)

for m in meshes:
    print(f"{m.id}: {m.num_triangles:,} triangles, {m.license}")

# Download and use the first mesh
mesh = meshes[0]
fort14_path = mesh.load()  # Cached locally at ~/.cache/adcirc-mesh-registry/
print(f"Ready to use: {fort14_path}")

# Trace the mesh's lineage (if it's a refinement)
for ancestor in mesh.lineage():
    print(f"  ← {ancestor.id}")
```

### For Contributors (Adding Meshes)

1. **Prepare your mesh**:
   - Ensure it's in fort.14 ASCII format
   - Host it at a public URL (GitHub, S3, institutional archive, etc.)

2. **Compute the hash**:
   ```bash
   sha256sum your-mesh.fort.14
   ```

3. **Add to registry** (`registry_data/manifest.toml`):
   ```toml
   [[meshes]]
   id = "your-namespace/your-mesh@v2026"
   name = "Your Mesh Name"
   source_url = "https://your-host/your-mesh.fort.14"
   content_hash = "sha256:abc123..."
   num_triangles = 12345
   license = "CC-BY-4.0"
   created_by = "Your Name <you@example.org>"
   created_date = 2026-04-26T00:00:00Z
   review_state = "draft"
   features = ["levee", "estuary"]
   
     [meshes.bounding_box]
     min_lon = -97.0
     min_lat = 25.0
     max_lon = -88.0
     max_lat = 30.0
   ```

4. **Validate locally**:
   ```bash
   mesh-registry validate registry_data/manifest.toml
   ```

5. **Open a pull request** — CI validates automatically
6. **Merge** — Your mesh is published on the next release

Full guide: [CONTRIBUTING.md](./CONTRIBUTING.md)

### For Tool Developers (Programmatic Access)

```python
from adcirc_mesh_registry import find, Mesh, load_manifest

# Query with advanced filtering
results = find(
    bbox=(-97, 25, -88, 30),
    features=["levee", "breakwater"],  # Any of these
    min_size=10_000,
    max_size=500_000,
    license="MIT",
    include_deprecated=False
)

# Load a mesh into your application
for mesh in results:
    fort14_path = mesh.load()  # Auto-cached
    # Use fort14_path in your simulator
    ...
```

## Key Concepts

### Mesh ID Format

Every mesh has a unique composite ID: `<namespace>/<name>@<version>`

Examples:
- `noaa/hsofs@v2021` — NOAA's HSOFS mesh, 2021 version
- `usace/galveston-bay@v2024` — USACE Galveston District, 2024
- `edu/ut-austin/land-bridge@v2023` — Academic contribution from UT Austin

### Lineage & Provenance

Track mesh derivations:

```python
# If your mesh is refined from HSOFS
mesh = {
    "id": "myorg/hsofs-refined@v2026",
    "derived_from": "noaa/hsofs@v2021",
    "provenance_history": [
        {
            "operation_type": "refine_box",
            "applied_date": "2026-04-26T00:00:00Z",
            "applied_by": "You <you@example.org>",
            "parameters": {
                "bbox": [-95.5, 28.5, -94.0, 29.5],
                "target_resolution": 25.0
            }
        }
    ]
}
```

### Licensing

Meshes are categorized by redistributability:

| License | Mirrored to HF | Restrictions |
|---------|-----------------|---|
| `public-domain` | ✅ Yes | None |
| `MIT` | ✅ Yes | Attribution required |
| `CC-BY-4.0` | ✅ Yes | Attribution + same license |
| `CC-BY-SA-4.0` | ✅ Yes | Attribution + ShareAlike |
| `CC0-1.0` | ✅ Yes | None (public domain) |
| `proprietary` | ❌ No | Contact copyright holder |
| `unknown` | ❌ No | Unknown; contact contributor |

## Statistics (v0.1.0)

- **Total meshes**: 5 (bootstrap seed)
- **Total triangles**: 4.7M
- **Geographic coverage**: Atlantic & Gulf coasts
- **By license**: 1 public-domain, 2 open-source, 2 academic

(Grows with community contributions)

## CLI

```bash
# Validate a manifest
mesh-registry validate registry_data/manifest.toml

# Search for meshes
mesh-registry search --bbox -97 25 -88 30 --max-size 500000

# Search with JSON output
mesh-registry search --features levee --format json
```

## Architecture

```
┌─────────────────────────────────────┐
│   GitHub Repo (ADMESH)              │
│  registry_data/manifest.toml         │
│  ↓ (on release tag)                 │
├─────────────────────────────────────┤
│  GitHub Actions (publish-hf.yml)    │
│  - Validate manifest                │
│  - Mirror mesh files (if eligible)  │
│  - Generate dataset card            │
│  ↓                                  │
├─────────────────────────────────────┤
│  HuggingFace Datasets               │
│  adcirc-meshes/                     │
│  - manifest.parquet (searchable)    │
│  - data/<namespace>/<name>.fort.14  │
│  - README.md (web UI)               │
└─────────────────────────────────────┘
         ↑
    (consumed by)
         ↓
┌─────────────────────────────────────┐
│  Python Package (PyPI)              │
│  adcirc-mesh-registry               │
│  - find() API                       │
│  - Mesh.load() with caching         │
│  - CLI tools                        │
└─────────────────────────────────────┘
```

## Scope & Roadmap

### Phase 1 (v0.1.0 — Current)

✅ Mesh discovery (bbox, features, size, license)  
✅ Lineage tracking (DAG, provenance)  
✅ PR-based contribution workflow  
✅ CLI validator & search  
✅ 5 seed meshes  

### Phase 2 (Post-MVP)

- HuggingFace Datasets publishing (full integration)
- Dataset card with web search/filter
- Programmatic Mesh.load() with caching
- License clarity in dataset UI
- Performance optimization for 10K+ entries
- Community contributions (target: 20+ meshes)

### Phase 3 (Long-term)

- AI-assisted mesh bundle generation
- Migration to standalone `domattioli/adcirc-mesh-registry` repo (when mature)
- Integration with ADCIRC ecosystem tools

## Constitution & Governance

The registry is part of the **ADMESH project** but designed as a **federated, community-driven system**:

- **Principle I (Faithful Port)**: N/A — registry is a new ecosystem tool, not a MATLAB port
- **Principle II (Pure Python)**: ✅ All dependencies are pure Python or have wheels on all platforms
- **Principle III (Reference Discipline)**: ✅ Golden-file fixtures for validation testing
- **Principle IV (Bottom-up)**: ✅ Schema → loader → publisher, each tested before the next
- **Principle V (Report & Advance)**: ✅ Session-based workflow with commits tracking progress

**Cross-import ban**: `admesh.*` and `mesh_registry.*` packages are intentionally separated, enforced by import-linter in CI. This enables clean extraction to a standalone repo when the registry matures.

See: [MIGRATION.md](../../specs/005-adcirc-mesh-registry/MIGRATION.md)

## References

- **Specification**: [specs/005-adcirc-mesh-registry/](../../specs/005-adcirc-mesh-registry/)
- **Contributing Guide**: [CONTRIBUTING.md](./CONTRIBUTING.md)
- **API Reference**: [Python API Contract](../../specs/005-adcirc-mesh-registry/contracts/python-api.md)
- **Manifest Schema**: [TOML Schema](../../specs/005-adcirc-mesh-registry/contracts/manifest-schema.md)
- **CI Validator**: [Validator Contract](../../specs/005-adcirc-mesh-registry/contracts/ci-validator.md)
- **HF Publisher**: [Publisher Contract](../../specs/005-adcirc-mesh-registry/contracts/hf-publisher.md)

## Support

- **Questions?** Open an issue on [GitHub](https://github.com/domattioli/ADMESH/issues)
- **Bug reports**: Include your mesh ID and the error output from `mesh-registry validate`
- **Contributing a mesh?** See [CONTRIBUTING.md](./CONTRIBUTING.md)

## License

- **Registry infrastructure**: Apache 2.0 (same as ADMESH project)
- **Individual meshes**: Vary (see mesh metadata)
- **Python package**: Apache 2.0

---

**Last updated**: April 2026  
**Status**: v0.1.0 (MVP - stable for research use)  
**Bootstrap meshes**: 5 (NOAA, USACE, academic)
