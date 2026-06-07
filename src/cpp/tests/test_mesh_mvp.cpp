#include "admesh/admesh.hpp"
#include <iostream>

int main() {
    admesh::Domain domain;
    domain.vertices.resize(3, 2);
    domain.vertices << 0, 0, 1, 0, 0.5, 1;

    admesh::TriangulateOptions opts;
    opts.h_max = 0.1;

    auto mesh = admesh::triangulate(domain, opts);

    std::cout << "Nodes: " << mesh.nodes.rows() << std::endl;
    std::cout << "Elements: " << mesh.elements.rows() << std::endl;

    return 0;
}
