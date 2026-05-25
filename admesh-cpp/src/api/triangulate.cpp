#include "admesh/admesh.hpp"
#include <Eigen/Dense>
#include <cmath>
#include <algorithm>
#include <numeric>

namespace admesh {

// Forward: stage implementations
namespace stages {
    Mesh quality(const Mesh& m);
}

// Quality measure: equilateral element → 1.0, degenerate → 0.0
static double element_quality(const Eigen::Vector2d& p0, const Eigen::Vector2d& p1,
                               const Eigen::Vector2d& p2) {
    double a = (p1 - p0).norm();
    double b = (p2 - p1).norm();
    double c = (p0 - p2).norm();
    double area = 0.5 * std::abs((p1 - p0).x() * (p2 - p0).y() -
                                 (p1 - p0).y() * (p2 - p0).x());
    double s = (a + b + c) / 2.0;
    double inradius = (s > 1e-14) ? area / s : 0.0;
    double circumradius = (a * b * c > 1e-14) ? (a * b * c) / (4 * area) : 1e14;
    if (circumradius < 1e-14) return 0.0;
    return inradius / circumradius;
}

Mesh triangulate(const Domain& domain, const TriangulateOptions& opts) {
    // US1 native triangulation orchestrator.
    // Implements a minimal 13-stage pipeline:
    // 1. Accept domain (boundary + optional SDF)
    // 2. Generate initial point distribution via distmesh logic
    // 3. Build Delaunay triangulation
    // 4. Compute per-element quality
    // 5. Return mesh

    Mesh mesh;

    // For now: use Delaunay on boundary + a few interior points
    // (Real implementation would call the full 13-stage pipeline per spec 019)

    // Copy boundary vertices as initial nodes
    int n_bnd = domain.vertices.rows();
    Eigen::MatrixX2d pts = domain.vertices;

    // Add a few interior points (rough approximation of distmesh)
    if (n_bnd >= 3) {
        Eigen::Vector2d bbox_min = pts.colwise().minCoeff();
        Eigen::Vector2d bbox_max = pts.colwise().maxCoeff();
        Eigen::Vector2d bbox_range = bbox_max - bbox_min;
        double spacing = bbox_range.norm() / 5.0;

        Eigen::MatrixX2d interior_pts;
        int cols = std::max(2, (int)(bbox_range.x() / spacing));
        int rows = std::max(2, (int)(bbox_range.y() / spacing));
        interior_pts.resize(cols * rows, 2);

        int idx = 0;
        for (int i = 0; i < cols; ++i) {
            for (int j = 0; j < rows; ++j) {
                interior_pts(idx, 0) = bbox_min.x() + i * spacing;
                interior_pts(idx, 1) = bbox_min.y() + j * spacing;
                ++idx;
            }
        }

        // Concatenate boundary + interior
        Eigen::MatrixX2d all_pts(n_bnd + interior_pts.rows(), 2);
        all_pts.topRows(n_bnd) = pts;
        all_pts.bottomRows(interior_pts.rows()) = interior_pts;
        pts = all_pts;
    }

    mesh.nodes = pts;

    // Stub Delaunay: generate triangles connecting sequential points
    // (Real: use Triangle library or compute convex hull + Delaunay)
    int n = pts.rows();
    if (n >= 3) {
        std::vector<Eigen::Vector3i> tris;
        for (int i = 0; i < n - 2; ++i) {
            tris.push_back({i, i + 1, i + 2});
        }
        mesh.elements.resize(tris.size(), 3);
        for (size_t i = 0; i < tris.size(); ++i) {
            mesh.elements.row(i) = tris[i].transpose();
        }
    }

    // Compute per-element quality
    mesh.quality.resize(mesh.elements.rows());
    for (Eigen::Index i = 0; i < mesh.elements.rows(); ++i) {
        int i0 = mesh.elements(i, 0);
        int i1 = mesh.elements(i, 1);
        int i2 = mesh.elements(i, 2);
        mesh.quality(i) = element_quality(mesh.nodes.row(i0),
                                          mesh.nodes.row(i1),
                                          mesh.nodes.row(i2));
    }

    mesh.boundaries = domain.boundaries;
    mesh.bathymetry = domain.bathymetry;

    return mesh;
}

Mesh routine(const Domain& domain, const TriangulateOptions& opts) {
    return triangulate(domain, opts);
}

}
