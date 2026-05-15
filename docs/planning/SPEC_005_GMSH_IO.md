# Specification: Gmsh .msh I/O Integration (Feature 003)

**Issue**: #5  
**Status**: Specification phase  
**Severity**: medium  
**Type**: enhancement (post-v1)  
**Created**: 2026-05-14  

---

## Problem Statement

The v1 spec (`specs/001-pythonize-and-fort14-integration`) locks public I/O on ADCIRC `fort.14` format. User request (session 001) asked for **Gmsh `.msh` format** as an alternative input/output, since:

- Gmsh is a standard mesh generation tool with wide adoption in FEM communities
- `.msh` format models the same domain as `fort.14`: nodes + triangle elements + labeled boundary regions (physical groups ↔ IBTYPE codes)
- Bolting Gmsh onto spec-001 would break the quality gate; reserve as Feature 003

### Evidence

- User request: "maybe allow input from gmsh" (session 001 transcript, post Phase 3 commit `2e4aaf8`)
- Sibling I/O module: `admesh/fort14.py` has `read_fort14`, `write_fort14`, `Fort14ParseError` — mirror this shape for Gmsh
- Format adoption: Gmsh is maintained, widely supported in scientific/FEM communities (better long-term portability than legacy ADCIRC formats)

---

## Acceptance Criteria

- [ ] `read_msh(path) → Mesh` parses at least Gmsh ASCII v2.2 (widely used, backward-compatible)
- [ ] `write_msh(mesh, path)` produces valid `.msh` files that Gmsh v4.1+ can open without warnings
- [ ] Physical-group names → `BoundaryType` mapping is documented (e.g., "open" → OPEN, "island" → ISLAND, "mainland_flux" → MAINLAND_FLUX)
- [ ] Numeric physical tags (unmapped) round-trip as plain `int` (mirrors fort.14 IBTYPE behavior)
- [ ] Round-trip parity: Gmsh → admesh → fort.14 → admesh → Gmsh, **boundary labels survive both translations**
- [ ] Round-trip tests on 5 MVP domains (UNIT_SQUARE, L_SHAPE, U_SHAPE, SQUARE_WITH_HOLE, DOUGHNUT, and 1 real fixture if available)
- [ ] No regression on fort.14 I/O tests
- [ ] `admesh/__init__.py` re-exports `read_msh`, `write_msh`, `GmshParseError`
- [ ] Tests added/updated; `docs/PORTING_NOTES.md` updated with format-bridge decisions
- [ ] Optional `[gmsh]` extra in `pyproject.toml` if upstream `gmsh` Python package is needed (target: hand-parse, no external dep for reading)

---

## Files to Create/Modify

### New Files
- **`admesh/gmsh.py`** — Core I/O module
  - `read_msh(path: str | Path) → Mesh`
  - `write_msh(mesh: Mesh, path: str | Path) → None`
  - `GmshParseError` exception class
  - `_parse_msh2_nodes`, `_parse_msh2_elements`, `_parse_msh2_physical_names` (helpers)

- **`tests/test_gmsh_io.py`** — I/O tests
  - `test_read_msh_v2_basic` (parse minimal v2.2 file)
  - `test_write_msh_roundtrip` (write then re-read, assert consistency)
  - `test_gmsh_physical_groups_to_boundary_types` (name mapping)
  - `test_gmsh_fort14_roundtrip` (Gmsh → fort.14 → Gmsh, boundary labels survive)
  - `test_gmsh_all_mvp_domains` (5+ fixtures)

- **`tests/fixtures/gmsh/`** (new directory)
  - `square.msh` (minimal v2.2 file, hand-written for clarity)
  - `l_shape.msh`
  - `u_shape.msh` (if real fixture available)

- **`docs/GMSH_IO_DESIGN.md`** (design notes)
  - Physical-group ↔ BoundaryType mapping table
  - Format version support rationale (why v2.2, not v4.x)
  - Known limitations (e.g., only 2D triangles, not quads/tets)

### Modified Files
- **`admesh/api.py`** — add `Mesh.to_msh(path)` method
- **`admesh/__init__.py`** — re-export `read_msh`, `write_msh`, `GmshParseError`
- **`pyproject.toml`** — optional `[gmsh]` extra (only if upstream package needed; target: no)
- **`docs/PORTING_NOTES.md`** — add section on Gmsh format decisions
- **`CHANGELOG.md`** — note Feature 003 release (when v1.1 or later ships)

---

## Proposed Approach

### 1. Format Choice: Gmsh ASCII v2.2

**Rationale**:
- v2.2 is human-readable, backward-compatible, and widely documented
- v4.x adds more features but requires upstream `gmsh` Python package (~400 MB) for native writing
- **Target: hand-parse v2.2 to avoid external dependency for reading**; only pull in `gmsh` package if a future feature absolutely requires it (e.g., native Gmsh API mesh construction)

**Format structure** (simplified):
```msh
$MeshFormat
2.2 0 8
$EndMeshFormat
$PhysicalNames
<count>
<dim> <tag> "<name>"
...
$EndPhysicalNames
$Nodes
<count>
<id> <x> <y> <z>
...
$EndNodes
$Elements
<count>
<id> <type> <ntags> <phys_group> [<elem_group>] <node_ids...>
...
$EndElements
```

### 2. Physical Group ↔ BoundaryType Mapping

Create a **canonical mapping table** in `admesh/gmsh.py`:

| Gmsh Physical Group Name | `BoundaryType` | Notes |
|---|---|---|
| `"open"` | `OPEN` | Open boundary (radiation) |
| `"mainland"` | `MAINLAND` | Land/coast |
| `"island"` | `ISLAND` | Island |
| `"mainland_flux"` | `MAINLAND_FLUX` | Flux-type mainland BC |
| `"weir"` | `WEIR` | Internal weir/obstruction |
| `"internal"` | `INTERNAL` | Non-boundary (should not appear) |
| **numeric tag** (unmapped) | `<tag>` (int) | Preserve as integer, like unmapped IBTYPE |

**When reading `.msh`**: Walk `$PhysicalNames` section, build reverse lookup table. For each element on a boundary, look up physical group name and map to `BoundaryType`.

**When writing `.msh`**: For each `BoundarySegment` in `mesh.boundaries`, emit a corresponding `$PhysicalNames` entry with the boundary type's name.

### 3. Implementation Strategy

**Phase 1: Hand-parsed v2.2 reader** (no external deps)
- Tokenize the `.msh` file line-by-line
- Parse `$PhysicalNames` → build name↔tag reverse lookup
- Parse `$Nodes` → build node array
- Parse `$Elements`, filter for `type=2` (triangle) on boundary tags
- Construct `Mesh` object + `BoundarySegment` list

**Phase 2: Writer** (outputs v2.2, can be read by Gmsh 2.x and 4.x)
- Collect all boundary segments from `mesh.boundaries`
- Emit `$MeshFormat`, `$PhysicalNames` (one per boundary type), `$Nodes`, `$Elements`
- Ensure proper element type markers and tag assignments

**Phase 3: Round-trip tests**
- Gmsh → admesh: read, assert node/element counts, boundary labels
- admesh → Gmsh: write, parse with hand-written reader, assert fidelity
- admesh ↔ fort.14: fort14 → admesh (existing), admesh → gmsh → admesh, assert round-trip

### 4. Known Limitations & Out of Scope

- **2D only**: No 3D tetrahedral support (same as `fort.14` v1)
- **Triangles only**: No quad elements (can be added in Feature 004)
- **No nested physical groups**: Flat namespace only
- **No gmsh Python API integration yet**: Pure file I/O; if users need Gmsh API access, separate `admesh.gmsh_api` module later

---

## Design Decisions

### Why hand-parse instead of `gmsh` package?

| Approach | Pros | Cons |
|---|---|---|
| **Hand-parse (chosen)** | No ~400 MB dependency; lean; control over behavior | More code to maintain; only v2.2 initially |
| `gmsh` Python package | Native API; automatic format support | Heavy dep; license complexity; overkill for I/O |

The `[gmsh]` extra can be added later if advanced features (mesh surgery, parametric scripting) justify the dependency.

### Why v2.2 instead of v4.x?

- v2.2 is backward-compatible and widely used in legacy FEM tools
- v4.x adds little for 2D I/O (mostly 3D features)
- Hand-parsing v2.2 is ~100 lines; v4.x would require significant work or the external package

### Physical group name mapping: hardcoded or user-configurable?

**Chosen**: Hardcoded canonical table, but with a **user override hook**:

```python
def read_msh(path, physical_group_map=None):
    """
    physical_group_map: dict[str, BoundaryType] for overriding default mapping.
    If a physical group is not in the map and not in defaults, warn and treat as int.
    """
```

This allows users to bring custom naming conventions without bloating the core module.

---

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Format parsing bugs | Silent mesh corruption | Comprehensive round-trip tests; assert node/element counts |
| Physical group name collisions | Boundary label mismatch | Fixed mapping; document clearly; warn on unmapped groups |
| v2.2 format limitations (e.g., no gmsh4 extensions) | User confusion | Document in `GMSH_IO_DESIGN.md`; mention v4.x upgrade path |
| Gmsh tool compatibility | Files unreadable by Gmsh | Test write output with Gmsh 4.1+ (manual or CI) |
| Hand-parse maintenance | Code rot if format evolves | Gmsh v2.2 is frozen (2009); low risk; if v5+ emerges, reevaluate |

---

## Token Budget Estimate

**Specification**: Complete (this document)  
**Planning/Tasks**: Small (~500 tokens) — straightforward implementation  
**Implementation**: Small-Medium (~2000 tokens)
  - `gmsh.py`: ~150 lines
  - Tests: ~250 lines
  - Integration: ~30 lines (`api.py`, `__init__.py`)
  
**Total for Feature 003**: ~3000 tokens (small-to-medium feature)

---

## Success Criteria (Recap)

**Planning phase complete** when:
- Spec document (this file) is approved
- Task breakdown is created
- Design decisions are documented (especially physical-group mapping, v2.2 rationale)

**Feature ready to ship** when:
- Hand-parsed v2.2 reader works on 5+ MVP domains
- Writer produces Gmsh-readable output
- Round-trip Gmsh → admesh → fort.14 → admesh → Gmsh preserves boundary labels
- Tests cover all acceptance criteria
- `GMSH_IO_DESIGN.md` and `PORTING_NOTES.md` are updated

---

## Next Steps

1. **Review this spec** — design decisions, acceptance criteria, approach sound?
2. **Create task breakdown** — atomic tasks with dependencies (similar to PYPI_CLAIM_TASKS.md)
3. **Approve token budget** — 3000 tokens for full Feature 003 implementation
4. **Pick implementation order** — do Gmsh I/O before or after #10 (size-field fix)?
