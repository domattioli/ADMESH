"""ADCIRC Mesh Registry — federated discovery and management for coastal-simulation meshes.

This package provides:
- `find()`: Query the registry by geographic region, features, license, and size
- `Mesh`: Object representation of a mesh with metadata and loading capability
- `load_manifest()`: Load a manifest from file or HuggingFace Datasets
- Exception hierarchy for error handling

Public API:
    find, Mesh, load_manifest, Registry exceptions
"""

from mesh_registry.schema import Mesh, BoundingBox, MeshOperation, MeshFeature, License, Manifest
from mesh_registry.manifest import load_manifest, write_manifest
from mesh_registry.query import find

# Exception hierarchy
class RegistryError(Exception):
    """Base exception for all registry errors."""
    pass

class ManifestNotFoundError(RegistryError):
    """Manifest file or dataset not found."""
    pass

class SchemaVersionError(RegistryError):
    """Manifest schema version incompatible with loader version."""
    pass

class ManifestValidationError(RegistryError):
    """Manifest failed validation (schema or invariants)."""
    pass

class MeshNotFoundError(RegistryError):
    """Mesh entry not found in manifest."""
    pass

class ContentHashMismatchError(RegistryError):
    """Downloaded file hash does not match manifest content_hash."""
    pass

class LineageCycleError(RegistryError):
    """Cycle detected in mesh derivation DAG."""
    pass

__all__ = [
    "find",
    "Mesh",
    "BoundingBox",
    "MeshOperation",
    "MeshFeature",
    "License",
    "Manifest",
    "load_manifest",
    "write_manifest",
    "RegistryError",
    "ManifestNotFoundError",
    "SchemaVersionError",
    "ManifestValidationError",
    "MeshNotFoundError",
    "ContentHashMismatchError",
    "LineageCycleError",
]

__version__ = "0.1.0"
