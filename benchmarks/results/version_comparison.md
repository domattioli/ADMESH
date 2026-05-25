# ADMESH version comparison — wnat_onur_boundary

Params derived from `wnat_test.14`: hmin=0.1187, hmax=0.9667, g=0.209. Fixed niter=120 (isolates per-call cost).

| Algorithm step | v0.5.0 (Numba) | speedup |
|---|---|---|
| domain load + SDF build | 0.016 | 1.0x |
| SDF grid eval (eval_sdf_grid) | 0.239 | 1.0x |
| curvature (apply_curvature) | 0.002 | 1.0x |
| medial axis (apply_medial_axis) | 0.375 | 1.0x |
| grading solve (solve_iter, g) | 0.006 | 1.0x |
| size-field build (subtotal) | 0.622 | 1.0x |
| distmesh (point gen + relax) | 8.223 | 1.0x |
| quality (mesh_quality) | 0.002 | 1.0x |
| **TOTAL** | **8.861** | **1.0x** |

| | v0.5.0 (Numba) |
|---|---|
| nodes | 10473 |
| elements | 18845 |
| distmesh iters | 120 |
| Min. Elem Quality | 0.023 |
| Mean Elem Quality | 0.940 |
| StDev Elem Quality | 0.087 |
