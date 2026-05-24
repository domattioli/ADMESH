// admesh-cpp/chilmesh.cpp
// C++ port of CHILmesh angle-based smoother + element quality (skew).
//
// Port of CHILmesh.angle_based_smoother (Zhou & Shimada 2000) + elem_quality.
// Uses half-edge–style succ_map ring traversal (faithful to CHILmesh Python).
//
// Build: g++ -std=c++17 -O3 -march=native chilmesh.cpp -o chilmesh
//
// Driver protocol (stdin):
//   line 1: n_nodes n_elems n_iter omega
//   next n_nodes lines: x y
//   next n_elems lines: v0 v1 v2  (0-based, CCW)
//
// Output (stdout):
//   smooth_s qual_s n_nodes n_elems mean_q min_q

#include <algorithm>
#include <array>
#include <cmath>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <limits>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

using Pt  = std::array<double, 2>;
using Tri = std::array<int, 3>;

// ── Canonical edge key (pair<int,int> → uint64_t) ─────────────────────────
static inline uint64_t edge_key(int a, int b) {
    if (a > b) std::swap(a, b);
    return (uint64_t(uint32_t(a)) << 32) | uint32_t(b);
}

// ── MeshTopo ──────────────────────────────────────────────────────────────
struct MeshTopo {
    int n_verts = 0, n_elems = 0, n_edges = 0;
    std::vector<Pt>  pts;
    std::vector<Tri> elems;
    std::vector<std::array<int,2>> edge2vert;  // (v_min, v_max)
    std::vector<std::array<int,2>> edge2elem;  // (elem_a, elem_b), -1 = boundary side
    std::vector<std::vector<int>>  vert2elem;  // vertex → incident element list
    std::unordered_set<int>        boundary_verts;

    void build(const std::vector<Pt>& points, const std::vector<Tri>& triangles) {
        pts   = points;
        elems = triangles;
        n_verts = (int)pts.size();
        n_elems = (int)elems.size();

        std::unordered_map<uint64_t, int> emap;
        emap.reserve(n_elems * 3);
        vert2elem.assign(n_verts, {});

        for (int ei = 0; ei < n_elems; ++ei) {
            const auto& t = elems[ei];
            for (int j = 0; j < 3; ++j) {
                int a = t[j], b = t[(j+1)%3];
                uint64_t k = edge_key(a, b);
                auto it = emap.find(k);
                if (it == emap.end()) {
                    int eid = (int)edge2vert.size();
                    if (a < b) edge2vert.push_back({a, b});
                    else       edge2vert.push_back({b, a});
                    edge2elem.push_back({ei, -1});
                    emap[k] = eid;
                } else {
                    edge2elem[it->second][1] = ei;
                }
            }
            for (int j = 0; j < 3; ++j)
                vert2elem[t[j]].push_back(ei);
        }
        n_edges = (int)edge2vert.size();

        for (int eid = 0; eid < n_edges; ++eid) {
            if (edge2elem[eid][1] == -1) {
                boundary_verts.insert(edge2vert[eid][0]);
                boundary_verts.insert(edge2vert[eid][1]);
            }
        }
    }
};

// ── Geometry helpers ───────────────────────────────────────────────────────

static inline double acos_deg(const Pt& p0, const Pt& p1, const Pt& p2) {
    double ux = p1[0]-p0[0], uy = p1[1]-p0[1];
    double wx = p2[0]-p0[0], wy = p2[1]-p0[1];
    double lu2 = ux*ux + uy*uy, lw2 = wx*wx + wy*wy;
    if (lu2 < 1e-28 || lw2 < 1e-28) return 0.0;
    double c = (ux*wx + uy*wy) / std::sqrt(lu2 * lw2);
    return std::acos(std::max(-1.0, std::min(1.0, c))) * (180.0 / M_PI);
}

// Skew quality for one CCW triangle (returns -1 if inverted).
// Formula: 1 - max((amax-60)/120, (60-amin)/60). Range [0,1], 1=equilateral.
static inline double tri_skew(const Pt& p0, const Pt& p1, const Pt& p2) {
    double dx1 = p1[0]-p0[0], dy1 = p1[1]-p0[1];
    double dx2 = p2[0]-p0[0], dy2 = p2[1]-p0[1];
    if (dx1*dy2 - dy1*dx2 <= 0.0) return -1.0;
    double a0 = acos_deg(p0, p1, p2);
    double a1 = acos_deg(p1, p0, p2);
    double a2 = 180.0 - a0 - a1;
    double amax = std::max({a0,a1,a2}), amin = std::min({a0,a1,a2});
    return 1.0 - std::max((amax-60.0)/120.0, (60.0-amin)/60.0);
}

// ── Ordered CCW vertex ring around v_idx ──────────────────────────────────
//
// Builds a succ_map (pred→succ) from the CCW element fan, then chains it
// into a ring. Faithful port of CHILmesh._ordered_vertex_ring.
// Returns empty if non-manifold or open (boundary) ring.
static std::vector<int> ordered_ring(
    int v_idx,
    const std::vector<int>& elem_ids,
    const std::vector<Tri>& elems)
{
    std::unordered_map<int,int> succ_map;
    succ_map.reserve(elem_ids.size());

    for (int eid : elem_ids) {
        const auto& t = elems[eid];
        int i = -1;
        for (int j = 0; j < 3; ++j) { if (t[j] == v_idx) { i = j; break; } }
        if (i < 0) continue;
        int pred = t[(i+2)%3];
        int succ = t[(i+1)%3];
        succ_map[pred] = succ;
    }
    if ((int)succ_map.size() != (int)elem_ids.size()) return {};  // non-manifold

    int start = succ_map.begin()->first;
    std::vector<int> ring = {start};
    int cur = start;
    for (int s = 0; s < (int)succ_map.size()-1; ++s) {
        auto it = succ_map.find(cur);
        if (it == succ_map.end() || it->second == start) break;
        ring.push_back(it->second);
        cur = it->second;
    }
    // Verify closed ring
    auto last = succ_map.find(ring.back());
    if (last == succ_map.end() || last->second != start) return {};  // open ring
    if ((int)ring.size() != (int)succ_map.size()) return {};
    return ring;
}

// Min skew quality over all incident elements, with v_idx at candidate pos.
// Returns -1 if any element becomes inverted.
static double local_min_quality(
    int v_idx,
    const Pt& vpos,
    const std::vector<int>& elem_ids,
    const std::vector<Tri>& elems,
    const std::vector<Pt>& p)
{
    double min_q = 1e9;
    for (int eid : elem_ids) {
        const auto& t = elems[eid];
        Pt p0 = (t[0]==v_idx) ? vpos : p[t[0]];
        Pt p1 = (t[1]==v_idx) ? vpos : p[t[1]];
        Pt p2 = (t[2]==v_idx) ? vpos : p[t[2]];
        double q = tri_skew(p0, p1, p2);
        if (q < min_q) min_q = q;
    }
    return min_q;
}

// ── Angle-based smoother (Zhou & Shimada 2000) ────────────────────────────
//
// For each interior vertex: bisector-weighted correction drives each sector
// angle toward target 2π/m. Deficit clamped ±π/3 to prevent wild moves in
// near-degenerate sectors. Gauss-Seidel updates accepted only when local
// min-quality strictly improves (monotone quality guarantee).
void angle_based_smoother(MeshTopo& topo, int n_iter, double omega, double tol) {
    auto& p = topo.pts;
    const int n = topo.n_verts;
    const double two_pi    = 2.0 * M_PI;
    const double def_cap   = M_PI / 3.0;  // 60° cap

    for (int iter = 0; iter < n_iter; ++iter) {
        double max_move = 0.0;

        for (int v = 0; v < n; ++v) {
            if (topo.boundary_verts.count(v)) continue;
            const auto& eids = topo.vert2elem[v];
            if (eids.empty()) continue;

            auto ring = ordered_ring(v, eids, topo.elems);
            if ((int)ring.size() < 2) continue;

            const int m = (int)ring.size();
            const double theta_star = two_pi / m;
            double cx = 0.0, cy = 0.0;

            for (int k = 0; k < m; ++k) {
                const Pt& a = p[ring[k]];
                const Pt& b = p[ring[(k+1)%m]];
                const Pt& vp = p[v];

                double dax = a[0]-vp[0], day = a[1]-vp[1];
                double dbx = b[0]-vp[0], dby = b[1]-vp[1];
                double la = std::sqrt(dax*dax + day*day);
                double lb = std::sqrt(dbx*dbx + dby*dby);
                if (la < 1e-14 || lb < 1e-14) continue;

                double uax = dax/la, uay = day/la;
                double ubx = dbx/lb, uby = dby/lb;
                double cos_a = std::max(-1.0, std::min(1.0, uax*ubx + uay*uby));
                double alpha  = std::acos(cos_a);

                double bx = uax+ubx, by = uay+uby;
                double bl = std::sqrt(bx*bx + by*by);
                if (bl > 1e-10) { bx /= bl; by /= bl; }
                else             { bx = -uay; by = uax; }  // 90° fallback

                double deficit = std::max(-def_cap, std::min(def_cap, theta_star - alpha));
                double avg_len = (la + lb) * 0.5;
                cx += deficit * avg_len * bx;
                cy += deficit * avg_len * by;
            }

            if (cx*cx + cy*cy < 1e-28) continue;

            double q0 = local_min_quality(v, p[v], eids, topo.elems, p);
            double sx = omega * cx / m;
            double sy = omega * cy / m;
            double sc = 1.0;

            for (int ls = 0; ls < 6; ++ls) {
                Pt cand = {p[v][0] + sc*sx, p[v][1] + sc*sy};
                if (local_min_quality(v, cand, eids, topo.elems, p) > q0) {
                    double move = sc * std::sqrt(sx*sx + sy*sy);
                    if (move > max_move) max_move = move;
                    p[v] = cand;
                    break;
                }
                sc *= 0.5;
            }
        }

        if (max_move < tol) break;
    }
}

// ── Mesh quality (skewness) ────────────────────────────────────────────────
std::pair<double,double> mesh_quality_skew(const MeshTopo& topo) {
    double sum_q = 0.0, min_q = 1.0;
    for (const auto& t : topo.elems) {
        double q = tri_skew(topo.pts[t[0]], topo.pts[t[1]], topo.pts[t[2]]);
        if (q < 0.0) q = 0.0;
        sum_q += q;
        if (q < min_q) min_q = q;
    }
    int n = (int)topo.elems.size();
    return {n > 0 ? sum_q/n : 0.0, n > 0 ? min_q : 0.0};
}

// ── Driver ────────────────────────────────────────────────────────────────
int main() {
    int n_nodes, n_elems, n_iter;
    double omega;
    std::cin >> n_nodes >> n_elems >> n_iter >> omega;
    if (!std::cin) return 1;

    std::vector<Pt> pts(n_nodes);
    for (int i = 0; i < n_nodes; ++i)
        std::cin >> pts[i][0] >> pts[i][1];

    std::vector<Tri> elems(n_elems);
    for (int i = 0; i < n_elems; ++i)
        std::cin >> elems[i][0] >> elems[i][1] >> elems[i][2];

    MeshTopo topo;
    topo.build(pts, elems);

    using clock = std::chrono::steady_clock;

    auto t0 = clock::now();
    angle_based_smoother(topo, n_iter, omega, 1e-8);
    double smooth_s = std::chrono::duration<double>(clock::now() - t0).count();

    auto t1 = clock::now();
    auto [mean_q, min_q] = mesh_quality_skew(topo);
    double qual_s = std::chrono::duration<double>(clock::now() - t1).count();

    std::cout << smooth_s << " " << qual_s << " "
              << n_nodes << " " << n_elems << " "
              << mean_q << " " << min_q << "\n";
    return 0;
}
