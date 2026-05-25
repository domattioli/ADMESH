# ADMESH version comparison — wnat_onur_boundary

Operating point: hmin=0.05, hmax=0.967, g=0.10, niter=120 (isolates per-call cost). ~49 k nodes.

| Algorithm step | v1.0.0 (C++ + Triangle) |
|---|---|
| domain load + SDF build | 0.021 |
| SDF grid eval (eval_sdf_grid) | 0.361 |
| curvature (apply_curvature) | 0.003 |
| medial axis (apply_medial_axis) | 0.451 |
| grading solve (solve_iter, g) | 0.005 |
| size-field build (subtotal) | 0.821 |
| distmesh (point gen + relax) | 25.559 |
| quality (mesh_quality) | 0.008 |
| **TOTAL** | **26.409** |

| | v1.0.0 (C++ + Triangle) |
|---|---|
| nodes | 49192 |
| elements | 93247 |
| distmesh iters | 120 |
| Min. Elem Quality | 0.050 |
| Mean Elem Quality | 0.963 |
| StDev Elem Quality | 0.054 |
