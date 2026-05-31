# MATLAB reference (archived, unmaintained)

The original **ADMESH MATLAB library** — the source this Python package is a
faithful port of. Homed here so the reference survives even if upstream repos
move or disappear. **Not maintained, not part of the Python build/test/run
path.** Nothing imports it; it is here for provenance and side-by-side reading.

## Contents

`admesh_library/` — the OSU CHIL Lab `01_ADMESH_Library`, 13 numbered stage
directories that the Python pipeline ports 1:1:

| Dir | Python counterpart |
|---|---|
| `01_ADMESH_Routine/` | top-level `triangulate` driver |
| `02_Create_Background_Grid/` | `admesh.background_grid` |
| `03_Distance_Function/` | `admesh.distance` (+ `mexmaci64`/`mexw64` MEX) |
| `04_Curvature_Function/` | `admesh.curvature` |
| `05_Medial_Axis/` | `admesh.medial_axis` |
| `06_Bathymetry_Function/` | `admesh.bathymetry` |
| `07_Dominate_Tide/` | `admesh.dominate_tide` |
| `08_Enforce_Boundary_Conditions/` | `admesh.boundary` |
| `09_Mesh_Size/` | `admesh.mesh_size` (`MeshSizeIterativeSolver.c` MEX → Numba JIT) |
| `10_Distmesh_2d/` | `admesh.distmesh` |
| `11_Mesh_Quality/` | `admesh.quality` |
| `12_In_Polygon/` | `admesh.in_polygon` |
| `13_In_Paint_NaNs/` | `admesh.inpaint` |

`.mexmaci64` / `.mexw64` are compiled MATLAB MEX binaries (macOS / Windows); the
matching C source for the size-field solver is `09_Mesh_Size/MeshSizeIterativeSolver.c`.

## Provenance

Original authors: Conroy, C.J., Kubatko, E.J., West, D.W. — see the 2012 paper
(`papers/Conroy-2012-ADMESH.pdf`) and the upstream
[coltonjconroy/ADMESH](https://github.com/coltonjconroy/ADMESH). Vendored from the
`archive/admesh_library/` tree of `domattioli/QuADMesh-MATLAB`.
