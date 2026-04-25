# Quickstart: Pre-Quadrangulation Triangle Smoother

**Feature**: 004-quad-prep-smoother
**Phase**: 1 (Design)
**Created**: 2026-04-25

This document is the "from zero to working" path for the
preprocessing smoother. Once the implementation lands, every code
block below should run as-is against the installed package. Before
implementation, this serves as the design-time check that the
declared API is ergonomic.

## When to use this

You have produced a triangle mesh with admesh and you want to feed
it to a downstream quadrangulation tool — CHILmesh `tri2quad`,
OceanMesh2D's quad converter, or any consumer that expects ADCIRC
v55+ quads. Without this preprocessing step, your triangles are
near-equilateral and fuse into rhombi rather than rectangles, so the
downstream quad smoother has to do disproportionate work.

The smoother nudges your tris toward right-isoceles (two equal-length
legs meeting at 90°, paired hypotenuses) so fusion is geometrically
clean.

## End-to-end example

### Polygon-defined domain

```python
import admesh
import numpy as np

# 1. Build a domain (existing admesh API)
square_polygon = np.array([
    [0.0, 0.0],
    [1.0, 0.0],
    [1.0, 1.0],
    [0.0, 1.0],
    [0.0, 0.0],
])
domain = admesh.Domain.from_polygon(square_polygon)

# 2. Triangulate as usual
mesh = admesh.triangulate(domain, h_min=0.05, h_max=0.05)
print(f"Pre-smooth: {mesh.n_nodes} nodes, {mesh.n_elements} elements")
print(f"  mesh_quality:      {admesh.mesh_quality(mesh.nodes, mesh.elements):.4f}")
print(f"  right_iso_quality: {admesh.right_iso_quality(mesh.nodes, mesh.elements):.4f}")

# 3. Run the pre-quadrangulation smoother
p_new, t = admesh.smooth_for_quadrangulation(
    mesh.nodes,
    mesh.elements,
    fd=domain.fd,                # required (FR-013)
    h=domain.size_field,         # optional but recommended
    pair_hint=True,
    n_outer=2,
)
mesh_smoothed = mesh._replace(nodes=p_new)  # connectivity unchanged

print(f"\nPost-smooth: {mesh_smoothed.n_nodes} nodes, {mesh_smoothed.n_elements} elements")
print(f"  mesh_quality:      {admesh.mesh_quality(p_new, t):.4f}  (expected to drop — that's the trade)")
print(f"  right_iso_quality: {admesh.right_iso_quality(p_new, t):.4f}  (expected to rise ≥ 0.10)")
```

Expected output (illustrative):

```
Pre-smooth: 484 nodes, 882 elements
  mesh_quality:      0.9534
  right_iso_quality: 0.4127

Post-smooth: 484 nodes, 882 elements
  mesh_quality:      0.7891  (expected to drop — that's the trade)
  right_iso_quality: 0.6234  (expected to rise ≥ 0.10)
```

### Mesh imported from fort.14

```python
import admesh

# Import an existing mesh
mesh = admesh.read_fort14("coastal_domain.14")

# Recover a domain (and its SDF) from the imported mesh
domain = admesh.Domain.from_mesh(mesh)

# Apply the smoother
p_new, _ = admesh.smooth_for_quadrangulation(
    mesh.nodes,
    mesh.elements,
    fd=domain.fd,                # critical: smoother raises ValueError if you pass None
    h=None,                      # no size field → uniform target
)

# Round-trip back out to fort.14 for the downstream quad tool
smoothed = mesh._replace(nodes=p_new)
admesh.write_fort14(smoothed, "coastal_domain_quad_prepped.14")
```

### Opt-in shortcut (when the API extension lands)

```python
# Same as the polygon example above, but the smoother is folded into
# triangulate() as the final stage:
mesh = admesh.triangulate(
    domain,
    h_min=0.05,
    h_max=0.05,
    for_quads=True,                  # opt-in (FR-011)
    quad_prep_n_outer=2,             # passes through to smooth_for_quadrangulation
    quad_prep_pair_hint=True,
)
# mesh is already smoothed; no second call needed.
```

This is optional in v1; if it isn't shipped, use the explicit
two-call path above.

## Common mistakes

### `ValueError: fd is required`

```python
# WRONG — smoother needs an SDF
p_new, t = admesh.smooth_for_quadrangulation(p, t, fd=None)
# ValueError: fd is required; pass an SDF callable

# RIGHT — supply Domain.fd or any callable returning signed distances
p_new, t = admesh.smooth_for_quadrangulation(p, t, fd=domain.fd)
```

The smoother does not synthesize an SDF from mesh topology — that's
a deliberate design decision (spec Q1 / FR-013). External callers
(`read_fort14` consumers without an analytical domain) construct an
SDF via `Domain.from_mesh(mesh).fd`.

### Trying to use `mesh_quality` to gate acceptance

```python
# WRONG — mesh_quality scores deviation from EQUILATERAL; it will
# drop after right-isoceles smoothing. That's expected.
assert admesh.mesh_quality(p_new, t) >= 0.6  # may fail!

# RIGHT — gate on right_iso_quality, the companion metric
assert admesh.right_iso_quality(p_new, t) >= admesh.right_iso_quality(p, t) + 0.10
```

This is exactly the trade the spec acknowledges (Edge Cases /
SC-007): right-isoceles and equilateral are different shapes, and
optimizing for one degrades the other.

### Forgetting that connectivity is preserved

```python
# WRONG — the returned t is the SAME OBJECT as your input t
p_new, t_new = admesh.smooth_for_quadrangulation(p, t, fd=fd)
assert t_new is t                             # True
t_new[0, 0] = 999                             # mutates your input t too!

# RIGHT — copy if you need to mutate independently
import numpy as np
t_owned = t_new.copy()
```

## Verifying the install

```python
import admesh
assert hasattr(admesh, "smooth_for_quadrangulation")
assert hasattr(admesh, "right_iso_quality")
print(f"admesh {admesh.__version__} — quad_prep ready")
```

## Performance expectations

- 10K nodes / ~20K elements: ≤ 10 s wall-clock with default settings
  (SC-005).
- Linear-ish in element count (per-iteration assembly is O(M); the
  sparse solve is O(N^1.5) for 2D Cholesky; pair-hint pre-pass is
  O(M log M)).
- No GPU, no MPI; single-threaded with optional Numba JIT on the
  inner element loop.

## Where to read more

- `specs/004-quad-prep-smoother/spec.md` — what & why
- `specs/004-quad-prep-smoother/research.md` — algorithmic
  formulation survey + decisions log
- `specs/004-quad-prep-smoother/data-model.md` — types & invariants
- `specs/004-quad-prep-smoother/contracts/python-api.md` — public
  API surface
- `docs/PORTING_NOTES.md` — leg-not-hypotenuse `h` scaling note
  (added by this feature)
