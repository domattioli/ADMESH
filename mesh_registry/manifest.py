"""TOML manifest loading, writing, and validation for the registry.

Supports:
- Single manifest.toml file (for <5K entries)
- Sharded manifests/ directory (for ≥5K entries, one file per namespace)
- Invariant validation across merged manifests
"""

from pathlib import Path
from typing import Union, List, Optional, Dict, Any
import tomllib

try:
    import tomli_w
except ImportError:
    tomli_w = None

from mesh_registry.schema import Manifest, Mesh


def load_manifest(path: Union[str, Path]) -> Manifest:
    """Load manifest from file or sharded directory.

    Args:
        path: Path to manifest.toml (single file) or manifests/ directory (sharded).

    Returns:
        Manifest with all entries merged and validated.

    Raises:
        FileNotFoundError: If manifest not found.
        ValueError: If manifest is invalid.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")

    all_meshes = []

    if path.is_file():
        # Single manifest file
        if not path.name.endswith(".toml"):
            raise ValueError(f"Manifest file must be TOML: {path}")
        data = _load_toml_file(path)
        all_meshes.extend(_extract_meshes(data))

    elif path.is_dir():
        # Sharded directory (manifests/<namespace>.toml files)
        toml_files = sorted(path.glob("*.toml"))
        if not toml_files:
            raise ValueError(f"No .toml files found in {path}")
        for toml_file in toml_files:
            data = _load_toml_file(toml_file)
            all_meshes.extend(_extract_meshes(data))

    else:
        raise ValueError(f"Path must be file or directory: {path}")

    # Create merged manifest with all entries
    schema_version = "1.0"  # Default; could be extracted from first file if needed
    manifest = Manifest(schema_version=schema_version, meshes=all_meshes)

    return manifest


def write_manifest(manifest: Manifest, path: Union[str, Path]) -> None:
    """Write manifest to TOML file.

    Args:
        manifest: Manifest object to write.
        path: Path to output manifest.toml.

    Raises:
        ImportError: If tomli_w not installed.
        ValueError: If path is invalid.
    """
    if tomli_w is None:
        raise ImportError("tomli-w required for manifest writing: pip install tomli-w")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert manifest to TOML-serializable dict
    data = _manifest_to_dict(manifest)

    with open(path, "wb") as f:
        tomli_w.dump(data, f)


def validate_invariants(manifest: Manifest) -> List[str]:
    """Validate manifest-level invariants.

    Returns:
        List of error messages (empty if all valid).
    """
    errors = []

    # Unique IDs
    mesh_ids = [m.id for m in manifest.meshes]
    if len(mesh_ids) != len(set(mesh_ids)):
        errors.append("Duplicate mesh IDs found")

    # No dangling derived_from
    valid_ids = set(mesh_ids)
    for mesh in manifest.meshes:
        if mesh.derived_from and mesh.derived_from not in valid_ids:
            errors.append(f"Dangling derived_from in {mesh.id}: {mesh.derived_from}")

    # No cycles in DAG
    def has_cycle(mesh_id: str, visited: set, path: set) -> bool:
        if mesh_id in path:
            return True
        if mesh_id in visited:
            return False
        visited.add(mesh_id)
        path.add(mesh_id)

        mesh = next((m for m in manifest.meshes if m.id == mesh_id), None)
        if mesh and mesh.derived_from:
            if has_cycle(mesh.derived_from, visited, path):
                return True

        path.remove(mesh_id)
        return False

    visited = set()
    for mesh in manifest.meshes:
        if mesh.id not in visited and has_cycle(mesh.id, visited, set()):
            errors.append(f"Cycle detected in derived_from DAG from {mesh.id}")

    # At most one authoritative per content_hash
    hash_to_authoritative = {}
    for mesh in manifest.meshes:
        if mesh.authoritative:
            if mesh.content_hash in hash_to_authoritative:
                errors.append(
                    f"Multiple authoritative entries for hash {mesh.content_hash}: "
                    f"{hash_to_authoritative[mesh.content_hash]} and {mesh.id}"
                )
            else:
                hash_to_authoritative[mesh.content_hash] = mesh.id

    # Tombstone consistency
    for mesh in manifest.meshes:
        if mesh.review_state == "deprecated":
            if not mesh.deprecation_reason:
                errors.append(f"Missing deprecation_reason for deprecated mesh {mesh.id}")
            if not mesh.deprecated_date:
                errors.append(f"Missing deprecated_date for deprecated mesh {mesh.id}")

    return errors


# Private helpers


def _load_toml_file(path: Path) -> Dict[str, Any]:
    """Load single TOML file and return dict."""
    with open(path, "rb") as f:
        return tomllib.load(f)


def _extract_meshes(data: Dict[str, Any]) -> List[Mesh]:
    """Extract mesh entries from TOML data dict."""
    meshes = []
    if "meshes" in data:
        for mesh_data in data["meshes"]:
            # Convert enum strings to enum objects
            if "license" in mesh_data and isinstance(mesh_data["license"], str):
                from mesh_registry.schema import License
                mesh_data["license"] = License(mesh_data["license"])

            if "features" in mesh_data:
                from mesh_registry.schema import MeshFeature
                mesh_data["features"] = [
                    MeshFeature(f) if isinstance(f, str) else f for f in mesh_data["features"]
                ]

            # Parse nested BoundingBox
            if "bounding_box" in mesh_data:
                from mesh_registry.schema import BoundingBox
                mesh_data["bounding_box"] = BoundingBox(**mesh_data["bounding_box"])

            # Parse nested operations
            if "provenance_history" in mesh_data:
                from mesh_registry.schema import MeshOperation, OperationKind
                ops = []
                for op_data in mesh_data["provenance_history"]:
                    if "operation_type" in op_data and isinstance(op_data["operation_type"], str):
                        op_data["operation_type"] = OperationKind(op_data["operation_type"])
                    ops.append(MeshOperation(**op_data))
                mesh_data["provenance_history"] = ops

            mesh = Mesh(**mesh_data)
            meshes.append(mesh)

    return meshes


def _manifest_to_dict(manifest: Manifest) -> Dict[str, Any]:
    """Convert Manifest object to TOML-serializable dict."""
    data = {
        "schema_version": manifest.schema_version,
        "meshes": [],
    }

    for mesh in manifest.meshes:
        mesh_dict = mesh.model_dump(mode="python", exclude_none=True)

        # Convert enums to strings
        if "license" in mesh_dict:
            mesh_dict["license"] = mesh_dict["license"].value
        if "features" in mesh_dict:
            mesh_dict["features"] = [f.value for f in mesh_dict["features"]]

        # Convert BoundingBox to dict
        if "bounding_box" in mesh_dict and hasattr(mesh_dict["bounding_box"], "model_dump"):
            mesh_dict["bounding_box"] = mesh_dict["bounding_box"].model_dump()

        # Convert operations
        if "provenance_history" in mesh_dict:
            ops = []
            for op in mesh_dict["provenance_history"]:
                if hasattr(op, "model_dump"):
                    op_dict = op.model_dump(mode="python", exclude_none=True)
                else:
                    op_dict = op
                if "operation_type" in op_dict:
                    if hasattr(op_dict["operation_type"], "value"):
                        op_dict["operation_type"] = op_dict["operation_type"].value
                ops.append(op_dict)
            mesh_dict["provenance_history"] = ops

        data["meshes"].append(mesh_dict)

    return data
