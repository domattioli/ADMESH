# Quickstart: Fix Domain.from_mesh Ring Sorting

## What This Fix Does

Replaces the ring-sorting criterion in `Domain.from_mesh()` from **node count** to **signed area** (shoelace formula). This ensures outer rings of multiply-connected domains are correctly identified, even when internal coastlines have more nodes than the outer ocean boundary.

## How to Test

### Test 1: Verify WNAT Fixture

```python
import admesh

# Load the real-world WNAT fixture
src = admesh.read_fort14("tests/fixtures/fort14/adcirc_examples/wnat_test.14")
print("Source bbox:", src.nodes.min(0), "to", src.nodes.max(0))
# Expected: [-97.85, 8.00] to [-60.04, 45.77]

# Recover the domain
dom = admesh.Domain.from_mesh(src)
print("Recovered bbox:", dom.bbox)
# Expected: (-97.85, 8.00, -60.04, 45.77) ✅

# Triangulate should now succeed (not ValueError: zero-size array)
mesh = admesh.triangulate(
    dom, h_min=0.05, h_max=2.0, seed=0, max_iter=200, quality_gate=(0.0, 0.0)
)
print(f"New mesh: {mesh.n_nodes} nodes, {mesh.n_elements} elements")
# Expected: non-empty mesh with area ~= original domain ✅
```

### Test 2: Run Unit Tests

```bash
cd /workspace/ADMESH

# Run all tests in test_api.py (includes the new ring-sorting test)
pytest tests/test_api.py::test_domain_from_mesh_multiply_connected -xvs

# Run Tier-1 acceptance test (wetting_and_drying round-trip)
pytest tests/test_default_size_field.py::test_tier1_wetting_and_drying_round_trip -xvs

# Run full test suite to check for regressions
pytest tests/ -x
```

### Test 3: Verify 5 MVP Domains (No Regression)

```python
import admesh

# These synthetic domains should round-trip without issues
for domain in [
    admesh.domains.UNIT_SQUARE,
    admesh.domains.L_SHAPE,
    admesh.domains.U_SHAPE,
    admesh.domains.SQUARE_WITH_HOLE,
    admesh.domains.ANNULUS,
]:
    print(f"Testing {domain.name}...")
    mesh = admesh.triangulate(domain, h_min=0.05, h_max=1.0)
    
    # Recover domain from generated mesh
    recovered = admesh.Domain.from_mesh(mesh)
    
    # Check bbox is reasonable
    assert abs(recovered.bbox[2] - recovered.bbox[0]) > 0, "bbox has zero width"
    assert abs(recovered.bbox[3] - recovered.bbox[1]) > 0, "bbox has zero height"
    
    print(f"  ✅ {domain.name} passed")
```

## Integration Points

### Modified Code Path

1. **User calls**: `Domain.from_mesh(mesh)`
2. **Internally**:
   - `_derive_boundary_segments(mesh.elements, mesh.nodes)` → returns rings in arbitrary order
   - **[CHANGED]** Sort rings by `_ring_area(ring, mesh.nodes)` descending
   - Take `rings[0]` as outer, `rings[1:]` as holes
3. **Returns**: `Domain` with correctly identified topology

### Files Modified

- `admesh/api.py`:
  - Add helper: `_ring_area(ring_segment, nodes) -> float`
  - Modify: `_derive_boundary_segments(...)` ring-sorting line
  - Modify: `Domain.from_mesh(...)` (should be no-op if sorting happens in `_derive_boundary_segments`)

### Files Tested

- `tests/test_api.py` — new/updated unit test for `Domain.from_mesh` with multiply-connected input
- `tests/test_default_size_field.py` — existing Tier-1 test (should still pass)

## Success Criteria (Developer View)

✅ **Acceptance**: All tests pass and mesh quality is preserved.

| Criterion | Test | Expected Result |
|-----------|------|-------------|--|
| **SC-001**: WNAT bbox precision | `test_domain_from_mesh_wnat_bbox` | bbox matches source to within `1e-9` |
| **SC-002**: WNAT non-empty mesh | `test_tier2_wnat_release_gate` | `triangulate(...)` succeeds (no ValueError) |
| **SC-003**: Mesh area coverage | `test_tier1_wetting_and_drying_round_trip` | new mesh area ≥ 95% original |
| **SC-004**: MVP regression | All 5 domains pass existing tests | green test suite |
| **SC-005**: Explicit multiply-connected | `test_domain_from_mesh_multiply_connected` | longest-by-node-count ring correctly ranked as hole |

## Deployment

Once all tests pass:

1. Commit changes to `claude/pensive-goodall-r2Td2`
2. Create PR against `main`
3. Merge once CI/review approves
4. No version bump required (bug fix, not API change)
5. Note in PORTING_NOTES.md (if MATLAB divergence existed; in this case, fix aligns with MATLAB)

## Rollback Plan

If a regression surfaces:
1. Revert the ring-sorting change (1-line change in `_derive_boundary_segments`)
2. Fall back to node-count sorting (`rings.sort(key=len, reverse=True)`)
3. Mark issue for further investigation (area-based sorting can sometimes reveal hidden mesh topology bugs upstream)

## Further Reading

- [Spec](spec.md) — full feature specification
- [Plan](plan.md) — design & architecture decisions
- [Data Model](data-model.md) — entity definitions & shoelace formula
