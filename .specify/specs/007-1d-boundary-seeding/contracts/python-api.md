# Python API Contract: 1D Boundary Seeding

**Feature**: 007-1d-boundary-seeding

## Public Surface Changes

### `admesh.domains.Domain`

New optional field `boundary_polygon: NDArray[np.float64] | None = None`.
All existing `Domain(...)` calls without `boundary_polygon` are unaffected.

### `admesh.routine.triangulate`

Signature unchanged. Behavior change: when `target.boundary_polygon is not None`,
seeds from `_seed_boundary_1d()` are prepended to `pfix`.

## Private API

`_seed_boundary_1d(polygon, fh, h0) -> NDArray`: module-private, not exported.

## Pre-defined Domain Changes

`NOTCHED_RECTANGLE` gains `boundary_polygon` (8-vertex polygon matching its geometry).
No changes to `UNIT_SQUARE`, `L_SHAPE`, `UNIT_DISK`, `ANNULUS`.

## Invariants

1. `triangulate(domain)` where `domain.boundary_polygon is None` is numerically identical to pre-feature.
2. Seed count for uniform fh on edge of length L at spacing h0 is `max(0, floor(L/h0) - 1)`.
