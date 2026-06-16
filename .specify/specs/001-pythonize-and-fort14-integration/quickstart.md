# Quickstart: admesh2D v1 (Pythonic API)

**Feature**: 001-pythonize-and-fort14-integration
**Date**: 2026-04-24

This is the idealized end-state usage. The plan commits to delivering this surface; this document is what a new user will read once v1 lands. No internal pipeline knowledge required.

---

## Install

```bash
pip install admesh2D                  # core library
pip install admesh2D[viz]             # adds matplotlib for mesh.plot()
```

---

## Three-line happy path

```python
import admesh

domain = admesh.domain_from_polygon([outer_ring_xy, hole_ring_xy])
mesh = admesh.triangulate(domain)
mesh.to_fort14("out.14")
```

That's it. `outer_ring_xy` is an `(M, 2)` NumPy array of (x, y) vertices for the outer boundary; `hole_ring_xy` is the same shape for an internal hole. The call returns a `Mesh` dataclass; `to_fort14` writes a valid ADCIRC v55 mesh file.

---

## Inspect the result

```python
>>> mesh
Mesh(n_nodes=4218, n_elements=8127, min_q=0.41, mean_q=0.69, n_boundaries=2)

>>> print(mesh)
Mesh
  nodes:      4218 × 2 (float64)
  elements:   8127 × 3 (int64)
  quality:    min=0.41, mean=0.69, max=0.93
  boundaries: 2 segments
    [0] OPEN     (1245 nodes)
    [1] MAINLAND ( 312 nodes)
  bathymetry: not set
```

`__repr__` is one-line; `__str__` is multi-line.

---

## Plot it (matplotlib optional)

```python
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
mesh.plot(ax=ax)         # nodes, triangles, boundary segments coloured by BoundaryType
plt.show()
```

If matplotlib is not installed, `mesh.plot()` raises `ImportError` with a message that names the `[viz]` extra.

---

## Round-trip: read fort.14, modify, write back

```python
import admesh

mesh = admesh.read_fort14("input.14")
print(mesh)
# ... arbitrary in-place analysis ...
mesh.to_fort14("output.14")

# Round-trip is lossless within documented precision:
roundtripped = admesh.read_fort14("output.14")
assert mesh.equals(roundtripped)
```

Boundary-segment BC labels (named or numeric) round-trip exactly. Coordinates round-trip within 6-decimal precision (configurable via the `precision=` kwarg on `to_fort14`).

---

## Custom size-field contribution (power user)

You want the mesh refined near a hand-chosen feature — say, a wave-breaking line. Write a callable `(N, 2) -> (N,)` returning your target size at each query point, and pass it as a `user_contribs` entry:

```python
import admesh
import numpy as np

def refine_near_breaker(pts):
    # `pts` is (N, 2) of (x, y) query points.
    # Return (N,) target sizes — smaller = finer mesh.
    breaker_x = 1500.0
    distance = np.abs(pts[:, 0] - breaker_x)
    return 50.0 + 0.2 * distance        # 50m at the breaker, growing outward

mesh = admesh.triangulate(
    domain,
    user_contribs=[refine_near_breaker],
)
```

The built-in stages (curvature, medial axis, bathymetry, tide) `min`-stack first — exactly as in MATLAB, byte-for-byte identical to the faithful-port surface. Then your contribution is combined with that result via the default `np.minimum.reduce` (so contributions can only refine, not coarsen). To use a different combiner — e.g., a max-of-mins — pass `combine=`:

```python
mesh = admesh.triangulate(
    domain,
    user_contribs=[refine_near_breaker, refine_near_inlet],
    combine=lambda arrs: np.maximum.reduce(arrs),   # coarser of refinements
)
```

The Phase-1 built-in stack is **not** affected by `combine` — Constitution Principle I keeps the faithful surface invariant.

---

## chilmesh integration

Per the spec's recommendation (Option A), admesh2D owns fort.14 export; chilmesh reads fort.14 independently. No cross-imports.

```python
# In your code:
import admesh
import chilmesh

mesh = admesh.triangulate(domain)
mesh.to_fort14("intermediate.14")

cm = chilmesh.ChilMesh.from_fort14("intermediate.14")
# ... continue with chilmesh's API ...
```

For in-process workflows where the disk round-trip is unwanted, write to an in-memory buffer:

```python
import io
buf = io.StringIO()
mesh.to_fort14(buf)
buf.seek(0)
cm = chilmesh.ChilMesh.from_fort14(buf)
```

---

## Backward compatibility

If you have code calling the existing module-level functions (`admesh.distmesh.distmesh2d_admesh`, `admesh.routine.ADmeshRoutine`, etc.) — that code keeps working. The new `triangulate()` is *additive*; the faithful-port surface is unchanged and still produces numerically identical output to MATLAB.

---

## What's next

- A richer visualization module (size-field heatmaps, quality histograms, iteration animations) is a planned follow-up.
- Streaming I/O for very large meshes (>10M nodes) is forward-compatible with the v1 design but not implemented yet.
- ADCIRC fort.13 (nodal attributes) is out of scope for v1.

---

> **Note**: As of 2026-04-24, this quickstart describes the **target** v1 API. The implementation tasks land in a follow-up `/speckit-tasks` invocation. Until v1 ships, the existing module-level faithful-port functions remain the recommended way to use admesh2D in production.
