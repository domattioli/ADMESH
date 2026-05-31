#include "admesh/admesh.hpp"
#include <Eigen/Dense>
#include <cmath>

namespace admesh {
namespace stages {

Mesh quality(const Mesh& m) {
    Mesh result = m;
    if (m.elements.rows() == 0) {
        result.quality.resize(0);
        return result;
    }
    result.quality.resize(m.elements.rows());
    for (Eigen::Index t = 0; t < m.elements.rows(); ++t) {
        int i0 = m.elements(t, 0), i1 = m.elements(t, 1), i2 = m.elements(t, 2);
        Eigen::Vector2d p0 = m.nodes.row(i0), p1 = m.nodes.row(i1), p2 = m.nodes.row(i2);
        double a = (p1 - p0).norm(), b = (p2 - p1).norm(), c = (p0 - p2).norm();
        double area = 0.5 * std::abs((p1 - p0).x() * (p2 - p0).y() - (p1 - p0).y() * (p2 - p0).x());
        if (area < 1e-14) { result.quality(t) = 0.0; continue; }
        double s = (a + b + c) / 2.0;
        double inrad = area / s, circrad = (a * b * c) / (4.0 * area);
        result.quality(t) = 2.0 * (inrad / circrad);
    }
    return result;
}

}
}
