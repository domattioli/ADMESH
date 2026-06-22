# Data Model: Gmsh `.msh` I/O

**Feature**: 008-gmsh-io-integration
**Date**: 2026-05-10

## Scope

This document describes only the **internal** parsing/serialization entities that live inside `admesh/gmsh.py`. The public surface — `Mesh`, `Domain`, `BoundarySegment`, `BoundaryType` — is defined in `specs/001-pythonize-and-fort14-integration/data-model.md` and is not redefined here.

## Internal Entities

### `GmshFile`

The top-level in-memory representation of a parsed `.msh` artifact, used as a staging area before flattening into a `Mesh`. Internal-only; not exported.

| Field | Type | Notes |
|-------|------|-------|
| `version` | `Literal["2.2", "4.1"]` | From `$MeshFormat` header |
| `is_ascii` | `bool` | v1 supports True only; raise on binary |
| `nodes` | `dict[int, tuple[float, float, float]]` | 1-based tag → (x, y, z) — z preserved for flatness check then dropped |
| `elements` | `list[GmshElement]` | All elements; reader filters by type after parse |
| `physical_groups` | `dict[int, PhysicalGroup]` | tag → PhysicalGroup |
| `entities` | `dict[tuple[int, int], EntityRef] \| None` | (dim, tag) → EntityRef; v4 only, None for v2 |
| `node_data_views` | `list[NodeDataView]` | Optional per-node scalar fields |
| `source_path` | `pathlib.Path \| None` | For error messages |

**Lifecycle**: built up by `_GmshReader` during a single pass; consumed by `_to_admesh_mesh()` which projects to the public `Mesh`. After projection, the `GmshFile` is discarded.

### `PhysicalGroup`

A named collection of geometric entities. Drives `BoundaryType` resolution.

| Field | Type | Notes |
|-------|------|-------|
| `dim` | `int` | 0 (point), 1 (curve), 2 (surface). v1 attends to 1 (boundary segments). |
| `tag` | `int` | Unique-per-dim within the file; 1-based |
| `name` | `str \| None` | From `$PhysicalNames`. Lowercased on lookup against `PHYSICAL_GROUP_MAP`. |

**Resolution rule**:
1. If `name` is in `PHYSICAL_GROUP_MAP` (case-insensitive), use the mapped `BoundaryType`.
2. Else if `name` is `None`, use the numeric `tag` as the `BoundaryType` value (FR-009 lossless-numeric path).
3. Else (unknown name), use `tag` as the numeric IBTYPE and emit a `UserWarning` with the unmapped name.

### `GmshElement`

A typed connectivity record.

| Field | Type | Notes |
|-------|------|-------|
| `element_type` | `int` | Gmsh type code. v1 supports 1 (line), 2 (triangle). |
| `node_ids` | `tuple[int, ...]` | 1-based node tags from the file |
| `physical_tag` | `int \| None` | First tag in v2 element record; resolved from entity in v4 |
| `entity_tag` | `int \| None` | v4 only |

**Validation**:
- `element_type ∉ {1, 2}` → `GmshParseError("higher-order or unsupported element type N at line L")`.
- For type 2 (triangle), `len(node_ids) == 3` else parse error.
- For type 1 (line), `len(node_ids) == 2` else parse error.

### `EntityRef` (v4 only)

A reference to a Gmsh geometric entity, used to propagate physical-group membership to elements that live inside the entity's `$Elements` block.

| Field | Type | Notes |
|-------|------|-------|
| `dim` | `int` | 0/1/2/3 |
| `tag` | `int` | Entity id (1-based) |
| `physical_tags` | `tuple[int, ...]` | Physical groups this entity belongs to |

### `NodeDataView`

A scalar field over nodes.

| Field | Type | Notes |
|-------|------|-------|
| `name` | `str` | `"bathymetry"` (case-insensitive) is the only one wired in v1 |
| `num_components` | `int` | v1 supports 1 only |
| `step` | `int` | Time-step index; v1 uses 0 only |
| `values` | `np.ndarray[float64]` | Length = `numNodes`. ADCIRC sign convention on disk (positive-down). Reader applies sign flip to internal positive-up. |

## Module-Level Constants (Public)

### `PHYSICAL_GROUP_MAP`

```python
PHYSICAL_GROUP_MAP: dict[str, BoundaryType] = {
    "open":          BoundaryType.OPEN,
    "mainland":      BoundaryType.MAINLAND,
    "island":        BoundaryType.ISLAND,
    "mainland_flux": BoundaryType.MAINLAND_FLUX,
}
```

Lookup is case-insensitive (`name.lower() in PHYSICAL_GROUP_MAP`).
Adding a new mapping is non-breaking — older files with the now-mapped name read as numeric IBTYPE and continue to round-trip identically.

## Boundary-Inference Algorithm (Reader)

Given parsed `GmshElement`s of type 1 (lines), assemble ordered boundary rings:

1. **Group lines by physical tag.** `tag → list[(node_a, node_b)]`.
2. **For each group:**
   - Build adjacency map `node → list[neighbor_node]` (each line contributes two entries).
   - Find a starting node — preference: a node with degree 2 that lies on the convex hull (heuristic: smallest-x then smallest-y); fallback: any degree-2 node.
   - Walk the ring with **leftmost-turn at junctions** (the same heuristic introduced for fort.14 in commit `c7c6568`, issue #38/#39 fix). Track visited edges; stop when the walk returns to the start node.
   - If the walk fails to close, raise `GmshParseError("open boundary chain for physical tag T")`.
3. **Tag each ring** with the resolved `BoundaryType` (per `PhysicalGroup` resolution rule above).
4. **Orientation normalization.** The outer ring must be CCW; holes (rings whose centroid is contained in another ring) must be CW. If a ring's orientation conflicts with its containment, flip it and emit a `UserWarning("ring orientation auto-corrected")`.

**Invariant after this stage**: the resulting `list[BoundarySegment]` is identical in shape to the one produced by `read_fort14`, so downstream code paths in the pipeline are agnostic to the source format.

## Boundary Emission Algorithm (Writer)

Given a `Mesh` with `BoundarySegment`s, produce Gmsh line elements with physical tags:

1. **Reverse-resolve `BoundaryType` → physical-group name** via `PHYSICAL_GROUP_MAP` inverse. Names not in the map use a synthesized `f"ibtype_{int(bc_value)}"` fallback (round-trip stable per FR-009).
2. **Emit a `$PhysicalNames` block** listing each used `(dim=1, tag, name)` tuple. Tags are assigned in first-seen order starting from 1.
3. **Walk each `BoundarySegment`** and emit one type-1 line element per consecutive node pair, carrying the segment's physical tag.
4. **Multiply-connected domains**: holes are emitted as additional rings under the appropriate `ISLAND` physical tag (or the segment's resolved tag). The orientation rule (CCW outer / CW holes) is enforced on emission.

## Z-Coordinate Handling

Reader and writer agree on a strict 2D contract:

- **Reader**: For every node, if `|z| < 1e-12`, drop `z` and store the 2D coordinate. Else raise `GmshParseError("non-planar mesh; node N has z=V")`.
- **Writer**: Always emit `z = 0.0`. The third coordinate is **not** repurposed for bathymetry (FR-007 mandates a separate `$NodeData` view).

## Bathymetry Handling

- **On disk**: `$NodeData` view named `"bathymetry"` (case-insensitive). Sign convention: ADCIRC depth-below-datum, positive-down.
- **In-memory**: Per-node scalar field on `Mesh.bathymetry`. Sign convention: elevation, positive-up.
- **Reader**: `mesh.bathymetry = -view_values` if the view exists; `None` otherwise.
- **Writer**: emit view if `mesh.bathymetry is not None`; values written as `-mesh.bathymetry`. The sign flip is exclusively at the I/O boundary (FR-007).

## Index-Base Conversion

- **On disk**: Gmsh tags are 1-based (matching fort.14 and the ADCIRC convention).
- **In-memory**: 0-based arrays per the constitution.
- **Boundary**: Conversion happens once on read (`tag - 1 → array index`) and once on write (`array index + 1 → tag`). No 1-based tag ever leaks into a `Mesh` attribute (FR-006).

## Equality Predicate (Round-Trip Tests)

Two `Mesh` objects are considered equal for round-trip purposes when:

| Field | Equality |
|-------|----------|
| `mesh.nodes` | `np.allclose(a, b, atol=1e-9)` |
| `mesh.elements` | `np.array_equal(a, b)` (after row-canonicalization: sort by (min, mid, max) per-row) |
| `mesh.boundary_segments` | Same count; per-segment same `BoundaryType` (numeric value match — symbolic name not required); same node sequence after rotation/flip canonicalization |
| `mesh.bathymetry` | `np.allclose(a, b, atol=1e-9)` if both not None; both None permitted; one-None-one-not is a failure |

This predicate is shared with the fort.14 round-trip tests; reuse via a test helper in `tests/_round_trip_helpers.py` (created during Phase 2 task scaffolding).
