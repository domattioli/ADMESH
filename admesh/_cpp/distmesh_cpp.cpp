// distmesh2d_step: C++ force-balance update loop (hot path)
// Computes truss forces + node movement for one iteration of distmesh2d

#include <Eigen/Dense>
#include <cmath>
#include <vector>

namespace admesh_cpp {

using MatrixXd = Eigen::MatrixXd;
using VectorXd = Eigen::VectorXd;
using VectorXi = Eigen::VectorXi;
using Ref = Eigen::Ref<const MatrixXd>;

/**
 * distmesh2d_step: Single iteration of force-balance point placement
 *
 * Given current point distribution p, bars (edges), and desired edge lengths h,
 * compute truss forces and return updated point positions.
 *
 * Args:
 *   p_in: (N, 2) point positions
 *   bars: (M, 2) edge connectivity (0-indexed)
 *   h_bars: (M,) desired edge length per bar
 *   Fscale: truss internal-pressure factor (>1)
 *   deltat: Euler time step
 *   nfix: number of fixed points (first nfix points don't move)
 *
 * Returns:
 *   p_out: (N, 2) updated positions
 */
void distmesh2d_step(
    const Ref& p_in,
    const MatrixXi& bars,
    const VectorXd& h_bars,
    double Fscale,
    double deltat,
    int nfix,
    MatrixXd& p_out
) {
    int N = p_in.rows();
    int M = bars.rows();

    if (M == 0) {
        p_out = p_in;
        return;
    }

    // 1. Bar vectors and lengths
    MatrixXd barvec = MatrixXd::Zero(M, 2);
    VectorXd L = VectorXd::Zero(M);

    for (int i = 0; i < M; ++i) {
        int i0 = bars(i, 0);
        int i1 = bars(i, 1);
        barvec(i, 0) = p_in(i0, 0) - p_in(i1, 0);
        barvec(i, 1) = p_in(i0, 1) - p_in(i1, 1);
        L(i) = std::sqrt(barvec(i, 0) * barvec(i, 0) + barvec(i, 1) * barvec(i, 1));
    }

    // 2. Compute desired edge length L0
    double L_norm_sq = (L.array() * L.array()).sum();
    double h_norm_sq = (h_bars.array() * h_bars.array()).sum();
    double L0 = Fscale * std::sqrt(L_norm_sq / h_norm_sq);

    // 3. Compute forces F = max(L0 - L, 0)
    VectorXd F = VectorXd::Zero(M);
    for (int i = 0; i < M; ++i) {
        F(i) = std::max(L0 - L(i), 0.0);
    }

    // 4. Compute force vectors (F / L) * barvec, handling L=0
    MatrixXd Fvec = MatrixXd::Zero(M, 2);
    for (int i = 0; i < M; ++i) {
        if (L(i) > 1e-14) {  // Avoid division by zero
            double scale = F(i) / L(i);
            Fvec(i, 0) = scale * barvec(i, 0);
            Fvec(i, 1) = scale * barvec(i, 1);
        }
    }

    // 5. Aggregate forces per node
    MatrixXd Ftot = MatrixXd::Zero(N, 2);
    for (int i = 0; i < M; ++i) {
        int i0 = bars(i, 0);
        int i1 = bars(i, 1);
        Ftot(i0, 0) += Fvec(i, 0);
        Ftot(i0, 1) += Fvec(i, 1);
        Ftot(i1, 0) -= Fvec(i, 0);
        Ftot(i1, 1) -= Fvec(i, 1);
    }

    // 6. Zero forces at fixed points
    for (int i = 0; i < nfix; ++i) {
        Ftot(i, 0) = 0.0;
        Ftot(i, 1) = 0.0;
    }

    // 7. Euler update: p_new = p + deltat * Ftot
    p_out = p_in + deltat * Ftot;
}

/**
 * distmesh2d_force_aggregation: Optimized force computation
 *
 * Batched computation for large meshes. Same as distmesh2d_step but
 * uses vectorized operations where possible.
 */
void distmesh2d_force_aggregation(
    const Ref& p_in,
    const MatrixXi& bars,
    const VectorXd& h_bars,
    double Fscale,
    double deltat,
    int nfix,
    MatrixXd& Ftot_out
) {
    int M = bars.rows();

    if (M == 0) {
        Ftot_out = MatrixXd::Zero(p_in.rows(), 2);
        return;
    }

    // Vectorized bar operations
    MatrixXd barvec(M, 2);
    for (int i = 0; i < M; ++i) {
        barvec.row(i) = p_in.row(bars(i, 0)) - p_in.row(bars(i, 1));
    }

    // Lengths
    VectorXd L = barvec.rowwise().norm();

    // L0 computation
    double L_norm_sq = (L.array() * L.array()).sum();
    double h_norm_sq = (h_bars.array() * h_bars.array()).sum();
    double L0 = Fscale * std::sqrt(L_norm_sq / h_norm_sq);

    // Forces
    VectorXd F = (L0 * VectorXd::Ones(M) - L).cwiseMax(0.0);

    // Force vectors (element-wise division, avoiding zeros)
    MatrixXd Fvec = MatrixXd::Zero(M, 2);
    for (int i = 0; i < M; ++i) {
        if (L(i) > 1e-14) {
            Fvec.row(i) = (F(i) / L(i)) * barvec.row(i);
        }
    }

    // Aggregate
    int N = p_in.rows();
    Ftot_out = MatrixXd::Zero(N, 2);
    for (int i = 0; i < M; ++i) {
        Ftot_out.row(bars(i, 0)) += Fvec.row(i);
        Ftot_out.row(bars(i, 1)) -= Fvec.row(i);
    }

    // Zero fixed points
    for (int i = 0; i < nfix; ++i) {
        Ftot_out.row(i).setZero();
    }
}

}  // namespace admesh_cpp
