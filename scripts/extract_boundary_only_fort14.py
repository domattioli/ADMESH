"""Extract boundary rings from a fort.14 mesh and write a slim fort.14.

Brute-force size reduction for committed test fixtures: take a real
upstream ADCIRC mesh (which may be tens of MB and well outside our
``tests/fixtures/fort14/`` 500 KB budget), keep only the topological
boundary, and re-triangulate the resulting polygon at coarse resolution
so the round-trip ``Domain.from_mesh`` test has data with islands /
holes (e.g. Bermuda) without checking in the full upstream mesh.

Pipeline
--------
    upstream fort.14
        │
        ├── read_fort14
        ├── walk topological boundary edges (edges in exactly 1 triangle)
        ├── chain into rings, sort by signed area (outer first)
        │
        ├── domain_from_polygon([outer, *holes])    ← Shapely SDF
        ├── triangulate(...)                        ← coarse h_max
        │
        └── write_fort14(slim)

Run::

    python scripts/extract_boundary_only_fort14.py \\
        path/to/upstream.14 \\
        tests/fixtures/fort14/community/wnat_islands.14 \\
        --h-max 0.5

Defaults emit a coarse h_max ≈ bbox_diag / 30 mesh, which for a typical
WNAT-extent input lands well under 200 KB.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import numpy as np

import admesh
from admesh.api import _derive_boundary_segments


def _ring_area(ring_xy: np.ndarray) -> float:
    x = ring_xy[:, 0]
    y = ring_xy[:, 1]
    return 0.5 * abs(
        np.sum(x[:-1] * y[1:] - x[1:] * y[:-1])
        + x[-1] * y[0]
        - x[0] * y[-1]
    )


def _ensure_ccw(ring_xy: np.ndarray) -> np.ndarray:
    x = ring_xy[:, 0]
    y = ring_xy[:, 1]
    signed = 0.5 * (
        np.sum(x[:-1] * y[1:] - x[1:] * y[:-1])
        + x[-1] * y[0]
        - x[0] * y[-1]
    )
    return ring_xy if signed >= 0 else ring_xy[::-1]


def extract(
    src_path: pathlib.Path,
    dst_path: pathlib.Path,
    h_max: float | None,
    quality_floor: float,
) -> None:
    print(f"reading {src_path} ...")
    src = admesh.read_fort14(src_path)
    print(
        f"  source: {src.n_nodes} nodes, {src.n_elements} elements, "
        f"declared boundaries={src.n_boundaries}"
    )

    segs = _derive_boundary_segments(src.elements, src.nodes)
    if not segs:
        sys.exit("error: source mesh has no topological boundary edges")

    rings_xy = [src.nodes[s.node_ids] for s in segs]
    ranked = sorted(
        rings_xy, key=_ring_area, reverse=True
    )  # outer = largest area
    outer = _ensure_ccw(ranked[0])
    holes = [_ensure_ccw(r)[::-1] for r in ranked[1:]]  # holes opposite
    print(
        f"  derived {len(rings_xy)} ring(s); outer area={_ring_area(outer):.4f}, "
        f"holes={len(holes)} (areas: "
        + ", ".join(f"{_ring_area(h):.4f}" for h in holes[:5])
        + (", ...)" if len(holes) > 5 else ")")
    )

    bbox_diag = float(
        np.hypot(
            outer[:, 0].max() - outer[:, 0].min(),
            outer[:, 1].max() - outer[:, 1].min(),
        )
    )
    if h_max is None:
        h_max = bbox_diag / 30.0
    print(f"  triangulating at h_max={h_max:.4f}  (bbox diag={bbox_diag:.2f})")

    domain = admesh.domain_from_polygon([outer, *holes])
    new = admesh.triangulate(
        domain,
        h_max=h_max,
        seed=0,
        max_iter=80,
        quality_gate=(quality_floor, 0.0),
    )
    print(f"  slim mesh: {new.n_nodes} nodes, {new.n_elements} elements")

    new = admesh.Mesh(
        nodes=new.nodes,
        elements=new.elements,
        boundaries=new.boundaries,
        quality=new.quality,
        title=f"slim re-mesh from {src_path.name} (boundary-only)",
    )
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    new.to_fort14(dst_path)
    size_kb = dst_path.stat().st_size / 1024.0
    print(f"  wrote {dst_path} ({size_kb:.1f} KB)")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("src", type=pathlib.Path, help="upstream fort.14 to read")
    p.add_argument("dst", type=pathlib.Path, help="slim fort.14 to write")
    p.add_argument(
        "--h-max",
        type=float,
        default=None,
        help="target edge length in source coordinates "
        "(default: bbox_diag / 30)",
    )
    p.add_argument(
        "--quality-floor",
        type=float,
        default=0.10,
        help="minimum acceptable per-element quality (default 0.10)",
    )
    args = p.parse_args(argv)
    if not args.src.exists():
        print(f"error: {args.src} does not exist", file=sys.stderr)
        return 2
    extract(args.src, args.dst, args.h_max, args.quality_floor)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
