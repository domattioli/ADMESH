# Spec 001 Constitution — Pythonic API Layer + Fort.14 I/O

**Scope**: Layer a Pythonic API over the faithful MATLAB port; implement ADCIRC fort.14 read/write; define chilmesh integration contract via fort.14 as the lingua franca.  
**Spec Document**: `specs/001-pythonize-and-fort14-integration/spec.md`  
**Related Specs**: ↑ None (foundational) | ↓ Spec 002 (consumes `triangulate()`), Spec 008 (Gmsh I/O parity)

## How This Constitution Relates to the Project Constitution

Refines Articles I–IV of `docs/governance/CONSTITUTION.md`:

- **Article I** (Faithful Port) → Spec Principle I (Faithful fort.14 Round-Trip): port discipline applies to I/O semantics, not just algorithm code.
- **Article III** (Reference-Test Discipline) → Spec Principle II: round-trip equality tests *are* the reference tests for I/O (no MATLAB `.npz` fixture possible for fort.14 serialization; round-trip is the ground truth).
- **Article IV** (Stage-by-Stage Bottom-Up) → Spec Principle III: boundaries extracted last, after nodes and elements, mirrors MATLAB's ordering.

New principle (Spec Principle IV) extends the project constitution's IBTYPE enum story: any numeric code not in `BoundaryType` must survive round-trip losslessly. This is additive — no conflict with Article I.

## Core Principles

### I. Faithful Fort.14 Round-Trip

Every node coordinate, element connectivity entry, and boundary-condition label that enters `write_fort14()` or `Mesh.to_fort14()` must be recoverable via `read_fort14()` within the file format's documented precision. There is no MATLAB `.npz` reference for this layer — the round-trip test *is* the spec.

**Scope**: ADCIRC fort.14 format version 55 only. No v51, no custom dialects, no binary extensions.

**Why**: fort.14 is the contract between ADMESH and every downstream consumer (chilmesh, ADCIRC, visualization tools). A lossy writer silently breaks every pipeline that reads our output.

### II. ADCIRC Code Losslessness

Any IBTYPE code present in a source fort.14 — including codes not in the `BoundaryType` enum (e.g., IBTYPE 22 = external barrier, 52 = weir) — must round-trip as its numeric value without data loss or warning suppression. Adding a new symbolic name later is a non-breaking change.

**Why**: Real coastal meshes use dozens of IBTYPE codes. If we only preserve the ~5 codes in our enum, we silently corrupt production meshes during round-trip.

### III. Boundary Semantics Precision

Boundary segments are ordered per-ring: outer boundary first, then hole boundaries in a deterministic order. Multiply-connected domains (annulus, domains with holes) must round-trip with rings correctly distinguished and ordered. The 1-based ↔ 0-based index conversion lives *only* in `admesh/fort14.py` — no internal code sees 1-based indices.

**Why**: CHILmesh downstream layers computation depends on boundary ordering. Misordering rings causes downstream flooding-model failures that are hard to trace back to the mesh generator.

### IV. Pythonic API as Public Surface

The `Mesh` dataclass with typed attributes (`.nodes`, `.elements`, `.boundaries`, `.quality`), `__repr__`, `.to_fort14()`, `.plot()` (optional) is the headline. MATLAB-mirror functions (`distmesh2d_admesh`, etc.) remain callable but are not first-class in docs or type stubs.

**Why**: The port must be pip-installable and usable without MATLAB knowledge. A thin Python API on top of the MATLAB-mirror preserves the port guarantee while serving a wider audience.

## Domain-Specific Constraints

- **Format**: ADCIRC fort.14 v55. No v51. No binary.
- **Elevation/Depth convention**: ADCIRC stores depth-below-datum (positive down). Internal arrays use elevation (positive up). Conversion applied exclusively in `admesh/fort14.py`. Round-trip must preserve the physical field exactly.
- **Index domain**: All internal arrays are 0-based. `read_fort14()` subtracts 1 on load; `write_fort14()` adds 1 on write. No leakage.
- **Fixed-precision text**: fort.14 stores coordinates as decimal text. Reading and re-writing must not accumulate drift past the file's stated precision (~8–12 significant digits).
- **Streaming API**: The reader/writer must not preclude streaming for large meshes (>10M nodes). v1 may buffer; the API must not foreclose a streaming implementation.
- **Optional dependencies**: matplotlib is optional (`[viz]` extra). No dependency on the 400 MB gmsh package.
- **Backward compatibility**: All MATLAB-mirror module-level functions (`admesh.distmesh.distmesh2d_admesh`, etc.) must continue to return identical numerical output after this spec lands.

## Quality Gates & Workflow

**Definition of done** (all must pass before merging spec 001 work):

- [ ] `read_fort14(path) -> Mesh` and `write_fort14(mesh, path)` exported from `admesh.__init__`
- [ ] `Mesh.to_fort14(path)` convenience method exists
- [ ] Round-trip equality test on all 5 MVP domains: nodes ± 1e-10, elements exact, boundary labels exact
- [ ] Round-trip on `tests/fixtures/fort14/adcirc_examples/` files — labels preserved, no IBTYPE code lost
- [ ] Edge cases tested: multiply-connected domains, paired-edge BC records (IBTYPE 3/4/13/24/25), ill-formed input raises `Fort14ParseError` with line number
- [ ] Depth ↔ elevation conversion verified: write then read returns original elevation values within 1e-10
- [ ] `pytest tests/ -q` green on `main`
- [ ] `docs/PORTING_NOTES.md` has entries for: elevation/depth flip, 1-based/0-based translation, IBTYPE code coverage
- [ ] `__repr__` shows node count, element count, quality metrics, boundary-condition breakdown (not raw arrays)

**Versioning policy**:
- **MAJOR**: Changing the fort.14 format version supported
- **MINOR**: Adding a new symbolic `BoundaryType` code, new `Mesh` attribute, new optional export format
- **PATCH**: Bug fix, doc update, tolerance adjustment

## Governance

**Amendment procedure**: PR against this file with version bump and rationale. Any amendment that adds a new format version or drops losslessness guarantees requires a main project CONSTITUTION.md Amendments log entry.

**Compliance review**: Every PR touching `admesh/fort14.py`, `admesh/api.py::Mesh`, or `admesh/__init__.py` must verify the Quality Gates checklist before merge.

**Conflict escalation**: If this spec's constraints conflict with a downstream spec (e.g., Spec 008), the conflict is resolved at the main project CONSTITUTION.md level.

## Amendments Log

### 2026-05-11 — v1.0.0 — Initial constitution

Synthesized from `spec.md`, `plan.md`, `data-model.md` clarifications (2026-04-24 session). Codifies the four core principles and adds explicit IBTYPE losslessness guarantee (Principle II) which was stated informally in spec.md edge-cases section.

No deviations from main project CONSTITUTION.md.

---
**Version**: 1.0.0 | **Ratified**: 2026-05-11 | **Last Amended**: 2026-05-11
