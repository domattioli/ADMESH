# Roadmap

The authoritative roadmap is
[`docs/governance/PROJECT_PLAN.md`](https://github.com/domattioli/ADMESH/blob/main/docs/governance/PROJECT_PLAN.md).
This page is the outward-facing version: where we are, where we're
going, and what's scoped but not yet on the v1 path.

For where ADMESH fits in the sibling-project landscape (CHILmesh,
MADMESHR, ADMESH-Domains, ADCIRC), see [Ecosystem](Ecosystem.md) — the
ecosystem page includes each sibling's roadmap and how the four
roadmaps interlock.

---

## Now — 0.1.0 release gate

Spec
[`002-size-field-defaults`](https://github.com/domattioli/ADMESH/tree/main/specs/002-size-field-defaults)
is **implementation-complete** as of 2026-04-26. It wires the
MATLAB-faithful default size-field stack (curvature + medial-axis
always-on; bathymetry + tide auto-on when `Domain` carries the data)
into `admesh.triangulate()` and extends `fort.14` for IBTYPE 3 / 4 /
13 / 24 paired-edge boundary records.

**Test status**: 259 passed / 8 skipped / 2 xfailed.

**Open release-blockers** (all in spec-002 scope):

- [#10](https://github.com/domattioli/ADMESH/issues/10) — Default
  size-field stack overshoots domain on real-world coastal fixtures.
  Tier-1 / Tier-2 acceptance gates xfailed pending resolution. Tuning
  work — no Article-II violation.
- [#11](https://github.com/domattioli/ADMESH/issues/11) —
  `Domain.from_mesh` outer-ring picker sorts by node count instead of
  signed area; trips Tier-2 on WNAT. Mechanical fix; spec
  [`003-fix-outer-ring-sorting`](https://github.com/domattioli/ADMESH/tree/main/specs/003-fix-outer-ring-sorting)
  carries the change.
- [#12](https://github.com/domattioli/ADMESH/issues/12) — WNAT fresh
  mesh missing Bermuda boundary feature. Investigation under
  [`specs/006-verify-h-parameter-usage`](https://github.com/domattioli/ADMESH/tree/main/specs/006-verify-h-parameter-usage).

The 0.1.0 PyPI tag follows when the Tier-2 / WNAT structural-validity
gate is green and the three blockers above close. Path:

```
resolve #11 (mechanical, spec-003)  →
resolve #10 (tuning)                →
un-xfail Tier-1/Tier-2 tests        →
bash scripts/pre_tag_check.sh       →
git tag v0.1.0                      →
pypi publish admesh2D
```

---

## Scoped specs (003 – 008)

Each has a directory under
[`specs/`](https://github.com/domattioli/ADMESH/tree/main/specs)
with `spec.md`, `plan.md`, and (most) `tasks.md`. Status reflects
PR / commit state, not relative priority.

| Spec | Title | Status | Tracking | Notes |
|---|---|---|---|---|
| **003** | Fix `Domain.from_mesh` outer-ring sorting | in progress | [#11](https://github.com/domattioli/ADMESH/issues/11) | Mechanical fix — sort outer rings by `|signed area|`, not node count. Gates 0.1.0. |
| **004** | Pre-quadrangulation triangle smoother (`quad_prep`) | scoped, design-stable | — | Preparatory smoother that conditions a triangulation for downstream tri→quad work. Out of v1 path; lands before MADMESHR's quad-dominant generator becomes a hard dependency. |
| **005** | ADCIRC mesh registry | migrated to [ADMESH-Domains](https://github.com/domattioli/ADMESH-Domains) | [#6](https://github.com/domattioli/ADMESH/issues/6) | Originally scoped inside ADMESH; has since become its own sibling repo + PyPI package + HF dataset (see [Ecosystem](Ecosystem.md)). The `MIGRATED.md` in spec-005 records the boundary. |
| **006** | Verify `h_min` / `h_max` parameter usage | investigation | [#12](https://github.com/domattioli/ADMESH/issues/12) | Diagnostic spec — confirm `triangulate()`'s `h_min` / `h_max` actually clamp where they advertise. Outcome feeds back into #10 / #12 tuning. |
| **007** | 1D distmesh boundary seeding | scoped | [#2](https://github.com/domattioli/ADMESH/issues/2) | MATLAB reference seeds boundary nodes with a 1D distmesh pass before the 2D mesh starts. Porting lifts boundary-resolution quality on coarse polygons. Not gating 0.1.0. |
| **008** | Gmsh `.msh` I/O integration | scoped | [#5](https://github.com/domattioli/ADMESH/issues/5) | Symmetric reader + writer for Gmsh `.msh` 2.x and 4.x. Opens interop with the Gmsh ecosystem for sub-region meshing + CAD-driven domains. |

---

## Post-v1 placeholders

Scoped but explicitly **not** on the v1 path.

### GPU + CPU-parallel acceleration

**Status:** post-v1. **Tracking:** [#8](https://github.com/domattioli/ADMESH/issues/8).

The size-field stack is embarrassingly parallel per query point. CuPy
and Numba `@njit(parallel=True)` paths are both viable. Decision
deferred until 0.1.0 lands and we have real benchmark data to
prioritise against.

### `admesh-segmenter` sibling project

**Status:** post-v1. **Tracking:** [#9](https://github.com/domattioli/ADMESH/issues/9).

Composable mesh sub-region selection. Crop a continental-scale mesh
to a sub-domain with proper boundary recovery. Lives in its own repo;
depends on ADMESH, not the other way around.

### SDF-coupled FEM smoother

**Status:** scoped (post-v1 sequencing). **Tracking:**
[#1](https://github.com/domattioli/ADMESH/issues/1).

The Balendran / target-Jacobian smoother from the MATLAB reference.
Improves element quality on near-boundary elements where pure
distmesh leaves slivers. Sequenced after spec-004 (`quad_prep`) so
the two smoother surfaces can be unified.

### Possible 3D-element extension

**Status:** unfiled — concept, no issue yet.

ADMESH today is strictly 2D (triangles in the horizontal plane,
with depth carried as a per-node scalar for ADCIRC). A future
direction is extending it to 3D volumetric elements (tetrahedra,
prisms, hexes) for fully 3D shallow-water or coastal-ocean models
that need vertical structure. Naming is undecided.

### Smart AI indexing for the mesh registry

**Status:** unfiled — concept owned by [ADMESH-Domains](https://github.com/domattioli/ADMESH-Domains).

If the registry sees adoption, the natural next layer is automatic
classification + semantic search: an indexer that ingests a `fort.14`,
extracts structural metadata (BC coverage by IBTYPE, bbox + node
count, simply- vs multiply-connected, bathymetry presence), and
produces an embedding suitable for natural-language queries
("mesh similar to WNAT but with finer Caribbean resolution"). Owned
by ADMESH-Domains; ADMESH only consumes the resulting dataset.

---

## Cross-repo project plans (snapshot)

ADMESH does not move independently. Companion roadmaps:

### [CHILmesh](https://github.com/domattioli/CHILmesh)

- **Where**: v0.1.1 (alpha). Project plan at
  [`.planning/project_plan.md`](https://github.com/domattioli/CHILmesh/blob/main/.planning/project_plan.md).
- **Going**: v0.2.0 — data-structure modernization + bridge
  architecture across MADMESHR / ADMESH / ADMESH-Domains. 12-month
  horizon through Q1 2027. Phases: planning (current), three
  development phases (months 2–6), stabilisation (months 7–9),
  release + communication (months 10–12).
- **Headline criteria**: 1.5×+ performance on large meshes; zero
  breaking API changes; clear bridge interfaces; 100 % test pass on
  all platforms.
- **Affects ADMESH**: CHILmesh is the receiving end of ADMESH's
  `Mesh` for smoothing / quality / mixed-element wrapping. Bridge
  interface stabilisation is a precondition for treating CHILmesh as
  the default post-processing layer.

### [MADMESHR](https://github.com/domattioli/MADMESHR)

- **Where**: MVP / proof-of-concept. Constitution v2.0.0; thesis
  document published.
- **Going**: Path to a published Python package — not yet on PyPI.
  Reinforcement-learning policy (Soft Actor-Critic) for advancing-
  front mixed-element generation.
- **Affects ADMESH**: The deprecate-or-sibling decision (see
  [Ecosystem](Ecosystem.md)) — waits on 0.1.0 ADMESH shipping and on
  MADMESHR reaching production maturity.

### [ADMESH-Domains](https://github.com/domattioli/ADMESH-Domains)

- **Where**: on PyPI (`admesh-domains`), with HuggingFace dataset
  mirror live and GitHub-pages site at
  [domattioli.github.io/ADMESH-Domains](https://domattioli.github.io/ADMESH-Domains/).
- **Going**: ~30 numbered specs in flight (most recent: #30 compare-
  mesh UI; #29 mesh-strategy comparison; #27 prune-site features;
  #10 mesh thumbnails; #9 site polish). The registry is no longer
  nascent — it's the operational fixture library for ADMESH itself.
- **Affects ADMESH**: ADMESH's test ladder (Tier-1, Tier-2) pulls
  from this registry. The Tier-2 fixture (`wnat_test.14`) lives
  there.

### [ADCIRC](https://adcirc.org/)

- **Where**: external project, the consumer of `fort.14` output.
- **Going**: not a dependency we control — ADMESH's job is to keep
  parsing + writing consistent with each shipped ADCIRC release of
  the `fort.14` spec.

---

## Constitutional invariants

Per
[`docs/governance/CONSTITUTION.md`](https://github.com/domattioli/ADMESH/blob/main/docs/governance/CONSTITUTION.md)
Article II:

- The 13 faithful-port stage modules in `admesh/*.py` stay
  numerically identical to the MATLAB reference. Spec work extends
  via `api.py`, `fort14.py`, `boundary_types.py`, `size_field.py`,
  `viz.py`, etc. — never by modifying stages.
- No C extensions in the first cut. Numba is acceptable; `ctypes`
  bindings to `MeshSizeIterativeSolver.c` are not.
- 0-based indexing throughout (the MATLAB-faithful sense is preserved
  by subtracting 1 wherever the source indexes into arrays).
