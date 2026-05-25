# ADMESH version comparison — wnat_onur_boundary

Params derived from `wnat_test.14`: hmin=0.0500, hmax=0.9667, g=0.100. Fixed niter=120 (isolates per-call cost).

| Algorithm step | v1.0.0 (C++ distmesh kernel) | speedup |
|---|---|---|
| domain load + SDF build | 0.018 | 1.0x |
| SDF grid eval (eval_sdf_grid) | 1.305 | 1.0x |
| curvature (apply_curvature) | 0.003 | 1.0x |
| medial axis (apply_medial_axis) | 1.922 | 1.0x |
| grading solve (solve_iter, g) | 0.006 | 1.0x |
| size-field build (subtotal) | 3.236 | 1.0x |
| distmesh (point gen + relax) | 25.9 | 1.0x |
| quality (mesh_quality) | 0.009 | 1.0x |
| **TOTAL** | **29.1** | **1.0x** |

| | v1.0.0 (C++ distmesh kernel) |
|---|---|
| nodes | 49375 |
| elements | 93645 |
| distmesh iters | 120 |
| Min. Elem Quality | 0.041 |
| Mean Elem Quality | 0.962 |
| StDev Elem Quality | 0.055 |
