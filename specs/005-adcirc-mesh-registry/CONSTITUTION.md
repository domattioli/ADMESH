# Spec 005 Constitution — ADCIRC Mesh Registry

**Scope**: Build a catalog of public ADCIRC/coastal-modeling test meshes with tracked metadata (source, license, citation, domain description). Provide a registry API for discovery and retrieval. Enable CHILmesh and other downstream projects to consume ADMESH output meshes via a standardized catalog.  
**Spec Document**: `specs/005-adcirc-mesh-registry/spec.md`  
**Related Specs**: ↑ Spec 001 (fort.14 I/O is the export format), Spec 002 (produces meshes that go into the registry) | ↓ Cross-repo: CHILmesh, MADMESHR

## How This Constitution Relates to the Project Constitution

This spec is **infrastructure**, not a port. No MATLAB source for a community mesh catalog. Pre-approved deviations from Articles I and III as "additive ecosystem infrastructure":

- **Article I** (Faithful Port) does not apply: No MATLAB equivalent. The 13 faithful-port stage modules are not touched.
- **Article III** (Reference-Test Discipline) adapted: No `.npz` MATLAB fixture. Testing via round-trip tests (registry entry → fort.14 → re-parse → metadata survives) and schema validation.

Project constitution's domain-correctness mandate is still honored: the registry stores meshes produced by the ADMESH pipeline; it doesn't change how they're generated.

## Core Principles

### I. Registry as Infrastructure

The registry is a catalog — not a generator. Its job is to make ADMESH-compatible meshes *discoverable* and *consumable*. The registry API (`fetch`, `list`, `query`, `register`) is the spec's domain. Mesh quality is governed by whatever spec produced the mesh.

**Why**: Conflating the registry with the generator would create circular dependencies and unclear ownership.

### II. Metadata Losslessness

Every mesh in the registry has metadata: source (URL or file path), license (SPDX identifier), citation (BibTeX/DOI), domain description (name, CRS, bbox, creation date). This metadata must survive round-trip:

- Registry entry → `admesh.read_fort14()` → `admesh.write_fort14()` → re-parse → metadata intact.
- Metadata stored in a versioned JSON schema (`catalog.json`). Schema changes trigger a spec amendment.

**Why**: A catalog without provenance is useless. Coastal modeling has strict requirements for data lineage.

### III. Cross-Project Compatibility

The registry must be consumable by CHILmesh, MADMESHR, and other downstream projects without taking a hard dependency on `admesh`. The catalog's public contract is:
- A versioned JSON schema (`catalog.json`)
- Downloadable fort.14 files
- A Python convenience API (`admesh.registry`) that is optional

**Why**: Forcing downstream projects to install `admesh` to read the registry creates install-graph entanglement.

## Domain-Specific Constraints

- **Metadata schema**: Versioned (v1.0.0). Required fields: `name`, `source_url`, `license`, `citation`, `domain_name`, `crs`, `bbox`, `n_nodes`, `n_elements`, `creation_date`, `checksum_sha256`.
- **License requirement**: Every entry must have an explicit SPDX license identifier. No "unknown" or "assumed public domain".
- **Citation format**: BibTeX or DOI required for published sources. Unpublished entries must state "unpublished" explicitly.
- **Format**: Fort.14 v55 (per Spec 001) only in the initial catalog.
- **Checksum**: SHA-256 of the fort.14 file stored in catalog entry. Integrity check on download.
- **No `admesh` install required for catalog access**: `catalog.json` parseable with stdlib `json`.

## Quality Gates & Workflow

**Definition of done** (v1.0.0 catalog):

- [ ] `catalog.json` schema defined and versioned (v1.0.0)
- [ ] At least 5 public ADCIRC meshes cataloged with complete metadata
- [ ] Round-trip test: catalog entry → `admesh.read_fort14()` → `admesh.write_fort14()` → re-parse, metadata survives
- [ ] Schema validation test: every catalog entry passes jsonschema validation
- [ ] `admesh.registry.list()` and `admesh.registry.fetch(name)` exist and work
- [ ] CHILmesh integration test (CHILmesh reads an ADMESH-cataloged fort.14 without error)
- [ ] Docs: guide for adding a new mesh to the catalog
- [ ] `pytest tests/test_registry*.py -q` green
- [ ] No regression on spec-001 or spec-002 tests

**Versioning policy**:
- **MAJOR**: Breaking change to `catalog.json` schema
- **MINOR**: Adding new optional fields, adding registry query methods
- **PATCH**: Bug fix, doc update, new catalog entries

## Governance

**Amendment procedure**: PR against this file. Schema changes MUST include a migration script. Cross-project impacts must be noted in the PR description.

**Compliance review**: Every PR adding/modifying catalog entries must run schema validation and checksum tests.

## Amendments Log

### 2026-05-11 — v1.0.0 — Initial constitution

Synthesized from `spec.md`, `plan.md`, `MIGRATED.md`. Codifies non-port deviation from Article I and metadata losslessness. Principle III (cross-project compat) is new — additive ecosystem governance.

---
**Version**: 1.0.0 | **Ratified**: 2026-05-11 | **Last Amended**: 2026-05-11
