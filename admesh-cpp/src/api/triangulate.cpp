#include "admesh/admesh.hpp"

namespace admesh {

Mesh triangulate(const Domain& domain, const TriangulateOptions& opts) {
    Mesh m;
    m.nodes = domain.vertices;
    m.elements.resize(0, 3);
    m.quality.resize(0);
    return m;
}

Mesh routine(const Domain& domain, const TriangulateOptions& opts) {
    return triangulate(domain, opts);
}

}
