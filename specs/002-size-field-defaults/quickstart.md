# Quickstart: Default Size-Field Stack

**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)
**Audience**: end users of `admesh` (after spec 002 lands)

This document walks the user idioms for spec 002 — what changes, what stays the same. Three tiers of usage, mirroring the test ladder.

---

## Tier 0 — A polygon and a triangulation

The headline use-case. Three lines, no kwargs:

```python
import admesh

domain = admesh.domain_from_polygon([outer_ring_xy])
mesh = admesh.triangulate(domain)
mesh.to_fort14("output.14")
```

Before spec 002: `mesh` was uniform-edge-length everywhere — the bad-mesh failure mode.
After spec 002: `mesh` has feature-aware sizing — short edges at concave corners, long edges in the interior, gradient-bounded transitions.

To tune the edge-length range:

```python
mesh = admesh.triangulate(domain, h_min=0.05, h_max=0.5)
```

To disable a stage (rare; advanced):

```python
mesh = admesh.triangulate(domain, enable_medial_axis=False)
```

To completely override the default stack with a custom callable (spec 001 pattern, still works):

```python
mesh = admesh.triangulate(domain, size_field=lambda p: 0.1 * np.ones(len(p)))
```

To compose a custom contribution *on top of* the default stack (spec 001 user_contribs pattern, still works):

```python
def refine_near_breaker(pts):
    return 50.0 + 0.2 * np.abs(pts[:, 0] - 1500.0)

mesh = admesh.triangulate(domain, user_contribs=[refine_near_breaker])
```

---

## Tier 1 — Round-trip an ADCIRC fort.14 file with internal barriers

Read the ADCIRC Example 10 (wetting-and-drying tutorial) mesh, build a `Domain` from it, re-triangulate with the default stack, write the new mesh back. **Note: `mesh.to_fort14` requires extending the spec-001 writer for the IBTYPE 3/24 paired-edge support that spec 002 lands**; until that's implemented, only the simpler single-node IBTYPEs (0, 1, 11, 20) round-trip correctly.

```python
import admesh

# Read source mesh — preserves all 9 land-boundary segments including
# IBTYPE 3 (external weir + crest) and IBTYPE 24 (internal barrier
# with paired-node + supercritical-flow coefficients).
src = admesh.read_fort14("tests/fixtures/fort14/adcirc_examples/wetting_and_drying_test.14")

# Build a Domain from the source mesh — outer ring + holes derived
# from boundaries, bathymetry wrapped as a LinearNDInterpolator over
# the source nodes.
domain = admesh.Domain.from_mesh(src)

# Re-triangulate with the default stack. Curvature + medial-axis
# stages always run; bathymetry stage activates because the source
# mesh had non-zero depths.
fresh = admesh.triangulate(domain, h_min=10.0, h_max=200.0)

# Write back; the writer preserves IBTYPE 3 + 24 records emitted by
# the source domain.
fresh.to_fort14("output_remeshed.14")
```

Behaviour notes:

- The **boundaries** of the source mesh become the polygonal input to triangulation — the new mesh's outer + island rings match the source's. Internal weir/barrier *records* (IBTYPE 3 / 24) are not topologically embedded in the new mesh; they're carried as metadata on the `Domain` and re-emitted on `write_fort14`.
- **Bathymetry** is preserved via the `LinearNDInterpolator`; the new mesh's nodes get depth values interpolated from the source's per-node depth column.
- The new mesh's node count and element count will differ from the source (the default stack picks size based on geometry, not on matching the source).

---

## Tier 1.5 — Real-world coastal domain (Shinnecock)

Same idiom as Tier 1; smaller fixture (~3K nodes) with real coastline + real bathymetry.

```python
src = admesh.read_fort14("tests/fixtures/fort14/adcirc_examples/shinnecock.14")
domain = admesh.Domain.from_mesh(src)
fresh = admesh.triangulate(domain, h_min=20.0, h_max=500.0)
fresh.to_fort14("shinnecock_remeshed.14")
```

The Shinnecock fixture is acquired during `/speckit-implement` (per [research.md](./research.md) Decision 6). Until then, the test ladder runs Tier 0 → Tier 1 → Tier 2, skipping Tier 1.5.

---

## Tier 2 — WNAT canonical (the release gate)

Same idiom; biggest fixture (~10K nodes); proves spec 002 can mesh a publication-grade domain.

```python
src = admesh.read_fort14("tests/fixtures/fort14/adcirc_examples/wnat_test.14")
domain = admesh.Domain.from_mesh(src)
fresh = admesh.triangulate(domain, h_min=0.05, h_max=2.0)  # degrees, since WNAT is in geographic CRS
fresh.to_fort14("wnat_remeshed.14")
```

The structural-validity assertions (`assert_structurally_valid(fresh, domain)` from [contracts/python-api-default-stack.md](./contracts/python-api-default-stack.md)) MUST pass for this fixture. That's the 0.1.0 release gate.

---

## Adding bathymetry to a domain you constructed yourself

If you didn't load from fort.14 but want bathymetry-driven refinement:

```python
import numpy as np
import admesh

def my_bathy(X, Y):
    # Synthetic ridge at x = 1500
    return 100.0 + 50.0 * np.exp(-(X - 1500.0)**2 / 200.0**2)

domain = admesh.domain_from_polygon([outer_ring_xy], bathymetry=my_bathy)
mesh = admesh.triangulate(domain)
```

The bathymetry stage activates automatically; mean edge length within the ridge region drops as the depth gradient rises.

---

## Adding tide forcing

Tide stage activates when `tide_period` is set. Combines naturally with `bathymetry`:

```python
domain = admesh.domain_from_polygon(
    [outer_ring_xy],
    bathymetry=my_bathy,
    tide_period=43200.0,    # 12-hour tide in seconds
)
mesh = admesh.triangulate(domain)
```

If you set `tide_period` without `bathymetry`, a `UserWarning` fires and a constant `default_depth=1.0` (metres) is used:

```python
domain = admesh.domain_from_polygon([outer_ring_xy], tide_period=43200.0)  # no bathymetry
mesh = admesh.triangulate(domain)
# UserWarning: tide_period set but Domain.bathymetry is None;
#              using constant default_depth=1.0
```

Override the constant:

```python
mesh = admesh.triangulate(domain, default_depth=10.0)
```

---

## What hasn't changed

Every spec-001 idiom continues to work verbatim:

```python
# Custom size_field — bypasses default stack
mesh = admesh.triangulate(domain, size_field=lambda p: 0.1 * np.ones(len(p)))

# user_contribs — composes on top
mesh = admesh.triangulate(domain, user_contribs=[my_refinement])

# Both supplied — UserWarning fires (spec 001 behaviour)
mesh = admesh.triangulate(
    domain,
    size_field=fh1,
    user_contribs=[fh2],
)

# Visualization (existing matplotlib helper)
mesh.plot()  # if installed via admesh2D[viz]

# fort.14 round-trip (extended for paired-edge IBTYPEs in spec 002)
m1 = admesh.read_fort14("a.14")
m1.to_fort14("b.14")
assert m1.equals(admesh.read_fort14("b.14"))
```

All 142 spec-001 faithful-port tests pass unchanged. The new behavior is strictly additive.
