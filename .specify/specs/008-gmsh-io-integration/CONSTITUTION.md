# Spec 008 Constitution — Gmsh .msh I/O Integration

**Scope**: Add `read_msh()`, `write_msh()`, `GmshParseError`, and `Mesh.to_msh()` to ADMESH. Hand-parse Gmsh ASCII v2 and v4 formats. Map physical groups to `BoundaryType` via a canonical table; preserve unmapped numeric codes losslessly. Mirror the fort.14 I/O module structure.  
**Spec Document**: `specs/008-gmsh-io-integration/spec.md`  
**Related Specs**: ↑ Spec 001 (Gmsh I/O mirrors fort.14 I/O module shape; `BoundaryType` enum shared) | → Future: Gmsh-as-mesh-generator input

## How This Constitution Relates to the Project Constitution

New I/O format, not a port. No MATLAB `readmsh.m` equivalent. Pre-approved deviations from Articles I and III (same status as fort.14 in Spec 001):

- **Article I** (Faithful Port) does not apply: Gmsh I/O is a new Python-only capability. The 13 faithful-port stage modules are not touched.
- **Article III** (Reference-Test Discipline) adapted: No MATLAB fixture. Round-trip test (admesh → Gmsh file → admesh, data preserved) is the ground truth.
- **Article II** (Pure-Python First) reinforced: Principle II (Zero-Dependency Parsing) below. No 400 MB `gmsh` Python package.

No conflicts with any other spec. Gmsh v2/v4 and fort.14 v55 coexist by design.

## Core Principles

### I. Format-Bridge Parity with Fort.14 I/O

`read_msh()` / `write_msh()` mirror `read_fort14()` / `write_fort14()` in module shape, error handling, and API conventions:
- `read_msh(path: str | Path) -> Mesh`
- `write_msh(mesh: Mesh, path: str | Path) -> None`
- `GmshParseError` raised with line number for malformed input
- `Mesh.to_msh(path)` convenience method
- Exported from `admesh.__init__` alongside fort.14 functions

**Why**: Parity reduces cognitive overhead. A user who knows fort.14 I/O should use Gmsh I/O with zero surprises.

### II. Zero-Dependency Format Parsing

Gmsh ASCII v2 and v4 must be hand-parsed using Python stdlib only (`re`, `io`, `pathlib`). No dependency on the `gmsh` Python package (400 MB, requires Gmsh installation). If a future feature genuinely requires the gmsh package, pull it in as `[gmsh]` optional extra only.

**Why**: The ADMESH goal is `pip install`-able without platform-specific toolchains. A 400 MB optional dependency is a footgun.

### III. Canonical Gmsh Format Support (ASCII Only)

- **v2 ASCII** (`.msh` with `$MeshFormat` 2.2 0 8): Full support.
- **v4 ASCII** (`.msh` with `$MeshFormat` 4.1 0 8): Full support.
- **Binary formats**: Explicitly deferred. Raise `NotImplementedError` with a pointer to the deferred feature.
- **Other versions**: Not supported. Raise `GmshParseError` with version info.

**Why**: ASCII formats are human-readable and cover 95%+ of real-world Gmsh outputs.

### IV. Physical Group ↔ BoundaryType Losslessness

Physical group names map to `BoundaryType` via a canonical table (case-insensitive):

| Gmsh physical name | BoundaryType |
|-------------------|--------------|
| `"open"`, `"ocean"` | OPEN (0) |
| `"mainland"`, `"coast"`, `"land"` | MAINLAND (1) |
| `"mainland_flux"`, `"river"` | MAINLAND_FLUX (20) |
| `"island"` | ISLAND (11) |

Unmapped names and unmapped numeric group tags are preserved as their numeric value (same as fort.14 IBTYPE losslessness in Spec 001 Principle II).

**Why**: Real Gmsh meshes use diverse physical group names. A mapping table covering only 4 names silently discards the rest.

## Domain-Specific Constraints

- **Format scope**: Gmsh ASCII v2 and v4 only. Triangular elements (`$Elements` type 2) primary. Quads flagged with warning.
- **Physical group mapping**: Canonical table in `admesh/gmsh.py::PHYSICAL_GROUP_MAP`. Extensible via `read_msh(custom_map={...})`.
- **Coordinate dimensions**: 2D meshes (z=0 or z ignored). 3D raises `GmshParseError` unless `project_2d=True` kwarg.
- **Round-trip parity**: admesh → Gmsh ASCII → admesh must preserve node coordinates within 1e-10, element connectivity exactly, physical group codes exactly.
- **No mandatory `gmsh` package**: `from admesh import read_msh` works without `gmsh` installed.

## Quality Gates & Workflow

**Definition of done**:

- [ ] `read_msh()`, `write_msh()`, `GmshParseError` in `admesh/gmsh.py`
- [ ] `Mesh.to_msh(path)` method exists
- [ ] Exported from `admesh.__init__`
- [ ] Gmsh v2 ASCII round-trip: nodes ± 1e-10, elements exact, physical groups exact
- [ ] Gmsh v4 ASCII round-trip: same as v2
- [ ] Physical group → `BoundaryType` mapping test (canonical table verified)
- [ ] Unmapped physical group name preserved as numeric code
- [ ] `GmshParseError` raised with line number for malformed input
- [ ] Gmsh binary input raises `NotImplementedError` (not silent failure)
- [ ] Cross-format round-trip: admesh → fort.14 → admesh → Gmsh → admesh, labels survive both
- [ ] `pytest tests/test_gmsh*.py -q` green
- [ ] No regression on fort.14 tests (Spec 001)
- [ ] `docs/PORTING_NOTES.md` entry for physical-group ↔ BoundaryType mapping decisions

**Versioning policy**:
- **MAJOR**: Breaking change to physical group mapping (removing canonical mappings)
- **MINOR**: Adding binary format support, new canonical physical group mappings, `custom_map` parameter
- **PATCH**: Bug fix, doc update, tolerance tweak

## Governance

**Amendment procedure**: PR against this file. If amendment adds mandatory gmsh-package dependency (overrides Principle II), it requires a main project CONSTITUTION.md Amendments log entry.

**Compliance review**: Every PR touching `admesh/gmsh.py` must run both v2 and v4 round-trip tests, verify the physical group mapping table, and confirm no `gmsh` package import in non-optional code paths.

## Amendments Log

### 2026-05-11 — v1.0.0 — Initial constitution

Synthesized from `spec.md`, `plan.md`, `data-model.md`. Principles I and IV mirror Spec 001's fort.14 structure. Principle II (zero-dependency) is new. Principle III (ASCII-only) is the scope boundary. No conflicts with any other spec.

---
**Version**: 1.0.0 | **Ratified**: 2026-05-11 | **Last Amended**: 2026-05-11
