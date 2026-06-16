# Quickstart: 1D Boundary Seeding

**Feature**: 007-1d-boundary-seeding

## What Changes

`NOTCHED_RECTANGLE` gains a `boundary_polygon` field. When `triangulate()` is
called on it, boundary nodes are pre-placed along all eight edges at
approximately `h0` spacing.

## Usage

```python
import admesh
from admesh.domains import NOTCHED_RECTANGLE
import numpy as np

p, t = admesh.triangulate(NOTCHED_RECTANGLE, h0=0.05)
notch_wall_mask = (np.abs(p[:, 0] - 0.05) < 1e-6) & (p[:, 1] >= 0.25)
print(f"Nodes on right notch wall: {notch_wall_mask.sum()}")  # expect >= 4
```

## Custom Domain with Boundary Polygon

```python
from admesh.domains import Domain
import numpy as np

my_domain = Domain(
    name="my_box",
    fd=my_sdf,
    bbox=(-1, -1, 1, 1),
    fixed_points=np.array([[-1,-1],[1,-1],[1,1],[-1,1]], dtype=float),
    boundary_polygon=np.array([[-1,-1],[1,-1],[1,1],[-1,1]], dtype=float),
)
p, t = admesh.triangulate(my_domain, h0=0.1)
```

## No-Op for Existing Domains

All other domains (`UNIT_SQUARE`, `L_SHAPE`, `UNIT_DISK`, `ANNULUS`) have
`boundary_polygon=None` and are unaffected.
