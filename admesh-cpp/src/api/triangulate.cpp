#include "admesh/admesh.hpp"

namespace admesh {
namespace stages {
    // Forward declare from distmesh.cpp
    Mesh triangulate_full(const Domain& domain, const TriangulateOptions& opts);
}

Mesh triangulate(const Domain& domain, const TriangulateOptions& opts) {
    // Main API: orchestrate the 13-stage pipeline
    // Currently: implements distmesh with Delaunay + quality
    // (Full stages 1-9 to be integrated)

    return stages::triangulate_full(domain, opts);
}

Mesh routine(const Domain& domain, const TriangulateOptions& opts) {
    return triangulate(domain, opts);
}

}
