"""Pure-ADMESH quad-readiness metrics and reporting (additive layer).

Companion to ``admesh.quad_prep.smooth_for_quadrangulation`` (spec-004).
Computes and reports per-triangle and per-node metrics for assessing mesh
readiness for downstream quad fusion (CHILmesh ``tri2quad``, OceanMesh2D, ADCIRC v55+).

No matplotlib, no chilmesh imports. Pure numpy + listed ADMESH API.
"""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from admesh.valence import compute_valence, _boundary_mask
from admesh._stages.quality import mesh_quality, right_iso_quality
from admesh.quad_prep import _build_pairing_map

if TYPE_CHECKING:
    from admesh.api import Mesh


def interior_valence_histogram(mesh: "Mesh") -> dict[int, int]:
    """Histogram of valence values for interior nodes only.

    Computes element-star valence (number of incident triangles) per node,
    then filters to interior nodes using the boundary mask. Boundary nodes
    are excluded entirely.

    Parameters
    ----------
    mesh : Mesh
        Input triangular mesh.

    Returns
    -------
    dict[int, int]
        Mapping from valence (int) to count of interior nodes with that
        valence. Empty dict if no interior nodes exist.

    Notes
    -----
    Valence for a node is the number of triangles incident to it.
    For an interior node in a regular triangulation, the ideal is 6
    (equilateral tiling).
    """
    valence = compute_valence(mesh.elements)
    boundary = _boundary_mask(mesh)
    interior_valence = valence[~boundary]

    if interior_valence.size == 0:
        return {}

    hist = {}
    for v in interior_valence:
        v_int = int(v)
        hist[v_int] = hist.get(v_int, 0) + 1
    return hist


def pct_even_interior(mesh: "Mesh") -> float:
    """Fraction of interior nodes with even valence.

    Computes the percentage of interior nodes whose valence is even.
    Returns 0.0 if no interior nodes exist.

    Parameters
    ----------
    mesh : Mesh
        Input triangular mesh.

    Returns
    -------
    float
        Fraction in [0, 1] of interior nodes with even valence.
    """
    valence = compute_valence(mesh.elements)
    boundary = _boundary_mask(mesh)
    interior_valence = valence[~boundary]

    if interior_valence.size == 0:
        return 0.0

    even_count = np.sum(interior_valence % 2 == 0)
    return float(even_count) / len(interior_valence)


def mean_abs_valence_dev(mesh: "Mesh", ideal: int = 8) -> float:
    """Mean absolute deviation of interior-node valence from ideal.

    Computes the mean of |valence[i] - ideal| over all interior nodes.
    Returns 0.0 if no interior nodes exist.

    Parameters
    ----------
    mesh : Mesh
        Input triangular mesh.
    ideal : int, optional
        Target valence; default 8 (quad-dominant target: 4 quads per node
        in a regular pattern). For equilateral triangulation, use 6.

    Returns
    -------
    float
        Mean absolute deviation of interior-node valence from ideal.
    """
    valence = compute_valence(mesh.elements)
    boundary = _boundary_mask(mesh)
    interior_valence = valence[~boundary]

    if interior_valence.size == 0:
        return 0.0

    return float(np.mean(np.abs(interior_valence - ideal)))


def iso_dev(p: NDArray[np.float64], t: NDArray[np.int64]) -> NDArray[np.float64]:
    """Per-triangle mean absolute angle deviation from right-isoceles target.

    For each triangle, computes its 3 interior angles (in degrees), sorts them
    ascending, and compares element-wise to the sorted right-isoceles target
    [45, 45, 90]. Returns the mean absolute difference (in degrees) per triangle.

    Degenerate triangles (zero-length edges) return np.nan.

    Parameters
    ----------
    p : ndarray, shape (N, 2), dtype float64
        Nodal coordinates.
    t : ndarray, shape (M, 3), dtype int64
        Triangle connectivity (0-based).

    Returns
    -------
    ndarray, shape (M,), dtype float64
        Per-triangle mean absolute angle deviation (in degrees). Degenerate
        elements marked as np.nan.

    Notes
    -----
    Right-isoceles target angles (sorted): [45, 45, 90] degrees.
    Computation: for each triangle, extract 3 edge lengths, compute interior
    angles via law of cosines, sort, then compute mean(|sorted_angles - [45,45,90]|).
    """
    p = np.asarray(p, dtype=np.float64)
    t = np.asarray(t, dtype=np.int64)

    if len(t) == 0:
        return np.array([], dtype=np.float64)

    x = p[:, 0]
    y = p[:, 1]

    # Edge lengths
    a = np.hypot(x[t[:, 1]] - x[t[:, 0]], y[t[:, 1]] - y[t[:, 0]])
    b = np.hypot(x[t[:, 2]] - x[t[:, 1]], y[t[:, 2]] - y[t[:, 1]])
    c = np.hypot(x[t[:, 0]] - x[t[:, 2]], y[t[:, 0]] - y[t[:, 2]])

    # Law of cosines: cos(angle) = (b^2 + c^2 - a^2) / (2*b*c)
    # For each vertex
    with np.errstate(divide="ignore", invalid="ignore"):
        cos_A = (b * b + c * c - a * a) / (2.0 * b * c)
        cos_B = (c * c + a * a - b * b) / (2.0 * c * a)
        cos_C = (a * a + b * b - c * c) / (2.0 * a * b)

    # Clip to [-1, 1] to handle numerical errors
    cos_A = np.clip(cos_A, -1.0, 1.0)
    cos_B = np.clip(cos_B, -1.0, 1.0)
    cos_C = np.clip(cos_C, -1.0, 1.0)

    angle_A = np.arccos(cos_A)  # radians
    angle_B = np.arccos(cos_B)
    angle_C = np.arccos(cos_C)

    # Convert to degrees
    angle_A_deg = np.degrees(angle_A)
    angle_B_deg = np.degrees(angle_B)
    angle_C_deg = np.degrees(angle_C)

    # Sort angles per triangle
    angles = np.column_stack([angle_A_deg, angle_B_deg, angle_C_deg])
    angles_sorted = np.sort(angles, axis=1)

    # Right-isoceles target: [45, 45, 90]
    target = np.array([45.0, 45.0, 90.0])

    # Mean absolute deviation per triangle
    dev = np.mean(np.abs(angles_sorted - target), axis=1)

    # Mark degenerate triangles (any edge length near zero) as NaN
    degen = (a < 1e-14) | (b < 1e-14) | (c < 1e-14)
    dev = np.where(degen, np.nan, dev)

    return dev


def edge_fidelity(
    p: NDArray[np.float64],
    t: NDArray[np.int64],
    h: Callable[[NDArray[np.float64]], NDArray[np.float64]] | None = None,
    *,
    band: tuple[float, float] = (0.7, 1.4),
) -> dict:
    """Edge-length fidelity to size field.

    Builds the unique undirected edge set from triangles. For each edge,
    computes ``ratio = edge_length / h(edge_midpoint)`` where h is a
    callable size field. If h is None, normalizes ratio by its own
    median instead.

    Returns a dict with ratios, in-band fraction, band bounds, and median ratio.

    Parameters
    ----------
    p : ndarray, shape (N, 2), dtype float64
        Nodal coordinates.
    t : ndarray, shape (M, 3), dtype int64
        Triangle connectivity (0-based).
    h : callable or None, optional
        Size-field function mapping (K, 2) points to (K,) edge-target lengths.
        If None, ratio is normalized by its own median.
    band : tuple[float, float], optional
        Desired ratio band [low, high]; default (0.7, 1.4).

    Returns
    -------
    dict
        Keys:
        - "ratios": ndarray, shape (E,), edge-length / target-length per edge
        - "in_band_fraction": float in [0, 1]
        - "band": tuple of (low, high)
        - "median": float, median of ratios
        - "n_edges": int, total number of unique edges

    Notes
    -----
    A ratio in [0.7, 1.4] is typically considered acceptable. If h is not
    provided, the median ratio becomes 1.0 by definition (self-normalized).
    """
    p = np.asarray(p, dtype=np.float64)
    t = np.asarray(t, dtype=np.int64)

    if len(t) == 0:
        return {
            "ratios": np.array([], dtype=np.float64),
            "in_band_fraction": 0.0,
            "band": band,
            "median": np.nan,
            "n_edges": 0,
        }

    # Collect all edges
    edges = []
    edge_set = set()
    for k in range(len(t)):
        for i in range(3):
            v0, v1 = t[k, i], t[k, (i + 1) % 3]
            edge_key = (int(min(v0, v1)), int(max(v0, v1)))
            if edge_key not in edge_set:
                edge_set.add(edge_key)
                edges.append((v0, v1))

    edges = np.array(edges, dtype=np.int64)
    if len(edges) == 0:
        return {
            "ratios": np.array([], dtype=np.float64),
            "in_band_fraction": 0.0,
            "band": band,
            "median": np.nan,
            "n_edges": 0,
        }

    # Edge lengths
    edge_len = np.hypot(p[edges[:, 1], 0] - p[edges[:, 0], 0],
                        p[edges[:, 1], 1] - p[edges[:, 0], 1])

    # Edge midpoints
    midpoints = (p[edges[:, 0]] + p[edges[:, 1]]) / 2.0

    # Target lengths
    if h is not None:
        target_len = h(midpoints)
    else:
        target_len = np.ones(len(edges))

    # Ratio
    with np.errstate(divide="ignore", invalid="ignore"):
        ratios = edge_len / np.maximum(target_len, 1e-300)

    if h is None:
        # Self-normalize by median
        median_ratio = np.nanmedian(ratios)
        if median_ratio > 0:
            ratios = ratios / median_ratio

    median = float(np.median(ratios))
    in_band = np.sum((ratios >= band[0]) & (ratios <= band[1]))
    in_band_frac = float(in_band) / len(ratios) if len(ratios) > 0 else 0.0

    return {
        "ratios": ratios,
        "in_band_fraction": in_band_frac,
        "band": band,
        "median": median,
        "n_edges": len(edges),
    }


def merged_quad_quality(mesh: "Mesh") -> dict:
    """Quality metrics for merged triangle-pairs (quad candidates).

    Uses ``_build_pairing_map`` to identify mutual longest-edge partner pairs.
    For each pair, constructs the 4-node quad by merging across the shared edge.
    Computes quad quality via ``mesh_quality`` with element='quad', falling back
    to ``right_iso`` pairing score if that fails.

    Returns counts and statistics on the paired/unpaired triangles and their
    resulting quad quality.

    Parameters
    ----------
    mesh : Mesh
        Input triangular mesh.

    Returns
    -------
    dict
        Keys:
        - "n_pairs": int, number of mutually paired triangles (= quads)
        - "n_unpaired_tris": int, number of unpaired triangles
        - "mean_quad_quality": float, mean quality of quads (or nan if empty)
        - "quad_qualities": ndarray, shape (n_pairs,), quality per quad

    Notes
    -----
    Empty mesh returns all zeros/empty. If quad quality computation fails,
    falls back to right_iso pairing and sets mean to np.nan on error while
    keeping counts valid.
    """
    if len(mesh.elements) == 0:
        return {
            "n_pairs": 0,
            "n_unpaired_tris": 0,
            "mean_quad_quality": np.nan,
            "quad_qualities": np.array([], dtype=np.float64),
        }

    pairs = _build_pairing_map(mesh.nodes, mesh.elements)
    paired = set()
    quad_list = []

    for k in range(len(pairs)):
        if pairs[k] >= 0 and k < pairs[k]:  # Ensure k < j to avoid double-counting
            j = int(pairs[k])
            paired.add(k)
            paired.add(j)
            tri_k = mesh.elements[k]
            tri_j = mesh.elements[j]

            # Find shared edge
            shared = None
            for i in range(3):
                v_a, v_b = tri_k[i], tri_k[(i + 1) % 3]
                for jj in range(3):
                    v_c, v_d = tri_j[jj], tri_j[(jj + 1) % 3]
                    if {v_a, v_b} == {v_c, v_d}:
                        shared = (v_a, v_b)
                        remaining_k = tri_k[(i + 2) % 3]
                        remaining_j = tri_j[(jj + 2) % 3]
                        break
                if shared:
                    break

            if shared:
                # Form quad: [remaining_k, shared[0], remaining_j, shared[1]]
                quad_nodes = np.array(
                    [remaining_k, shared[0], remaining_j, shared[1]], dtype=np.int64
                )
                quad_list.append(quad_nodes)

    n_pairs = len(quad_list)
    n_unpaired = len(mesh.elements) - 2 * n_pairs

    quad_qualities = np.array([], dtype=np.float64)
    mean_q = np.nan

    if n_pairs > 0:
        quads = np.array(quad_list, dtype=np.int64)
        try:
            _, mean_q, qual = mesh_quality(mesh.nodes, quads, element="quad")
            quad_qualities = qual
        except Exception:
            # Fallback: use right_iso pairing score scaled to [0,1]
            try:
                right_iso_score = right_iso_quality(mesh.nodes, mesh.elements)
                mean_q = right_iso_score
                quad_qualities = np.full(n_pairs, right_iso_score, dtype=np.float64)
            except Exception:
                mean_q = np.nan
                quad_qualities = np.full(n_pairs, np.nan, dtype=np.float64)

    return {
        "n_pairs": n_pairs,
        "n_unpaired_tris": n_unpaired,
        "mean_quad_quality": mean_q,
        "quad_qualities": quad_qualities,
    }


def quadability_report(
    mesh: "Mesh",
    h: Callable[[NDArray[np.float64]], NDArray[np.float64]] | None = None,
    ideal: int = 8,
    band: tuple[float, float] = (0.7, 1.4),
) -> dict:
    """Comprehensive quad-readiness report for a triangular mesh.

    Aggregates all quad-readiness metrics: valence, isotropy, edge fidelity,
    and merged-quad quality. Includes baseline triangle quality from mesh_quality.

    Parameters
    ----------
    mesh : Mesh
        Input triangular mesh.
    h : callable or None, optional
        Size-field function for edge fidelity. If None, fidelity is
        self-normalized.
    ideal : int, optional
        Target interior-node valence for quad-dominant grids; default 8.
    band : tuple[float, float], optional
        Acceptable edge-ratio band for fidelity; default (0.7, 1.4).

    Returns
    -------
    dict
        Keys:
        - "n_interior": int, number of interior nodes
        - "n_boundary": int, number of boundary nodes
        - "valence_histogram": dict[int, int], histogram of interior valence
        - "pct_even_interior": float in [0, 1]
        - "mean_abs_valence_dev": float, from ideal valence
        - "iso_dev_mean": float, degrees, mean angle deviation from right-isoceles
        - "iso_dev_std": float, degrees, std dev of angle deviations
        - "fidelity": dict (from edge_fidelity)
        - "merged_quad": dict (from merged_quad_quality)
        - "min_q": float, min triangle quality
        - "mean_q": float, mean triangle quality

    Notes
    -----
    All metrics handle empty mesh gracefully (return zeros/nan as appropriate).
    """
    boundary = _boundary_mask(mesh)
    n_interior = int((~boundary).sum())
    n_boundary = int(boundary.sum())

    # Valence metrics
    hist = interior_valence_histogram(mesh)
    pct_even = pct_even_interior(mesh)
    mean_abs_val_dev = mean_abs_valence_dev(mesh, ideal=ideal)

    # Isotropy metrics
    iso = iso_dev(mesh.nodes, mesh.elements)
    iso_mean = float(np.nanmean(iso)) if len(iso) > 0 else np.nan
    iso_std = float(np.nanstd(iso)) if len(iso) > 0 else np.nan

    # Edge fidelity
    fidelity = edge_fidelity(mesh.nodes, mesh.elements, h=h, band=band)

    # Merged quad quality
    merged = merged_quad_quality(mesh)

    # Triangle quality from mesh_quality
    min_q, mean_q, _ = mesh_quality(mesh.nodes, mesh.elements, element="triangle")

    return {
        "n_interior": n_interior,
        "n_boundary": n_boundary,
        "valence_histogram": hist,
        "pct_even_interior": pct_even,
        "mean_abs_valence_dev": mean_abs_val_dev,
        "iso_dev_mean": iso_mean,
        "iso_dev_std": iso_std,
        "fidelity": fidelity,
        "merged_quad": merged,
        "min_q": min_q,
        "mean_q": mean_q,
    }


def format_report(report: dict) -> str:
    """Human-readable multi-line summary of quadability report.

    Parameters
    ----------
    report : dict
        Output from :func:`quadability_report`.

    Returns
    -------
    str
        Multi-line formatted text suitable for terminal or log output.
    """
    lines = [
        "Quadability Report",
        "=" * 70,
    ]

    lines.append(f"Mesh Size: {report['n_interior']:d} interior + {report['n_boundary']:d} boundary nodes")
    lines.append(f"  Triangles: {len(report.get('fidelity', {}).get('ratios', []))} (approx)")
    lines.append("")

    lines.append("Valence (Interior Nodes)")
    lines.append("-" * 70)
    hist = report["valence_histogram"]
    if hist:
        for v in sorted(hist.keys()):
            lines.append(f"  Valence {v}: {hist[v]:5d} nodes")
    else:
        lines.append("  (no interior nodes)")
    lines.append(f"  Even fraction: {100 * report['pct_even_interior']:.1f}%")
    lines.append(f"  Mean |dev from ideal({report.get('ideal', 8)})|: {report['mean_abs_valence_dev']:.2f}")
    lines.append("")

    lines.append("Isotropy (Angle Deviation from Right-Isoceles Target [45,45,90]°)")
    lines.append("-" * 70)
    lines.append(f"  Mean deviation: {report['iso_dev_mean']:.2f}°")
    lines.append(f"  Std deviation:  {report['iso_dev_std']:.2f}°")
    lines.append("")

    lines.append("Edge Fidelity to Size Field")
    lines.append("-" * 70)
    fid = report["fidelity"]
    lines.append(f"  Edges: {fid['n_edges']}")
    lines.append(f"  Median ratio: {fid['median']:.3f}")
    lines.append(f"  In band [{fid['band'][0]:.1f}, {fid['band'][1]:.1f}]: {100 * fid['in_band_fraction']:.1f}%")
    lines.append("")

    lines.append("Merged Quad Quality (via Longest-Edge Pairing)")
    lines.append("-" * 70)
    mq = report["merged_quad"]
    lines.append(f"  Paired triangles (quads): {mq['n_pairs']}")
    lines.append(f"  Unpaired triangles: {mq['n_unpaired_tris']}")
    if mq['n_pairs'] > 0:
        lines.append(f"  Mean quad quality: {mq['mean_quad_quality']:.4f}")
    else:
        lines.append(f"  Mean quad quality: (no pairs)")
    lines.append("")

    lines.append("Triangle Quality (Baseline)")
    lines.append("-" * 70)
    lines.append(f"  Min: {report['min_q']:.4f}")
    lines.append(f"  Mean: {report['mean_q']:.4f}")
    lines.append("")

    return "\n".join(lines)
