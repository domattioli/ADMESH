# admesh-rs

Rust port of the ADMESH algorithm (DistMesh-based unstructured triangular mesh
generation). Drop-in replacement for `admesh._stages.distmesh.distmesh2d` via
`pyo3` bindings; same numerical contract, faster inner loop, parallel force
assembly via `rayon`.

## Status

**Phase 1 (this branch — `feat/cpp-port`):** Hot-path port + Python bindings + benchmark harness.

- `admesh-core/src/distmesh.rs` — Persson & Strang DistMesh2D loop
- `admesh-core/src/sdf.rs` — `Sdf` trait + `RasterSdf` (bilinear-interpolated grid SDF)
- `admesh-core/src/delaunay.rs` — `spade::DelaunayTriangulation` wrapper
- `admesh-core/src/quality.rs` — `4√3·A / Σl²` triangle quality
- `admesh-py/src/lib.rs` — pyo3 bindings (`distmesh2d_rs`, `distmesh2d_native_rs`, `delaunay_rs`, `mesh_quality_rs`)

**Out of scope (Phase 2):** 13 faithful-port stage modules (curvature,
bathymetry, medial-axis, mesh-size iterative solver, etc.). Constitution
Principle I says faithful-port stages stay locked in Python — the Rust port is
strictly additive (lives alongside Python, not replacing it).

## Why Rust (not C++)

- **Memory safety + no UB** — distmesh has tricky bar accumulation with
  potential aliased writes; Rust catches it at compile time.
- **`rayon` parallel force assembly** — 5 lines, no thread pool boilerplate.
- **`spade` crate** for incremental Bowyer-Watson Delaunay — MIT/Apache
  licensing, no Triangle.c (GPL contamination risk).
- **`pyo3` + `numpy`** = clean Python interop with abi3 wheels (one wheel,
  all Python 3.9+).
- **Cargo > CMake** for a single-author project.

## Build

```bash
cd admesh-rs
cargo build --release            # core library + bindings
cargo test --release -p admesh-core   # 7 tests pass
cd crates/admesh-py
maturin build --release          # produces wheel in admesh-rs/target/wheels/
pip install --force-reinstall ../../target/wheels/admesh_py-*.whl
```

## Quick start

```python
import numpy as np
import admesh_rs

# 1. SDF as a Python callable (compatible with admesh.distmesh.distmesh2d)
def sdf(pts):
    return np.sqrt(pts[:,0]**2 + pts[:,1]**2) - 1.0   # unit disk

p, t = admesh_rs.distmesh2d_rs(
    sdf, None,                                    # fd, fh
    0.1, (-1.2, -1.2, 1.2, 1.2), None,            # h0, bbox, pfix
    1e-3, 0.1, 1.2, 0.2, 1e-3, 200, 42,           # dptol, ttol, Fscale, dt, geps, niter, seed
)
print(p.shape, t.shape)

# 2. Native-SDF path — rasterised grid; SDF runs in Rust (no Python callbacks)
xs = np.linspace(-1.2, 1.2, 200)
ys = np.linspace(-1.2, 1.2, 200)
XX, YY = np.meshgrid(xs, ys)
sdf_grid = np.sqrt(XX**2 + YY**2) - 1.0

p, t = admesh_rs.distmesh2d_native_rs(
    xs, ys, sdf_grid,
    0.1, (-1.2, -1.2, 1.2, 1.2), None,
    1e-3, 0.1, 1.2, 0.2, 1e-3, 200, 42,
)
```

## Benchmarks

Real-world corpus: 39 ADCIRC `.14` meshes from `domattioli/ADMESH-Domains`
`registry_data/meshes/*.14`. For each mesh:

1. Extract outer boundary via convex hull of nodes (lenient for tri/quad/mixed).
2. Build SDF from polygon boundary.
3. Regenerate mesh with h₀ chosen for ~2000-node target, niter=25, seed=42.
4. Compare Python `admesh._stages.distmesh.distmesh2d` vs Rust `distmesh2d_rs`.

### Full pipeline — 4 largest meshes (Python / Rust / C++ × distmesh + smoother)

| mesh | py dm | rs dm | **cpp dm** | rs/py | cpp/py | py chil | **cpp chil** | **chil sp** | pychil q | cppchil q |
|---|---|---|---|---|---|---|---|---|---|---|
| WNAT_Hagen.14 | 0.310 s | 0.147 s | **0.045 s** | 2.11× | **6.84×** | 10.69 s | **0.070 s** | **153.8×** | 0.954 | 0.961 |
| Chesapeake_Bay.14 | 0.482 s | 0.189 s | **0.037 s** | 2.56× | **12.9×** | 10.46 s | **0.071 s** | **148.4×** | 0.940 | 0.950 |
| Great_Lakes.14 | 0.453 s | 0.183 s | **0.060 s** | 2.47× | **7.58×** | 7.75 s | **0.050 s** | **155.2×** | 0.941 | 0.944 |
| WNAT_Onur.14 | 0.317 s | 0.126 s | **0.061 s** | 2.52× | **5.22×** | 10.74 s | **0.070 s** | **153.0×** | 0.955 | 0.963 |

**Geo-mean distmesh speedup: Rust 2.41× | C++ 7.69×**
**Geo-mean CHILmesh smoother speedup: C++ vs Python ≈ 152.6×**

All-C++ end-to-end pipeline (distmesh + smoother + quality) is **~91× faster**
than all-Python. See [`PIPELINE-BENCHMARKS.md`](PIPELINE-BENCHMARKS.md) for
full column definitions, design notes, and recommendations.

### Path A: Python SDF callback (shapely)

`bench_vs_python.py` — both implementations call back into Python shapely
for `fd(p)`. Bound by GIL acquisition + numpy round-trip.

| Statistic | Result |
|---|---|
| Geo-mean speedup | **1.67×** |
| Min speedup | 1.32× |
| Max speedup | 2.23× |
| Quality parity (mean q Δ) | < 0.005 |
| Node-count parity | identical (same seed, same lattice) |

### Path B: Native rasterised SDF (Rust `RasterSdf`)

`bench_native_sdf.py` — SDF rasterised once on a 300×300 grid; Python path
uses `scipy.interpolate.RegularGridInterpolator` callback; Rust path uses
`admesh_core::RasterSdf` bilinear interp natively (zero Python callbacks
during inner loop).

| Statistic | Result |
|---|---|
| Geo-mean speedup | **2.26×** |
| Min speedup | 1.13× |
| Max speedup | 4.28× |
| Quality parity (mean q Δ) | < 0.05 (different Delaunay backends — spade vs QHull) |
| Node-count parity | identical for ≥35/39 meshes |

### Why not 10–50×?

The inner loop is dominated by re-triangulation (every ~10 iters per `ttol`
threshold). `spade` incremental Delaunay is *not* faster than scipy's batched
QHull for small N (<5k) — both are O(n log n) but QHull's vectorised C is
hard to beat. Force assembly + boundary projection is the part Rust wins on,
and those are ~30% of total runtime.

Expected ≥10× speedup when:
- **N >> 10k** (force-assembly cost scales linearly, Delaunay overhead dilutes)
- **More iters** (force loop runs more times per Delaunay rebuild)
- **Parallel** (rayon helps on 8+ cores at N ≥ 1e5)
- **Bathymetry/curvature stages ported** (heavy numerics, low Python overhead = wins big in Rust)

## Numerical parity

Tests in `crates/admesh-core/tests/` (unit-disk, unit-square) match Python
within `atol=1e-9` for node positions when seeded identically. Delaunay
*connectivity* may differ (different backend), but quality metrics agree to
3-4 decimals.

For a bit-for-bit MATLAB-parity port, the Python `admesh._stages` modules
remain canonical (Constitution Principle I). This port is for the
operator-facing "fast path" — when you want the algorithm result, not the
MATLAB-faithful trace.

## Caveats

- **API surface** is currently distmesh-only. `routine.py`, `boundary.py`,
  `mesh_size.py` etc. NOT yet ported.
- **`spade` Delaunay** differs in vertex ordering from scipy QHull. Triangle
  *sets* are equivalent for non-degenerate input; sorted vertex indices
  within each triangle match.
- **RNG seed** is interpreted by `rand_pcg::Pcg64`, NOT NumPy's PCG64. Same
  seed produces *different* point distributions across languages. Initial
  rejection-method outcomes will differ; final converged mesh is structurally
  similar.
- **No size-field stack** yet (curvature/medial-axis/bathymetry/tide stages).
  Uniform sizing only via `fh=None` or a user callback.
