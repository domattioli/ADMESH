# Contract: Python API — Default Size-Field Stack

**Spec**: [../spec.md](../spec.md) · **Plan**: [../plan.md](../plan.md)
**Surface**: `admesh.triangulate`, `admesh.Domain`, `admesh.BoundaryType`
**Audience**: callers of the public `admesh` API

This document is the authoritative contract for the new public-API surface introduced by spec 002. Every signature, kwarg default, and behavioural promise here MUST be reflected in the implementation and tests.

---

## `admesh.triangulate`

Extended signature (additions in **bold**):

```python
def triangulate(
    domain: Domain,
    *,
    # --- Existing kwargs (spec 001) ---
    h_min: float = 0.05,
    h_max: float = 0.5,
    size_field: Callable[[NDArray], NDArray] | None = None,
    user_contribs: Sequence[Callable[[NDArray], NDArray]] | None = None,
    combine: Callable[..., NDArray] = lambda *a: np.minimum.reduce(a),
    fixed_points: NDArray | None = None,
    quality_gate: tuple[float, float] = (0.30, 0.60),
    max_iter: int = 1000,
    # --- NEW kwargs (spec 002) ---
    h_target: float | None = None,
    enable_curvature: bool = True,
    enable_medial_axis: bool = True,
    default_depth: float = 1.0,
    tide_elements_per_wavelength: float = 100.0,
) -> Mesh:
    ...
```

**Behavioural contract**:

1. **No `size_field=` and no `user_contribs=`** (the headline case): `triangulate` constructs a default size-field callable via `_build_default_size_field(domain, ...)`. The callable composes (curvature, medial-axis) always-on; (bathymetry, tide) opt-in based on `domain.bathymetry` and `domain.tide_period`.

2. **`size_field=` supplied, `user_contribs=` empty**: existing spec-001 behaviour. The user's callable is the only source of edge sizing; the default stack does NOT run. This is the backward-compat path for spec-001 callers.

3. **`size_field=None`, `user_contribs=[...]` supplied**: the default stack is built (as case 1) and the user's contributions compose on top via `combine` (default elementwise minimum). The Phase-2 user_contribs semantics from spec 001 are preserved verbatim.

4. **Both `size_field=` and `user_contribs=` supplied**: existing spec-001 warning fires (`UserWarning`); `user_contribs` is ignored. Behaviour matches spec 001.

5. **`tide_period` set on domain, but `domain.bathymetry is None`**: `UserWarning("tide_period set but Domain.bathymetry is None; using constant default_depth=...")` fires; the tide stage runs with `default_depth` as a uniform depth grid.

6. **`enable_curvature=False, enable_medial_axis=False, domain.bathymetry is None, domain.tide_period is None`**: default stack is empty → falls back to uniform `h(p) = h_target or h_max`. Identical to today's spec-001 default.

7. **`h_max / h_min < 2`** (degenerate dynamic range): default stack short-circuits to uniform fallback (no grid construction, no Eikonal smoother). Documented threshold; no warning.

8. **Backward compat tests**: every spec-001 quickstart example MUST produce a `Mesh` whose `mesh.equals(spec_001_baseline)` returns `True` when the spec-001 invocation is faithfully reproduced (i.e. with `size_field=` set explicitly to the spec-001 callable).

---

## `admesh.Domain`

Extended dataclass (per [data-model.md](../data-model.md)):

```python
@dataclass(frozen=True, slots=True)
class Domain:
    fd: Callable[[NDArray], NDArray]
    bbox: tuple[float, float, float, float]
    polygons: tuple[ShapelyPolygon, ...] | None = None
    fixed_points: NDArray | None = None
    # NEW
    bathymetry: Callable[[NDArray, NDArray], NDArray] | None = None
    tide_period: float | None = None
```

**Constructors**:

```python
def domain_from_polygon(
    rings: Sequence[NDArray],
    *,
    bathymetry: Callable | None = None,
    tide_period: float | None = None,
) -> Domain: ...

def domain_from_sdf(
    fd: Callable,
    bbox: tuple[float, float, float, float],
    *,
    bathymetry: Callable | None = None,
    tide_period: float | None = None,
) -> Domain: ...

# NEW classmethod on Domain
@classmethod
def from_mesh(
    cls,
    mesh: Mesh,
    *,
    tide_period: float | None = None,
    bbox_pad: float = 0.0,
) -> Domain: ...
```

**`Domain.from_mesh` contract**:

- Walks the mesh's boundary segments to derive outer ring + holes (uses the existing `_derive_boundary_segments` helper from spec 001 in reverse).
- If `mesh.bathymetry is None`, the returned `Domain.bathymetry` is also `None`.
- If `mesh.bathymetry` is present, builds a `scipy.interpolate.LinearNDInterpolator` over `(mesh.nodes, mesh.bathymetry)`. The wrapped callable is `lambda X, Y: interp(np.column_stack([X.ravel(), Y.ravel()])).reshape(X.shape)`. Returns NaN outside the convex hull; downstream `bathymetry.create_elevation_grid` calls `inpaint_nans` automatically.
- `tide_period` kwarg sets `Domain.tide_period` directly; not derived from the mesh.
- `bbox_pad` adds the given amount to each side of the source mesh's bbox; default `0.0` matches the source mesh exactly.

---

## `admesh.BoundaryType`

Extended enum (per [data-model.md](../data-model.md)):

```python
class BoundaryType(IntEnum):
    OPEN = 0
    MAINLAND = 1
    ISLAND = 11
    MAINLAND_FLUX = 20
    WALL = 1
    # NEW
    EXTERNAL_BARRIER = 3
    EXTERNAL_BARRIER_FLUX = 4
    INTERNAL_BARRIER_PIPE = 13
    INTERNAL_BARRIER = 24
```

Existing values (0, 1, 11, 20) are unchanged. Adding new members does not break callers comparing against integer codes.

---

## `_build_default_size_field` (private, but contract-relevant)

The mapping from public kwargs to MATLAB-internal `build_h` parameters is the load-bearing translation in this spec. Documented here so callers can reason about *why* a particular `h_min` produces a particular per-stage scale:

| Public kwarg | `build_h` parameter | Mapping rule |
|---|---|---|
| `enable_curvature=True` | `curvature_scale=h_min` | enabled if True; `None` otherwise |
| `enable_medial_axis=True` | `medial_scale=h_min` | enabled if True; `None` otherwise |
| `domain.bathymetry` | `bathymetry=domain.bathymetry` | passed through; `None` skips the stage |
| (implicit) | `bathy_scale=1.0` | sensible default; advanced users can pass `size_field=` for override |
| `domain.tide_period` | `tide_period=domain.tide_period` | passed through |
| `tide_elements_per_wavelength` | `tide_scale=tide_elements_per_wavelength` | direct |
| `h_target or h_max` | `base=h_target or h_max` | base edge length where no stage applies |
| `h_min` | `hmin=h_min` | direct |
| `h_max` | `hmax=h_max` | direct |
| (built-in) | `g=0.2` | grading slope; documented constant matching MATLAB defaults |

When `domain.bathymetry is None` and `domain.tide_period is not None`:

```python
fallback_bathymetry = lambda X, Y: np.full(X.shape, default_depth)
warnings.warn("tide_period set but Domain.bathymetry is None; using constant default_depth=...", UserWarning)
build_h(domain, ..., bathymetry=fallback_bathymetry, ...)
```

The mapping rule for `bathy_scale=1.0` is intentionally a fixed sensible default rather than a public kwarg. Advanced users who need to tune it pass a fully custom `size_field=` callable; we do NOT expose every MATLAB-internal scale as a public kwarg (per spec FR-006).

---

## Test contract — structural validity

The release-gating regression test (FR-014) MUST assert these three properties for every fixture in the test ladder:

```python
def assert_structurally_valid(mesh: Mesh, domain: Domain, *, tol: float = 1e-9) -> None:
    """The 0.1.0 release gate. Three asserts, no quality numbers."""

    # (a) Every element has strictly positive signed area.
    pts = mesh.nodes[mesh.elements]            # (E, 3, 2)
    signed_area = 0.5 * (
        (pts[:, 1, 0] - pts[:, 0, 0]) * (pts[:, 2, 1] - pts[:, 0, 1])
      - (pts[:, 2, 0] - pts[:, 0, 0]) * (pts[:, 1, 1] - pts[:, 0, 1])
    )
    assert np.all(signed_area > tol), f"{(signed_area <= tol).sum()} degenerate elements"

    # (b) Every input boundary edge appears as a triangle edge.
    if domain.polygons is not None:
        input_edges = _polygon_edges(domain.polygons, tol)
        mesh_edges = _triangle_edges(mesh.elements)
        missing = input_edges - mesh_edges
        assert not missing, f"{len(missing)} input boundary edges missing"

    # (c) Union of triangle areas covers the input domain area to within tolerance.
    if domain.polygons is not None:
        domain_area = sum(p.area for p in domain.polygons)
        mesh_area = signed_area.sum()
        assert abs(mesh_area - domain_area) < tol * max(domain_area, 1.0), (
            f"coverage gap: |mesh_area - domain_area| = {abs(mesh_area - domain_area)}"
        )
```

Helpers `_polygon_edges` and `_triangle_edges` are implementation details of `tests/test_default_size_field.py`. The test fixture ladder is enumerated in [data-model.md](../data-model.md) and the spec's "Test Fixture Ladder" entity.
