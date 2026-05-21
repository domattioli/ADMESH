# Spec 015 — Inventory

Snapshot date: 2026-05-21.

## A1 — ADMESH public module catalog

Classification: `gen` = generator-side, `cons` = consumer-side, `bdry` = boundary (lives on the wire).
Source: `admesh/__init__.py` re-exports + each module's docstring.

| Module | One-line purpose | Primary public symbols | Class |
|---|---|---|---|
| `admesh/api.py` | Public Pythonic API: `Mesh`, `Domain`, `BoundarySegment`, `triangulate()` entry point | `Mesh`, `Domain`, `BoundarySegment`, `triangulate` | **bdry** |
| `admesh/boundary_types.py` | Boundary-type enum (ADCIRC IBTYPE codes) | `BoundaryType` | **bdry** |
| `admesh/fort14.py` | ADCIRC v55 fort.14 reader/writer | `read_fort14`, `write_fort14`, `Fort14ParseError` | **bdry** |
| `admesh/loaders.py` | TOML / fort.14 / JSON Domain loaders | `load_domain_from_toml`, `load_domain_from_json`, `load_domain_from_fort14` | **gen** |
| `admesh/registry.py` | ADMESH-Domains 0.3.x registry integration | `load_domain_from_registry`, `list_available_domains`, `load_domain_with_metadata` | **gen** |
| `admesh/size_field.py` | Two-phase size-field composition (built-in + user terms) | `SizeFieldFn`, `compose_size_field` | **gen** |
| `admesh/quality.py` (shim → `_stages.quality`) | Per-element shape-quality metrics on an existing mesh | `mesh_quality`, `right_iso_quality` | **cons** |
| `admesh/quad_prep.py` | Pre-quadrangulation smoother — nudges tris toward right-isoceles for tri2quad fusion | `smooth_for_quadrangulation` | **cons** |
| `admesh/valence.py` | Valence balancing via edge flipping; mutates an existing mesh | `compute_valence`, `balance_valence_triangles`, `ValenceStats`, `BalanceConfig`, `BalanceResult`, `get_valence_report` | **cons** |
| `admesh/viz.py` | Optional matplotlib visualization of `Mesh` | `plot_mesh` (lazy matplotlib import) | **cons** |
| `admesh/boundary.py` (shim → `_stages.boundary`) | Boundary-segment derivation from interior triangulation | (re-export only) | **gen** |
| `admesh/distmesh.py` (shim → `_stages.distmesh`) | DistMesh PDE-driven point relaxation | (re-export only) | **gen** |
| `admesh/distance.py` (shim → `_stages.distance`) | SDF evaluation on a grid | (re-export only) | **gen** |
| `admesh/mesh_size.py` (shim → `_stages.mesh_size`) | Gradient-limited Eikonal smoother + `build_h` | (re-export only) | **gen** |
| `admesh/background_grid.py` (shim → `_stages.background_grid`) | Stage 02: construct uniform background grid | (re-export only) | **gen** |
| `admesh/curvature.py` (shim → `_stages.curvature`) | Curvature-driven size-field term | (re-export only) | **gen** |
| `admesh/medial_axis.py` (shim → `_stages.medial_axis`) | Medial-axis distance term | (re-export only) | **gen** |
| `admesh/bathymetry.py` (shim → `_stages.bathymetry`) | Bathymetry-driven term | (re-export only) | **gen** |
| `admesh/dominate_tide.py` (shim → `_stages.dominate_tide`) | Tidal-wavelength term | (re-export only) | **gen** |
| `admesh/in_polygon.py` (shim → `_stages.in_polygon`) | Point-in-polygon test | (re-export only) | **gen** |
| `admesh/inpaint.py` (shim → `_stages.inpaint`) | Grid inpainting for missing values | (re-export only) | **gen** |
| `admesh/routine.py` (shim → `_stages.routine`) | High-level orchestration of stages | (re-export only) | **gen** |
| `admesh/domains.py` (shim → `_stages.domains`) | Built-in demo domain factory | (re-export only) | **gen** |

**Summary counts:** 3 boundary, 14 generator-side, 4 consumer-side, 2 generator-helper (loaders/registry).

## A2 — CHILmesh inferred public surface

**Source:** `https://github.com/domattioli/CHILmesh` README + PyPI `chilmesh` page. Inferred from docs; not read from source.
**Snapshot date:** 2026-05-21.
**Inferred flag:** `true` for every row.

| CHILmesh surface | Inferred purpose | Class |
|---|---|---|
| `CHILmesh` mesh data structure | Tri/quad/mixed half-edge mesh container | **bdry-candidate** (shared structure) |
| `tri2quad` | Tri-to-quad fusion | **cons** |
| Smoother(s) (Laplacian / quality-driven) | Improve element quality on an existing mesh | **cons** |
| Quality metrics | Per-element scalar quality scores | **cons** |
| Mesh I/O (fort.14 or its own format) | Persist/load CHILmesh containers | **bdry** |
| Visualization | Render CHILmesh to matplotlib / pyvista | **cons** |

**Caveat:** This is a docs-inferred surface. If CHILmesh actually ships additional generator-side capability (e.g. its own background-grid builder or PDE solver), the disposition table in spec.md should be revisited.

## A3 — Cross-repo test seam

| Test file | What it pins | Imports CHILmesh? |
|---|---|---|
| `tests/test_fort14_chilmesh_compat.py` | Round-trip identity: ADMESH `write_fort14` → ADMESH `read_fort14` produces a `Mesh` byte-stable enough that CHILmesh-style consumers see no semantic drift | No (proxy test — self-consistency only) |
| `tests/test_fort14_chilmesh_smoke.py` | Smoke test that CHILmesh-flavored fort.14 inputs parse cleanly | No at module-import time; may shell-out conditionally |

**Contract:** `fort.14` is the locked wire format. Both tests live in ADMESH and verify ADMESH's side of the seam without requiring CHILmesh installed.

## Disposition preview (drafts for Phase C)

These are draft dispositions; final versions land in ADR-001 §Decision and spec.md acceptance criteria.

| Module | Draft disposition | Rationale draft |
|---|---|---|
| `quad_prep` | **keep** | Tight coupling to the generator: it runs as a smoothing post-pass on a *fresh* triangulation before tri2quad. The smoother is ADMESH's gift to CHILmesh, not CHILmesh's territory. Justification: it's positioned *between* generation and consumption, and it ships with ADMESH so users who never touch CHILmesh still benefit. |
| `quality` | **keep** | Quality metrics are used by ADMESH's release-readiness gate (spec 009 R4) and by the distmesh stopping criterion. Moving them creates a circular dep. CHILmesh may grow its own quality metrics, but they need not be the same ones. |
| `valence` | **keep, but coordinate with #84** | Valence balancing is consumer-side (mutates an existing mesh), but issue #84 (max-valence as a generator-side constraint) means the *concept* of valence is being pulled both ways. ADR records that `admesh.valence` stays for now; #84's design must thread that needle explicitly. |
| `viz` | **keep** | A `[viz]` extra in `pyproject.toml` already gates the optional matplotlib dep. Moving it to CHILmesh forces every ADMESH user who wants `plot_mesh` to also install CHILmesh — net negative. |
| `Mesh` dataclass (`api.py`) | **stays in ADMESH** | The canonical mesh data structure stays generator-side because the generator produces it. CHILmesh consumes via `admesh.Mesh` import or `fort.14` round-trip. ADR explicitly forecloses a "shared base class" extraction unless CHILmesh provides written motivation. |
| `fort.14` I/O | **stays in ADMESH, contract locked** | Locked by spec 009 R4 + the two cross-repo test files. CHILmesh's own fort.14 layer (if any) must conform to this contract; no fork. |

**Net effect:** Zero `move-to-chilmesh` actions in this round, zero `extract-to-shared-lib`. The decision is to **formalize the existing boundary** rather than redraw it. This is itself a valid outcome — the ADR documents that the audit found no overlap requiring code motion.

If the maintainer or a future ADMESH session disputes a `keep` row, that row gets reopened in a follow-up issue per Phase E rules.
