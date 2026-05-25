# ADMESH version comparison — wnat_onur_boundary

Params derived from `wnat_test.14`: hmin=0.1187, hmax=0.9667, g=0.209. Fixed niter=120 (isolates per-call cost).

| Algorithm step | v1.0.0 (C++ distmesh) | speedup |
|---|---|---|
| domain load + SDF build | 0.017 | 1.0x |
| SDF grid eval (eval_sdf_grid) | 0.267 | 1.0x |
| curvature (apply_curvature) | 0.003 | 1.0x |
| medial axis (apply_medial_axis) | 0.409 | 1.0x |
| grading solve (solve_iter, g) | 0.006 | 1.0x |
| size-field build (subtotal) | 0.685 | 1.0x |
| distmesh (point gen + relax) | 8.520 | 1.0x |
| quality (mesh_quality) | 0.002 | 1.0x |
| **TOTAL** | **9.224** | **1.0x** |

| | v1.0.0 (C++ distmesh) |
|---|---|
| nodes | 10473 |
| elements | 18839 |
| distmesh iters | 120 |
| Min. Elem Quality | 0.015 |
| Mean Elem Quality | 0.940 |
| StDev Elem Quality | 0.089 |
