# Data Model: Fix Domain.from_mesh Ring Sorting

## Entities

### Ring (Data Structure)

**What it represents**: A closed boundary in a multiply-connected polygon (outer or hole).

**Attributes**:
- `node_ids: NDArray[int]` — indices into the mesh nodes array, ordered to form a closed loop.
- `nodes: NDArray[float, (N, 2)]` — the actual (x, y) coordinates of the ring (populated from mesh.nodes[node_ids]).
- `signed_area: float` — 2D signed area computed via the shoelace formula.

**Computation**:
```
signed_area = 0.5 * (sum(x[i] * y[i+1] - x[i+1] * y[i]) + x[-1]*y[0] - x[0]*y[-1])
```

**Relationships**:
- A `Domain` contains one outer ring + zero or more holes (both are `Ring` objects).
- A `Ring` is derived from a `Mesh` via boundary-edge walking (see `_derive_boundary_segments`).

---

### Domain

**What it represents**: A multiply-connected 2D region (polygon with holes).

**Key Attributes** (existing):
- `sdf: Callable[[NDArray], NDArray]` — signed distance function
- `bbox: tuple[float, float, float, float]` — bounding box (xmin, ymin, xmax, ymax)
- `h_frac: float` — size-field fractional preference

**New/Modified Behavior**:
- `outer_ring: Ring` — set to `rings[0]` after area-based sorting (not node-count sorting).
- `holes: list[Ring]` — set to `rings[1:]` (inner rings with smaller areas).

---

## Key Formulas & Invariants

### Shoelace Formula (2D Signed Area)

For a polygon with vertices `(x_0, y_0), (x_1, y_1), ..., (x_n, y_n)`:

```
A = 0.5 * abs( sum_{i=0}^{n} (x_i * y_{i+1} - x_{i+1} * y_i) )
```

**Sign Convention**:
- Positive: counter-clockwise (CCW) orientation.
- Negative: clockwise (CW) orientation.

**For ring identification**:
- The **outer ring** of a multiply-connected polygon always has the **largest absolute area**.
- Holes (interior rings) have smaller areas.
- Sorting by `abs(signed_area)` in descending order places the outer ring first.

### Invariant: Outer Ring Uniqueness

After area-based sorting:
```
assert abs(signed_area[0]) > abs(signed_area[i]) for all i > 0
```

This guarantees the outer ring is unambiguous, even if multiple rings have similar node counts.

---

## State Transitions

### from_mesh() Flow

1. **Input**: `mesh: Mesh` (nodes, elements)
2. **Step 1**: Call `_derive_boundary_segments(elements, nodes)` → returns list of `Ring` objects in arbitrary order.
3. **Step 2**: **[CHANGED]** Sort rings by `abs(signed_area)` descending → `rings[0]` is outer.
4. **Step 3**: Create `Domain(outer_ring=rings[0], holes=rings[1:], sdf=..., bbox=...)`
5. **Output**: `domain: Domain`

### Validation Points

- ✅ Ring node IDs form a closed loop.
- ✅ Signed area is finite (no NaN or Inf).
- ✅ Outer ring area > all hole areas.
- ✅ Domain bbox spans all ring vertices.

---

## Testing Entities

### Test Fixture: WNAT (Multiply-Connected, Interior Ring Longest by Node Count)

- **Source**: `tests/fixtures/fort14/adcirc_examples/wnat_test.14`
- **Topology**: Outer ocean boundary + interior Gulf of Mexico coastline.
- **Key Property**: Gulf coast ring has **more nodes** than Atlantic boundary ring.
- **Expected Behavior After Fix**: Gulf coast is correctly identified as a *hole*, not the outer ring.

### Test Fixture: Wetting & Drying (Tier-1)

- **Source**: `tests/fixtures/fort14/adcirc_examples/wetting_and_drying_test.14`
- **Topology**: Outer boundary + internal IBTYPE-24 weirs.
- **Key Property**: Simple case where outer ring is longest by node count (should still work).
- **Expected Behavior After Fix**: No regression; outer ring still identified correctly.

---

## Contracts (N/A)

This is a library with no external API contract changes. The fix is internal to `Domain.from_mesh`.
