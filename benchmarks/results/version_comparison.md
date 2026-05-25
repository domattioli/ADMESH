# ADMESH version comparison — wnat_onur_boundary

Params derived from `wnat_test.14`: hmin=0.1330, hmax=0.9667, g=0.209. Fixed niter=120 (isolates per-call cost).

| Algorithm step | v0.2.1 (original Python) | v0.5.0 (Numba-optimized Python) | speedup |
|---|---|---|---|
| domain load + SDF build | 0.018 | 0.017 | 1.0x |
| SDF grid eval (eval_sdf_grid) | 1.558 | 0.271 | 5.8x |
| curvature (apply_curvature) | 0.002 | 0.003 | 0.9x |
| medial axis (apply_medial_axis) | 0.477 | 0.425 | 1.1x |
| grading solve (solve_iter, g) | 0.498 | 0.007 | 75.6x |
| size-field build (subtotal) | 2.536 | 0.705 | 3.6x |
| distmesh (point gen + relax) | 246.9 | 7.662 | 32.2x |
| quality (mesh_quality) | 0.002 | 0.001 | 1.1x |
| **TOTAL** | **249.5** | **8.386** | **29.8x** |

| | v0.2.1 (original Python) | v0.5.0 (Numba-optimized Python) |
|---|---|---|
| nodes | 8736 | 8735 |
| elements | 15654 | 15644 |
| distmesh iters | 120 | 120 |
| Min. Elem Quality | 0.017 | 0.009 |
| Mean Elem Quality | 0.931 | 0.932 |
| StDev Elem Quality | 0.100 | 0.099 |
