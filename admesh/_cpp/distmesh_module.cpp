// pybind11 binding layer for C++ distmesh solver
// Wraps force-balance update loop (hot path)
//
// Uses raw NumPy buffer access (py::array_t unchecked<>) to avoid Eigen
// copy/conversion overhead.  The force-step inner loops are written for
// auto-vectorisation by -O3 -march=native.

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <cmath>
#include <cstdint>
#include <vector>

namespace py = pybind11;

PYBIND11_MODULE(_distmesh_cpp, m) {
    m.doc() = "ADMESH C++ distmesh2d force-balance solver (v1.0.0)";

    m.def("distmesh2d_step", [](
        py::array_t<double,   py::array::c_style | py::array::forcecast> p_np,
        py::array_t<int64_t,  py::array::c_style | py::array::forcecast> bars_np,
        py::array_t<double,   py::array::c_style | py::array::forcecast> h_np,
        double Fscale,
        double deltat,
        int    nfix
    ) -> py::array_t<double> {

        const auto p_buf    = p_np.unchecked<2>();
        const auto bars_buf = bars_np.unchecked<2>();
        const auto h_buf    = h_np.unchecked<1>();

        const int N = static_cast<int>(p_np.shape(0));
        const int M = static_cast<int>(bars_np.shape(0));

        if (M == 0) {
            // Return copy of p
            py::array_t<double> out({N, 2});
            auto ob = out.mutable_unchecked<2>();
            for (int i = 0; i < N; ++i) { ob(i,0)=p_buf(i,0); ob(i,1)=p_buf(i,1); }
            return out;
        }

        // ---- 1. Bar vectors and lengths ------------------------------------
        // Contiguous SoA layout: bvx[i], bvy[i], L[i]
        // Helps the compiler vectorise the arithmetic loops below.
        std::vector<double> bvx(M), bvy(M), Lv(M);
        for (int i = 0; i < M; ++i) {
            const int i0 = static_cast<int>(bars_buf(i, 0));
            const int i1 = static_cast<int>(bars_buf(i, 1));
            double dx = p_buf(i0, 0) - p_buf(i1, 0);
            double dy = p_buf(i0, 1) - p_buf(i1, 1);
            bvx[i] = dx;
            bvy[i] = dy;
            Lv[i]  = std::sqrt(dx * dx + dy * dy);
        }

        // ---- 2. Element-wise L0 — MATLAB line 163 --------------------------
        //   scalar_factor = Fscale * sqrt( sum(L^2) / sum(h^2) )
        //   L0[i] = h[i] * scalar_factor
        double L_norm_sq = 0.0, h_norm_sq = 0.0;
        for (int i = 0; i < M; ++i) {
            L_norm_sq += Lv[i] * Lv[i];
            double hi  = h_buf(i);
            h_norm_sq += hi * hi;
        }
        const double sf = (h_norm_sq > 0.0)
            ? Fscale * std::sqrt(L_norm_sq / h_norm_sq)
            : 0.0;

        // ---- 3. Force scale per bar: s[i] = max(h[i]*sf - L[i], 0) / L[i] -
        std::vector<double> sx(M), sy(M);
        for (int i = 0; i < M; ++i) {
            double L0_i = h_buf(i) * sf;
            double Fi   = L0_i - Lv[i];
            if (Fi > 0.0 && Lv[i] > 1e-14) {
                double s = Fi / Lv[i];
                sx[i] = s * bvx[i];
                sy[i] = s * bvy[i];
            } else {
                sx[i] = 0.0;
                sy[i] = 0.0;
            }
        }

        // ---- 4. Scatter: Ftot[i0] += Fvec[i], Ftot[i1] -= Fvec[i] --------
        std::vector<double> Ftx(N, 0.0), Fty(N, 0.0);
        for (int i = 0; i < M; ++i) {
            const int i0 = static_cast<int>(bars_buf(i, 0));
            const int i1 = static_cast<int>(bars_buf(i, 1));
            if (i0 >= 0 && i0 < N && i1 >= 0 && i1 < N) {
                Ftx[i0] += sx[i];   Fty[i0] += sy[i];
                Ftx[i1] -= sx[i];   Fty[i1] -= sy[i];
            }
        }

        // ---- 5. Zero fixed nodes -------------------------------------------
        for (int i = 0; i < nfix && i < N; ++i) {
            Ftx[i] = 0.0;  Fty[i] = 0.0;
        }

        // ---- 6. Euler update: p_new = p + deltat * Ftot --------------------
        auto result = py::array_t<double>({N, 2});
        auto rb = result.mutable_unchecked<2>();
        for (int i = 0; i < N; ++i) {
            rb(i, 0) = p_buf(i, 0) + deltat * Ftx[i];
            rb(i, 1) = p_buf(i, 1) + deltat * Fty[i];
        }
        return result;

    },
    "Compute one distmesh2d force-balance step (MATLAB-faithful element-wise L0).\n"
    "\n"
    "Parameters\n"
    "----------\n"
    "p_in   : (N,2) float64 C-contiguous — node positions\n"
    "bars   : (M,2) int32  C-contiguous — edge indices (0-based)\n"
    "h_bars : (M,)  float64             — desired edge lengths\n"
    "Fscale : float — pressure scale factor (MATLAB default 1.15)\n"
    "deltat : float — Euler time step       (MATLAB default 0.3)\n"
    "nfix   : int   — number of pinned nodes at start of p\n"
    "\n"
    "Returns\n"
    "-------\n"
    "(N,2) float64 array — updated node positions",
    py::arg("p_in"), py::arg("bars"), py::arg("h_bars"),
    py::arg("Fscale"), py::arg("deltat"), py::arg("nfix"));
}
