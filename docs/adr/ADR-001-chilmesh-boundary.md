# ADR-001 — ADMESH ↔ CHILmesh boundary

| Field | Value |
|---|---|
| Status | Proposed |
| Date proposed | 2026-05-21 |
| Snapshot date (CHILmesh inferred surface) | 2026-05-21 |
| Spec | [spec 015 — chilmesh overlap analysis](../../specs/015-chilmesh-overlap-analysis/) |
| Issue | [#81 overlap with chilmesh](https://github.com/domattioli/ADMESH/issues/81) |
| Branch | `daily-maintenance` |

## Context

ADMESH is a Python mesh **generator**, ported from `01_ADMESH_Library` of `domattioli/QuADMesh-MATLAB`. CHILmesh is a same-author Python **mesh data structure + smoother** library, published to PyPI as `chilmesh`.

The two are conceptually adjacent — both touch unstructured 2D meshes, share concepts (nodes, elements, boundary segments, smoothing, quality), and the ADMESH ↔ CHILmesh round-trip is exercised by two tests in this repo (`tests/test_fort14_chilmesh_compat.py`, `tests/test_fort14_chilmesh_smoke.py`).

Until this ADR, the boundary between the two was informal: `CLAUDE.md` named CHILmesh as "downstream of ADMESH" but did not enumerate which ADMESH modules might rightfully belong on the CHILmesh side. Three open issues prompted the formalization:

- **#84** (max-valence for vertices) — touches `admesh/valence.py`, which is consumer-side by nature.
- **#41** (dimensional mapping for smoothing) — touches `admesh/quad_prep.py`, also consumer-side.
- **#9** (`admesh-segmenter` sibling proposal) — the precedent that some consumer-side functionality earns its own package.

Without a written boundary, every such issue would relitigate the question. This ADR settles it.

## Decision

The ADMESH public surface is classified into three roles:

- **gen (generator-side, ADMESH-owned):** modules that construct mesh topology/geometry from a `Domain`.
- **cons (consumer-side):** modules that take an existing mesh and inspect, modify, score, or extract sub-regions.
- **bdry (boundary):** the wire format (`fort.14`), the shared dataclass (`Mesh`), and the enum that names boundary types (`BoundaryType`).

### Disposition table

The audit in `specs/015-chilmesh-overlap-analysis/inventory.md` classified every public ADMESH module. For every `cons` module, the decision is:

| Module | Role | Disposition | Rationale |
|---|---|---|---|
| `admesh.api` (`Mesh`, `Domain`, `BoundarySegment`, `triangulate`) | bdry | **stay in ADMESH** | Generator produces the structure; CHILmesh consumes it via `import admesh` or fort.14 round-trip. No shared base class. |
| `admesh.boundary_types.BoundaryType` | bdry | **stay in ADMESH** | Wire format authority. Locked by spec 001 FR-022. |
| `admesh.fort14` | bdry | **stay in ADMESH, contract locked** | Spec 009 R4 + chilmesh-compat tests pin the contract. CHILmesh conforms to it. |
| `admesh.quad_prep.smooth_for_quadrangulation` | cons | **keep in ADMESH** | Runs *between* fresh-generation and CHILmesh-side tri2quad fusion. Ships as ADMESH's gift to downstream consumers, including users who never touch CHILmesh. |
| `admesh.quality.{mesh_quality, right_iso_quality}` | cons | **keep in ADMESH** | Coupled to release-readiness gate (spec 009 R4) and distmesh stopping criterion. Moving creates a circular dependency. |
| `admesh.valence.*` | cons | **keep in ADMESH; coordinate with #84** | Valence balancing is consumer-side, but #84 wants max-valence as a *generator-side* constraint. ADR records that `admesh.valence` stays for now; #84's design must thread the seam explicitly. |
| `admesh.viz.plot_mesh` | cons | **keep in ADMESH** | `[viz]` extra already gates matplotlib. Moving forces CHILmesh install for plotting — net negative. |
| All `admesh._stages.*` modules | gen | **stay in ADMESH** | Faithful ports of MATLAB; Constitution Principle I binds them here. |
| `admesh.loaders`, `admesh.registry`, `admesh.size_field` | gen-helper | **stay in ADMESH** | Pure generator-side. |

### Net result

**Zero `move-to-chilmesh` actions. Zero `extract-to-shared-lib` actions.** The audit finds no module that warrants moving. The boundary holds where it stands today; this ADR's value is in writing that down so the next issue doesn't relitigate it.

### Cross-repo invariants

1. **`fort.14` is the wire format.** Both repos read/write it; ADMESH owns the reference implementation.
2. **`admesh.Mesh` is the canonical dataclass.** CHILmesh consumes it; it does not duplicate it. No shared base class.
3. **`BoundaryType` enum is authoritative in ADMESH.** Any new boundary type goes here first.
4. **No silent overlap.** If a future change adds a smoother / quality / viz feature in either repo, the author must check this ADR and either justify staying on their side or open a follow-up issue.

## Consequences

**Enables:**
- Issue #84 (max-valence) has a clear seam to design against: generator-side constraint that uses `admesh.valence` as the consumer-side check.
- Issue #41 (dimensional mapping for smoothing) stays in ADMESH (`quad_prep` is on the ADMESH side).
- Issue #9 (segmenter sibling) precedent is reaffirmed: heavy consumer-side functionality earns its own package, but existing consumer-side modules with tight generator coupling stay home.

**Costs:**
- Maintainer discipline: every PR that adds a `cons`-flavored feature in ADMESH must justify why it doesn't go to CHILmesh. The ADR provides the rubric.
- Stale-snapshot risk: CHILmesh's public surface was inferred from docs on 2026-05-21. A future spec must reverify if the disposition table is ever cited as a tiebreaker.

**Forecloses:**
- Spontaneous module moves without an updated ADR.
- Adding a shared "mesh base class" extracted to a third package.
- Forking the `fort.14` format on either side.

## Follow-up

No follow-up issues are required for code work — the audit found nothing to move. The following actions remain:

- [ ] Issue #81 receives a closing comment linking this ADR. Maintainer reviews and either closes #81 or files a dispute issue.
- [ ] When issue #84 (max-valence) reaches design phase, its spec must cite this ADR and document how it handles the valence seam.
- [ ] On any future PR adding a `cons`-flavored module to ADMESH, reviewers cite this ADR.

## Snapshot reverification trigger

Update this ADR's snapshot date and re-run the inventory if any of the following happen:

- CHILmesh ships a major version that changes its public surface.
- ADMESH adds a new public `cons` module.
- A new cross-repo test joins `tests/test_fort14_chilmesh_*.py`.
- A maintainer disputes a `keep` row.
