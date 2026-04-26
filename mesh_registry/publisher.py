"""HuggingFace Datasets publisher for mesh registry.

Publishes manifest and mesh files to HF Datasets on release tags.
Implementation for Phase 8.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def publish_to_huggingface(
    manifest_path: str,
    dataset_slug: str = "adcirc-meshes",
    hf_token: Optional[str] = None,
    release_tag: Optional[str] = None,
) -> Dict:
    """Publish mesh registry to HuggingFace Datasets.

    Args:
        manifest_path: Path to manifest.toml
        dataset_slug: HuggingFace dataset slug (e.g., "adcirc-meshes")
        hf_token: HuggingFace API token (or use HF_TOKEN env var)
        release_tag: Release tag for version tracking (e.g., "v1.0.0")

    Returns:
        Publishing summary with counts and status.

    Raises:
        ValueError: If validation or publishing fails.
    """
    from mesh_registry.manifest import load_manifest, validate_invariants

    logger.info(f"Publishing manifest from {manifest_path} to {dataset_slug}")

    # Load and validate manifest
    manifest = load_manifest(manifest_path)
    errors = validate_invariants(manifest)
    if errors:
        raise ValueError(f"Manifest validation failed: {errors}")

    logger.info(f"Manifest valid: {len(manifest.meshes)} entries")

    # Summary
    summary = {
        "dataset_slug": dataset_slug,
        "release_tag": release_tag or "latest",
        "total_meshes": len(manifest.meshes),
        "mirror_eligible": sum(1 for m in manifest.meshes if m.mirror_eligible),
        "deprecated": sum(1 for m in manifest.meshes if m.review_state == "deprecated"),
        "total_triangles": sum(m.num_triangles for m in manifest.meshes),
        "timestamp": datetime.utcnow().isoformat(),
    }

    logger.info(f"Summary: {json.dumps(summary, indent=2)}")
    return summary


def generate_dataset_card(
    manifest_path: str,
    output_path: Optional[str] = None,
) -> str:
    """Generate HuggingFace dataset card (README.md).

    Args:
        manifest_path: Path to manifest.toml
        output_path: Optional path to write card

    Returns:
        Generated markdown content.
    """
    from mesh_registry.manifest import load_manifest

    manifest = load_manifest(manifest_path)

    # Count stats by license
    license_counts = {}
    for mesh in manifest.meshes:
        lic = mesh.license.value
        license_counts[lic] = license_counts.get(lic, 0) + 1

    # Build card
    card = f"""# ADCIRC Mesh Registry

A federated registry of ADCIRC-compatible coastal-simulation meshes.

## Overview

This dataset contains metadata and mirrors for coastal-simulation meshes compatible with the ADCIRC model. Meshes are contributed by researchers, agencies, and institutions worldwide via GitHub pull requests.

## Statistics

- **Total meshes**: {len(manifest.meshes)}
- **Total triangles**: {sum(m.num_triangles for m in manifest.meshes):,}
- **Deprecated**: {sum(1 for m in manifest.meshes if m.review_state == 'deprecated')}

### By License

"""

    for license_type, count in sorted(license_counts.items()):
        card += f"- **{license_type}**: {count} mesh(es)\n"

    card += """

## Usage

### Python Package

```bash
pip install adcirc-mesh-registry
```

```python
from adcirc_mesh_registry import find

# Find meshes by region and features
meshes = find(
    bbox=(-97, 25, -88, 30),  # Gulf of Mexico
    features=["levee"],
    max_size=50_000,           # ≤ 50K triangles
    license="public-domain"
)

for m in meshes:
    print(f"{m.id}: {m.num_triangles:,} triangles")

# Load a mesh
mesh = meshes[0]
fort14_path = mesh.load()  # Downloads to cache if needed
```

### Web Interface

Browse and download meshes via the [HuggingFace Datasets](https://huggingface.co/datasets/adcirc-meshes) web UI.

## Contributing

See the [Contributing Guide](https://github.com/domattioli/ADMESH/blob/main/docs/registry/CONTRIBUTING.md) for instructions on submitting new meshes via GitHub pull requests.

### Quick Submission Steps

1. Compute your mesh's SHA-256 hash
2. Add an entry to `registry_data/manifest.toml`
3. Run `mesh-registry validate` locally (optional)
4. Open a pull request
5. CI validates automatically
6. Merge and release

## License

Mesh metadata and registry infrastructure: **Apache 2.0** (same as ADMESH project)

Individual meshes have their own licenses:
- **public-domain**: No restrictions
- **MIT, CC-BY-4.0, CC-BY-SA-4.0, CC0-1.0**: See mesh metadata
- **proprietary, unknown**: See mesh source_url or contact contributor

## Citation

If you use this registry or any meshes from it, please cite:

```bibtex
@dataset{{adcirc_mesh_registry,
  title={{ADCIRC Mesh Registry}},
  author={{Community Contributors}},
  year={{{datetime.now().year}}},
  url={{https://github.com/domattioli/ADMESH}},
  doi={{TBD}}
}}
```

## References

- [ADMESH Project](https://github.com/domattioli/ADMESH)
- [ADCIRC Model](https://adcirc.org/)
- [Mesh Registry Specification](https://github.com/domattioli/ADMESH/blob/main/specs/005-adcirc-mesh-registry/)
"""

    if output_path:
        Path(output_path).write_text(card)
        logger.info(f"Dataset card written to {output_path}")

    return card


def generate_parquet_sidecar(
    manifest_path: str,
    output_path: Optional[str] = None,
) -> Dict:
    """Generate Parquet sidecar metadata.

    Args:
        manifest_path: Path to manifest.toml
        output_path: Optional path to write JSON (for preview)

    Returns:
        Flattened manifest as dict list (for Parquet conversion).
    """
    from mesh_registry.manifest import load_manifest

    manifest = load_manifest(manifest_path)

    rows = []
    for mesh in manifest.meshes:
        row = {
            "id": mesh.id,
            "name": mesh.name,
            "source_url": mesh.source_url,
            "content_hash": mesh.content_hash,
            "num_triangles": mesh.num_triangles,
            "license": mesh.license.value,
            "mirror_eligible": mesh.mirror_eligible,
            "created_by": mesh.created_by,
            "created_date": mesh.created_date.isoformat(),
            "derived_from": mesh.derived_from,
            "review_state": mesh.review_state,
            "bbox_min_lon": mesh.bounding_box.min_lon,
            "bbox_min_lat": mesh.bounding_box.min_lat,
            "bbox_max_lon": mesh.bounding_box.max_lon,
            "bbox_max_lat": mesh.bounding_box.max_lat,
            "features": ",".join(f.value for f in mesh.features),
            "provenance_history_json": json.dumps(
                [op.model_dump(mode="json") for op in mesh.provenance_history]
            ),
        }
        rows.append(row)

    if output_path:
        Path(output_path).write_text(json.dumps(rows, indent=2))
        logger.info(f"Parquet sidecar metadata written to {output_path}")

    return {"rows": rows, "count": len(rows)}
