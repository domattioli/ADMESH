"""Precompute node trajectories for the ADMESH Delaware Bay hero animation.

The hero tells ADMESH's three-stage story over a *graded* (non-uniform)
mesh of the Delaware Bay funnel:

    1. Initialized  - nodes scattered on a perturbed, size-aware lattice
       inside the Delaware Bay / River outline. Dense in the narrow upper
       river, coarse out in the open bay (rough, tangled triangulation).
    2. Truss solver - DistMesh-style force balance with variable rest
       lengths L0 proportional to the local size function h(x); nodes
       relax toward elements sized by h while staying near-equilateral.
    3. FEM smoothed - a final Laplacian / FEM smoothing pass cleans up
       interior valence and pushes element quality to its peak.

The Delaware Bay outline is the *real* domain registered in the sibling
``admesh-domains`` repository (``registry_data/meshes/Deleware_Bay.14``,
the refined ``hmin=100m / hmax=20000m`` variant). We extract its outer
boundary ring and re-mesh it at hero-friendly resolution.

Non-uniformity is driven by an explicit size function with the three
classic ADMESH / DistMesh hyperparameters (here in degrees, scaled from
the registered metres so the hero stays legible while preserving a
strong, graded hmax/hmin contrast):

    hmin  - smallest target edge length (degrees) in the narrow river
            and tight to the coast.
    hmax  - largest target edge length (degrees) out in the open bay.
    g     - gradient limit on the size function (|grad h| <= g), enforced
            by fast-sweeping on a background grid so element size grows
            smoothly rather than jumping.

To keep frames interpolatable, triangle *connectivity* is fixed (computed
once on the relaxed point set); only node *positions* move between
keyframes, and each stage stores a short trajectory for eased motion.

Output: ``scripts/hero/delbay_stages.npz`` consumed by ``delbay_hero.py``.

Usage:
    python scripts/hero/precompute_delbay_stages.py
"""
from __future__ import annotations

import pathlib
from collections import defaultdict

import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy.spatial import Delaunay
from shapely.geometry import Polygon, Point
from shapely.prepared import prep

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "delbay_stages.npz"
RNG = np.random.default_rng(11)

# Real Delaware Bay domain from the sibling admesh-domains registry.
# (The refined hmin=100m / hmax=20000m variant.) Falls back to the
# cached ring committed alongside this script if the sibling repo or the
# raw mesh isn't available.
DELBAY_MESH_CANDIDATES = [
    HERE.parents[2] / "ADMESH-Domains" / "registry_data" / "meshes"
    / "Deleware_Bay_hmin_100_hmax_20000.14",
    HERE.parents[2] / "ADMESH-Domains" / "registry_data" / "meshes"
    / "Deleware_Bay.14",
]
RING_CACHE = HERE / "delbay_ring.npy"

# --- Size-function hyperparameters (degrees of lon/lat) ---------------------
# Registered Delaware Bay sizing is hmin=100m, hmax=20000m (a 200x span).
# Rendered at hero resolution with the same graded intent but a legible
# ~8x contrast so individual elements stay visible.
HMIN = 0.007   # fine: upper Delaware River channel + coastline (smaller → more boundary nodes → no slivers)
HMAX = 0.090   # coarse: open bay / Atlantic mouth
G = 0.20       # gradient limit: |grad h| <= G (smooth size growth)

RELAX_ITERS = 26
SMOOTH_ITERS = 8


def read_fort14(path: pathlib.Path) -> tuple[np.ndarray, np.ndarray]:
    """Parse an ADCIRC fort.14: return node xy (N,2) and tri elements (M,3)."""
    with path.open() as fh:
        fh.readline()  # title
        ne, nn = (int(t) for t in fh.readline().split()[:2])
        xy = np.empty((nn, 2))
        for i in range(nn):
            p = fh.readline().split()
            xy[i] = (float(p[1]), float(p[2]))
        elems = np.empty((ne, 3), dtype=np.int64)
        for i in range(ne):
            p = fh.readline().split()
            elems[i] = (int(p[2]) - 1, int(p[3]) - 1, int(p[4]) - 1)
    return xy, elems


def _signed_area(ring: np.ndarray) -> float:
    if len(ring) < 3:
        return 0.0
    x, y = ring[:, 0], ring[:, 1]
    return 0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)


def extract_outer_ring(xy: np.ndarray, elems: np.ndarray) -> np.ndarray:
    """Largest boundary ring (K,2) from triangle edges used by one element."""
    edge_count: dict[tuple[int, int], int] = defaultdict(int)
    for a, b, c in elems:
        for u, v in ((a, b), (b, c), (c, a)):
            edge_count[(u, v) if u < v else (v, u)] += 1
    adj: dict[int, list[int]] = defaultdict(list)
    for (u, v), n in edge_count.items():
        if n == 1:
            adj[u].append(v)
            adj[v].append(u)
    seen: set[int] = set()
    best: list[int] = []
    best_area = 0.0
    for start in adj:
        if start in seen:
            continue
        loop = [start]
        seen.add(start)
        prev, cur = -1, start
        while True:
            opts = [w for w in adj[cur] if w != prev and w not in seen]
            if not opts:
                opts = [w for w in adj[cur] if w == start]
                break_after = True
            else:
                break_after = False
            if not opts:
                break
            nxt = opts[0]
            if nxt == start:
                break
            loop.append(nxt)
            seen.add(nxt)
            prev, cur = cur, nxt
            if break_after:
                break
        area = abs(_signed_area(xy[loop]))
        if area > best_area:
            best_area, best = area, loop
    return xy[best]


def delaware_bay_polygon() -> Polygon:
    """Load + simplify the real Delaware Bay outline (cached as .npy)."""
    ring = None
    for cand in DELBAY_MESH_CANDIDATES:
        if cand.exists():
            print(f"reading real domain: {cand.name}")
            xy, elems = read_fort14(cand)
            ring = extract_outer_ring(xy, elems)
            np.save(RING_CACHE, ring.astype(np.float32))
            break
    if ring is None:
        if not RING_CACHE.exists():
            raise FileNotFoundError(
                "Delaware Bay mesh not found in sibling admesh-domains repo "
                f"and no cache at {RING_CACHE}"
            )
        print(f"using cached ring: {RING_CACHE.name}")
        ring = np.load(RING_CACHE)
    poly = Polygon(ring).buffer(0).simplify(0.006, preserve_topology=True)
    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    return poly


# --------------------------------------------------------------------------
# Graded size function h(x): hmin near coast/river, hmax offshore,
# gradient-limited by g via fast sweeping on a background grid.
# --------------------------------------------------------------------------
def build_size_field(poly: Polygon):
    minx, miny, maxx, maxy = poly.bounds
    pad = HMAX
    nx, ny = 200, 320
    gx = np.linspace(minx - pad, maxx + pad, nx)
    gy = np.linspace(miny - pad, maxy + pad, ny)
    GX, GY = np.meshgrid(gx, gy)               # (ny, nx)
    pts = np.column_stack([GX.ravel(), GY.ravel()])

    # Distance from each grid point to the coastline (boundary).
    ext = poly.exterior
    dist = np.array([ext.distance(Point(p)) for p in pts]).reshape(ny, nx)

    # Local channel width proxy: 2 x distance-to-boundary for interior points.
    pg = prep(poly)
    inside = np.array([pg.contains(Point(p)) for p in pts]).reshape(ny, nx)
    width = 2.0 * dist  # interior "thickness"

    # Base target size: grow away from the coast, but cap by channel width so
    # the narrow river stays fine even at its centerline.
    h = HMIN + 0.85 * dist
    h = np.minimum(h, HMIN + 0.6 * width)
    h = np.clip(h, HMIN, HMAX)

    # Gradient limiting: enforce |grad h| <= G via iterative fast sweeping.
    dx = gx[1] - gx[0]
    dy = gy[1] - gy[0]
    for _ in range(60):
        changed = 0.0
        # 4-direction sweeps
        for axis, step in ((1, dx), (0, dy)):
            for fwd in (True, False):
                rolled = np.roll(h, 1 if fwd else -1, axis=axis)
                cand = rolled + G * step
                newh = np.minimum(h, cand)
                changed = max(changed, np.max(h - newh))
                h = newh
        if changed < 1e-5:
            break

    interp = RegularGridInterpolator((gy, gx), h, bounds_error=False,
                                     fill_value=HMAX)

    def hfun(P: np.ndarray) -> np.ndarray:
        P = np.atleast_2d(P)
        return interp(np.column_stack([P[:, 1], P[:, 0]]))

    return hfun, (gx, gy, h)


# --------------------------------------------------------------------------
# Size-aware point seeding (rejection sampling by local density 1/h^2).
# --------------------------------------------------------------------------
def seed_points(poly: Polygon, hfun):
    minx, miny, maxx, maxy = poly.bounds
    pg = prep(poly)
    # Dense candidate lattice at hmin spacing, then probabilistic thinning.
    xs = np.arange(minx, maxx, HMIN)
    ys = np.arange(miny, maxy, HMIN * np.sqrt(3) / 2)
    cand = []
    for j, y in enumerate(ys):
        off = (HMIN / 2) if (j % 2) else 0.0
        row = np.column_stack([xs + off, np.full(xs.shape, y)])
        cand.append(row)
    cand = np.vstack(cand)
    keep_mask = np.array([pg.contains(Point(p)) for p in cand])
    cand = cand[keep_mask]
    h_at = hfun(cand)
    # Keep probability ~ (hmin / h)^2  -> density ~ 1/h^2 (uniform per-area).
    prob = (HMIN / h_at) ** 2
    interior = cand[RNG.random(len(cand)) < prob]
    # Boundary nodes spaced by local h along the perimeter.
    ext = poly.exterior
    bdry = [np.asarray(ext.coords[0])]
    s = 0.0
    L = ext.length
    while s < L:
        p = np.asarray(ext.interpolate(s).coords[0])
        step = float(hfun(p)[0])
        s += max(step, HMIN)
        bdry.append(p)
    bdry = np.array(bdry[:-1])
    # Drop interior points too close to the boundary.
    h_int = hfun(interior)
    far = np.array([ext.distance(Point(p)) > 0.45 * hi
                    for p, hi in zip(interior, h_int)])
    return interior[far], bdry


# --------------------------------------------------------------------------
# DistMesh truss relaxation with variable rest length L0 ~ h(midpoint).
# --------------------------------------------------------------------------
def relax(interior, bdry, poly, hfun, iters):
    pg = prep(poly)
    ext = poly.exterior
    pts = interior.copy()
    n_int = len(pts)
    frames = []
    for _ in range(iters):
        allpts = np.vstack([pts, bdry])
        tri = Delaunay(allpts)
        bars = set()
        for s in tri.simplices:
            mid = allpts[s].mean(axis=0)
            if not pg.contains(Point(mid)):
                continue
            for u, v in ((s[0], s[1]), (s[1], s[2]), (s[2], s[0])):
                bars.add((u, v) if u < v else (v, u))
        bars = np.array(list(bars))
        p1, p2 = allpts[bars[:, 0]], allpts[bars[:, 1]]
        vec = p1 - p2
        L = np.hypot(vec[:, 0], vec[:, 1])
        mids = 0.5 * (p1 + p2)
        hbar = hfun(mids)
        # DistMesh scaling: L0 = Fscale * hbar * sqrt(sum L^2 / sum hbar^2).
        scale = np.sqrt(np.sum(L ** 2) / np.sum(hbar ** 2))
        L0 = 1.2 * hbar * scale
        F = np.maximum(L0 - L, 0.0)
        Fvec = (F / np.maximum(L, 1e-12))[:, None] * vec
        disp = np.zeros_like(allpts)
        np.add.at(disp, bars[:, 0], Fvec)
        np.add.at(disp, bars[:, 1], -Fvec)
        pts = pts + 0.2 * disp[:n_int]
        for i in range(n_int):
            if not pg.contains(Point(pts[i])):
                d = ext.interpolate(ext.project(Point(pts[i])))
                pts[i] = (d.x, d.y)
        frames.append(np.vstack([pts, bdry]).copy())
    return frames


def laplacian_smooth(pts, simplices, n_int, iters):
    nbr = defaultdict(set)
    for s in simplices:
        for a in s:
            for b in s:
                if a != b:
                    nbr[a].add(b)
    frames = []
    p = pts.copy()
    for _ in range(iters):
        q = p.copy()
        for i in range(n_int):
            ns = list(nbr[i])
            if ns:
                q[i] = 0.4 * p[i] + 0.6 * p[ns].mean(axis=0)
        p = q
        frames.append(p.copy())
    return frames


def tri_quality(pts, simplices):
    a, b, c = pts[simplices[:, 0]], pts[simplices[:, 1]], pts[simplices[:, 2]]
    ab = np.linalg.norm(b - a, axis=1)
    bc = np.linalg.norm(c - b, axis=1)
    ca = np.linalg.norm(a - c, axis=1)
    area = 0.5 * np.abs((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1])
                        - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1]))
    s = (ab + bc + ca) / 2
    rin = np.divide(area, s, out=np.zeros_like(area), where=s > 0)
    rout = np.divide(ab * bc * ca, 4 * area, out=np.ones_like(area), where=area > 0)
    q = np.divide(2 * rin, rout, out=np.zeros_like(area), where=rout > 0)
    return np.clip(q, 0, 1)


def tri_to_quad_frames(final_tri: np.ndarray, tri_simplices: np.ndarray,
                       n_frames: int = 18) -> tuple[
    np.ndarray, np.ndarray, np.ndarray, int]:
    """Generate tri-to-quad conversion: blended frames + final quad mesh.

    For each triangle, split into 3 quads using incenter and edge midpoints.
    Creates (n_frames) blending frames from tri to quad node space.

    Parameters
    ----------
    final_tri : (N, 2)
        Final triangle node positions
    tri_simplices : (M, 3)
        Triangle connectivity
    n_frames : int
        Number of blending frames from tri to quad

    Returns
    -------
    quad_frames : (n_frames, N_quad, 2)
        Quad node positions (constant across frames)
    quad_simplices : (M_quad, 4)
        Quad connectivity (3 quads per triangle)
    tri_to_quad_frames : (n_frames, N_quad, 2)
        Positions during blend from tri to quad node space
    n_tri_to_quad_frames : int
        n_frames
    """
    M = len(tri_simplices)
    N = len(final_tri)

    # Build quad structure: original tri nodes + new nodes (incenter + 3 midpoints per tri)
    # Allocate space for all quad nodes: N (original) + 4*M (new per triangle)
    quad_nodes = np.zeros((N + 4 * M, 2), dtype=np.float32)
    quad_nodes[:N] = final_tri.copy()

    quad_simp_list = []
    next_idx = N

    # For each triangle, create incenter and edge midpoints
    for k, (i0, i1, i2) in enumerate(tri_simplices):
        p0, p1, p2 = final_tri[i0], final_tri[i1], final_tri[i2]

        # Incenter (centroid)
        incenter = (p0 + p1 + p2) / 3.0
        idx_I = next_idx
        quad_nodes[idx_I] = incenter
        next_idx += 1

        # Edge midpoints
        m01 = (p0 + p1) / 2.0
        idx_m01 = next_idx
        quad_nodes[idx_m01] = m01
        next_idx += 1

        m12 = (p1 + p2) / 2.0
        idx_m12 = next_idx
        quad_nodes[idx_m12] = m12
        next_idx += 1

        m20 = (p2 + p0) / 2.0
        idx_m20 = next_idx
        quad_nodes[idx_m20] = m20
        next_idx += 1

        # Create 3 quads: one per corner (CCW winding)
        # Quad 0 (corner p0): (p0, m01, I, m20)
        quad_simp_list.append([i0, idx_m01, idx_I, idx_m20])
        # Quad 1 (corner p1): (p1, m12, I, m01)
        quad_simp_list.append([i1, idx_m12, idx_I, idx_m01])
        # Quad 2 (corner p2): (p2, m20, I, m12)
        quad_simp_list.append([i2, idx_m20, idx_I, idx_m12])

    quad_simplices = np.array(quad_simp_list, dtype=np.int32)

    # Generate blending frames: interpolate new quad nodes from tri-space
    tri_to_quad_frames_list = []
    for frame_idx in range(n_frames):
        alpha = frame_idx / max(1, n_frames - 1)  # 0 -> 1

        # Each frame has all quad node positions
        tri_frame = np.zeros((N + 4 * M, 2), dtype=np.float32)
        # Original tri nodes stay fixed throughout blend
        tri_frame[:N] = final_tri

        # New quad nodes: interpolate from tri-space (centroids / edge midpoints)
        # toward final quad-space (exact incenter / exact edge midpoints)
        next_idx = N
        for k, (i0, i1, i2) in enumerate(tri_simplices):
            p0, p1, p2 = final_tri[i0], final_tri[i1], final_tri[i2]
            tri_centroid = (p0 + p1 + p2) / 3.0

            # Incenter blends from centroid to incenter (same, so no-op)
            incenter = tri_centroid
            tri_frame[next_idx] = (1 - alpha) * tri_centroid + alpha * incenter
            next_idx += 1

            # Edge midpoints: start at triangle centroid, blend to actual midpoint
            m01 = (p0 + p1) / 2.0
            tri_frame[next_idx] = (1 - alpha) * tri_centroid + alpha * m01
            next_idx += 1

            m12 = (p1 + p2) / 2.0
            tri_frame[next_idx] = (1 - alpha) * tri_centroid + alpha * m12
            next_idx += 1

            m20 = (p2 + p0) / 2.0
            tri_frame[next_idx] = (1 - alpha) * tri_centroid + alpha * m20
            next_idx += 1

        tri_to_quad_frames_list.append(tri_frame)

    tri_to_quad_frames = np.array(tri_to_quad_frames_list, dtype=np.float32)

    # Quad frames: final quad positions (constant across all blend frames)
    quad_frames = np.tile(quad_nodes[np.newaxis, :, :], (n_frames, 1, 1)).astype(np.float32)

    return quad_frames, quad_simplices, tri_to_quad_frames, n_frames


def main() -> None:
    print(f"hyperparameters: hmin={HMIN}  hmax={HMAX}  g={G}")
    poly = delaware_bay_polygon()
    print(f"Delaware Bay outline: {len(poly.exterior.coords)} verts, "
          f"area {poly.area:.3f} deg^2")

    hfun, _grid = build_size_field(poly)
    interior, bdry = seed_points(poly, hfun)
    n_int = len(interior)
    print(f"seeded {n_int} interior + {len(bdry)} boundary nodes "
          f"(graded by h)")

    relax_frames = relax(interior, bdry, poly, hfun, RELAX_ITERS)
    final_relaxed = relax_frames[-1]

    tri = Delaunay(final_relaxed)
    cent = final_relaxed[tri.simplices].mean(axis=1)
    pg = prep(poly)
    inside = np.array([pg.contains(Point(c)) for c in cent])
    simplices = tri.simplices[inside]
    # Sliver filter applied after all frames are built (see below).
    n_inside = inside.sum()
    simplices = tri.simplices[inside]

    # Initialized stage: jitter interior for a rough look, but ensure no
    # triangle in the (fixed) connectivity inverts (which would give q=0).
    ext = poly.exterior
    h_int = hfun(final_relaxed[:n_int])
    init = final_relaxed.copy()
    raw_jitter = RNG.normal(scale=0.16, size=(n_int, 2)) * h_int[:, None]
    # Build per-node neighbour list from the fixed connectivity.
    nbr_map: dict[int, list[int]] = defaultdict(list)
    for s in simplices:
        for a in s:
            for b in s:
                if a != b:
                    nbr_map[a].append(b)
    # Apply jitter in random order; after each node move check all its
    # triangles stay CCW (positive signed area).  If any inverts, scale
    # the displacement back until they're all positive.
    order = RNG.permutation(n_int)
    for i in order:
        p_orig = init[i].copy()
        for alpha in (1.0, 0.7, 0.4, 0.15, 0.0):
            cand = p_orig + alpha * raw_jitter[i]
            if not pg.contains(Point(cand)):
                continue
            # Check all triangles containing node i.
            ok = True
            for s in simplices:
                if i not in s:
                    continue
                pts_tri = init[list(s)]
                idx_in_tri = list(s).index(i)
                pts_tri[idx_in_tri] = cand
                a_, b_, c_ = pts_tri
                area = (b_[0]-a_[0])*(c_[1]-a_[1]) - (c_[0]-a_[0])*(b_[1]-a_[1])
                if area < HMIN ** 2 * 0.02:   # reject near-zero as well as negative
                    ok = False
                    break
            if ok:
                init[i] = cand
                break

    relax_seq = [init]
    for k, fr in enumerate(relax_frames):
        t = (k + 1) / len(relax_frames)
        relax_seq.append((1 - t) * init + t * fr)

    smooth_frames = laplacian_smooth(final_relaxed, simplices, n_int, SMOOTH_ITERS)

    frames = np.stack(relax_seq + smooth_frames)   # (T, N, 2)

    # Keep only triangles whose area exceeds threshold in EVERY frame,
    # so min q > 0 holds throughout the animation.
    thresh = HMIN ** 2 * 0.02
    vp = frames[:, simplices]                       # (T, M, 3, 2)
    areas = 0.5 * np.abs(
        (vp[:, :, 1, 0] - vp[:, :, 0, 0]) * (vp[:, :, 2, 1] - vp[:, :, 0, 1])
        - (vp[:, :, 2, 0] - vp[:, :, 0, 0]) * (vp[:, :, 1, 1] - vp[:, :, 0, 1])
    )                                               # (T, M)
    good = (areas > thresh).all(axis=0)             # (M,)
    n_before = len(simplices)
    simplices = simplices[good]
    print(f"  kept {len(simplices)} triangles after all-frame sliver filter "
          f"(dropped {n_before - len(simplices)})")

    q_init = tri_quality(frames[0], simplices)
    q_relax = tri_quality(final_relaxed, simplices)
    q_final = tri_quality(frames[-1], simplices)
    print(f"mean quality: init={q_init.mean():.3f}  min={q_init.min():.3f}  "
          f"truss={q_relax.mean():.3f}  fem={q_final.mean():.3f}  min={q_final.min():.3f}")

    # Stage 4: Tri2Quad conversion
    print("\ncomputing tri-to-quad stage...")
    quad_frames, quad_simplices, tri_to_quad_blend_frames, n_tri_to_quad_frames = tri_to_quad_frames(
        frames[-1], simplices, n_frames=18
    )
    print(f"  generated {n_tri_to_quad_frames} tri-to-quad blend frames")
    print(f"  quad mesh: {quad_frames.shape[1]} nodes, {len(quad_simplices)} quads")

    np.savez_compressed(
        OUT,
        frames=frames.astype(np.float32),
        simplices=simplices.astype(np.int32),
        ring=np.asarray(poly.exterior.coords, dtype=np.float32),
        n_interior=n_int,
        n_relax_frames=len(relax_seq),
        n_smooth_frames=len(smooth_frames),
        hmin=HMIN, hmax=HMAX, g=G,
        quad_frames=quad_frames.astype(np.float32),
        quad_simplices=quad_simplices.astype(np.int32),
        tri_to_quad_frames=tri_to_quad_blend_frames.astype(np.float32),
        n_tri_to_quad_frames=n_tri_to_quad_frames,
    )
    print(f"wrote {OUT.name}  ({frames.shape[0]} frames, "
          f"{len(simplices)} triangles, {len(quad_simplices)} quads, "
          f"{n_tri_to_quad_frames} blend frames)")


if __name__ == "__main__":
    main()
