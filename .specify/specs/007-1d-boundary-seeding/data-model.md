# Data Model: 1D Boundary Seeding

**Feature**: 007-1d-boundary-seeding
**Date**: 2026-05-07

## Entities

### Domain (modified)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | — | Domain identifier |
| `fd` | `SDF` | — | Signed distance function |
| `bbox` | `tuple[float,float,float,float]` | — | Bounding box |
| `fixed_points` | `NDArray[float64]` | `empty((0,2))` | Corner/constraint points |
| **`boundary_polygon`** | `NDArray[float64] or None` | `None` | **NEW** Ordered boundary vertices `(M,2)` |

### _seed_boundary_1d

```
_seed_boundary_1d(polygon, fh, h0) -> NDArray[float64] shape (K,2)
```

Algorithm: For each edge, evaluate local_h = fh(midpoint) or h0. Place
n_segs-1 interior seeds at t=k/n_segs for k=1..n_segs-1.

## Relationships

```
triangulate(target: Domain)
  if target.boundary_polygon is not None:
    seeds = _seed_boundary_1d(target.boundary_polygon, fh, h0)
    pfix = concatenate([seeds, target.fixed_points])
  -> distmesh2d(fd, fh, h0, bbox, pfix=pfix)
```
