"""Mesh generators for the exact-coast challenge.

Each ``run_*`` takes ``rings`` (outer first, then holes), a ``GridField`` that
already carries the node-budget scale s, and the base size H.  It returns
``(nodes, tris, seconds)``.  Timing covers geometry set-up plus meshing, single
thread, and excludes the shared size-field build and file reading.
"""

from __future__ import annotations

import time

import numpy as np


def _unique_pts(rings):
    """Deduplicate vertices by exact coordinate; return (pts, ring index lists)."""
    idx: dict[tuple[float, float], int] = {}
    pts: list[tuple[float, float]] = []
    loops = []
    for r in rings:
        loop = []
        for x, y in np.asarray(r, float):
            k = (float(x), float(y))
            if k not in idx:
                idx[k] = len(pts)
                pts.append(k)
            loop.append(idx[k])
        # drop consecutive repeats
        loop = [v for i, v in enumerate(loop) if v != loop[i - 1]]
        loops.append(loop)
    return np.array(pts), loops


def _compact(nodes, tris):
    used = np.unique(tris)
    remap = -np.ones(len(nodes), int)
    remap[used] = np.arange(len(used))
    return nodes[used], remap[tris]


# ---------------------------------------------------------------- ADMESH
def run_admesh(rings, field, H):
    import warnings

    import admesh
    from admesh.loaders import _domain_from_polygon

    dom = _domain_from_polygon([np.asarray(r, float) for r in rings])
    # admesh's h0 is the lattice spacing at the smallest requested size (the
    # default channel_refine path sets h0 = field floor).  Use the actual
    # minimum of the scaled field inside the domain so sizes are honoured.
    X, Y = np.meshgrid(field.x, field.y)
    P = np.c_[X.ravel(), Y.ravel()]
    inside = np.asarray(dom.sdf(P)) < 0
    h0 = float(field(P[inside]).min())
    t0 = time.perf_counter()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = admesh.triangulate(
            dom, h_max=h0,
            size_field=field, seed=0, boundary="fixed", simplify=None,
            quality_gate=(0.0, 0.0),
        )
    dt = time.perf_counter() - t0
    nodes, tris = _compact(np.asarray(m.nodes, float), np.asarray(m.elements, int))
    return nodes, tris, dt


# ------------------------------------------------------------------ Gmsh
def _quiet_init(gmsh):
    """gmsh.initialize() prints harmless PETSc getdomainname errors to fd 2 in the
    sandbox; silence fd 2 for the call only."""
    import os

    saved = os.dup(2)
    null = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(null, 2)
        gmsh.initialize()
    finally:
        os.dup2(saved, 2)
        os.close(saved)
        os.close(null)


def run_gmsh(rings, field, H, optimize: bool = False):
    import gmsh

    pts, loops = _unique_pts(rings)
    t0 = time.perf_counter()
    _quiet_init(gmsh)
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("General.NumThreads", 1)
        gmsh.option.setNumber("Mesh.MaxNumThreads1D", 1)
        gmsh.option.setNumber("Mesh.MaxNumThreads2D", 1)
        gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
        gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
        gmsh.option.setNumber("Mesh.Algorithm", 6)  # Frontal-Delaunay
        gmsh.model.add("coast")
        g = gmsh.model.geo
        ptag = [g.addPoint(x, y, 0.0, H) for x, y in pts]
        cl = []
        for loop in loops:
            lines = [g.addLine(ptag[loop[i]], ptag[loop[(i + 1) % len(loop)]])
                     for i in range(len(loop))]
            cl.append(g.addCurveLoop(lines))
        g.addPlaneSurface(cl)
        g.synchronize()
        gmsh.model.mesh.setSizeCallback(lambda dim, tag, x, y, z, lc: field.at(x, y))
        gmsh.model.mesh.generate(2)
        if optimize:
            gmsh.model.mesh.optimize("Laplace2D", niter=5)
        ntags, coords, _ = gmsh.model.mesh.getNodes()
        _, etags = gmsh.model.mesh.getElementsByType(2)[0], gmsh.model.mesh.getElementsByType(2)[1]
        dt = time.perf_counter() - t0
        xyz = np.asarray(coords).reshape(-1, 3)[:, :2]
        order = {int(t): i for i, t in enumerate(ntags)}
        tris = np.array([order[int(t)] for t in etags]).reshape(-1, 3)
    finally:
        gmsh.finalize()
    nodes, tris = _compact(xyz, tris)
    return nodes, tris, dt


# -------------------------------------------------------------- Triangle
def run_triangle(rings, field, H, max_rounds: int = 8):
    import triangle
    from shapely.geometry import Polygon

    pts, loops = _unique_pts(rings)
    segs = np.array([(loop[i], loop[(i + 1) % len(loop)])
                     for loop in loops for i in range(len(loop))])
    holes = np.array([Polygon(r).representative_point().coords[0] for r in rings[1:]]
                     ).reshape(-1, 2)
    t0 = time.perf_counter()
    inp = dict(vertices=pts, segments=segs)
    if len(holes):
        inp["holes"] = holes
    out = triangle.triangulate(inp, "pq30")
    sq = np.sqrt(3.0) / 4.0
    for _ in range(max_rounds):
        v, t = out["vertices"], out["triangles"]
        cen = v[t].mean(axis=1)
        amax = sq * field(cen) ** 2
        a = 0.5 * np.abs((v[t[:, 1], 0] - v[t[:, 0], 0]) * (v[t[:, 2], 1] - v[t[:, 0], 1])
                      - (v[t[:, 1], 1] - v[t[:, 0], 1]) * (v[t[:, 2], 0] - v[t[:, 0], 0]))
        viol = a > amax
        if not viol.any():
            break
        ref = dict(vertices=v, segments=out["segments"], triangles=t,
                   triangle_max_area=amax)
        new = triangle.triangulate(ref, "rpq30a")
        stable = abs(len(new["triangles"]) - len(t)) < 0.005 * len(t)
        out = new
        if stable:
            break
    dt = time.perf_counter() - t0
    nodes, tris = _compact(np.asarray(out["vertices"], float), np.asarray(out["triangles"], int))
    return nodes, tris, dt


# ------------------------------------------------------------ oceanmesh
LAST_DIAG: dict = {}


def run_oceanmesh(rings, field, H, pfix: bool = False, max_iter: int = 50):
    """oceanmesh via its Domain / Grid / generate_mesh API (as in its README and tests).

    oceanmesh's examples build the domain with om.Shoreline(<shapefile>) +
    om.signed_distance_function(shore), which reads a shapefile and cannot take a
    plain polygon.  Fallback used here: om.Domain(bbox, sdf) where sdf is
    admesh.loaders._shapely_sdf (same sdf the size field was built from).  The size
    function is an om.Grid holding the shared field values (bilinear
    om.Grid.build_interpolant, extrapolate=True).  om.enforce_mesh_gradation is NOT
    applied: the shared field is already gradient-limited (g=0.2) and the call
    needs dx == dy and is defined on a different gradation scale.
    Cleanup as in the README: make_mesh_boundaries_traversable then
    delete_faces_connected_to_one_face.  Diagnostics go to LAST_DIAG.
    """
    import os

    os.environ.setdefault("MPLCONFIGDIR", "/tmp/claude/mpl")
    import oceanmesh as om
    from admesh.loaders import _shapely_sdf

    import metrics as M

    sdf = _shapely_sdf([np.asarray(r, float) for r in rings])
    allp = np.vstack(rings)
    bbox = (allp[:, 0].min(), allp[:, 0].max(), allp[:, 1].min(), allp[:, 1].max())
    X, Y = np.meshgrid(field.x, field.y)
    P = np.c_[X.ravel(), Y.ravel()]
    hmin = float(field(P[np.asarray(sdf(P)) < 0]).min())
    grid = om.Grid(
        bbox=(field.x[0], field.x[-1], field.y[0], field.y[-1]),
        dx=field.dx, dy=field.dy, hmin=hmin,
        values=(field.H * field.scale).T.copy(),  # (nx, ny)
        extrapolate=True, crs="EPSG:4326",
    )
    grid.build_interpolant()
    domain = om.Domain(bbox, sdf)
    kw = {}
    if pfix:
        kw["pfix"] = _unique_pts(rings)[0]
    t0 = time.perf_counter()
    p0, t0_ = om.generate_mesh(domain, grid, max_iter=max_iter, seed=0, **kw)
    p1, t1 = om.make_mesh_boundaries_traversable(p0, t0_)
    p2, t2 = om.delete_faces_connected_to_one_face(p1, t1)
    dt = time.perf_counter() - t0

    def stats(p, t):
        p = np.asarray(p, float)
        t = np.asarray(t, int)
        q = M.triangle_quality(p, t)
        be = M.boundary_edges(t)
        bv = np.unique(be)
        onb = np.isin(t, bv).any(axis=1)
        bad = q < 0.3
        return dict(q=q, nt=len(t), nb=len(bv), qmin=float(q.min()),
                    bad=int(bad.sum()), bad_on_b=int((bad & onb).sum()))

    r, c = stats(p0, t0_), stats(p2, t2)
    LAST_DIAG.clear()
    LAST_DIAG.update(
        oc_q_min_raw=r["qmin"], oc_q_min_clean=c["qmin"],
        oc_faces_removed=r["nt"] - c["nt"], oc_bverts_removed=r["nb"] - c["nb"],
        oc_bad_raw=r["bad"], oc_bad_raw_on_boundary=r["bad_on_b"],
        oc_bad_clean=c["bad"], oc_bad_clean_on_boundary=c["bad_on_b"],
        oc_nodes_raw=len(p0),
    )
    nodes, tris = _compact(np.asarray(p2, float), np.asarray(t2, int))
    return nodes, tris, dt


RUNNERS = {
    "oceanmesh": lambda r, f, H: run_oceanmesh(r, f, H, False, 50),
    "oceanmesh_it100": lambda r, f, H: run_oceanmesh(r, f, H, False, 100),
    "oceanmesh_it200": lambda r, f, H: run_oceanmesh(r, f, H, False, 200),
    "oceanmesh_pfix": lambda r, f, H: run_oceanmesh(r, f, H, True, 50),
    "oceanmesh_pfix_it200": lambda r, f, H: run_oceanmesh(r, f, H, True, 200),
    "admesh": run_admesh,
    "gmsh": lambda r, f, H: run_gmsh(r, f, H, False),
    "gmsh_opt": lambda r, f, H: run_gmsh(r, f, H, True),
    "triangle": run_triangle,
}
