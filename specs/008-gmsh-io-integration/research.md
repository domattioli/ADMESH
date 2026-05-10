# Research: Gmsh `.msh` I/O

**Feature**: 008-gmsh-io-integration
**Date**: 2026-05-10

## R1. Gmsh ASCII v2.2 vs v4.1 Grammar

**Decision**: Support both versions in the reader. Writer defaults to v4.1; v2.2 available via `version="2.2"`.

**v2.2 layout** (single global block per type):
```
$MeshFormat
2.2 0 8
$EndMeshFormat
$PhysicalNames
N
dim tag "name"
...
$EndPhysicalNames
$Nodes
N
tag x y z
...
$EndNodes
$Elements
N
tag type numTags tag1 tag2 ... node1 node2 ...
...
$EndElements
```

The first tag in `numTags` for a v2 element is the physical group; the second is the elementary entity. v1 uses tag 1 (physical) only.

**v4.1 layout** (entity-block organization):
```
$MeshFormat
4.1 0 8
$EndMeshFormat
$PhysicalNames
N
dim tag "name"
...
$EndPhysicalNames
$Entities
numPoints numCurves numSurfaces numVolumes
[per-entity blocks: tag, bbox, num_physical_tags, physical_tags..., (etc)]
$EndEntities
$Nodes
numEntityBlocks numNodes minNodeTag maxNodeTag
[per-entity block]:
  entityDim entityTag parametric numNodesInBlock
  tag1
  ...
  x1 y1 z1
  ...
$EndNodes
$Elements
numEntityBlocks numElements minElementTag maxElementTag
[per-entity block]:
  entityDim entityTag elementType numElementsInBlock
  tag node1 node2 ...
  ...
$EndElements
```

In v4, physical groups attach to **entities**, not directly to elements; the parser must build an `entity_tag → physical_tags` map from `$Entities` and then resolve elements via their containing entity.

**Implementation strategy**: Single internal AST `GmshFile` with version-tagged dispatch in two private helpers `_parse_v22(lines)` and `_parse_v41(lines)`. Both produce the same `GmshFile` object. Keeps each parser ≤200 SLOC; total ≤500 SLOC budget per SC-005.

**Citation**: Gmsh manual §10 "File formats" — http://gmsh.info/doc/texinfo/gmsh.html#File-formats (versions 2.2 and 4.1 sections).

## R2. Physical-Group ↔ Entity-Block Linkage

**Decision**: Resolve physical-group membership at parse time, stored on each `GmshElement.physical_tag`. Downstream code never reaches back into the entity table.

**v2 path**: Each element record carries its physical tag in field 4 (immediately after `numTags`). Direct read.

**v4 path**: Each element lives in an entity block whose header gives `(entityDim, entityTag, ...)`. The reader looks up `entityTag` in the pre-built `entity_to_physical_tags` map and assigns the **first** physical tag (Gmsh allows multiple, but our model is single-tag per element). Multi-physical-group elements emit a `UserWarning` documenting the dropped tags.

**Edge case**: An element whose entity has no physical-group association → `physical_tag = None`. For type-1 (line) elements, this means the segment is part of the unlabelled fallback ring (FR-012 path). For type-2 (triangle), this is fine — only boundary lines need physical tags.

## R3. Boundary Inference

**Decision**: Reuse the ring-walk + leftmost-turn-at-junctions heuristic introduced for fort.14 in commit `c7c6568` (issue #38/#39 fix). The algorithm has already proven robust on real-world ADCIRC meshes including WNAT (15 junction nodes, multi-ring closure).

**Algorithm** (per data-model.md):
1. Group lines by physical tag.
2. For each group: build adjacency map; pick a deterministic start node; walk to close.
3. Tag rings by `BoundaryType`; orient CCW outer / CW holes.
4. Reject open chains as parse errors.

**Known limitation**: If a single physical tag covers two disjoint loops (e.g., two separate islands tagged `"island"`), the walk produces two rings under the same tag. This is the **expected** Gmsh convention and round-trips correctly on the fort.14 side (where both rings get IBTYPE 11).

**Citation**: `admesh/api.py::_derive_boundary_segments` (commit `c7c6568`); reuse the `_pick_next` leftmost-turn helper directly from there if visibility allows, else copy with attribution.

## R4. `gmsh -check` Exit Semantics

**Decision**: Use `gmsh -check <path>` as the writer-validation gate; exit code 0 + zero `Warning:` lines on stderr = success.

**Behavior**: `gmsh -check` parses the file and validates topology. Exit code is 0 on success and 1 on any error. **Warnings** are printed to stderr prefixed `Warning:` but do not affect exit code. SC-002 tightens the gate to "zero warnings" because Gmsh emits warnings for legal-but-suspect files (e.g., missing physical groups), and we want to catch those during testing.

**CI integration**: Test marked `pytest.mark.skipif(not shutil.which("gmsh"))`. CI image installs `gmsh` via apt (`apt-get install -y gmsh`). Local-dev environments without Gmsh skip the test with a documented `xfail`.

**Citation**: Gmsh CLI reference — `gmsh -help`, "check" mode.

## R5. Z-Coordinate Flatness Rule

**Decision**: Drop `z` if `|z| < 1e-12`; raise `GmshParseError` otherwise.

**Rationale**: Double-precision text round-trip can introduce ~1e-15 noise on values that started as exact 0. A `1e-12` threshold is six orders of magnitude above that floor and well below any geographically meaningful elevation. The threshold is documented in `docs/PORTING_NOTES.md` and is **not** user-configurable in v1 (one fewer dimension for misuse).

**Alternative considered**: Auto-flatten any `z` to 0 with a warning. Rejected — silent dimension reduction is a footgun for users who accidentally feed a 3D mesh to admesh.

**Alternative considered**: Use `z` as bathymetry. Rejected — bathymetry has its own `$NodeData` channel (R7 below); reusing `z` would conflict and prevent meshes that legitimately have both (`z = 0` planar, bathymetry as separate field).

## R6. Optional Block Tolerance

**Decision**: Reader silently skips `$Periodic`, `$Entities`-not-needed-in-v2 (impossible — v2 has no Entities), `$NodeData` views other than `"bathymetry"`, `$ElementData`, `$ElementNodeData`, `$Comments`. Writer never emits any of these.

**Rationale**: A reader that errors on unknown blocks is brittle against file generators that add metadata. A writer that emits no extras keeps the round-trip predicate clean.

**Edge case**: A `$Periodic` block on an admesh-rejected mesh (we don't model periodicity) is parsed-and-discarded. If a user needs periodicity, that's a future feature; v1 does not actively support it.

## R7. `$NodeData` Bathymetry View

**Decision**: View name `"bathymetry"` (case-insensitive) is the well-known channel; ADCIRC sign convention (positive-down) on disk; sign-flipped to internal positive-up at the I/O boundary.

**Grammar** (v2 and v4 are similar enough to share):
```
$NodeData
1                          # numStringTags
"bathymetry"               # the view name
1                          # numRealTags
0.0                        # the time value
3                          # numIntegerTags
0                          # time-step index
1                          # numScalarComponents (must be 1 for v1)
N                          # numNodes
tag value
...
$EndNodeData
```

**Reader**: For each `$NodeData` block, peek at the first string tag. If it lowercases to `"bathymetry"`, capture values into `mesh.bathymetry = -values_array`. Else skip.

**Writer**: Emit when and only when `mesh.bathymetry is not None`. Always uses `numScalarComponents=1`, `time=0.0`, `step=0`. Writes `-mesh.bathymetry` (sign flip).

## R8. Existing Patterns to Mirror

**Decision**: Lift these patterns directly from `admesh/fort14.py`:

1. **Parse-error-with-line-number**: `Fort14ParseError(detail, line_number=L)` — verbatim shape.
2. **Index-conversion boundary**: One `tag - 1` site on read (in the node-block parser), one `tag + 1` site on write (in the element-block writer). No leakage.
3. **Sign-flip boundary**: One `-bathymetry` on read, one `-bathymetry` on write.
4. **Round-trip equality predicate**: Centralize in `tests/_round_trip_helpers.py` (new file in test scaffolding); both fort.14 and Gmsh round-trip tests use the same predicate.
5. **Streaming-capable design**: Reader works in a single forward pass over file lines. The current implementation collects lines into memory, but the function signature accepts a `path` (not a string blob), so swapping to line-by-line iteration is a non-breaking future change.

## R9. `gmsh` PyPI Package — Hard-Pass on v1

**Decision**: The `gmsh` PyPI package is *not* added as a hard or optional dependency in v1.

**Rationale**:
- ~400 MB install (FR-005 evidence; the issue body cites this).
- Pulls in compiled C/C++ via `manylinux` wheel — conflicts with Constitution Principle II ("Pure-Python First").
- All v1 functionality (read/write linear-triangle ASCII meshes) is achievable with hand-rolled parsing in <500 SLOC.

**Forward-compat**: A `[gmsh]` extra namespace is reserved in `pyproject.toml` (empty in v1) so that future features needing CAD geometry import or programmatic Gmsh model construction can opt-in without a breaking dependency change.

## R10. Test-Fixture Strategy

**Decision**: Generate fixtures via the Gmsh CLI from canonical `.geo` scripts checked into the repo.

**Layout**:
```
tests/fixtures/gmsh/
├── geo/
│   ├── unit_square.geo
│   ├── L_shape.geo
│   ├── unit_disk.geo
│   ├── annulus.geo
│   └── notched_rectangle.geo
├── unit_square_v22.msh
├── unit_square_v41.msh
├── ... (all 5 × 2 = 10 base fixtures)
├── nonplanar.msh           # hand-edited to break z-flatness
├── quad9.msh               # generated with `Mesh.ElementOrder = 2`
└── malformed_header.msh    # hand-edited to break $MeshFormat
```

The `.geo` source files are the canonical inputs; `.msh` fixtures are regenerated via a `Makefile` target (`make gmsh-fixtures`) that calls `gmsh -2 -format msh22 unit_square.geo -o unit_square_v22.msh` etc.

**Rationale**: Fixtures should be *generated* not committed-as-binary because (a) they're large (~kB each), (b) Gmsh format details may evolve and we want a single source of truth, (c) reviewers can inspect the `.geo` source instead of opaque `.msh` text.

**Trade-off**: This adds a dev-dependency on the Gmsh CLI for fixture regeneration. Acceptable because we already need it for the `gmsh -check` writer-validation gate (R4). Documented in `quickstart.md` and `tests/fixtures/gmsh/README.md`.
