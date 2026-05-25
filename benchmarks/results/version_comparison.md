# ADMESH version comparison — wnat_onur_boundary

Params derived from `wnat_test.14`: hmin=0.1187, hmax=0.9667, g=0.209. Fixed niter=120 (isolates per-call cost).

| Algorithm step | v0.2.1 (original Python) | v0.5.0 (Numba-optimized Python) | speedup |
|---|---|---|---|
| domain load + SDF build | 0.018 | 0.018 | 1.0x |
| SDF grid eval (eval_sdf_grid) | 1.497 | 0.277 | 5.4x |
| curvature (apply_curvature) | 0.002 | 0.003 | 0.9x |
| medial axis (apply_medial_axis) | 0.466 | 0.423 | 1.1x |
| grading solve (solve_iter, g) | 0.484 | 0.006 | 75.4x |
| size-field build (subtotal) | 2.450 | 0.709 | 3.5x |
| distmesh (point gen + relax) | 292.0 | 9.077 | 32.2x |
| quality (mesh_quality) | 0.002 | 0.002 | 1.0x |
| **TOTAL** | **294.5** | **9.805** | **30.0x** |

| | v0.2.1 (original Python) | v0.5.0 (Numba-optimized Python) |
|---|---|---|
| nodes | 10473 | 10473 |
| elements | 18843 | 18845 |
| distmesh iters | 120 | 120 |
| Min. Elem Quality | 0.020 | 0.023 |
| Mean Elem Quality | 0.940 | 0.940 |
| StDev Elem Quality | 0.088 | 0.087 |
