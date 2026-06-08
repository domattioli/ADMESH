"""Valence balancing for triangular meshes via edge flipping.

Improves interior node valence toward the ideal value of 6 (equilateral
triangulation ideal). Boundary nodes are never repositioned; their element
star changes only insofar as interior-edge flips touch adjacent triangles.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from admesh.api import Mesh


@dataclass
class BalanceConfig:
    """Parameters governing the edge-flip valence balancing algorithm."""
    ideal_valence: int = 6
    max_iterations: int = 20
    convergence_threshold: float = 0.01
    quality_gate: float = 0.05


@dataclass
class ValenceStats:
    """Valence statistics for interior nodes only."""
    min_val: int
    max_val: int
    mean_val: float
    pct_at_ideal: float


@dataclass
class BalanceResult:
    """Output of :func:`balance_valence_triangles`."""
    mesh: "Mesh"
    stats_before: ValenceStats
    stats_after: ValenceStats
    iterations: int
    converged: bool
    edges_flipped: int


def compute_valence(elements: np.ndarray) -> np.ndarray:
    """Return per-node element-star valence (number of incident triangles).

    Parameters
    ----------
    elements:
        Shape ``(M, 3)``, 0-based node indices.

    Returns
    -------
    valence : ndarray[int32], shape (N,)
        ``valence[i]`` = number of triangles containing node ``i``.
    """
    if elements.size == 0:
        return np.zeros(0, dtype=np.int32)
    n = int(elements.max()) + 1
    val = np.zeros(n, dtype=np.int32)
    np.add.at(val, elements.ravel(), 1)
    return val


def _valence_stats(valence: np.ndarray, ideal: int, interior: np.ndarray) -> ValenceStats:
    v = valence[interior]
    if v.size == 0:
        return ValenceStats(0, 0, 0.0, 0.0)
    return ValenceStats(int(v.min()), int(v.max()), float(v.mean()), float(np.mean(v == ideal)))


def _boundary_mask(mesh: "Mesh") -> np.ndarray:
    mask = np.zeros(mesh.n_nodes, dtype=bool)
    for seg in mesh.boundaries:
        mask[seg.node_ids] = True
    return mask


def _tri_quality(p0: np.ndarray, p1: np.ndarray, p2: np.ndarray) -> float:
    """Equilateral-triangle quality in [0, 1]."""
    a = float(np.linalg.norm(p1 - p0))
    b = float(np.linalg.norm(p2 - p1))
    c = float(np.linalg.norm(p0 - p2))
    s = (a + b + c) / 2.0
    area = max(s * (s - a) * (s - b) * (s - c), 0.0) ** 0.5
    denom = a ** 2 + b ** 2 + c ** 2
    return 0.0 if denom < 1e-14 else 4.0 * 3.0 ** 0.5 * area / denom


def balance_valence_triangles(
    mesh: "Mesh",
    config: BalanceConfig | None = None,
) -> BalanceResult:
    """Improve interior-node valence via edge flipping.

    Scans interior edges and flips those whose flip reduces the total
    absolute valence deficiency of interior nodes, subject to a per-flip
    quality gate. Boundary node positions and boundary segment topology
    are never altered.

    Parameters
    ----------
    mesh:
        Input triangular mesh.
    config:
        Algorithm parameters; defaults to :class:`BalanceConfig` defaults.

    Returns
    -------
    BalanceResult
        Contains the modified mesh plus before/after statistics.
    """
    if config is None:
        config = BalanceConfig()
    ideal = config.ideal_valence
    nodes = mesh.nodes
    elems = mesh.elements.copy()
    bnd = _boundary_mask(mesh)
    interior_idx = np.where(~bnd)[0]
    valence = compute_valence(elems)
    stats_before = _valence_stats(valence, ideal, interior_idx)

    def _deficit(n: int, delta: int) -> int:
        return 0 if bnd[n] else abs(int(valence[n]) + delta - ideal)

    edges_flipped = 0
    converged = False
    it = 0

    for it in range(config.max_iterations):
        e2t: dict[tuple[int, int], list[int]] = {}
        for ei, tri in enumerate(elems):
            for k in range(3):
                u, v = int(tri[k]), int(tri[(k + 1) % 3])
                e2t.setdefault((min(u, v), max(u, v)), []).append(ei)

        flips = 0
        dirty: set[int] = set()

        for (a, b), tris in e2t.items():
            if len(tris) != 2 or tris[0] in dirty or tris[1] in dirty:
                continue
            t1, t2 = tris
            others_c = [x for x in elems[t1].tolist() if x != a and x != b]
            others_d = [x for x in elems[t2].tolist() if x != a and x != b]
            if len(others_c) != 1 or len(others_d) != 1:
                continue
            c, d = others_c[0], others_d[0]
            if c == d:
                continue

            before = _deficit(a, 0) + _deficit(b, 0) + _deficit(c, 0) + _deficit(d, 0)
            after  = _deficit(a, -1) + _deficit(b, -1) + _deficit(c, 1) + _deficit(d, 1)
            if after >= before:
                continue

            cd = (min(c, d), max(c, d))
            if cd in e2t and len(e2t[cd]) >= 2:
                continue

            pc, pd, pa, pb = nodes[c], nodes[d], nodes[a], nodes[b]
            if (_tri_quality(pc, pd, pa) < config.quality_gate or
                    _tri_quality(pc, pd, pb) < config.quality_gate):
                continue

            elems[t1] = [c, d, a]
            elems[t2] = [c, d, b]
            valence[a] -= 1
            valence[b] -= 1
            valence[c] += 1
            valence[d] += 1
            dirty.update([t1, t2])
            flips += 1
            edges_flipped += 1

        if flips == 0:
            converged = True
            break

    stats_after = _valence_stats(valence, ideal, interior_idx)

    from admesh.api import Mesh
    from admesh._stages.quality import mesh_quality
    _, _, q = mesh_quality(nodes, elems)
    new_mesh = Mesh(
        nodes=mesh.nodes,
        elements=elems,
        boundaries=mesh.boundaries,
        bathymetry=mesh.bathymetry,
        quality=q,
        title=mesh.title,
    )
    return BalanceResult(
        mesh=new_mesh,
        stats_before=stats_before,
        stats_after=stats_after,
        iterations=it + 1,
        converged=converged,
        edges_flipped=edges_flipped,
    )


def get_valence_report(mesh: "Mesh", config: BalanceConfig | None = None) -> str:
    """Return a human-readable valence statistics report for *mesh*."""
    cfg = config or BalanceConfig()
    bnd = _boundary_mask(mesh)
    val = compute_valence(mesh.elements)
    s = _valence_stats(val, cfg.ideal_valence, np.where(~bnd)[0])
    return (
        f"Valence Report (ideal={cfg.ideal_valence})\n"
        f"  Interior nodes : {int((~bnd).sum())}\n"
        f"  Min/Mean/Max   : {s.min_val}/{s.mean_val:.2f}/{s.max_val}\n"
        f"  At ideal       : {100 * s.pct_at_ideal:.1f}%"
    )
