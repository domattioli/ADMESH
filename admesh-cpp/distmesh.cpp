// admesh-cpp: standalone C++ baseline of distmesh2d.
// Mirrors admesh._stages.distmesh.distmesh2d + admesh-rs/distmesh.rs.
//
// Build: g++ -std=c++17 -O3 -march=native -fopenmp distmesh.cpp -o distmesh
//
// Driver protocol (stdin):
//   line 1: niter h0 xmin ymin xmax ymax sdf_nx sdf_ny seed
//   line 2: sdf xs (sdf_nx floats, space-separated)
//   line 3: sdf ys (sdf_ny floats)
//   lines 4..: sdf grid rows (sdf_ny rows × sdf_nx floats each)
//
// Output (stdout):
//   line 1: elapsed_seconds n_nodes n_elements mean_quality
//   followed by node and element data (text, for cross-checks).

#include "vendor/delaunator.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <limits>
#include <random>
#include <set>
#include <sstream>
#include <unordered_set>
#include <vector>

#ifdef _OPENMP
#include <omp.h>
#endif

using Pt = std::array<double, 2>;

// ── Rasterised SDF (bilinear interp) ──────────────────────────────────────
struct RasterSdf {
    std::vector<double> xs, ys;
    std::vector<double> grid; // row-major, shape (ny, nx)
    int nx, ny;

    double eval_one(double x, double y) const {
        if (x < xs.front() || x > xs.back() || y < ys.front() || y > ys.back())
            return 1.0;
        // Locate index by uniform-spacing assumption
        double dx = (xs.back() - xs.front()) / (nx - 1);
        double dy = (ys.back() - ys.front()) / (ny - 1);
        int ix = std::min(nx - 2, std::max(0, int((x - xs.front()) / dx)));
        int iy = std::min(ny - 2, std::max(0, int((y - ys.front()) / dy)));
        double tx = (x - xs[ix]) / (xs[ix + 1] - xs[ix]);
        double ty = (y - ys[iy]) / (ys[iy + 1] - ys[iy]);
        double v00 = grid[iy * nx + ix];
        double v10 = grid[iy * nx + ix + 1];
        double v01 = grid[(iy + 1) * nx + ix];
        double v11 = grid[(iy + 1) * nx + ix + 1];
        double a = v00 * (1 - tx) + v10 * tx;
        double b = v01 * (1 - tx) + v11 * tx;
        return a * (1 - ty) + b * ty;
    }

    void eval(const std::vector<Pt>& pts, std::vector<double>& out) const {
        out.resize(pts.size());
#pragma omp parallel for
        for (int i = 0; i < (int)pts.size(); ++i)
            out[i] = eval_one(pts[i][0], pts[i][1]);
    }
};

// ── Triangle-quality metric (4√3·A / Σl²) ─────────────────────────────────
inline double tri_quality(const Pt& a, const Pt& b, const Pt& c) {
    double ax = b[0] - a[0], ay = b[1] - a[1];
    double bx = c[0] - b[0], by = c[1] - b[1];
    double cx = a[0] - c[0], cy = a[1] - c[1];
    double l1 = ax * ax + ay * ay;
    double l2 = bx * bx + by * by;
    double l3 = cx * cx + cy * cy;
    double denom = l1 + l2 + l3;
    if (denom <= 0.0) return 0.0;
    double area = 0.5 * std::fabs(ax * (-cy) - ay * (-cx));
    return 6.928203230275509 * area / denom;
}

// ── distmesh2d core ───────────────────────────────────────────────────────
struct DistmeshResult {
    std::vector<Pt> nodes;
    std::vector<std::array<int, 3>> elements;
    double elapsed_s = 0.0;
    double mean_q = 0.0;
};

DistmeshResult distmesh2d(
    const RasterSdf& sdf,
    double h0,
    double xmin, double ymin, double xmax, double ymax,
    int niter, uint64_t seed)
{
    using clock = std::chrono::steady_clock;
    auto t0 = clock::now();

    const double dptol = 1e-3;
    const double ttol = 0.1;
    const double Fscale = 1.2;
    const double deltat = 0.2;
    const double geps = 1e-3 * h0;
    const double deps = std::sqrt(std::numeric_limits<double>::epsilon()) * h0;

    // 1. Initial hex lattice
    std::vector<Pt> p;
    double dy = h0 * std::sqrt(3.0) / 2.0;
    int nx = int((xmax - xmin) / h0) + 2;
    int ny = int((ymax - ymin) / dy) + 2;
    p.reserve(nx * ny);
    for (int j = 0; j < ny; ++j) {
        double y = ymin + j * dy;
        if (y > ymax + 0.5 * h0) break;
        double off = (j % 2 == 1) ? h0 / 2.0 : 0.0;
        for (int i = 0; i < nx; ++i) {
            double x = xmin + i * h0 + off;
            if (x > xmax + 0.5 * h0) break;
            p.push_back({x, y});
        }
    }

    // Filter inside
    std::vector<double> dv;
    sdf.eval(p, dv);
    std::vector<Pt> pin;
    pin.reserve(p.size());
    for (size_t i = 0; i < p.size(); ++i)
        if (dv[i] < geps) pin.push_back(p[i]);
    p.swap(pin);

    // Init Pold to infinity
    std::vector<Pt> pold(p.size(), {std::numeric_limits<double>::infinity(),
                                    std::numeric_limits<double>::infinity()});

    std::vector<std::array<int, 3>> t;
    std::vector<std::array<int, 2>> bars;

    for (int k = 0; k < niter; ++k) {
        // Check whether to retriangulate
        double moved_max = 0.0;
        for (size_t i = 0; i < p.size(); ++i) {
            double dxm = p[i][0] - pold[i][0];
            double dym = p[i][1] - pold[i][1];
            double m = std::sqrt(dxm * dxm + dym * dym) / h0;
            if (m > moved_max) moved_max = m;
        }
        if (moved_max > ttol) {
            pold = p;
            // Flatten coords for delaunator
            std::vector<double> coords;
            coords.reserve(p.size() * 2);
            for (auto& q : p) { coords.push_back(q[0]); coords.push_back(q[1]); }
            try {
                delaunator::Delaunator del(coords);
                // Filter triangles by centroid in domain
                std::vector<Pt> centroids;
                centroids.reserve(del.triangles.size() / 3);
                for (size_t i = 0; i < del.triangles.size(); i += 3) {
                    size_t a = del.triangles[i], b = del.triangles[i+1], c = del.triangles[i+2];
                    centroids.push_back({(p[a][0] + p[b][0] + p[c][0]) / 3.0,
                                         (p[a][1] + p[b][1] + p[c][1]) / 3.0});
                }
                std::vector<double> cd;
                sdf.eval(centroids, cd);
                t.clear();
                for (size_t i = 0, ti = 0; i < del.triangles.size(); i += 3, ++ti) {
                    if (cd[ti] < -geps) {
                        std::array<int, 3> tri = {(int)del.triangles[i],
                                                  (int)del.triangles[i+1],
                                                  (int)del.triangles[i+2]};
                        std::sort(tri.begin(), tri.end());
                        t.push_back(tri);
                    }
                }
                // Build unique bars
                std::set<std::array<int, 2>> bs;
                for (auto& tri : t) {
                    for (int e = 0; e < 3; ++e) {
                        int x = tri[e], y = tri[(e + 1) % 3];
                        bs.insert(x < y ? std::array<int,2>{x, y} : std::array<int,2>{y, x});
                    }
                }
                bars.assign(bs.begin(), bs.end());
            } catch (...) { break; }
        }
        if (bars.empty()) break;

        // Force assembly
        std::vector<Pt> ftot(p.size(), {0.0, 0.0});
        double l_sq = 0.0, h_sq = 0.0;
        std::vector<double> hbars(bars.size(), 1.0);
        std::vector<double> bar_l(bars.size());
        std::vector<Pt> bar_vec(bars.size());
        for (size_t i = 0; i < bars.size(); ++i) {
            int a = bars[i][0], b = bars[i][1];
            double vx = p[a][0] - p[b][0];
            double vy = p[a][1] - p[b][1];
            double l = std::sqrt(vx*vx + vy*vy);
            bar_vec[i] = {vx, vy};
            bar_l[i] = l;
            l_sq += l * l;
            h_sq += hbars[i] * hbars[i];
        }
        double scale = Fscale * std::sqrt(l_sq / h_sq);
        for (size_t i = 0; i < bars.size(); ++i) {
            double l0 = hbars[i] * scale;
            double force = std::max(l0 - bar_l[i], 0.0);
            if (bar_l[i] > 0.0) {
                double fx = force * bar_vec[i][0] / bar_l[i];
                double fy = force * bar_vec[i][1] / bar_l[i];
                ftot[bars[i][0]][0] += fx;
                ftot[bars[i][0]][1] += fy;
                ftot[bars[i][1]][0] -= fx;
                ftot[bars[i][1]][1] -= fy;
            }
        }

        std::vector<Pt> pnew(p.size());
        for (size_t i = 0; i < p.size(); ++i) {
            pnew[i][0] = p[i][0] + deltat * ftot[i][0];
            pnew[i][1] = p[i][1] + deltat * ftot[i][1];
        }

        // Boundary projection
        std::vector<double> dnew;
        sdf.eval(pnew, dnew);
        std::vector<Pt> po;
        std::vector<int> oidx;
        for (size_t i = 0; i < pnew.size(); ++i)
            if (dnew[i] > 0.0) { po.push_back(pnew[i]); oidx.push_back(i); }
        if (!po.empty()) {
            std::vector<Pt> po_dx(po.size()), po_dy(po.size());
            for (size_t i = 0; i < po.size(); ++i) {
                po_dx[i] = {po[i][0] + deps, po[i][1]};
                po_dy[i] = {po[i][0], po[i][1] + deps};
            }
            std::vector<double> d_po, d_dx, d_dy;
            sdf.eval(po, d_po);
            sdf.eval(po_dx, d_dx);
            sdf.eval(po_dy, d_dy);
            for (size_t i = 0; i < po.size(); ++i) {
                double dx = (d_dx[i] - d_po[i]) / deps;
                double dy = (d_dy[i] - d_po[i]) / deps;
                double denom = dx * dx + dy * dy;
                if (denom > 0.0) {
                    pnew[oidx[i]][0] -= d_po[i] * dx / denom;
                    pnew[oidx[i]][1] -= d_po[i] * dy / denom;
                }
            }
        }

        // Stopping check
        double max_d = 0.0;
        for (size_t i = 0; i < pnew.size(); ++i) {
            double dxm = pnew[i][0] - p[i][0];
            double dym = pnew[i][1] - p[i][1];
            double m = std::sqrt(dxm * dxm + dym * dym);
            if (m > max_d) max_d = m;
        }
        p = pnew;
        if (max_d / h0 < dptol) break;
    }

    // Final retri
    if (p.size() >= 3) {
        std::vector<double> coords;
        for (auto& q : p) { coords.push_back(q[0]); coords.push_back(q[1]); }
        try {
            delaunator::Delaunator del(coords);
            std::vector<Pt> centroids;
            for (size_t i = 0; i < del.triangles.size(); i += 3)
                centroids.push_back({
                    (p[del.triangles[i]][0]+p[del.triangles[i+1]][0]+p[del.triangles[i+2]][0])/3.0,
                    (p[del.triangles[i]][1]+p[del.triangles[i+1]][1]+p[del.triangles[i+2]][1])/3.0});
            std::vector<double> cd;
            sdf.eval(centroids, cd);
            t.clear();
            for (size_t i = 0, ti = 0; i < del.triangles.size(); i += 3, ++ti) {
                if (cd[ti] < -geps) {
                    std::array<int, 3> tri = {(int)del.triangles[i],
                                              (int)del.triangles[i+1],
                                              (int)del.triangles[i+2]};
                    std::sort(tri.begin(), tri.end());
                    t.push_back(tri);
                }
            }
        } catch (...) {}
    }

    auto t1 = clock::now();
    double elapsed = std::chrono::duration<double>(t1 - t0).count();

    // Quality
    double q_sum = 0.0;
    for (auto& tri : t)
        q_sum += tri_quality(p[tri[0]], p[tri[1]], p[tri[2]]);
    double mean_q = t.empty() ? 0.0 : q_sum / t.size();

    return {p, t, elapsed, mean_q};
}

int main() {
    // Parse driver protocol
    int niter, nx, ny;
    double h0, xmin, ymin, xmax, ymax;
    uint64_t seed;
    std::cin >> niter >> h0 >> xmin >> ymin >> xmax >> ymax >> nx >> ny >> seed;

    RasterSdf sdf;
    sdf.nx = nx;
    sdf.ny = ny;
    sdf.xs.resize(nx);
    sdf.ys.resize(ny);
    sdf.grid.resize(nx * ny);
    for (int i = 0; i < nx; ++i) std::cin >> sdf.xs[i];
    for (int j = 0; j < ny; ++j) std::cin >> sdf.ys[j];
    for (int j = 0; j < ny; ++j)
        for (int i = 0; i < nx; ++i)
            std::cin >> sdf.grid[j * nx + i];

    auto r = distmesh2d(sdf, h0, xmin, ymin, xmax, ymax, niter, seed);
    std::cout << r.elapsed_s << " " << r.nodes.size() << " " << r.elements.size()
              << " " << r.mean_q << "\n";
    return 0;
}
