# Public Python API Contract: Gmsh `.msh` I/O

**Feature**: 008-gmsh-io-integration
**Date**: 2026-05-10
**Mirrors**: `specs/001-pythonize-and-fort14-integration/contracts/python-api.md`

## Top-Level Surface

The following names are added to the `admesh` top-level namespace via `admesh/__init__.py`:

```python
from admesh.gmsh import (
    read_msh,
    write_msh,
    GmshParseError,
    PHYSICAL_GROUP_MAP,
)
```

`Mesh.to_msh(...)` is added as a method on the existing `Mesh` class (defined in `admesh/api.py`).

No existing public name is renamed, removed, or rebound.

## Function Signatures

### `read_msh`

```python
def read_msh(path: str | os.PathLike) -> Mesh:
    """Parse a Gmsh ASCII .msh file (v2.2 or v4.1) and return a Mesh.

    Parameters
    ----------
    path
        Filesystem path to a Gmsh ASCII .msh file.

    Returns
    -------
    Mesh
        A 2D triangular mesh with boundary segments resolved from
        $PhysicalNames groups (see PHYSICAL_GROUP_MAP for the canonical
        name→BoundaryType mapping). Bathymetry, if present as a $NodeData
        view named "bathymetry", is loaded with sign convention flipped to
        the internal positive-up representation.

    Raises
    ------
    GmshParseError
        On malformed input, unsupported version, binary mode, non-planar
        nodes (|z| >= 1e-12), or higher-order/unsupported element types.
    FileNotFoundError
        If `path` does not exist.

    Warnings
    --------
    UserWarning
        - When the file has no $PhysicalNames block (fallback: single
          MAINLAND ring).
        - When a physical-group name is not in PHYSICAL_GROUP_MAP (the
          numeric tag is preserved per FR-009).
        - When a ring's orientation is auto-corrected to satisfy the
          CCW-outer / CW-holes invariant.
    """
```

### `write_msh`

```python
def write_msh(
    mesh: Mesh,
    path: str | os.PathLike,
    *,
    version: str = "4.1",
) -> None:
    """Serialize a Mesh as a Gmsh ASCII .msh file.

    Parameters
    ----------
    mesh
        Mesh to serialize. Must be a 2D triangular mesh.
    path
        Output filesystem path. Existing files are overwritten.
    version
        Gmsh ASCII format version. One of "2.2" or "4.1". Default "4.1".

    Returns
    -------
    None

    Raises
    ------
    ValueError
        If `version` is not in {"2.2", "4.1"}.
    GmshParseError
        Reserved for future input-validation cases (e.g., non-triangular
        elements). v1 raises ValueError for these cases.

    Side Effects
    ------------
    Writes a UTF-8 ASCII file at `path`. The file is well-formed per the
    Gmsh manual for the requested version and passes `gmsh -check <path>`
    with zero warnings (validated in tests).
    """
```

### `Mesh.to_msh`

```python
class Mesh:
    # ... existing members from spec 001 ...

    def to_msh(
        self,
        path: str | os.PathLike,
        *,
        version: str = "4.1",
    ) -> None:
        """Alias for ``admesh.write_msh(self, path, version=version)``.

        See :func:`admesh.write_msh` for full semantics.
        """
```

### `GmshParseError`

```python
class GmshParseError(ValueError):
    """Raised by ``read_msh`` (and reserved for ``write_msh``) on parse failure.

    Attributes
    ----------
    line_number : int | None
        1-based line number in the source .msh file where the error was
        detected. None if the error is whole-file (e.g., binary mode).
    detail : str
        Human-readable description of the failure mode and what was
        expected.
    """

    line_number: int | None
    detail: str

    def __init__(self, detail: str, *, line_number: int | None = None) -> None: ...
```

Mirrors `Fort14ParseError` exactly in shape and conventions.

## Module Constant

### `PHYSICAL_GROUP_MAP`

```python
PHYSICAL_GROUP_MAP: dict[str, BoundaryType] = {
    "open":          BoundaryType.OPEN,
    "mainland":      BoundaryType.MAINLAND,
    "island":        BoundaryType.ISLAND,
    "mainland_flux": BoundaryType.MAINLAND_FLUX,
}
```

**Lookup rule**: case-insensitive (`name.lower() in PHYSICAL_GROUP_MAP`).
**Stability**: additions are non-breaking (older files with the now-mapped name read as numeric IBTYPE and continue to round-trip identically). Removals or rebindings are breaking and require a major-version bump per Constitution Article on public-API stability.

## Backward Compatibility

This feature is purely additive on the spec-001 surface:

- `Mesh`, `Domain`, `BoundarySegment`, `BoundaryType` are unchanged.
- `read_fort14`, `write_fort14`, `Fort14ParseError` are unchanged.
- `Mesh.to_fort14` is unchanged. `Mesh.to_msh` is added as a new method.
- The faithful-port surface (`admesh.distmesh.distmesh2d_admesh`, etc.) is unchanged.
- `import admesh` continues to succeed without the `gmsh` PyPI package installed (FR-005, SC-004). The `[gmsh]` extra namespace is reserved in `pyproject.toml` for future features but is empty in v1.

## Error-Path Summary

| Condition | Exception | Line number reported? |
|-----------|-----------|----------------------|
| File missing | `FileNotFoundError` | — |
| Binary `.msh` | `GmshParseError` | header line |
| Unsupported version (not 2.2 or 4.1) | `GmshParseError` | header line |
| Malformed `$MeshFormat` | `GmshParseError` | offending line |
| Non-planar node (`|z| ≥ 1e-12`) | `GmshParseError` | node-block line |
| Higher-order element type | `GmshParseError` | element-block line |
| Open boundary chain for a physical tag | `GmshParseError` | None (post-parse) |
| `version` arg not in `{"2.2", "4.1"}` | `ValueError` | — |

## Test-Layer Contract

Each function in this contract has at least one test in `tests/test_gmsh_*.py`:

- `read_msh` — `tests/test_gmsh_read.py` (≥6 tests across versions and edge cases)
- `write_msh` — `tests/test_gmsh_write.py` (≥4 tests including `gmsh -check` gate)
- `Mesh.to_msh` — covered transitively by `test_gmsh_write.py`
- `GmshParseError` — exercised by negative tests in `test_gmsh_read.py` (≥3 tests: non-planar, higher-order, malformed header)
- `PHYSICAL_GROUP_MAP` — covered by `test_gmsh_roundtrip.py` (each mapped name appears in at least one fixture)

Total new tests: ≥15 (per SC-006).
