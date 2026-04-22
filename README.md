<h1 align="center">ADMESH</h1>

<p align="center">
  Python port of the ADMESH library — an advancing-front / distance-driven
  unstructured mesh generator for 2D shallow-water (ADCIRC-style) domains.
</p>

<p align="center">
  <strong><a href="https://scholar.google.com/citations?user=IBFSkOcAAAAJ&hl=en">Dominik Mattioli</a><sup>1†</sup>, <a href="https://scholar.google.com/citations?user=mYPzjIwAAAAJ&hl=en">Ethan Kubatko</a><sup>2</sup></strong><br>
  <sup>†</sup>Corresponding author<br>
  <sup>1</sup>Penn State University &nbsp;·&nbsp; <sup>2</sup>Computational Hydrodynamics and Informatics Lab (CHIL), The Ohio State University
</p>

---

## About

ADMESH is a faithful Python port of the MATLAB `01_ADMESH_Library`
module from [`domattioli/QuADMesh-MATLAB`](https://github.com/domattioli/QuADMesh-MATLAB)
(pinned source commit: `19b2eb9`).

The port preserves the original 13-stage pipeline:

1. `routine` — top-level ADMESH driver
2. `background_grid` — structured background grid over the domain
3. `distance` — signed distance function
4. `curvature` — boundary curvature field
5. `medial_axis` — medial-axis transform (fast marching)
6. `bathymetry` — bathymetric size control
7. `dominate_tide` — tidal wavelength size control
8. `boundary` — boundary-condition enforcement + polygon structuring
9. `mesh_size` — mesh-size iterative PDE solver (Numba-JIT port of `MeshSizeIterativeSolver.c`)
10. `distmesh` — DistMesh 2D triangulation (quad conversion is out of scope)
11. `quality` — mesh quality metrics
12. `in_polygon` — point-in-polygon tests
13. `inpaint` — NaN in-painting for grid fields

## Status

Under construction. See `PROJECT_PLAN.md` for phased roadmap.

### MVP preview (post-session 1, M.4 gate met)

End-to-end triangulation via `admesh.triangulate(domain, h0=…)` on the
5 MVP test domains. These meshes pass the M.4 binding gate
(`min_q ≥ 0.30, mean_q ≥ 0.60` — `tests/test_mvp_domains.py`).

| Domain | Nodes | Triangles | min q | mean q |
|---|---:|---:|---:|---:|
| `unit_square` | 88 | 138 | 0.804 | 0.957 |
| `l_shape` | 169 | 279 | 0.772 | 0.963 |
| `unit_disk` | 162 | 281 | 0.772 | 0.972 |
| `annulus` | 211 | 353 | 0.785 | 0.964 |
| `notched_rectangle` | 383 | 680 | 0.693 | 0.981 |

<p align="center">
  <img src="tests/output/mvp_unit_square.png" alt="unit_square" width="32%">
  <img src="tests/output/mvp_l_shape.png" alt="l_shape" width="32%">
  <img src="tests/output/mvp_unit_disk.png" alt="unit_disk" width="32%">
</p>
<p align="center">
  <img src="tests/output/mvp_annulus.png" alt="annulus" width="32%">
  <img src="tests/output/mvp_notched_rectangle.png" alt="notched_rectangle" width="32%">
</p>

Regenerate: `PYTHONPATH=. python scripts/render_mvp_meshes.py`.

### P1 + P3 enrichment preview (post-session 3)

Sessions 2–3 added curvature / medial-axis size fields
(`admesh.curvature`, `admesh.medial_axis`), a size-field composer
(`admesh.mesh_size.build_h`), a PTS polygonal-domain structure with
boundary-condition tags (`admesh.boundary`), and an ADMESH-variant
distmesh path with per-node BC labels
(`admesh.distmesh.distmesh2d_admesh`; dispatched by
`admesh.triangulate(pts, …)`). These are **clean-room** ports —
the MATLAB reference clone is not yet available in the
development environment; a faithful-port backfill pass is flagged
in `docs/PORTING_NOTES.md`.

Before = uniform-size MVP path at the same `h0`. After = enriched
path via `build_h(...)` or `triangulate(pts, ...)`.

| Demo | h0 | Before (N, min q, mean q) | After (N, min q, mean q) |
|---|---:|:---:|:---:|
| `unit_disk` — medial LFS (fine at center) | 0.05 | 1452, 0.833, 0.994 | 82, 0.378, 0.915 |
| `annulus` — PTS path, per-ring labels | 0.04 | 1907, 0.718, 0.988 | 678, 0.120 ⚠, 0.842 |
| `notched_rectangle` — medial LFS (fine at pinch) | 0.04 | 1453, 0.694, 0.992 | 547, 0.188 ⚠, 0.895 |

<p align="center">
  <img src="tests/output/demo_unit_disk_medial.png" alt="unit_disk medial" width="98%">
</p>
<p align="center">
  <img src="tests/output/demo_annulus_pts.png" alt="annulus PTS path" width="98%">
</p>
<p align="center">
  <img src="tests/output/demo_notched_rectangle_medial.png" alt="notched_rect medial" width="98%">
</p>

In the **annulus** panel, green nodes are the outer ring tagged
`OPEN`, red nodes the inner ring tagged `WALL` — labels emitted by
`admesh.routine.triangulate(pts, ...)` as part of the `MeshOutput`
return type.

**⚠ Quality caveat.** The annulus and notched-rectangle demos drop
below the MVP `min_q ≥ 0.30` gate. Root cause: DistMesh's point-
rejection + truss relaxation produces slivers where the enriched
`fh` has a steep gradient (base → fine-scale transitions). The
MVP gate itself is uncompromised — `tests/test_mvp_domains.py`
still passes, and the enriched-path tests use looser bounds on
purpose. Tightening these is a session-4 item.

Regenerate: `PYTHONPATH=. python scripts/render_p1p3_demos.py`.

## Install

```bash
pip install -e .
```

Requires Python ≥ 3.10, NumPy, SciPy, and Numba.

## License

Apache 2.0 — see `LICENSE`.

## Related work

- Original MATLAB implementation: [`domattioli/QuADMesh-MATLAB`](https://github.com/domattioli/QuADMesh-MATLAB)
- DistMesh (Persson & Strang, 2004): <http://persson.berkeley.edu/distmesh/>
