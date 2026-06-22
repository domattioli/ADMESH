# Contract: C++ Public API (`admesh-cpp`)

The native surface a C++ consumer links against — **no Python in the process**
(FR-001, US1). Header: `include/admesh/admesh.hpp`. Namespace: `admesh`.

## Types

```cpp
namespace admesh {

struct BoundarySegment {
  Eigen::VectorXi node_indices;   // 0-based
  int bc_type;                    // ADCIRC IBTYPE
};

struct Domain {
  Eigen::MatrixX2d vertices;
  Eigen::MatrixX2i segments;
  std::vector<BoundarySegment> boundaries;
  std::array<double,4> bbox;
  std::function<Eigen::VectorXd(const Eigen::MatrixX2d&)> sdf;   // optional; batched (R6)
  std::optional<Eigen::VectorXd> bathymetry;
};

struct Mesh {
  Eigen::MatrixX2d nodes;
  Eigen::MatrixX3i elements;
  std::vector<BoundarySegment> boundaries;
  std::optional<Eigen::VectorXd> bathymetry;
  Eigen::VectorXd quality;
};

struct TriangulateOptions {
  double h_min = 0.0;             // 0 ⇒ unset
  double h_max = 0.0;
  std::function<Eigen::VectorXd(const Eigen::MatrixX2d&)> size_field;  // optional, batched
  unsigned seed = 0;
  int max_iter = 0;               // 0 ⇒ stage default
  bool quality_gate = true;
};

}  // namespace admesh
```

## Functions

```cpp
// Mesh a domain. Deterministic given (domain, options, seed).
Mesh triangulate(const Domain& domain, const TriangulateOptions& opts);

// Domain construction from file — required for the no-Python consumer.
Domain load_domain(const std::filesystem::path& path);   // fort.14 / .json / .toml by extension

// fort.14 I/O — byte-faithful round-trip incl. IBTYPE 3/4/13/24 (FR-008).
Mesh   read_fort14(const std::filesystem::path& path);
void   write_fort14(const Mesh& mesh, const std::filesystem::path& path);
```

## Guarantees

- **No Python**: links + runs with zero Python runtime (SC-002).
- **Determinism**: identical `(Domain, TriangulateOptions, seed)` ⇒ identical mesh
  on a given platform; cross-platform within parity tolerance (SC-005, R3).
- **fort.14 round-trip**: `write_fort14(read_fort14(f))` is byte-faithful,
  paired-edge/weir records preserved (FR-008, US1 scenario 2).
- **No `-ffast-math`** on bit-parity translation units; reduction order pinned (FR-005).

## CMake consumption

```cmake
find_package(admesh REQUIRED)            # installed
target_link_libraries(myapp PRIVATE admesh::admesh)
# or
add_subdirectory(admesh-cpp)
```
