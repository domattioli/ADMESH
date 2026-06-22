# Phase 1 Data Model: Default Size-Field Stack

**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Research**: [research.md](./research.md)
**Date**: 2026-04-25

This document specifies the entity changes spec 002 makes. Every change is **strictly additive** — existing constructors and method signatures from spec 001 keep working. New fields default to `None` (or sensible no-op values).

---

## Domain (extended)

```python
@dataclass(frozen=True, slots=True)
class Domain:
    # --- Existing fields (spec 001) ---
    fd: Callable[[NDArray], NDArray]            # signed distance function (N, 2) → (N,)
    bbox: tuple[float, float, float, float]     # (xmin, ymin, xmax, ymax)
    polygons: tuple[ShapelyPolygon, ...] | None # optional ring data when constructed from polygon
    fixed_points: NDArray | None                # optional N×2 fixed seed points

    # --- NEW fields (spec 002) ---
    bathymetry: Callable[[NDArray, NDArray], NDArray] | None = None
    tide_period: float | None = None
```

**Validation rules**:
- `bathymetry`, when not `None`, MUST be callable with the signature `(X, Y) -> Z` — both `X` and `Y` are arbitrary-shape ndarrays of matching shape, and the return MUST broadcast to that shape. Validated lazily at first sample.
- `tide_period`, when not `None`, MUST be `> 0` (seconds). Validated at construction.
- `bathymetry is None` AND `tide_period is not None`: not an error at construction; deferred to `triangulate()` where a `UserWarning` fires and the constant `default_depth` is used.

**New constructors / classmethods**:

```python
@classmethod
def from_mesh(
    cls,
    mesh: Mesh,
    *,
    tide_period: float | None = None,
    bbox_pad: float = 0.0,
) -> Domain:
    """Build a Domain from a triangulated Mesh — closes the round-trip story.

    Boundary rings are derived from the mesh's boundary segments
    (re-using spec-001's `_derive_boundary_segments` in reverse —
    walking the segments to recover ring polygons). Bathymetry, if
    present on the mesh, is wrapped as a `LinearNDInterpolator`.
    """
```

**Backward compatibility**:
- Existing `Domain(fd=..., bbox=...)` constructions continue to work; the new fields default to `None`.
- `domain_from_polygon(rings, bathymetry=None, tide_period=None)`: kwargs added with `None` defaults.
- `domain_from_sdf(fd, bbox, bathymetry=None, tide_period=None)`: kwargs added.

---

## BoundarySegment (extended)

```python
@dataclass(frozen=True, slots=True)
class BoundarySegment:
    # --- Existing fields (spec 001) ---
    node_ids: NDArray[np.int64]              # (N,) 0-based indices into Mesh.nodes
    bc_type: BoundaryType | int              # named or numeric IBTYPE
    is_open: bool                            # True for OPEN/-1, False for land BCs

    # --- NEW fields (spec 002) ---
    paired_node_ids: NDArray[np.int64] | None = None  # (N,) for IBTYPE 13/24/25 paired-edge
    barrier_data: NDArray[np.float64] | None = None   # (N, K) for IBTYPE 3/4/13/24/25
```

**Column shapes for `barrier_data`** (lock-in for fort.14 round-trip parity with ADCIRC v55):

| IBTYPE | Name | `paired_node_ids` | `barrier_data` shape | Columns |
|---|---|---|---|---|
| 0 | OPEN | `None` | `None` | — |
| -1 | (open ocean alias) | `None` | `None` | — |
| 1 | MAINLAND / WALL | `None` | `None` | — |
| 11 | ISLAND | `None` | `None` | — |
| 20 | MAINLAND_FLUX | `None` | `None` | — |
| **3** | **EXTERNAL_BARRIER** | `None` | **(N, 3)** | `(crest_elev, coef_subcritical, coef_supercritical)` |
| **4** | **EXTERNAL_BARRIER_FLUX** | `None` | **(N, 4)** | `(crest_elev, coef_sub, coef_super, normal_flux)` |
| **13** | **INTERNAL_BARRIER_PIPE** | `(N,)` | **(N, 5)** | `(pipe_height, coef_pipe, pipe_diameter, ...)` per ADCIRC v55 |
| **24** | **INTERNAL_BARRIER** | `(N,)` | **(N, 5)** | `(crest_elev, coef_sub, coef_super, ?, ?)` per ADCIRC v55 |
| **25** | (paired internal pipe + flow) | `(N,)` | **(N, K)** | TBD — preserved as raw float64 columns from disk |

For unmapped IBTYPE codes, `bc_type` is a plain `int`; `paired_node_ids` and `barrier_data` are populated *only if* the disk format is recognizable as paired-edge (i.e. the segment-header line declares "node pairs" rather than single-node count). Otherwise treated as single-node and the extra columns are dropped (legacy spec-001 behaviour preserved for unknown codes).

**Validation rules**:
- If `paired_node_ids is not None`, then `len(paired_node_ids) == len(node_ids)`.
- If `barrier_data is not None`, then `barrier_data.shape[0] == len(node_ids)` and `barrier_data.dtype == np.float64`.
- `Mesh.equals(...)` extends to compare `paired_node_ids` (exact int) and `barrier_data` (`atol`/`rtol`-aware).

---

## BoundaryType (extended enum)

```python
class BoundaryType(IntEnum):
    """ADCIRC IBTYPE codes recognized by admesh.fort14."""

    # --- Existing members (spec 001) ---
    OPEN = 0
    MAINLAND = 1
    ISLAND = 11
    MAINLAND_FLUX = 20
    WALL = 1                          # alias for MAINLAND, retained for spec-001 callers

    # --- NEW members (spec 002) ---
    EXTERNAL_BARRIER = 3              # single-node external weir + crest
    EXTERNAL_BARRIER_FLUX = 4         # single-node external barrier + normal flow
    INTERNAL_BARRIER_PIPE = 13        # paired-node internal pipe/culvert
    INTERNAL_BARRIER = 24             # paired-node internal barrier + supercritical flow
```

**Codes outside this set** continue to round-trip as plain `int` per spec-001's policy (`BoundarySegment.bc_type: BoundaryType | int`). IBTYPE 25 is intentionally not named — too rare to justify, but disk values of 25 round-trip as `int(25)` with paired-edge detection driven by the segment-header phrasing in fort.14.

---

## Mesh (no changes)

`Mesh` itself gains no new fields. Round-trip parity with the new `BoundarySegment` shape is achieved entirely through the existing `boundaries: tuple[BoundarySegment, ...]` field. `Mesh.equals(...)` is extended to compare the new `BoundarySegment` fields.

---

## Default Size-Field Stack (conceptual entity, not a class)

The "default size-field stack" is the composition recipe `triangulate()` invokes when neither `size_field=` nor `user_contribs=` is supplied. It is implemented as a thin wrapper around `admesh.mesh_size.build_h(...)` with the following parameter mapping:

```python
def _build_default_size_field(
    domain: Domain,
    *,
    h_min: float,
    h_max: float,
    h_target: float | None,
    enable_curvature: bool,
    enable_medial_axis: bool,
    default_depth: float,
) -> Callable[[NDArray], NDArray]:
    """Compose the default Phase-1 size-field callable.

    Maps the public-API kwargs into the build_h(...) parameter shape:
      curvature_scale = h_min if enable_curvature else None
      medial_scale    = h_min if enable_medial_axis else None
      bathymetry      = domain.bathymetry  (or constant-depth fallback)
      bathy_scale     = 1.0  (a sensible default; advanced users supply their own size_field)
      tide_period     = domain.tide_period
      tide_scale      = 100  (elements per wavelength; documented default)
      base            = h_target or h_max
      hmin, hmax      = h_min, h_max
    """
```

This mapping is documented in `contracts/python-api-default-stack.md`. It is the authoritative public-knob → MATLAB-internal-knob translation.

---

## Relationships diagram (mermaid-style ASCII)

```
Domain
├── fd: callable                    (existing)
├── bbox: tuple                     (existing)
├── polygons: tuple                 (existing)
├── fixed_points: ndarray           (existing)
├── bathymetry: callable | None     (NEW — wrapped LinearNDInterpolator from Mesh.from_mesh)
└── tide_period: float | None       (NEW)

Mesh                                (unchanged shape)
├── nodes: ndarray
├── elements: ndarray
├── boundaries: tuple[BoundarySegment, ...]
├── bathymetry: ndarray | None      (existing — per-node depth samples)
├── quality: ndarray | None
└── title: str | None

BoundarySegment                     (extended)
├── node_ids: ndarray               (existing)
├── bc_type: BoundaryType | int     (existing)
├── is_open: bool                   (existing)
├── paired_node_ids: ndarray | None (NEW)
└── barrier_data: ndarray | None    (NEW)

Mesh.from_domain_round_trip:
    Domain --triangulate--> Mesh --Domain.from_mesh--> Domain
                                  (bathymetry callable interpolant
                                   built from Mesh.bathymetry samples)
```

---

## Migration / breaking-change summary

**Zero breaking changes.** All extensions are additive:

| Surface | Spec 001 callers | Spec 002 status |
|---|---|---|
| `Domain(fd=, bbox=)` | works | works (new fields default to `None`) |
| `domain_from_polygon(rings)` | works | works (new kwargs default to `None`) |
| `triangulate(domain)` | uniform-`h` fallback | now invokes default stack |
| `triangulate(domain, size_field=fh)` | works (uniform bypass) | works (full bypass; default stack does NOT run) |
| `triangulate(domain, user_contribs=[...])` | composes on top of uniform | composes on top of new default stack |
| `BoundarySegment(node_ids=, bc_type=, is_open=)` | works | works (new fields default to `None`) |
| `BoundaryType.OPEN/MAINLAND/ISLAND/MAINLAND_FLUX/WALL` | works | works (4 new members added; existing values unchanged) |
| `read_fort14(path)` | reads spec-001 supported codes | also reads IBTYPE 3/4/13/24 paired-edge records (new) |
| `write_fort14(mesh, path)` | writes spec-001 codes | also writes paired-edge records when `barrier_data` is set |
| `mesh.equals(other)` | works | works (extended to compare new fields) |
| `Mesh.bathymetry`, `Mesh.to_fort14`, etc. | unchanged | unchanged |

The single behavioural change for default callers is: `triangulate(domain)` produces a feature-aware mesh (curvature + LFS resolution at boundaries) instead of a uniform mesh. This is the headline of the spec.
