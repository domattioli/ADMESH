# Pipeline

End-to-end walkthrough: how a `Domain` becomes a triangle mesh and
ends up as a `fort.14` for ADCIRC. Each step is one stage module —
follow the link to the source if you want the algorithm detail.
Concept primer in [Concepts](Concepts.md). Module-level map in
[Architecture overview](Architecture-Overview.md).

---

## The 3-line happy path

Today's public entry points (`admesh/__init__.py`):

```python
import admesh

# Path A — analytical example domain
domain = admesh.domains.UNIT_DISK              # or UNIT_SQUARE / L_SHAPE / ANNULUS / NOTCHED_RECTANGLE
mesh   = admesh.triangulate(domain)
admesh.write_fort14(mesh, "out.14")

# Path B — load from a fort.14, re-mesh, write back
domain = admesh.load_domain_from_fort14("input.14")
mesh   = admesh.triangulate(domain, h_max=500.0)
admesh.write_fort14(mesh, "out.14")
```

Other public loaders: `load_domain_from_toml`, `load_domain_from_json`,
`load_domain_from_registry` (pulls from
[ADMESH-Domains](https://github.com/domattioli/ADMESH-Domains)).

A polygon-ring constructor (`domain_from_polygon([rings…])`) is
scoped as part of the spec-002 surface — see
[`docs/governance/PROJECT_PLAN.md`](https://github.com/domattioli/ADMESH/blob/main/docs/governance/PROJECT_PLAN.md)
for current wiring status.

Underneath, every call fans out into the stage pipeline below.

---

## Stage flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│   USER INPUT                                                             │
│   • analytical Domain (admesh.domains.UNIT_DISK, …)                      │
│   • OR load_domain_from_{fort14|toml|json|registry}                      │
│   • optional user_contribs=(bathy_fn, tide_fn, …)                        │
└──────────────────────────────┬───────────────────────────────────────────┘
                               │
                               ▼
              ┌──────────────────────────────┐
              │  Domain  (sdf + bbox + pfix) │   ←── two interchangeable types
              │  api.Domain or domains.Domain│       (see step 1 below)
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │  background_grid.py          │   ←── structured grid over bbox
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │  distance.py  (SDF)          │   ←── signed distance at every
              │                              │       grid point
              └──────────────┬───────────────┘
                             │
                             ▼
   ┌─────────────────────────┴─────────────────────────┐
   │                                                   │
   ▼                                                   ▼
┌──────────────────┐                       ┌──────────────────────────┐
│ curvature.py     │                       │ medial_axis.py            │
│ h_curvature(x)   │                       │ h_medial(x)               │
└────────┬─────────┘                       └────────┬─────────────────┘
         │                                          │
         │            ┌─────────────────────────────┤
         │            │                             │
         │  ┌─────────▼──────────┐    ┌─────────────▼──────────┐
         │  │ bathymetry.py       │    │ dominate_tide.py        │
         │  │ h_bathy(x)          │    │ h_tide(x)               │
         │  │ via user_contribs=  │    │ via user_contribs=      │
         │  └─────────┬──────────┘    └─────────────┬──────────┘
         │            │                             │
         └────────────┴─────────────┬───────────────┘
                                    │
                                    ▼
              ┌──────────────────────────────┐
              │ size_field.compose_size_field│   ←── elementwise min (default)
              │   + user_contribs            │       or caller-supplied combine
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │ mesh_size.build_h            │   ←── PDE relax + interp
              │ (Numba iterative solver)     │       to query points
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │ distmesh.distmesh2d_admesh   │   ←── force-based node motion
              │   seed → relax → reproject   │       + SDF reprojection
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │ boundary.enforce_boundary_   │   ←── BC enforcement,
              │   conditions                 │       polygon structure
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │ quality.py                   │   ←── shape-q per element
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │ api.Mesh dataclass           │
              │   (frozen, NumPy-backed)     │
              └──────────────┬───────────────┘
                             │
                             ▼
                ┌──────────────────────────┐
                │ fort14.write_fort14      │   ←── ADCIRC native format
                │   incl. paired-edge BCs  │       (IBTYPE 3, 4, 13, 24)
                └──────────────┬───────────┘
                               │
                               ▼
                       fort.14 → ADCIRC
```

---

## Step-by-step

### 1. Build a `Domain`

There are two `Domain` types in the codebase. They are interchangeable
at the `triangulate()` boundary:

| Type | Where | What it carries |
|---|---|---|
| `admesh.api.Domain` | [`admesh/api.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/api.py) | `sdf`, `bbox`, optional `pfix`, `pts`, `bc_segments` (spec-001/002 surface) |
| `admesh.domains.Domain` | [`admesh/domains.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/domains.py) | `name`, `fd`, `bbox`, `fixed_points`, `boundary_polygon` (faithful-port surface) |

Four construction paths:

| Path | How |
|---|---|
| Analytical example | `admesh.domains.UNIT_DISK` (also `UNIT_SQUARE`, `L_SHAPE`, `ANNULUS`, `NOTCHED_RECTANGLE`) |
| From a fort.14 | `admesh.load_domain_from_fort14("path.14")` |
| From TOML / JSON | `admesh.load_domain_from_toml("path.toml")` / `_from_json("path.json")` |
| From the registry | `admesh.load_domain_from_registry("wnat_test")` (needs `admesh-domains` installed) |
| From an existing mesh | `admesh.api.Domain.from_mesh(mesh)` — reverse-engineers the SDF from boundary rings; used for re-meshing |

Per-node bathymetry lives on the resulting `Mesh` (`Mesh.bathymetry`),
not on the `Domain` — turning on the bathymetry / tide size-field
contributions is a `compose_size_field` + `user_contribs=` concern,
not a `Domain` attribute.

### 2. Background grid + SDF

Internal step inside `triangulate()`. ADMESH lays a structured grid
over the domain's bounding box, computes the **signed distance** at
each grid point, and stashes it for fast lookup later. Each size-field
contribution then evaluates on the same grid.

<p align="center">
  <img src="https://raw.githubusercontent.com/domattioli/ADMESH/main/output/demo_annulus_pts.png" alt="Annulus domain — initial seeded points before distmesh relax" width="50%">
</p>

### 3. Size-field contributions

Each contribution returns an array `h(x_i)` evaluated at the grid
points. The composer combines them via `combine=` (default
`np.minimum.reduce`):

| Contribution | Source | Wiring |
|---|---|---|
| `h_max` / `h_min` clamp | `triangulate(h_max=…, h_min=…)` | always applied |
| `h_curvature` | [`admesh/curvature.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/curvature.py) | spec-002 Phase-1 default stack (in flight per #10) |
| `h_medial` | [`admesh/medial_axis.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/medial_axis.py) | spec-002 Phase-1 default stack |
| `h_bathy` | [`admesh/bathymetry.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/bathymetry.py) | wire by passing `user_contribs=[bathy_fn]` (auto-on planned per spec-002) |
| `h_tide` | [`admesh/dominate_tide.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/dominate_tide.py) | wire by passing `user_contribs=[tide_fn]` (auto-on planned per spec-002) |
| `h_user[i]` | callable | `user_contribs=(fn_a, fn_b, …)` |
| `size_field=` override | callable | replaces the entire composed stack |

Override the composer entirely by passing your own
`size_field: (N,2) -> (N,)`. Override the combine rule by passing
`combine=` (e.g., `np.mean`, weighted reductions).

### 4. Size-field assembly + relaxation

[`admesh/mesh_size.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/mesh_size.py)
takes the composed contributions and runs a smoothing PDE over the
grid so the size field varies gradually — without this, a high-
curvature spike at a single grid cell creates a single tiny triangle
surrounded by jumps. The relaxation uses a Numba `@njit`'d iterative
solver, MATLAB-equivalent in numerical output.

### 5. Distmesh — actually building the mesh

Force-based node motion (see [Concepts](Concepts.md) §4). Iterates until
the maximum node velocity is below a tolerance. A final
`_boundary_cleanup` pass removes slivers that touch the boundary at
near-zero angles.

<p align="center">
  <img src="https://raw.githubusercontent.com/domattioli/ADMESH/main/output/mvp_unit_disk.png" alt="Distmesh output on a unit disk" width="32%">
  &nbsp;
  <img src="https://raw.githubusercontent.com/domattioli/ADMESH/main/output/mvp_annulus.png" alt="Distmesh output on an annulus" width="32%">
  &nbsp;
  <img src="https://raw.githubusercontent.com/domattioli/ADMESH/main/output/mvp_unit_square.png" alt="Distmesh output on a unit square" width="32%">
</p>

### 6. BC enforcement

The mesher emits a triangulation; the boundary nodes need to be
categorised into BC segments (mainland, island, open ocean, weir,
…). `boundary.enforce_boundary_conditions` builds the
`PolygonStructure` that the `fort.14` writer needs. Faithful port of
`EnforceBoundaryConditions.m`. See
[`admesh/boundary.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/boundary.py).

### 7. Quality scoring

[`admesh/quality.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/quality.py)
attaches a `shape_q ∈ [0, 1]` to every element. This is the headline
correctness signal — see [Concepts](Concepts.md) §6.

### 8. `fort.14` write

```python
mesh.to_fort14("out.14")
```

Writes the geometry + the BC sections, including paired-edge records
for IBTYPE 3 / 4 / 13 / 24. Idempotent: a round-trip
read → write → read is exact-equal. See
[fort.14 cheat sheet](fort14-Cheat-Sheet.md) for the IBTYPE table and
[`admesh/fort14.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/fort14.py)
for the writer.

---

## Reverse direction: re-meshing from an existing `fort.14`

```python
mesh    = admesh.read_fort14("input.14")
domain  = admesh.api.Domain.from_mesh(mesh)
new     = admesh.triangulate(domain, h_target=500.0)
new.to_fort14("output.14")
```

This is the typical workflow for **re-meshing** a known coastline
with a different size-field stack — for example, refining a coarse
operational mesh, or coarsening a fine mesh for sensitivity studies.

Two issues currently affect this path:
[#10](https://github.com/domattioli/ADMESH/issues/10) (default
stack overshoots the domain on real coastal fixtures) and
[#11](https://github.com/domattioli/ADMESH/issues/11)
(`Domain.from_mesh` picks the wrong outer ring on multi-ring meshes
because it sorts by node count, not signed area). Both gate the
0.1.0 PyPI tag.

A side-by-side comparison plot (source mesh vs. re-meshed output)
is regenerated into `tests/output/tier1_source_vs_fresh.png` by the
Tier-1 pytest run — current shape-q-mean on the source is `0.99`,
on the re-mesh `0.92`, which is the gap [#10](https://github.com/domattioli/ADMESH/issues/10)
exists to close.

---

## Tier-2 release gate

The end-to-end correctness gate is the **Western North Atlantic**
fixture (`tests/fixtures/fort14/adcirc_examples/wnat_test.14`).
0.1.0 ships when:

1. The fixture's `Domain.from_mesh` → `triangulate` → re-meshed
   output passes the structural-validity gate
   (`tests/_structural_validity.py`).
2. The full pipeline completes in ≤ 60 s (FR-016).
3. Shape-q distribution is comparable to the source.

<p align="center">
  <img src="https://raw.githubusercontent.com/domattioli/ADMESH/main/output/release_gate_rebuild.png" alt="WNAT release-gate rebuild" width="80%">
</p>

See [Roadmap](Roadmap.md) and
[`docs/governance/PROJECT_PLAN.md`](https://github.com/domattioli/ADMESH/blob/main/docs/governance/PROJECT_PLAN.md)
for the current status of each gate.
