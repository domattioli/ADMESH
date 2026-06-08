// pybind11 binding for ADMESH C++ core (Phase 5: US2 Python facade)
// Wraps Domain, Mesh, triangulate() for drop-in Python compatibility

#include <pybind11/pybind11.h>
#include <pybind11/eigen.h>
#include <Eigen/Dense>

namespace py = pybind11;

// Stub: reference the src/cpp headers if integrated
// For now, define minimal Python-visible types

struct Domain {
    Eigen::MatrixX2d vertices;
    Eigen::MatrixX2i segments;
    std::array<double, 4> bbox;
};

struct Mesh {
    Eigen::MatrixX2d nodes;
    Eigen::MatrixX3i elements;
    Eigen::VectorXd quality;
};

struct TriangulateOptions {
    double h_min = 0.0;
    double h_max = 0.1;
    unsigned seed = 0;
    int max_iter = 0;
    bool quality_gate = true;
};

// Forward: C++ triangulate() would be called here
// For now, Python fallback via _backend selector
Mesh triangulate_cpp(const Domain& domain, const TriangulateOptions& opts) {
    Mesh m;
    m.nodes = domain.vertices;
    m.elements.resize(0, 3);
    m.quality.resize(0);
    return m;
}

PYBIND11_MODULE(_admesh_binding, m) {
    m.doc() = "ADMESH C++ core binding (Phase 5: Python facade)";

    py::class_<Domain>(m, "Domain")
        .def(py::init<>())
        .def_readwrite("vertices", &Domain::vertices)
        .def_readwrite("segments", &Domain::segments)
        .def_readwrite("bbox", &Domain::bbox);

    py::class_<Mesh>(m, "Mesh")
        .def(py::init<>())
        .def_readwrite("nodes", &Mesh::nodes)
        .def_readwrite("elements", &Mesh::elements)
        .def_readwrite("quality", &Mesh::quality);

    py::class_<TriangulateOptions>(m, "TriangulateOptions")
        .def(py::init<>())
        .def_readwrite("h_min", &TriangulateOptions::h_min)
        .def_readwrite("h_max", &TriangulateOptions::h_max)
        .def_readwrite("seed", &TriangulateOptions::seed)
        .def_readwrite("max_iter", &TriangulateOptions::max_iter)
        .def_readwrite("quality_gate", &TriangulateOptions::quality_gate);

    m.def("triangulate", &triangulate_cpp, "Triangulate a domain");
}
