#pragma once

#include <Eigen/Dense>
#include <vector>
#include <array>
#include <optional>
#include <functional>
#include <filesystem>

namespace admesh {

enum class BoundaryType : int {
    OPEN = 0,
    MAINLAND = 1,
    ISLAND = 11,
    MAINLAND_FLUX = 20
};

struct BoundarySegment {
    Eigen::VectorXi node_indices;
    int bc_type;
};

struct Domain {
    Eigen::MatrixX2d vertices;
    Eigen::MatrixX2i segments;
    std::vector<BoundarySegment> boundaries;
    std::array<double, 4> bbox;
    std::optional<std::function<Eigen::VectorXd(const Eigen::MatrixX2d&)>> sdf;
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
    double h_min = 0.0;
    double h_max = 0.1;
    std::optional<std::function<Eigen::VectorXd(const Eigen::MatrixX2d&)>> size_field;
    unsigned seed = 0;
    int max_iter = 0;
    bool quality_gate = true;
};

// Main API
Mesh triangulate(const Domain& domain, const TriangulateOptions& opts);

// Domain construction from file
Domain load_domain(const std::filesystem::path& path);

// fort.14 I/O
Mesh read_fort14(const std::filesystem::path& path);
void write_fort14(const Mesh& mesh, const std::filesystem::path& path);

// Stage entry points (for testing)
Mesh routine(const Domain& domain, const TriangulateOptions& opts);

}
