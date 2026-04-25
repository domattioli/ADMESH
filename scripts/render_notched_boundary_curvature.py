"""Notched-rectangle boundary unrolled to 1D — pre/post distmesh + κ(s).

For the notched_rectangle domain:

1. **Pre (iteration 0)** — initial-distribution nodes from the same
   hex-lattice + rejection sampler ``distmesh2d`` itself uses, then
   project the near-boundary subset onto the boundary. This is the
   actual boundary-node set entering iteration 1 of the Domain path
   (the same path the ``demo_notched_rectangle_medial`` figure uses).
   Falls back to uniform arc-length resampling when no near-boundary
   lattice points exist.
2. **Post** — converged Domain-path triangulation with the same
   enriched ``fh`` the notched-rect demo uses (medial-axis LFS
   refinement). Boundary nodes identified by ``|fd(p)| < tol``.
3. Sample κ on a fine grid via :func:`admesh.curvature.curvature_grid`,
   then trace it along the boundary by sampling the grid at points
   parameterized by arc length ``s ∈ [0, perimeter)``.
4. Render a 2-row figure sharing the same s-axis: top = pre nodes
   over κ(s); bottom = post nodes over κ(s). Vertical guides label
   the eight corners of the notched rectangle.

Run:
    python scripts/render_notched_boundary_curvature.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import RegularGridInterpolator

from admesh import domains
from admesh.boundary import PTS
from admesh.curvature import curvature_grid
from admesh.distance import eval_sdf_grid
from admesh.distmesh import _initial_distribution, _rejection_method
from admesh.mesh_size import build_h
from admesh.routine import triangulate

matplotlib.use("Agg")

OUTDIR = Path(__file__).resolve().parent.parent / "tests" / "output"
OUTDIR.mkdir(parents=True, exist_ok=True)


def _arc_length(ring: np.ndarray) -> tuple[np.ndarray, float]:
    """Cumulative arc length at each ring vertex (closed loop)."""
    closed = np.vstack([ring, ring[:1]])
    seg = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    return s[:-1], float(s[-1])


def _project_to_ring(p: np.ndarray, ring: np.ndarray) -> np.ndarray:
    """Arc-length parameter ``s`` of each point ``p[i]`` on ``ring``.

    Each query point is snapped to the nearest segment of the closed
    ring; ``s`` is the arc length up to the segment start plus the
    in-segment projection length.
    """
    s_v, _ = _arc_length(ring)
    n = len(ring)
    s_out = np.empty(len(p))
    closed = np.vstack([ring, ring[:1]])
    seg_start = closed[:-1]
    seg_end = closed[1:]
    seg_vec = seg_end - seg_start
    seg_len = np.linalg.norm(seg_vec, axis=1)

    for i, q in enumerate(p):
        # Project q onto every segment, clamp t∈[0,1], pick the closest.
        rel = q - seg_start
        denom = (seg_vec * seg_vec).sum(axis=1)
        denom[denom < 1e-30] = 1.0
        t = np.clip((rel * seg_vec).sum(axis=1) / denom, 0.0, 1.0)
        proj = seg_start + t[:, None] * seg_vec
        d = np.linalg.norm(q - proj, axis=1)
        k = int(np.argmin(d))
        s_out[i] = s_v[k] + t[k] * seg_len[k]
    return s_out


def _sample_curvature_along_boundary(
    domain, ring: np.ndarray, grid_delta: float = 0.005, n_samples: int = 1000,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute κ on a grid, then sample it at points along the ring.

    Returns ``(s_dense, kappa_dense, X, Y)`` so the caller can also draw
    the 2D inset if useful. The κ samples are taken slightly INSIDE the
    boundary (offset by ``2·grid_delta`` along the inward normal) so we
    pick up finite κ values rather than the NaN-masked exact-boundary
    pixels (where ``|∇D| → 0`` at corners).
    """
    X, Y, D = eval_sdf_grid(domain.fd, domain.bbox, grid_delta)
    kappa = curvature_grid(D, grid_delta)

    xs = X[0, :]
    ys = Y[:, 0]
    interp = RegularGridInterpolator(
        (ys, xs), kappa, method="linear", bounds_error=False, fill_value=np.nan,
    )

    # Walk the closed boundary at uniform arc length.
    s_v, S = _arc_length(ring)
    s_dense = np.linspace(0.0, S, n_samples, endpoint=False)
    closed = np.vstack([ring, ring[:1]])
    seg_start = closed[:-1]
    seg_end = closed[1:]
    seg_vec = seg_end - seg_start
    seg_len = np.linalg.norm(seg_vec, axis=1)

    # Inward normal: rotate +90°(CCW ring → interior on the left of the
    # forward direction). Notched rectangle is CCW from PTS.from_domain.
    seg_unit = seg_vec / np.maximum(seg_len[:, None], 1e-30)
    inward = np.column_stack([-seg_unit[:, 1], seg_unit[:, 0]])
    offset = 2.0 * grid_delta

    # Bin s_dense into segments.
    seg_idx = np.searchsorted(s_v, s_dense, side="right") - 1
    seg_idx = np.clip(seg_idx, 0, len(s_v) - 1)
    t = (s_dense - s_v[seg_idx]) / np.maximum(seg_len[seg_idx], 1e-30)
    pt = seg_start[seg_idx] + t[:, None] * seg_vec[seg_idx] + offset * inward[seg_idx]

    kappa_dense = interp(np.column_stack([pt[:, 1], pt[:, 0]]))
    return s_dense, kappa_dense, X, Y


def main() -> None:
    np.random.seed(0)
    dom = domains.NOTCHED_RECTANGLE
    h0 = 0.04

    # ------------------------------------------------------------------
    # Reference ring for the arc-length parameterization. We use a
    # finely-resampled boundary (the PTS contour) ONLY as the geometric
    # anchor for the s-coordinate; pre and post nodes both project onto it.
    # ------------------------------------------------------------------
    perim = 7.0  # 2.0 + 1.0 + 0.95 + 0.5 + 0.1 + 0.5 + 0.95 + 1.0
    pts = PTS.from_domain(dom, n_bnd=int(round(perim / h0)))
    ring = pts.rings[0]

    # ------------------------------------------------------------------
    # 1. PRE (iteration 0) — the initial point distribution that
    #    distmesh2d Domain path generates: hex lattice + rejection on fd
    #    + rejection on fh, then keep points within ``geps`` of the
    #    boundary. These are the nodes that will be projected exactly
    #    onto the boundary in iteration 1 (so they ARE the iter-0
    #    boundary node set, modulo a sub-h0 projection step).
    # ------------------------------------------------------------------
    fh = build_h(dom, base=0.12, medial_scale=0.04, grid_delta=0.02)
    rng = np.random.default_rng(0)

    # Replicate distmesh2d's initial distribution + rejection pipeline.
    p_lat = _initial_distribution(dom.bbox, h0)
    geps = 1e-3 * h0
    p_lat = p_lat[dom.fd(p_lat) < geps]
    if len(dom.fixed_points) > 0:
        # Drop lattice points within h0/2 of any fixed corner (distmesh
        # convention) to avoid duplicates after pfix prepend.
        fp = dom.fixed_points
        keep = np.ones(len(p_lat), dtype=bool)
        for f in fp:
            keep &= np.linalg.norm(p_lat - f, axis=1) > h0 / 2.0
        p_lat = p_lat[keep]
        p_lat = np.vstack([fp, p_lat])
    p_lat = _rejection_method(p_lat, fh, rng) if fh is not None else p_lat

    # "Iteration-0 boundary node set" = lattice points that are within
    # h0/2 of the boundary AFTER projection along -∇fd. Projection
    # mirrors what distmesh's iteration-1 boundary step does.
    fd_vals = dom.fd(p_lat)
    near = np.abs(fd_vals) < h0 / 2.0
    pre_bnd_xy = p_lat[near]
    # Project onto boundary by Newton step along ∇fd.
    eps = 1e-7
    fdp = dom.fd(pre_bnd_xy)
    gx = (dom.fd(pre_bnd_xy + np.array([eps, 0.0])) - fdp) / eps
    gy = (dom.fd(pre_bnd_xy + np.array([0.0, eps])) - fdp) / eps
    g_mag2 = gx ** 2 + gy ** 2
    pre_bnd_xy = pre_bnd_xy - np.column_stack([
        fdp * gx / np.maximum(g_mag2, 1e-30),
        fdp * gy / np.maximum(g_mag2, 1e-30),
    ])
    s_pre = _project_to_ring(pre_bnd_xy, ring)
    print(f"Pre (iteration 0) boundary nodes: {len(pre_bnd_xy)} "
          f"(perimeter {perim:.3f})")

    # ------------------------------------------------------------------
    # 2. POST — Domain-path triangulation, identify converged boundary
    #    nodes by ``|fd(p)| < geps``. Same fh as the demo.
    # ------------------------------------------------------------------
    p_post, _ = triangulate(dom, h0=h0, fh=fh, niter=250, seed=0)
    on_bnd = np.abs(dom.fd(p_post)) < 5.0 * geps
    post_bnd_xy = p_post[on_bnd]
    s_post = _project_to_ring(post_bnd_xy, ring)
    print(f"Post (converged) boundary nodes:  {len(post_bnd_xy)}")

    # ------------------------------------------------------------------
    # 3. κ along the boundary.
    # ------------------------------------------------------------------
    s_dense, kappa_dense, X, Y = _sample_curvature_along_boundary(
        dom, ring, grid_delta=0.005, n_samples=2000,
    )

    # Replace NaNs (right at corner singularities) with neighboring values
    # for plotting continuity. NaNs are real — they mark where |∇D|<eps —
    # but they fragment the line plot.
    kappa_plot = kappa_dense.copy()
    nan = np.isnan(kappa_plot)
    if nan.any():
        idx = np.arange(len(kappa_plot))
        kappa_plot[nan] = np.interp(idx[nan], idx[~nan], kappa_plot[~nan])

    # ------------------------------------------------------------------
    # 4. Corner s-values for vertical guides — derived from the eight
    #    fixed-point corners of the notched rectangle.
    # ------------------------------------------------------------------
    corners = np.array([
        [-1.0, -0.5],  # 0  bottom-left
        [ 1.0, -0.5],  # 1  bottom-right
        [ 1.0,  0.5],  # 2  top-right (outer)
        [ 0.05, 0.5],  # 3  notch top-right
        [ 0.05, 0.0],  # 4  notch tip-right
        [-0.05, 0.0],  # 5  notch tip-left
        [-0.05, 0.5],  # 6  notch top-left
        [-1.0,  0.5],  # 7  top-left (outer)
    ])
    s_corners = _project_to_ring(corners, ring)
    corner_labels = [
        "BL", "BR", "TR", "notch ↘", "tip R", "tip L", "notch ↙", "TL",
    ]

    # ------------------------------------------------------------------
    # 5. Plot.
    # ------------------------------------------------------------------
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)

    # Background κ(s) — use a symmetric log-ish color scale; here just plot
    # κ as a line and shade the region under |κ|.
    for ax in axes:
        ax.plot(s_dense, kappa_dense, color="#888", lw=0.8, label="κ(s)")
        ax.axhline(0.0, color="k", lw=0.4, alpha=0.4)
        for sc, lbl in zip(s_corners, corner_labels):
            ax.axvline(sc, color="#bbb", lw=0.5, ls=":")
            ax.text(sc, 0, f" {lbl}", fontsize=7, color="#666",
                    va="bottom", ha="left", rotation=90, alpha=0.85)
        ax.grid(True, alpha=0.2)

    # Top: pre nodes — sample κ at each pre node so we can color the marker.
    kappa_at_pre = np.interp(s_pre, s_dense, kappa_plot)
    sc0 = axes[0].scatter(
        s_pre, kappa_at_pre, c=kappa_at_pre, cmap="coolwarm",
        s=28, edgecolor="k", linewidths=0.4, zorder=3,
        vmin=-np.nanmax(np.abs(kappa_dense)),
        vmax=np.nanmax(np.abs(kappa_dense)),
    )
    axes[0].set_title(
        f"Pre-distmesh — iteration-0 lattice projection: "
        f"{len(pre_bnd_xy)} nodes (hex lattice + rejection + boundary snap)",
        fontsize=10,
    )
    axes[0].set_ylabel("κ (1/length)")

    # Bottom: post nodes.
    kappa_at_post = np.interp(s_post, s_dense, kappa_plot)
    sc1 = axes[1].scatter(
        s_post, kappa_at_post, c=kappa_at_post, cmap="coolwarm",
        s=28, edgecolor="k", linewidths=0.4, zorder=3,
        vmin=-np.nanmax(np.abs(kappa_dense)),
        vmax=np.nanmax(np.abs(kappa_dense)),
    )
    axes[1].set_title(
        f"Post-distmesh — boundary nodes from converged Domain-path mesh "
        f"(medial-LFS fh): {len(post_bnd_xy)} nodes",
        fontsize=10,
    )
    axes[1].set_xlabel("arc length s along boundary (CCW from bottom-left)")
    axes[1].set_ylabel("κ (1/length)")

    cbar = fig.colorbar(sc1, ax=axes, orientation="vertical", pad=0.02, aspect=30)
    cbar.set_label("κ (signed)")

    fig.suptitle(
        "notched_rectangle: boundary unrolled to 1D — node placement vs. κ(s)\n"
        "+κ = convex (outward turn), −κ = concave (re-entrant)",
        fontsize=11,
    )

    out_path = OUTDIR / "demo_notched_boundary_curvature.png"
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out_path}")

    # ------------------------------------------------------------------
    # 6. Print a small summary table — discrete turning angle (signed
    #    integrated κ at each corner). For a CCW polygon, +turn = convex,
    #    −turn = re-entrant. This reports cleanly even at concave corners
    #    where the inward-offset grid sample picks up the wrong side.
    # ------------------------------------------------------------------
    print("\nDiscrete turn (signed integrated κ) at corners:")
    n = len(corners)
    for i, (sc, lbl) in enumerate(zip(s_corners, corner_labels)):
        v_in = corners[i] - corners[(i - 1) % n]
        v_out = corners[(i + 1) % n] - corners[i]
        v_in /= np.linalg.norm(v_in)
        v_out /= np.linalg.norm(v_out)
        cross = float(v_in[0] * v_out[1] - v_in[1] * v_out[0])
        dot = float(v_in[0] * v_out[0] + v_in[1] * v_out[1])
        ang = float(np.arctan2(cross, dot))
        sign = "convex (+)" if ang > 1e-6 else ("re-entrant (−)" if ang < -1e-6 else "flat")
        print(f"  s = {sc:6.3f}  {lbl:>8s}   Δθ = {ang:+7.4f} rad   {sign}")


if __name__ == "__main__":
    main()
