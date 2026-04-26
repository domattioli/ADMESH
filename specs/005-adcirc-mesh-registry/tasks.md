---
description: "Implementation tasks for ADCIRC Mesh Registry feature"
---

# Tasks: ADCIRC Mesh Registry

**Branch**: `005-adcirc-mesh-registry` | **Status**: Ready for Implementation
**Input**: Specification from `specs/005-adcirc-mesh-registry/spec.md` and plan from `specs/005-adcirc-mesh-registry/plan.md`

**Tests**: All user stories include test tasks (per Constitution Principle III, adapted for non-port feature). Write tests FIRST and ensure they FAIL before implementation.

**Organization**: Tasks grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions
- All tasks use `mesh_registry/` package path and `registry_data/` for manifest

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure for registry implementation inside ADMESH

- [ ] T001 Create project structure: `mesh_registry/`, `registry_data/`, `tests/fixtures/registry/`, `.github/workflows/` directories
- [ ] T002 Create `mesh_registry/__init__.py` with public API re-exports (find, Mesh, load_manifest, Registry exceptions)
- [ ] T003 [P] Add registry dependencies to `pyproject.toml`: pydantic v2, shapely v2, httpx, huggingface_hub, click, tomli-w, responses/respx for tests
- [ ] T004 [P] Create `.github/workflows/validate-pr.yml` stub for registry manifest validation CI
- [ ] T005 [P] Create `.github/workflows/publish-hf.yml` stub for release-tag publishing to HuggingFace
- [ ] T006 [P] Configure import-linter in CI to enforce cross-import ban (admesh ↔ mesh_registry forbidden)
- [ ] T007 Create `registry_data/manifest.toml` as empty seed file with `schema_version = "1.0"`
- [ ] T008 Create initial test fixtures directory: `tests/fixtures/registry/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core schema, validation, and manifest I/O infrastructure that all user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T009 [P] Implement Mesh entity model in `mesh_registry/schema.py` with pydantic v2: composite slug ID parsing, all 22 fields per spec, field validation
- [ ] T010 [P] Implement BoundingBox sub-model in `mesh_registry/schema.py` with antimeridian crossing support (min_lon, min_lat, max_lon, max_lat)
- [ ] T011 [P] Implement MeshOperation entity in `mesh_registry/schema.py` with OperationKind enum (refine_box, coarsen_box, add_island, remove_region, add_levee, splice, other)
- [ ] T012 [P] Implement MeshFeature controlled vocabulary in `mesh_registry/schema.py` (13 tags: open_ocean, inlet, estuary, tidal_flat, barrier_island, levee, breakwater, wetland, shipping_channel, river_outflow, bay, lagoon, reef)
- [ ] T013 [P] Implement License entity in `mesh_registry/schema.py` with 7 identifiers (public-domain, MIT, CC-BY-4.0, CC-BY-SA-4.0, CC0-1.0, proprietary, unknown) mapping to open-source/redistribution/attribution booleans
- [ ] T014 Implement Manifest model in `mesh_registry/schema.py` with invariant validation: unique IDs, no dangling derived_from refs, no DAG cycles, ≤1 authoritative per hash, tombstone consistency
- [ ] T015 [P] Implement TOML load in `mesh_registry/manifest.py`: load_manifest(path) → Manifest, handle single file or sharded dir (manifests/<namespace>.toml)
- [ ] T016 [P] Implement TOML write in `mesh_registry/manifest.py`: write_manifest(manifest, path) → None, format as array-of-tables per spec
- [ ] T017 Implement manifest-level invariant checker in `mesh_registry/manifest.py`: validate_invariants(manifest) → List[ValidationError]
- [ ] T018 [P] Create pydantic schema.json export in `mesh_registry/schema.py` for HF dataset card generation
- [ ] T019 [P] Create exception hierarchy in `mesh_registry/__init__.py`: RegistryError, ManifestNotFoundError, SchemaVersionError, ManifestValidationError, MeshNotFoundError, ContentHashMismatchError, LineageCycleError
- [ ] T020 [P] Create test fixtures in `tests/fixtures/registry/`: 3 seed TOML manifests (simple.toml, with_lineage.toml, with_deprecation.toml) with 2–5 entries each

**Checkpoint**: Foundation complete — schema models, TOML I/O, and invariant validation ready; user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Discover Meshes by Geographic Region and Features (Priority: P1) 🎯 MVP

**Goal**: Enable researchers to find meshes by spatial region, features, size, and license using a single query interface.

**Independent Test**: Can be tested by querying the registry with bounding box and feature filters and getting back matching mesh results, sorted by size.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T021 [P] [US1] Contract test for bbox overlap query in `tests/test_registry_query.py`: verify find(bbox=(-97, 25, -80, 30)) returns meshes overlapping that region
- [ ] T022 [P] [US1] Contract test for feature filtering in `tests/test_registry_query.py`: verify find(features=["levee", "breakwater"]) returns only tagged meshes
- [ ] T023 [P] [US1] Contract test for size filtering in `tests/test_registry_query.py`: verify find(max_size=10000) returns meshes with ≤10K triangles
- [ ] T024 [P] [US1] Contract test for license filtering in `tests/test_registry_query.py`: verify find(license="public-domain") excludes proprietary/unknown
- [ ] T025 [P] [US1] Integration test for sorting by size in `tests/test_registry_query.py`: verify results sorted by num_triangles ascending

### Implementation for User Story 1

- [ ] T026 Implement find() function in `mesh_registry/query.py`: signature find(bbox=..., features=..., min_size=..., max_size=..., license=..., namespace=..., include_deprecated=False, manifest=...) → List[Mesh]
- [ ] T027 [P] [US1] Implement bbox overlap detection in `mesh_registry/query.py` using shapely.box().intersects() for antimeridian-safe logic
- [ ] T028 [P] [US1] Implement feature filtering logic in `mesh_registry/query.py`: multi-select intersection
- [ ] T029 [P] [US1] Implement size range filtering in `mesh_registry/query.py`: min_size ≤ num_triangles ≤ max_size
- [ ] T030 [P] [US1] Implement license filtering in `mesh_registry/query.py` respecting license type restrictions
- [ ] T031 [US1] Implement result sorting by num_triangles in find() (ascending by default)
- [ ] T032 [US1] Implement query result caching strategy for repeated calls (depends on loaded manifest path)
- [ ] T033 [US1] Add validation for bbox coordinates (plausibility check: area > 1 km², longitude ≤ 180°)
- [ ] T034 [US1] Add logging for query execution (manifest path, filter counts, result count, latency)

**Checkpoint**: User Story 1 fully functional — researchers can discover meshes by region, features, size, and license; results testable independently

---

## Phase 4: User Story 2 - Track Mesh Lineage and Provenance (Priority: P1)

**Goal**: Enable researchers to trace mesh ancestry, see what operations were applied, and understand authoritative vs. derived versions.

**Independent Test**: Can be tested by tracing a derived mesh back to its parent and viewing the transformation operations in the registry.

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T035 [P] [US2] Contract test for lineage resolution in `tests/test_registry_manifest.py`: verify Mesh.lineage() returns chain of ancestors up to root
- [ ] T036 [P] [US2] Contract test for derived_from resolution in `tests/test_registry_manifest.py`: verify parent ID resolves to parent Mesh object (including deprecated parents)
- [ ] T037 [P] [US2] Contract test for DAG cycle detection in `tests/test_registry_manifest.py`: verify validation rejects cycles in derived_from graph
- [ ] T038 [P] [US2] Contract test for dangling reference detection in `tests/test_registry_manifest.py`: verify validation rejects derived_from pointing to non-existent mesh
- [ ] T039 [P] [US2] Integration test for provenance_history traversal in `tests/test_registry_manifest.py`: verify operations + timestamps accessible and in order

### Implementation for User Story 2

- [ ] T040 [US2] Implement Mesh.lineage() method in `mesh_registry/schema.py`: return list of ancestor Mesh objects in order from immediate parent to root
- [ ] T041 [P] [US2] Implement derived_from resolution in `mesh_registry/query.py`: resolve parent ID to parent Mesh object (handle deprecated parents)
- [ ] T042 [P] [US2] Implement DAG cycle detection in `mesh_registry/manifest.py`: algorithm to detect cycles in derived_from graph; raise LineageCycleError if found
- [ ] T043 [P] [US2] Implement dangling reference check in `mesh_registry/manifest.py`: verify every derived_from ID exists in manifest
- [ ] T044 [US2] Add provenance_history access via Mesh.operations() method: return list of MeshOperation objects in applied_date order
- [ ] T045 [US2] Implement operation parameter validation in MeshOperation: ensure parameter dict keys match OperationKind requirements
- [ ] T046 [US2] Add authoritative flag resolution in find(): when multiple meshes have same content_hash, identify authoritative by oldest created_date or explicit authoritative=true flag

**Checkpoint**: User Story 2 fully functional — lineage DAG is traversable, provenance is recorded and accessible, cycle protection in place

---

## Phase 5: User Story 3 - Submit New Meshes via Pull Request Workflow (Priority: P1)

**Goal**: Enable contributors to add meshes via GitHub PR with automated CI validation and human review.

**Independent Test**: Can be tested by submitting a PR with a new mesh entry, running CI validation, and confirming validation reports are generated.

### Tests for User Story 3 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T047 [P] [US3] Contract test for schema validation in `tests/test_registry_schema.py`: verify new mesh entry against Mesh model; collect all errors before exit
- [ ] T048 [P] [US3] Contract test for invariant checks in `tests/test_registry_manifest.py`: verify unique ID, no dangling refs, no cycles on new entry
- [ ] T049 [P] [US3] Contract test for hash verification in `tests/test_registry_validator.py`: verify content_hash matches downloaded file (small-file path <10 MB)
- [ ] T050 [P] [US3] Contract test for URL reachability warning in `tests/test_registry_validator.py`: verify HEAD request check and warn on 4xx/5xx
- [ ] T051 [P] [US3] Contract test for bbox plausibility check in `tests/test_registry_validator.py`: verify bbox area > 1 km² and longitude ≤ 180°
- [ ] T052 [P] [US3] Contract test for triangle-count plausibility in `tests/test_registry_validator.py`: verify 100 ≤ num_triangles ≤ 5×10⁷

### Implementation for User Story 3

- [ ] T053 Implement CLI validator in `mesh_registry/cli.py`: `mesh-registry validate manifest.toml` command
- [ ] T054 [P] [US3] Implement validator.validate_manifest() in `mesh_registry/validator.py`: run all schema + invariant + sanity checks, return structured errors/warnings
- [ ] T055 [P] [US3] Implement error formatter in `mesh_registry/validator.py`: JSON output with {errors: [...], warnings: [...], summary: "..."}
- [ ] T056 [P] [US3] Implement URL reachability check in `mesh_registry/validator.py`: HEAD request to source_url, warn on non-2xx (not error)
- [ ] T057 [P] [US3] Implement hash consistency check in `mesh_registry/validator.py`: for small files (<10 MB), download and verify content_hash; for large files, trust contributor
- [ ] T058 [P] [US3] Implement bbox plausibility check in `mesh_registry/validator.py`: area > 1 km², longitude span ≤ 180°
- [ ] T059 [P] [US3] Implement triangle-count plausibility check in `mesh_registry/validator.py`: warn if outside [100, 5×10⁷]
- [ ] T060 [US3] Implement validate-pr.yml workflow: on PR to manifest*.toml, run validator and post summary comment with error/warning list + diff
- [ ] T061 [US3] Implement diff generation in `mesh_registry/validator.py`: compare old/new manifest state, report Added/Modified/Removed entries
- [ ] T062 [US3] Create CONTRIBUTING.md walkthrough: fork, compute hash, add entry, validate locally, open PR, address feedback, merge
- [ ] T063 [US3] Add validation error codes to spec: SCHEMA_INVALID_FIELD, INVARIANT_DUPLICATE_ID, INVARIANT_DANGLING_REF, INVARIANT_LINEAGE_CYCLE, INVARIANT_MULTIPLE_AUTHORITATIVE, INVARIANT_TOMBSTONE_INCOMPLETE, SCHEMA_VERSION_INCOMPATIBLE, SANITY_URL_UNREACHABLE, SANITY_HASH_MISMATCH, SANITY_BBOX_DEGENERATE, SANITY_TRIANGLE_COUNT_OUTLIER

**Checkpoint**: User Story 3 fully functional — contributors can submit PRs, CI validates automatically, human review enabled via GitHub

---

## Phase 6: User Story 4 - Programmatically Query Registry from Downstream Tools (Priority: P2)

**Goal**: Enable downstream Python tools to programmatically find and load meshes for automation and integration.

**Independent Test**: Can be tested by importing the Python package, querying, and confirming Mesh.load() returns a file path.

### Tests for User Story 4 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T064 [P] [US4] Integration test for find() in `tests/test_registry_query.py`: import adcirc_mesh_registry, call find(...), verify List[Mesh] return type
- [ ] T065 [P] [US4] Integration test for Mesh.load() in `tests/test_registry_loader.py`: verify cache location, hash validation, and file availability
- [ ] T066 [P] [US4] Integration test for offline mode in `tests/test_registry_loader.py`: verify manifest=path kwarg allows local-only operation
- [ ] T067 [P] [US4] Integration test for cache hit in `tests/test_registry_loader.py`: verify repeated load() uses cached file without re-download
- [ ] T068 [P] [US4] Integration test for Mesh.lineage() in `tests/test_registry_manifest.py`: verify callable on loaded Mesh objects

### Implementation for User Story 4

- [ ] T069 [P] [US4] Implement load_manifest() function in `mesh_registry/loader.py`: auto-fetch from HuggingFace Datasets or load from local path, return Manifest
- [ ] T070 [P] [US4] Implement manifest auto-discovery in `mesh_registry/loader.py`: fetch from `huggingface.co/datasets/adcirc-meshes/manifest.parquet` (or configured slug)
- [ ] T071 [US4] Implement Mesh.load() method in `mesh_registry/schema.py`: download from source_url (or HF mirror if mirror_eligible), validate content_hash, cache to $XDG_CACHE_HOME
- [ ] T072 [P] [US4] Implement cache strategy in `mesh_registry/loader.py`: XDG_CACHE_HOME/adcirc-mesh-registry/, per-mesh subdirs by namespace/name@version
- [ ] T073 [P] [US4] Implement content_hash validation on load in `mesh_registry/loader.py`: verify downloaded file hash on every load, raise ContentHashMismatchError if mismatch
- [ ] T074 [P] [US4] Implement fallback to source_url in `mesh_registry/loader.py`: if HF mirror unavailable, attempt source_url download with warning
- [ ] T075 [US4] Implement Mesh.to_fort14() method in `mesh_registry/schema.py`: return path to loaded mesh file (no conversion; assumes fort.14 format)
- [ ] T076 [US4] Add optional manifest kwarg to find(): allow offline use by passing local manifest path
- [ ] T077 [US4] Add httpx async support in `mesh_registry/loader.py`: async_load() for bulk downloads in downstream tools

**Checkpoint**: User Story 4 fully functional — Python package API exposed, meshes loadable and cacheable, programmatic query enabled for automation

---

## Phase 7: User Story 5 - Resolve License and Attribution Issues (Priority: P2)

**Goal**: Make license information clear and queryable, reducing compliance risk and enabling confident reuse.

**Independent Test**: Can be tested by querying meshes and confirming license field is populated and queryable.

### Tests for User Story 5 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T078 [P] [US5] Contract test for license field presence in `tests/test_registry_schema.py`: verify every Mesh entry has license from predefined set or "unknown"
- [ ] T079 [P] [US5] Contract test for license filtering in `tests/test_registry_query.py`: verify find(license=<type>) returns only matching entries
- [ ] T080 [P] [US5] Contract test for mirror_eligible derivation in `tests/test_registry_schema.py`: verify derived from license (true for public/open, false for proprietary/unknown)
- [ ] T081 [P] [US5] Integration test for license metadata in dataset card in `tests/test_registry_publisher.py`: verify license breakdown in HF card

### Implementation for User Story 5

- [ ] T082 [P] [US5] Implement License enum in `mesh_registry/schema.py` with 7 identifiers (public-domain, MIT, CC-BY-4.0, CC-BY-SA-4.0, CC0-1.0, proprietary, unknown)
- [ ] T083 [P] [US5] Add license metadata fields to License entity: full_name, is_open_source, allows_redistribution, attribution_required
- [ ] T084 [P] [US5] Implement mirror_eligible property on Mesh: derived from license (true for public/open, false for proprietary/unknown)
- [ ] T085 [P] [US5] Implement license filtering in find() (already in US1 query.py, but verify license logic)
- [ ] T086 [P] [US5] Add license breakdown to HF dataset card: count meshes per license, highlight redistributable vs. link-only
- [ ] T087 [US5] Add citation block to dataset card: BibTeX referencing GitHub repo + tag
- [ ] T088 [US5] Add license disclaimer to quickstart.md: explain mirror vs. link-only, attribution requirements, unknown license handling

**Checkpoint**: User Story 5 fully functional — license information clear and queryable, dataset card includes license metadata, compliance risk reduced

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Finishing touches, documentation, workflow automation, and seed data

- [ ] T089 [P] Implement CLI publish command in `mesh_registry/cli.py`: `mesh-registry publish --hf-token=...` for local ops use
- [ ] T090 [P] Implement publisher in `mesh_registry/publisher.py`: HuggingFace Datasets mirroring logic (file upload, tombstone cleanup, Parquet generation)
- [ ] T091 [P] Implement publish-hf.yml workflow: on release tag, run publisher, atomic commit to HF dataset
- [ ] T092 [P] Implement Parquet sidecar generation in `mesh_registry/publisher.py`: flatten Mesh objects to Parquet schema (bbox → 4 columns, features → list<string>, provenance_history → JSON string)
- [ ] T093 [P] Implement dataset card Jinja template in `mesh_registry/templates/hf_card.md.j2`: mesh count, license breakdown, geographic coverage, citation, schema reference, quickstart code
- [ ] T094 [P] Implement mesh file mirroring in `mesh_registry/publisher.py`: for mirror_eligible=True, download from source_url and upload to HF data/<namespace>/<name>/<version>.fort.14
- [ ] T095 [P] Implement tombstone cleanup in `mesh_registry/publisher.py`: for review_state=deprecated, delete file from HF mirror (keep metadata)
- [ ] T096 [P] Implement idempotent publish in `mesh_registry/publisher.py`: re-uploading same files is no-op; use SHA-based content addressing
- [ ] T097 [P] Implement HF token management: GitHub repo secret for `HF_TOKEN`, token scope scoped to single dataset repo
- [ ] T098 [P] Implement backoff strategy in `mesh_registry/publisher.py`: exponential backoff (2s, 4s, 8s, 16s) on rate limits; abort after 4 retries
- [ ] T099 [P] Add determinism enforcement to validator output: no time-of-day, hostname, or random ordering dependencies
- [ ] T100 [P] Create `docs/registry/CONTRIBUTING.md`: PR-based submission walkthrough (fork, hash, template, validate, PR, review, merge)
- [ ] T101 [P] Create `docs/registry/README.md`: Promoted quickstart.md; researcher, contributor, and maintainer sections
- [ ] T102 [P] Validate quickstart.md examples: run code snippets against fixture manifests; confirm researcher, contributor, maintainer workflows work end-to-end
- [ ] T103 [P] Seed registry with 5 initial meshes in `registry_data/manifest.toml`: NOAA HSOFS, USACE Galveston, academic refinement examples, with diverse licenses and features
- [ ] T104 [P] Create `tests/fixtures/registry/golden-seed-manifest.toml`: reference 5-mesh state for end-to-end validation
- [ ] T105 [P] Implement performance validation: confirm find() on 10K-entry manifest completes in <1 second (SC-009)
- [ ] T106 [P] Implement performance validation: confirm validator on 10K-entry manifest completes in <30 seconds (SC-004)
- [ ] T107 [P] Create GitHub release template for mesh registry: tag format `v1.2.0`, includes changelog, link to HF dataset
- [ ] T108 Verify import-linter rule enforcement in CI: confirm cross-import ban (admesh ↔ mesh_registry) is checked and fails on violation
- [ ] T109 Update ADMESH pyproject.toml: add `[project.optional-dependencies]` `registry = [...]` with all registry-only dependencies; baseline install doesn't pull them
- [ ] T110 Update ADMESH README.md: link to registry quickstart; mention registry as add-on ecosystem tool
- [ ] T111 Create migration plan document (deferred): `specs/005-adcirc-mesh-registry/MIGRATION.md` outline for future repo extraction (≥20 meshes or ≥3 external dependents)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — **BLOCKS all user stories**
- **User Stories (Phases 3–7)**: All depend on Foundational phase completion; can then proceed in parallel
  - US1 (Discovery): Can start immediately after Foundational
  - US2 (Lineage): Can start immediately after Foundational; benefits from US1 query.py code
  - US3 (PR workflow): Can start immediately after Foundational
  - US4 (Programmatic): Can start immediately after Foundational; depends on US1 find()
  - US5 (License): Can start immediately after Foundational; integrates into US1 query.py
- **Polish (Phase 8)**: Depends on all user stories; includes HF publisher and seed data

### Within User Stories

- Tests MUST be written and FAIL before implementation
- Schema/entity models before query/filtering
- Query implementation before loader
- All story implementation before CLI
- Story complete before moving to next priority

### Parallel Opportunities

- **Setup Phase (Phase 1)**: All [P] tasks can run in parallel (different files)
- **Foundational Phase (Phase 2)**: All [P] schema tasks (T009–T013) can run in parallel; T014–T020 follow sequentially
- **User Stories**: Once Foundational is complete, all 5 stories can be staffed in parallel:
  - Developer A: US1 Discovery (T021–T034)
  - Developer B: US2 Lineage (T035–T046)
  - Developer C: US3 PR Workflow (T047–T063)
  - Developer D: US4 Programmatic (T064–T077)
  - Developer E: US5 License (T078–T088)
- **Polish Phase (Phase 8)**: All [P] tasks can run in parallel (different files)

### Parallel Example: User Story 1 Discovery

```bash
# Tests (write first, ensure FAIL):
T021 T022 T023 T024 T025  # all [P], run together

# Implementation (models before services before endpoints):
T026  # find() function skeleton
T027 T028 T029 T030  # [P] filtering logic, run together
T031  # sorting
T032 T033 T034  # caching, validation, logging
```

---

## Implementation Strategy

### MVP First (User Stories 1–3 Only)

This is the recommended MVP scope for Phase 1 ship:

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 (Discovery) ← MVP core
4. Complete Phase 4: User Story 2 (Lineage) ← MVP supporting
5. Complete Phase 5: User Story 3 (PR Workflow) ← MVP intake
6. **STOP and VALIDATE**: Test all three stories independently, with 5 seed meshes
7. Create release tag `v0.1.0` and run publish-hf.yml
8. Demo to stakeholders; gather feedback

**Why this MVP?**: Discovery (US1) solves the core problem; Lineage (US2) prevents conflicts; PR Workflow (US3) enables growth. US4–US5 are nice-to-haves for initial release.

### Incremental Delivery (Full Feature)

1. MVP (US1–US3) as above
2. Add User Story 4 (Programmatic) → ecosystem integration unlocked
3. Add User Story 5 (License) → compliance risk reduced
4. Polish Phase (Phase 8) → documentation and seed data finalized

### Parallel Team Strategy

With multiple developers:

1. **Week 1**: Team completes Setup + Foundational together (Phases 1–2)
2. **Week 2–3**: Once Foundational is done:
   - Developer A: US1 Discovery (tests + implementation)
   - Developer B: US2 Lineage (tests + implementation)
   - Developer C: US3 PR Workflow (tests + CI validator)
   - Developer D: US4 Programmatic (when US1 query.py ready)
   - Developer E: US5 License (integrates into US1 filtering)
3. **Week 4**: Polish Phase (all [P] tasks parallel)
4. **Week 5**: Integration testing, seed data acquisition, release

---

## Total Task Summary

- **Total Tasks**: 111
- **Setup Phase**: 8 tasks
- **Foundational Phase**: 12 tasks
- **User Story 1** (Discovery): 14 tasks (5 tests + 9 implementation)
- **User Story 2** (Lineage): 12 tasks (5 tests + 7 implementation)
- **User Story 3** (PR Workflow): 14 tasks (6 tests + 8 implementation)
- **User Story 4** (Programmatic): 14 tasks (5 tests + 9 implementation)
- **User Story 5** (License): 11 tasks (4 tests + 7 implementation)
- **Polish Phase**: 22 tasks

**Tests**: 25 test tasks total (integrated per user story per TDD discipline)

**Parallel Opportunities**: ~40 tasks marked [P]; foundational and polish phases can achieve significant parallelization

**Critical Path**: Setup (1 day) → Foundational (3 days) → US1+US2+US3 (5 days) → Polish (2 days) ≈ **11 days for full feature at full staffing**

---

## Notes

- Each [P] task = different file or module, no blocking dependencies
- Each [Story] label maps task to specific user story for traceability
- Every user story is independently completable and testable
- Tests written FIRST, run FIRST, ensure FAIL before implementation
- Commit after each task or logical group (e.g., all filtering logic in one commit)
- Stop at any Phase checkpoint to validate story independently
- Schema version field in manifest.toml supports forward compatibility: new optional fields = MINOR version, new required fields = MAJOR version
- Avoid cross-story dependencies: each story should be independently mergeable
- Constitution Principle III (reference-test discipline) adapted for non-port: use golden-file fixtures instead of MATLAB reference
- Migration to separate `domattioli/adcirc-mesh-registry` repo planned but deferred (see plan.md Migration Notes)
