#include "admesh/admesh.hpp"
#include <Eigen/Dense>
#include <iostream>
#include <chrono>
#include <cmath>

int main() {
    // Create a synthetic domain similar to WNAT (large polygon boundary)
    // For real test, would load from fort.14 file

    std::cout << "ADMESH C++ Benchmark (WNAT-scale domain)\n";
    std::cout << "=======================================\n\n";

    // Synthetic WNAT-like domain: circular ring with many vertices
    int n_boundary = 144;  // Like WNAT
    admesh::Domain domain;
    domain.vertices.resize(n_boundary, 2);
    domain.bbox = {-100, -50, 0, 50};

    // Create circular boundary (approximates WNAT extent)
    double radius = 40;
    double cx = -50, cy = 0;
    for (int i = 0; i < n_boundary; ++i) {
        double angle = 2 * M_PI * i / n_boundary;
        domain.vertices(i, 0) = cx + radius * std::cos(angle);
        domain.vertices(i, 1) = cy + radius * std::sin(angle);
    }

    admesh::TriangulateOptions opts;
    opts.h_max = 0.1;
    opts.h_min = 0.01;
    opts.max_iter = 100;

    std::cout << "Domain: " << n_boundary << " boundary vertices\n";
    std::cout << "Parameters: h_max=" << opts.h_max << ", h_min=" << opts.h_min << "\n\n";

    // Time triangulate
    std::cout << "Running triangulate()...\n";
    auto t_start = std::chrono::high_resolution_clock::now();

    admesh::Mesh mesh = admesh::triangulate(domain, opts);

    auto t_end = std::chrono::high_resolution_clock::now();
    double elapsed_ms = std::chrono::duration<double, std::milli>(t_end - t_start).count();
    double elapsed_s = elapsed_ms / 1000.0;

    std::cout << "\n✓ Done\n\n";
    std::cout << "Results:\n";
    std::cout << "--------\n";
    std::cout << "Time:      " << elapsed_s << " seconds (" << elapsed_ms << " ms)\n";
    std::cout << "Nodes:     " << mesh.nodes.rows() << "\n";
    std::cout << "Elements:  " << mesh.elements.rows() << "\n";

    if (mesh.quality.rows() > 0) {
        double min_q = mesh.quality.minCoeff();
        double mean_q = mesh.quality.mean();
        double max_q = mesh.quality.maxCoeff();
        std::cout << "Quality:   min=" << min_q << ", mean=" << mean_q << ", max=" << max_q << "\n";
    }

    std::cout << "\n| Metric | Value |\n";
    std::cout << "|--------|-------|\n";
    std::cout << "| Time (C++) | " << elapsed_s << "s |\n";
    std::cout << "| Nodes | " << mesh.nodes.rows() << " |\n";
    std::cout << "| Elements | " << mesh.elements.rows() << " |\n";

    return 0;
}
