# ADMESH version comparison — wnat_onur_boundary

Params derived from `wnat_test.14`: hmin=0.0500, hmax=0.9667, g=0.100. Fixed niter=120 (isolates per-call cost).

| Algorithm step | v0.2.1 (original Python) | v0.5.0 (Numba-optimized Python) | speedup |
|---|---|---|---|
| domain load + SDF build | 0.018 | 0.017 | 1.0x |
| SDF grid eval (eval_sdf_grid) | 1.464 | 0.271 | 5.4x |
| curvature (apply_curvature) | 0.003 | 0.003 | 1.0x |
| medial axis (apply_medial_axis) | 0.462 | 0.416 | 1.1x |
| grading solve (solve_iter, g) | 0.496 | 0.005 | 97.2x |
| size-field build (subtotal) | 2.425 | 0.695 | 3.5x |
| distmesh (point gen + relax) | 1255.0 | 46.5 | 27.0x |
| quality (mesh_quality) | 0.009 | 0.009 | 1.1x |
| **TOTAL** | **1257.5** | **47.2** | **26.6x** |

| | v0.2.1 (original Python) | v0.5.0 (Numba-optimized Python) |
|---|---|---|
| nodes | 49377 | 49377 |
| elements | 93655 | 93642 |
| distmesh iters | 120 | 120 |
| Min. Elem Quality | 0.038 | 0.010 |
| Mean Elem Quality | 0.963 | 0.962 |
| StDev Elem Quality | 0.055 | 0.057 |
