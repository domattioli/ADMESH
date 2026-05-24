#!/usr/bin/env python3
"""Build an ADMESH benchmark domain from a fort.14 mesh that lacks boundary records.

Many ADCIRC meshes (e.g. WNAT_Onur.14) ship node + element tables but no
NOPE/NBOU boundary section, so admesh.loaders.load_domain_from_fort14 cannot
read them. This script reconstructs the domain boundary directly from mesh
geometry: a free edge (belonging to exactly one triangle) is a boundary edge;
chaining free edges yields the coastline rings (outer ocean perimeter + island
holes). The result is written as an ADMESH domain JSON ({bbox, rings}).

Usage:
    python scripts/make_wnat_benchmark.py \
        --in  /home/user/ADMESH-Domains/registry_data/meshes/WNAT_Onur.14 \
        --out benchmarks/data/wnat_onur_boundary.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import time

import numpy as np


def parse_fort14_geometry(path: str) -> tuple[np.ndarray, np.ndarray]:
    """Read only the node coords and triangle connectivity (0-based).

    Tolerates a missing NOPE/NBOU boundary footer.
    """
    with open(path) as fh:
        fh.readline()  # title
        ne, np_ = (int(x) for x in fh.readline().split()[:2])
        xy = np.empty((np_, 2), dtype=np.float64)
        for i in range(np_):
            p = fh.readline().split()
            xy[i, 0] = float(p[1])
            xy[i, 1] = float(p[2])
        tri = np.empty((ne, 3), dtype=np.int64)
        for i in range(ne):
            p = fh.readline().split()
            tri[i, 0] = int(p[2])
            tri[i, 1] = int(p[3])
            tri[i, 2] = int(p[4])
    return xy, tri - 1


def free_edges(tri: np.ndarray) -> np.ndarray:
    """Edges that belong to exactly one triangle (the mesh boundary)."""
    e = np.vstack([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
    e.sort(axis=1)
    uniq, cnt = np.unique(e, axis=0, return_counts=True)
    return uniq[cnt == 1]


def chain_rings(edges: np.ndarray) -> list[np.ndarray]:
    """Walk boundary edges into closed rings of node indices."""
    adj: dict[int, list[int]] = {}
    for a, b in edges:
        adj.setdefault(int(a), []).append(int(b))
        adj.setdefault(int(b), []).append(int(a))

    used: set[tuple[int, int]] = set()

    def key(a: int, b: int) -> tuple[int, int]:
        return (a, b) if a < b else (b, a)

    rings: list[np.ndarray] = []
    for start in list(adj):
        for nxt in adj[start]:
            if key(start, nxt) in used:
                continue
            ring = [start]
            used.add(key(start, nxt))
            prev, cur = start, nxt
            while cur != start:
                ring.append(cur)
                nbrs = [n for n in adj[cur] if n != prev and key(cur, n) not in used]
                if not nbrs:
                    nbrs = [n for n in adj[cur] if key(cur, n) not in used]
                if not nbrs:
                    break
                nn = nbrs[0]
                used.add(key(cur, nn))
                prev, cur = cur, nn
            if len(ring) >= 3:
                rings.append(np.asarray(ring, dtype=np.int64))
    return rings


def signed_area(coords: np.ndarray) -> float:
    x, y = coords[:, 0], coords[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    args = ap.parse_args()

    t0 = time.perf_counter()
    xy, tri = parse_fort14_geometry(args.inp)
    fe = free_edges(tri)
    rings_idx = chain_rings(fe)
    rings = [xy[r] for r in rings_idx]
    # Largest |area| ring is the outer boundary; order outer-first.
    rings.sort(key=lambda c: abs(signed_area(c)), reverse=True)

    xmin, ymin = xy.min(0)
    xmax, ymax = xy.max(0)
    payload = {
        "name": pathlib.Path(args.inp).stem,
        "bbox": [float(xmin), float(ymin), float(xmax), float(ymax)],
        "rings": [c.tolist() for c in rings],
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(payload, f)

    print(
        f"{pathlib.Path(args.inp).name}: nodes={len(xy)} tris={len(tri)} "
        f"free_edges={len(fe)} rings={len(rings)} "
        f"outer_verts={len(rings[0])} total_verts={sum(len(c) for c in rings)} "
        f"-> {out} ({time.perf_counter() - t0:.2f}s)"
    )


if __name__ == "__main__":
    main()
