# Quickstart

This page walks through the most common ADMESH workflows: triangulating a
polygon, round-tripping an ADCIRC `fort.14`, composing a custom size
field, and loading a domain from the `admesh-domains` registry.

## Setup

```python
import admesh
import numpy as np
```

All examples assume ADMESH ≥ 0.1.0.

## Triangulate a polygon

The simplest workflow: define a polygon by its vertex ring, call
`triangulate`, and read out the mesh.

```python
# Unit square with one hole.
outer = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
hole = np.array([[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]])

domain = admesh.Domain(
    sdf=lambda p: ...,  # signed-distance function over the multi-ring polygon
    bbox=(0.0, 0.0, 1.0, 1.0),
)

mesh = admesh.triangulate(domain, h_max=0.05)

print(mesh.n_nodes, mesh.n_elements)
print("min quality:", mesh.quality.min())
```

For polygon-based domains, the canonical builder is
[`admesh.load_domain_from_json`](api/loaders.md) — see that page for the
expected JSON schema. The `admesh.Domain` constructor accepts a signed-
distance callable directly when you want full control.

## Round-trip an ADCIRC `fort.14`

```python
src = admesh.read_fort14("examples/coast.14")
src.to_fort14("examples/coast_out.14")

roundtripped = admesh.read_fort14("examples/coast_out.14")
assert src.equals(roundtripped)
```

`Mesh.equals` tolerates `atol=1e-5` on node coordinates and exact match on
connectivity + boundary segments. The `Fort14ParseError` exception carries
`line_no / expected / actual` for any malformed input.

## Build a `Domain` from an existing mesh

When you have a mesh and want to re-triangulate it with new size-field
defaults, use `Domain.from_mesh`:

```python
src = admesh.read_fort14("coastal_fixture.14")
domain = admesh.Domain.from_mesh(src)

fresh = admesh.triangulate(domain, h_min=10.0, h_max=200.0)
```

`Domain.from_mesh` extracts the outer boundary ring (largest signed area)
and any interior holes (smaller rings), then builds a Shapely-backed SDF
plus a bathymetry interpolant from the source mesh's depth values.

## Custom size-field contribution

Pass a callable that maps `(N, 2)` points to `(N,)` desired edge lengths.
Multiple contributions can be combined via `compose_size_field`.

```python
def refine_near_inlet(points):
    """Tighten edges within 500 m of the inlet at x=1500."""
    return 50.0 + 0.2 * np.abs(points[:, 0] - 1500.0)

def refine_near_island(points):
    """Tighten edges within 100 m of a circular island at (3000, 2000)."""
    d = np.linalg.norm(points - np.array([3000.0, 2000.0]), axis=1)
    return 20.0 + 0.5 * np.clip(d - 100.0, 0.0, None)

mesh = admesh.triangulate(
    domain,
    h_min=20.0,
    h_max=500.0,
    user_contribs=(refine_near_inlet, refine_near_island),
    combine=np.minimum.reduce,  # take the tightest contribution at each point
)
```

The default `combine` is `np.minimum.reduce` — at every point, the tightest
of the contributions wins. Pass `np.add` or `np.maximum.reduce` to change
the policy.

## Load from the `admesh-domains` registry

> ⚠️ **Status as of 2026-05-15**: registry loaders are documented but the
> adapter is broken against `admesh-domains` 0.3.x (see
> [issue #64](https://github.com/domattioli/ADMESH/issues/64)). Use file
> loaders below until the fix lands.

When the adapter is repaired, the registry workflow will be:

```python
# Discover available domains.
for mesh_id, desc in sorted(admesh.list_available_domains().items()):
    print(f"{mesh_id}: {desc}")

# Load a registered domain by id.
domain = admesh.load_domain_from_registry("BaranjaHill")
mesh = admesh.triangulate(domain)

# Or load with provenance metadata.
domain, meta = admesh.load_domain_with_metadata("BaranjaHill")
print(f"License: {meta.get('license')}, contributor: {meta.get('contributed_by')}")
```

## Load from a local `fort.14` or polygon file

```python
# fort.14 — full ADCIRC mesh, including boundary types.
domain = admesh.load_domain_from_fort14("examples/coast.14")

# JSON — polygon rings + fixed points.
domain = admesh.load_domain_from_json("examples/inlet.json")

# TOML — same content, TOML-formatted.
domain = admesh.load_domain_from_toml("examples/inlet.toml")
```

See [Domain loaders](api/loaders.md) for the JSON / TOML schemas.

## Pre-quad smoother (spec 004)

If you plan to convert the triangulation to quads downstream, run the
right-isoceles smoother first:

```python
domain = admesh.load_domain_from_fort14("coast.14")
mesh = admesh.triangulate(domain)

# Nudge triangles toward right-isoceles shape so pair-fusion is clean.
p_new, _ = admesh.smooth_for_quadrangulation(
    mesh.nodes, mesh.elements, domain.sdf,
)

# Quality check.
q = admesh.right_iso_quality(p_new, mesh.elements)
print("right-isoceles quality (mean):", q.mean())
```

## Valence balancing (issue #27)

After triangulation, you may want to balance the number of triangles
meeting at each node (the *valence*). The default heuristic targets 6
interior-node valence and 4 boundary-node valence.

```python
result = admesh.balance_valence_triangles(mesh, max_passes=3)
print(f"Flipped {result.n_flips} edges across {result.n_passes} passes")
print(f"Valence after: mean={result.stats.mean_valence:.2f}")
```

See [`BalanceConfig`](api/valence.md) for tuning the targets.

## Visualization

Install the `[viz]` extra (`pip install admesh2D[viz]`) for the matplotlib
adapter:

```python
import matplotlib.pyplot as plt
from admesh.viz import plot_mesh

fig, ax = plt.subplots(figsize=(8, 6))
plot_mesh(mesh, ax=ax, show_boundary=True)
plt.show()
```

## Where to go next

- **[API Reference](api/triangulate.md)** — every public symbol documented.
- **[Constitution](governance/CONSTITUTION.md)** — the rules ADMESH follows
  for faithful-port discipline, no C extensions, and reference-test cadence.
- **[Project plan](governance/PROJECT_PLAN.md)** — historical and current
  status; "Path to 0.1.0" lives at the top.
- **[Contributing](https://github.com/domattioli/ADMESH/blob/development/CONTRIBUTING.md)** — dev setup, branch contract,
  filing issues.
