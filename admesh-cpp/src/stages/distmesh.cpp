#include "admesh/admesh.hpp"
#include "../vendor/delaunator.hpp"
#include <Eigen/Dense>
#include <cmath>
#include <random>
#include <vector>
#include <algorithm>

namespace admesh {
namespace stages {

// distmesh2d: 2D Delaunay-based mesh generation via force-balance relaxation
// Inputs: domain boundary, size field h(x,y), options
// Output: triangulated mesh

Mesh distmesh(const Mesh& m_in) {
    // TODO: implement full distmesh
    // For now: return input (placeholder)
    return m_in;
}

// Standalone triangulate with full pipeline
Mesh triangulate_full(const Domain& domain, const TriangulateOptions& opts) {
    // Generate boundary nodes from domain vertices
    Eigen::MatrixX2d p = domain.vertices;
    int n_bnd = p.rows();

    // Generate interior points on regular grid within bbox
    std::array<double, 4> bbox = domain.bbox;
    double h_max = opts.h_max > 0 ? opts.h_max : 0.1;
    double spacing = h_max * std::sqrt(3) / 2;  // hex packing

    Eigen::MatrixX2d interior;
    {
        std::vector<Eigen::Vector2d> pts;
        for (double x = bbox[0] + spacing; x < bbox[1]; x += spacing) {
            for (double y = bbox[2] + spacing; y < bbox[3]; y += spacing) {
                Eigen::Vector2d pt(x, y);
                // Rough point-in-polygon check (simplified)
                if (x > bbox[0] && x < bbox[1] && y > bbox[2] && y < bbox[3]) {
                    pts.push_back(pt);
                }
            }
        }
        interior.resize(pts.size(), 2);
        for (size_t i = 0; i < pts.size(); ++i) {
            interior.row(i) = pts[i];
        }
    }

    // Combine boundary + interior
    Eigen::MatrixX2d all_p(n_bnd + interior.rows(), 2);
    all_p.topRows(n_bnd) = p;
    all_p.bottomRows(interior.rows()) = interior;
    p = all_p;

    // Delaunay triangulation (via delaunator header-only lib)
    std::vector<double> coords;
    for (int i = 0; i < p.rows(); ++i) {
        coords.push_back(p(i, 0));
        coords.push_back(p(i, 1));
    }

    delaunator::Delaunator triangulator(coords);

    // Extract triangles
    Mesh mesh;
    mesh.nodes = p;
    mesh.elements.resize(triangulator.triangles.size() / 3, 3);
    for (size_t i = 0; i < triangulator.triangles.size(); i += 3) {
        mesh.elements(i / 3, 0) = triangulator.triangles[i];
        mesh.elements(i / 3, 1) = triangulator.triangles[i + 1];
        mesh.elements(i / 3, 2) = triangulator.triangles[i + 2];
    }

    // Compute quality
    mesh.quality.resize(mesh.elements.rows());
    for (Eigen::Index t = 0; t < mesh.elements.rows(); ++t) {
        int i0 = mesh.elements(t, 0), i1 = mesh.elements(t, 1), i2 = mesh.elements(t, 2);
        Eigen::Vector2d p0 = mesh.nodes.row(i0), p1 = mesh.nodes.row(i1), p2 = mesh.nodes.row(i2);
        double a = (p1 - p0).norm(), b = (p2 - p1).norm(), c = (p0 - p2).norm();
        double area = 0.5 * std::abs((p1 - p0)(0) * (p2 - p0)(1) - (p1 - p0)(1) * (p2 - p0)(0));
        if (area < 1e-14) { mesh.quality(t) = 0.0; continue; }
        double s = (a + b + c) / 2.0;
        double inrad = area / s, circrad = (a * b * c) / (4.0 * area);
        mesh.quality(t) = 2.0 * (inrad / circrad);
    }

    mesh.boundaries = domain.boundaries;
    mesh.bathymetry = domain.bathymetry;

    return mesh;
}

}  // stages
}  // admesh
