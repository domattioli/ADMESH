# C++ Extensions for ADMESH v1.0.0 (Alpha)

Target: pybind11-wrapped C++ distmesh2d solver using Eigen for iterative point placement.

## Architecture

- `distmesh_cpp.cpp` — main solver loop (Eigen matrix operations)
- `distmesh_module.cpp` — pybind11 binding layer
- `CMakeLists.txt` — build config

## Integration path

1. Build: `pip install -e . --no-build-isolation` (triggers `setup.py` → pybind11 build)
2. Runtime: `distmesh.py` detects `_cpp.distmesh` and dispatches to C++ path if available
3. Fallback: pure-Python Numba path if C++ not compiled (default on `main`)

## Performance target

- distmesh2d: 46.5s (Numba) → 12.0s (C++) = 3.875x improvement
- Total WNAT: 47.2s → 12.7s = 3.7x improvement

## Status

Pre-alpha. Branch: `cpp-distmesh` (development only, not shipped on PyPI until v1.0.0 stable).
