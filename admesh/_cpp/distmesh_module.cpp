// pybind11 binding layer for C++ distmesh solver
// Wraps force-balance update loop (hot path)

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/eigen.h>
#include <Eigen/Dense>

namespace py = pybind11;
namespace admesh_cpp_extern {
    // Forward declarations (implemented in distmesh_cpp.cpp)
    using MatrixXd = Eigen::MatrixXd;
    using VectorXd = Eigen::VectorXd;
    using VectorXi = Eigen::VectorXi;
    using Ref = Eigen::Ref<const MatrixXd>;

    void distmesh2d_step(
        const Ref& p_in,
        const VectorXi& bars_i0,
        const VectorXi& bars_i1,
        const VectorXd& h_bars,
        double Fscale,
        double deltat,
        int nfix,
        MatrixXd& p_out
    );
}

PYBIND11_MODULE(_distmesh_cpp, m) {
    m.doc() = "ADMESH C++ distmesh2d force-balance solver (v1.0.0 alpha)";

    m.def("distmesh2d_step", [](
        const Eigen::MatrixXd& p_in,
        const Eigen::MatrixXi& bars,
        const Eigen::VectorXd& h_bars,
        double Fscale,
        double deltat,
        int nfix
    ) -> Eigen::MatrixXd {
        // Convert bars from (M, 2) to separate i0, i1 arrays for Eigen operations
        int M = bars.rows();
        Eigen::VectorXd L = Eigen::VectorXd::Zero(M);

        // Compute bar vectors and lengths
        Eigen::MatrixXd barvec = Eigen::MatrixXd::Zero(M, 2);
        for (int i = 0; i < M; ++i) {
            int i0 = bars(i, 0);
            int i1 = bars(i, 1);
            barvec(i, 0) = p_in(i0, 0) - p_in(i1, 0);
            barvec(i, 1) = p_in(i0, 1) - p_in(i1, 1);
            L(i) = std::sqrt(barvec(i, 0) * barvec(i, 0) + barvec(i, 1) * barvec(i, 1));
        }

        // Compute L0
        double L_norm_sq = (L.array() * L.array()).sum();
        double h_norm_sq = (h_bars.array() * h_bars.array()).sum();
        double L0 = Fscale * std::sqrt(L_norm_sq / h_norm_sq);

        // Compute forces
        Eigen::VectorXd F = (L0 * Eigen::VectorXd::Ones(M) - L).cwiseMax(0.0);

        // Compute force vectors
        Eigen::MatrixXd Fvec = Eigen::MatrixXd::Zero(M, 2);
        for (int i = 0; i < M; ++i) {
            if (L(i) > 1e-14) {
                Fvec.row(i) = (F(i) / L(i)) * barvec.row(i);
            }
        }

        // Aggregate forces
        int N = p_in.rows();
        Eigen::MatrixXd Ftot = Eigen::MatrixXd::Zero(N, 2);
        for (int i = 0; i < M; ++i) {
            Ftot.row(bars(i, 0)) += Fvec.row(i);
            Ftot.row(bars(i, 1)) -= Fvec.row(i);
        }

        // Zero fixed points
        for (int i = 0; i < nfix; ++i) {
            Ftot.row(i).setZero();
        }

        // Euler update
        return p_in + deltat * Ftot;
    },
    "Compute one distmesh2d force-balance step",
    py::arg("p_in"), py::arg("bars"), py::arg("h_bars"),
    py::arg("Fscale"), py::arg("deltat"), py::arg("nfix"));
}
