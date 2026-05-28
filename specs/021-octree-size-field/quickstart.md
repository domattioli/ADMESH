# Quickstart: Octree Background Grid (spec 021)

Developer-facing walkthrough for validating the feature. The **user-facing** call is unchanged — that is the point (Contract C1).

## User perspective (no API change)

```python
import admesh
mesh = admesh.triangulate("coastline.14", h_min=20.0, h_max=5000.0)
```

On a multi-scale domain (a narrow inlet inside a large basin), the mesh now resolves the medial axis inside the inlet and spans it with ≥ 4 elements — where the previous uniform-grid build left it under-resolved. No new arguments are required; the octree is the default substrate with an automatic uniform-grid fallback.

## Developer validation steps

1. **Build the synthetic multi-scale benchmark** (new fixture): a basin of extent `L` with a thin inlet of width `W`, `L/W ≥ 1000`.
2. **Octree resolves the medial axis** (SC-001):
   - `fh = admesh._stages.mesh_size.build_h(domain, hmin=W/8, hmax=L/20, medial_scale=...)`
   - Assert the medial-axis distance is finite on inlet-interior leaves and the target `h` there ≈ inlet half-width / R (not `h_max`).
3. **Uniform baseline fails** (SC-001 contrast): build the same domain on the uniform grid at a spacing tractable for `L`; assert the medial axis inside the inlet is empty (boundary-distance-only fallback).
4. **≥ 4 elements per feature** (SC-002, "target + verify"): triangulate; for each known feature, count element edges crossing its narrowest transverse extent; assert ≥ 4.
5. **Below-floor warning** (SC-003): give a feature narrower than `h_min`; assert a `UserWarning` names the under-resolved feature.
6. **Sub-quadratic growth** (SC-004): build for ratios 10/100/1000; record leaf counts; assert sub-quadratic and ≥ 10× fewer leaves than uniform-at-finest at 1000.
7. **Fallback** (FR-018): force `build_octree` to fail; assert `build_h` warns and still returns a valid `fh` via the uniform path.
8. **Faithful-port regression** (Principle III): `pytest tests/ -q` green; stages NOT on the octree reproduce their fixtures unchanged.
9. **Gradient-limit parity** (Principle II): `solve_iter_graph` `_py` vs `_nb` agree to `atol=1e-10`.

## Governance step (gate)

Before this lands in a tagged release, merge the Constitution amendment (v2.0.0) carving `background_grid` / `medial_axis` / `mesh_size` out of Principle I, with a Sync Impact Report (FR-015, Contract C7).

## What to look at

- `admesh/_stages/octree_grid.py` (new), and the three modified `_stages/` modules.
- `specs/021-octree-size-field/contracts/octree-size-field.md` for the interface contracts.
- `specs/021-octree-size-field/research.md` R4 for the medial-axis-on-octree rationale.
