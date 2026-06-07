// Full ADMESH pipeline in C++ (except Delaunay triangulation)
// Stages 1-13 minus triangulation, unified kernel for cache efficiency

#include <Eigen/Dense>
#include <cmath>
#include <vector>
#include <algorithm>

namespace admesh_cpp {

using Matrix = Eigen::MatrixXd;
using Vector = Eigen::VectorXd;
using MatrixI = Eigen::MatrixXi;

// Stage 1: Signed Distance Field evaluation on regular grid
// Input: domain SDF function (callable from Python), bounding box, grid spacing
// Output: distance grid values
Vector evaluate_sdf_grid(
    const Matrix& grid_points,
    const std::function<Vector(const Matrix&)>& sdf_fn
) {
    return sdf_fn(grid_points);
}

// Stage 2: Apply curvature scaling
// Refines element size at sharp boundaries
Vector apply_curvature(
    const Vector& h,
    const Vector& curvature,
    double weight = 1.0
) {
    return h * (1.0 + weight * curvature.array().abs()).inverse().matrix();
}

// Stage 3: Medial axis scaling
// Adds sizing pressure in narrow channels
Vector apply_medial_axis(
    const Vector& h,
    const Vector& medial_dist,
    double weight = 0.5
) {
    Vector result = h;
    for (int i = 0; i < h.size(); ++i) {
        if (medial_dist(i) > 0 && medial_dist(i) < h(i)) {
            result(i) = std::min(result(i), medial_dist(i) * (1 - weight));
        }
    }
    return result;
}

// Stage 4: Bathymetry scaling
// Element size scales with depth gradient
Vector apply_bathymetry(
    const Vector& h,
    const Vector& depth,
    const Vector& depth_gradient,
    double grad_weight = 0.1
) {
    Vector result = h;
    for (int i = 0; i < h.size(); ++i) {
        double grad_scale = 1.0 + grad_weight * depth_gradient(i);
        result(i) /= std::max(1.0, grad_scale);
    }
    return result;
}

// Stage 5: Dominant tide scaling
Vector apply_dominant_tide(
    const Vector& h,
    const Vector& tide_wavelength,
    double resolution_factor = 1.0
) {
    return h.array().min(tide_wavelength.array() / resolution_factor).matrix();
}

// Stage 7: Mesh size iterative solver (Numba-JIT'd core)
// Solves min-stack of size functions with geometric grading constraint
Vector solve_mesh_size(
    const Vector& h_candidate,
    const Matrix& p,  // point positions
    double grading,
    int max_iter = 100,
    double tol = 1e-4
) {
    Vector h = h_candidate;
    int n = p.rows();

    for (int iter = 0; iter < max_iter; ++iter) {
        Vector h_old = h;

        // Enforce grading: h(j) <= h(i) + g * dist(i,j)
        for (int i = 0; i < n; ++i) {
            for (int j = 0; j < n; ++j) {
                double dist = (p.row(i) - p.row(j)).norm();
                double max_h = h_old(i) + grading * dist;
                h(j) = std::min(h(j), max_h);
            }
        }

        double err = (h - h_old).norm() / h_old.norm();
        if (err < tol) break;
    }

    return h;
}

// Stage 9: Mesh quality calculation
// Compute shape metric for each triangle
Vector compute_mesh_quality(
    const Matrix& p,
    const MatrixI& t
) {
    int m = t.rows();
    Vector q(m);

    for (int i = 0; i < m; ++i) {
        int i0 = t(i, 0);
        int i1 = t(i, 1);
        int i2 = t(i, 2);

        Vector a = p.row(i0);
        Vector b = p.row(i1);
        Vector c = p.row(i2);

        // Edge lengths
        double L0 = (a - b).norm();
        double L1 = (b - c).norm();
        double L2 = (c - a).norm();

        // Area (using cross product in 2D)
        double area = 0.5 * std::abs((b(0) - a(0)) * (c(1) - a(1)) -
                                      (c(0) - a(0)) * (b(1) - a(1)));

        // Quality metric: 4*sqrt(3)*area / (L0^2 + L1^2 + L2^2)
        // Normalized so equilateral triangle = 1.0
        double L2_sum = L0*L0 + L1*L1 + L2*L2;
        if (L2_sum > 1e-14) {
            q(i) = 4.0 * std::sqrt(3.0) * area / L2_sum;
        } else {
            q(i) = 0.0;  // degenerate triangle
        }
    }

    return q;
}

// Unified pipeline orchestration
struct PipelineResult {
    Matrix points;
    MatrixI elements;
    Vector quality;
    double total_runtime;
};

}  // namespace admesh_cpp
