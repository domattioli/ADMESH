# Phase 1 Data Model: Octree Background Grid

Entities and their fields/relationships, derived from the spec Key Entities and the research decisions. These are *design* shapes, not final signatures (see contracts/).

## OctreeGrid

The hierarchical substrate replacing the uniform `BackgroundGrid`.

| Field | Type | Notes |
|-------|------|-------|
| `bbox` | `(xmin, ymin, xmax, ymax)` | Padded domain extent (same padding rule as today, default `h0`). |
| `root` | `OctreeLeaf` | Top cell covering the whole padded bbox. |
| `leaves` | `list[OctreeLeaf]` | Flattened leaf list (refinement complete, 2:1 balanced). |
| `h_min` | `float` | Refinement floor; no leaf is smaller (R2/FR-004). |
| `adjacency` | leaf-graph | Edge-adjacent leaf pairs + centre-to-centre spacing (drives FMM + gradient limiter). |

**Relationships**: built from a `Domain` (uses `domain.fd` SDF + size drivers); consumed by the medial-axis stage and `build_h`. **Degenerate case**: a single refinement level ⇒ equivalent to the uniform grid (FR-017). **Invariants**: every leaf size ∈ `[h_min, root_size]`; adjacent leaf sizes differ by ≤ 2× (FR-003); leaves tile the bbox without overlap.

## OctreeLeaf

| Field | Type | Notes |
|-------|------|-------|
| `center` | `(x, y)` | Leaf centroid (sample point for size drivers + interpolation). |
| `size` | `float` | Edge length of the square leaf. |
| `depth` | `int` | Refinement level (diagnostic; floor is `h_min`, not depth). |
| `D` | `float` | Signed distance at the leaf (from `domain.fd`). |
| `neighbors` | `list[int]` | Indices into `OctreeGrid.leaves` (edge-adjacent). |

## Size-field arrays (per-leaf, replacing the `(LY, LX)` grid arrays)

| Quantity | Shape | Source |
|----------|-------|--------|
| `D` | `(n_leaves,)` | SDF on leaves. |
| `h` | `(n_leaves,)` | Composite target edge length (min-stack of drivers), pre-limit. |
| `MAD` | `(n_leaves,)` | Medial-axis distance via FMM on the leaf graph (R4). |
| `LFS` | `(n_leaves,)` | `|D| + MAD`. |
| `h_smooth` | `(n_leaves,)` | After leaf-graph gradient limiting (R5), clipped to `[h_min, h_max]`. |

These mirror the current `(LY, LX)` arrays but indexed by leaf rather than by `(row, col)`; the composition rule (min-stack of curvature/medial/bathymetry/tide) is unchanged.

## MedialAxisResult (on the octree)

| Field | Type | Notes |
|-------|------|-------|
| `medial_leaves` | boolean mask `(n_leaves,)` | Leaves on the medial axis (generalised AOF detection, R4). |
| `MAD` | `(n_leaves,)` | Distance to nearest medial leaf (FMM). |
| `resolved` | `bool` | Whether any feature above `h_min` produced a non-empty medial axis (drives the FR-006/FR-012 warning). |

## Four-Elements-Per-Feature Target

| Field | Type | Notes |
|-------|------|-------|
| `min_elements` | `float` | Configurable lower bound, default ≥ 4 (FR-011). |
| target relation | — | `h_target ≤ feature_width / min_elements` at the medial axis (the size-function *driver*); separately **verified** by counting element edges across the feature in the output mesh (FR-010, clarify "target + verify"). |

## Principle I Exception Record

Not a runtime entity — the dated Constitution amendment (docs/governance/CONSTITUTION.md + .specify/memory/constitution.md, v2.0.0) naming the exempted stages (`background_grid`, `medial_axis`, `mesh_size`) and the rationale. Tracked as a task and a release gate (FR-015).

## Validation Benchmark Set

| Item | Type | Notes |
|------|------|-------|
| synthetic basin+inlet | new fixture | Controllable L/W ratio; deterministic; exercises the `h_min` floor (SC-001). |
| real ADCIRC multi-scale mesh | reference fixture | Realism; selected during tasks/implement (SC-007). |
