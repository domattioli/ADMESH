# Quickstart: Gmsh `.msh` I/O

**Feature**: 008-gmsh-io-integration
**Date**: 2026-05-10

The new Gmsh I/O surface is symmetric with the existing fort.14 I/O. If you've used `read_fort14`/`write_fort14`, you already know how this works.

## Read a Gmsh-authored mesh

```python
import admesh

mesh = admesh.read_msh("path/to/my_mesh.msh")

print(mesh)  # Mesh(nodes=4321, elements=8530, boundary_segments=4, …)
print([seg.bc_type for seg in mesh.boundary_segments])
# [BoundaryType.OPEN, BoundaryType.MAINLAND, BoundaryType.ISLAND, BoundaryType.ISLAND]
```

The reader handles both Gmsh ASCII v2.2 and v4.1 transparently. The version is read from the file's `$MeshFormat` header — you do not pass a `version` argument.

## Write an admesh mesh as Gmsh

```python
import admesh

# Triangulate any of the canonical demo domains
domain = admesh.Domain.unit_square()
mesh = admesh.triangulate(domain)

# Write Gmsh v4.1 (default)
mesh.to_msh("out_v41.msh")

# Or write Gmsh v2.2 for older toolchains
mesh.to_msh("out_v22.msh", version="2.2")
```

The writer always emits `z = 0.0` for every node (admesh is 2D); bathymetry, if present, ships as a `$NodeData` view named `"bathymetry"` in ADCIRC sign convention.

Boundary labels ride on `$PhysicalNames`. The canonical mapping is:

| `BoundaryType` | Physical-group name |
|----------------|---------------------|
| `OPEN`           | `"open"`            |
| `MAINLAND`       | `"mainland"`        |
| `ISLAND`         | `"island"`          |
| `MAINLAND_FLUX`  | `"mainland_flux"`   |
| (numeric IBTYPE) | `"ibtype_<N>"`      |

The mapping is exposed as `admesh.PHYSICAL_GROUP_MAP` for inspection.

## Round-trip Gmsh ↔ ADCIRC fort.14

```python
import admesh

# Gmsh → admesh → fort.14
mesh = admesh.read_msh("input.msh")
mesh.to_fort14("output.14")

# fort.14 → admesh → Gmsh
mesh2 = admesh.read_fort14("output.14")
mesh2.to_msh("roundtrip.msh")

# The round-trip is structurally lossless for the 5 MVP domains
# (unit_square, L_shape, unit_disk, annulus, notched_rectangle) and
# preserves boundary labels including unmapped numeric IBTYPE codes.
```

## Common errors

```python
# Non-planar Gmsh mesh
admesh.read_msh("3d_mesh.msh")
# admesh.GmshParseError: non-planar mesh; node 42 has z=1.5 (line 137)

# Higher-order elements
admesh.read_msh("triangle6_mesh.msh")
# admesh.GmshParseError: higher-order element type 9 at line 891
# (v1 supports linear triangles only)

# Missing physical groups
admesh.read_msh("no_groups.msh")
# UserWarning: no $PhysicalNames block — falling back to single MAINLAND ring
# Returns: Mesh(...) with one BoundaryType.MAINLAND ring
```

## CLI fixture regeneration (dev only)

```bash
# From repo root:
make gmsh-fixtures

# Equivalent to:
for domain in unit_square L_shape unit_disk annulus notched_rectangle; do
    gmsh -2 -format msh22 tests/fixtures/gmsh/geo/${domain}.geo \
         -o tests/fixtures/gmsh/${domain}_v22.msh
    gmsh -2 -format msh41 tests/fixtures/gmsh/geo/${domain}.geo \
         -o tests/fixtures/gmsh/${domain}_v41.msh
done
```

Requires the Gmsh CLI binary on `PATH`. The `gmsh -check` test gate uses the same binary.

## What is intentionally **not** in v1

- Binary `.msh` (raise on read; never emit)
- Higher-order elements (`Triangle6`, `Quad9`, …)
- Mixed-element 2D meshes (triangle + quad)
- Periodic-mesh blocks
- CAD geometry import (`.brep`, `.step`)
- The `gmsh` PyPI package as a runtime dependency
- Streaming reader/writer for >10M-node meshes (design does not foreclose this; implementation is forward-compat)

Each of these is documented in `plan.md` and tracked for follow-up issues if user demand surfaces.
