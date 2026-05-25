# Quickstart: Full C++ Rewrite of ADMESH

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-05-25

Three consumer paths, one C++ source of truth.

## 1. Native C++ consumer (no Python) — US1

```bash
cd admesh-cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
ctest --test-dir build          # standalone parity + smoke, no Python (SC-002)
cmake --install build --prefix /opt/admesh
```

```cpp
#include <admesh/admesh.hpp>
int main() {
  auto domain = admesh::load_domain("wnat.14");      // fort.14 / .json / .toml
  admesh::TriangulateOptions opt; opt.h_min = 0.05;
  auto mesh = admesh::triangulate(domain, opt);
  admesh::write_fort14(mesh, "out.14");              // byte-faithful round-trip
}
```

## 2. Python user (drop-in, accelerated) — US2

```bash
pip install admesh2D          # prebuilt wheel: C++ core active, no compiler ran
python -c "import admesh; print(admesh.triangulate.__doc__)"
```

```python
import admesh
from admesh import domains

mesh = admesh.triangulate(domains.UNIT_DISK, h_max=0.1)   # auto → C++ core
mesh.to_fort14("disk.14")

# Debug A/B: force a backend
m_py  = admesh.triangulate(domains.UNIT_DISK, h_max=0.1, backend="python")
m_cpp = admesh.triangulate(domains.UNIT_DISK, h_max=0.1, backend="cpp")
# counts + quality match within parity tolerance (SC-005)
```

No-toolchain fallback (no wheel, no compiler) still meshes via Numba (FR-004):

```bash
ADMESH_BACKEND=python python my_mesh.py    # or auto-degrades when C++ module absent
```

## 3. Maintainer porting a stage — US3

```bash
# Augment the stage's existing parity test, then:
pytest tests/test_distance.py -q            # runs BOTH python + cpp params vs same .npz
```

A stage is "done" only when its `cpp` param is green against the MATLAB fixture
at the stage's parity mode (bit-parity, or relaxed-with-rationale). See
[contracts/parity-gate.md](./contracts/parity-gate.md).

## Validate the whole feature

```bash
pytest tests/ -q                                   # SC-001: full suite green, C++-backed
cd admesh-cpp && ctest --test-dir build            # SC-002: standalone C++, no Python
python benchmarks/compare_versions.py --hmin 0.05 --g 0.10 --niter 120 \
    --ref current="C++" --ref v0.5.0="Numba"       # SC-003: per-stage + e2e speedup, no threshold
```

## Success snapshot

| Criterion | Check |
|---|---|
| SC-001 | `pytest tests/ -q` green, zero regressions |
| SC-002 | `ctest` meshes MVP + WNAT, no Python |
| SC-003 | benchmark reports per-stage + e2e speedup (measurement, not a target) |
| SC-004 | wheels import-and-mesh + standalone lib builds on every target |
| SC-005 | identical counts + quality-within-tol vs Numba on MVP + WNAT |
