"""End-to-end chilmesh round-trip demo (T035).

Build an annulus mesh through admesh2D's v1 Pythonic API, write it to
``fort.14``, and print the segment-by-segment summary that any
fort.14 consumer (chilmesh, OceanMesh, etc.) would see when reading
the file back.

This script is documentation-shaped: copy, modify, run. It is not
exercised by CI — the corresponding test
``tests/test_fort14_chilmesh_smoke.py`` covers verification when
chilmesh is locally installed.

Usage:
    python scripts/chilmesh_roundtrip_demo.py [output.14]

If no output path is given, the demo writes to ``annulus_demo.14``
in the current working directory.
"""

from __future__ import annotations

import sys

import numpy as np

import admesh
from admesh import BoundarySegment, BoundaryType


def _annulus_sdf(p: np.ndarray, *, inner: float = 0.4, outer: float = 1.0) -> np.ndarray:
    r = np.hypot(p[:, 0], p[:, 1])
    return np.maximum(r - outer, inner - r)


def main(out_path: str = "annulus_demo.14") -> None:
    print("=== admesh2D → fort.14 → consumer round-trip demo ===\n")

    # 1) Build a domain. The annulus has an outer ocean boundary and an
    #    inner island boundary, so it's the natural multiply-connected
    #    case the chilmesh integration is meant to handle.
    domain = admesh.domain_from_sdf(
        sdf=_annulus_sdf, bbox=(-1.0, -1.0, 1.0, 1.0)
    )
    mesh = admesh.triangulate(domain, h_max=0.12, max_iter=200, seed=0)
    print("Triangulation:")
    print(repr(mesh))
    print()
    print(mesh)
    print()

    # 2) Apply BC labels to the derived rings. Convention: longest ring
    #    is the outer (ocean) boundary, shorter ring is the island.
    rings = sorted(mesh.boundaries, key=lambda s: s.node_ids.size, reverse=True)
    if len(rings) >= 2:
        labelled = (
            BoundarySegment(node_ids=rings[0].node_ids, bc_type=BoundaryType.OPEN, is_open=True),
            BoundarySegment(
                node_ids=rings[1].node_ids,
                bc_type=BoundaryType.ISLAND,
                is_open=False,
            ),
        )
        mesh = admesh.Mesh(
            nodes=mesh.nodes,
            elements=mesh.elements,
            boundaries=labelled,
            quality=mesh.quality,
            title="annulus_demo",
        )

    # 3) Write fort.14 and print what a downstream reader would see.
    mesh.to_fort14(out_path)
    rt = admesh.read_fort14(out_path)

    print(f"Wrote {out_path}")
    print(f"Round-trip equal: {mesh.equals(rt, atol=1e-5)}\n")

    print("Per-segment summary (what chilmesh / any fort.14 reader will see):")
    for i, seg in enumerate(rt.boundaries):
        if isinstance(seg.bc_type, BoundaryType):
            label = seg.bc_type.name
        else:
            label = f"code={int(seg.bc_type)}"
        block = "open" if seg.is_open else "land"
        print(
            f"  [{i}] {label:<14} block={block:<5} nodes={seg.node_ids.size:>4d}"
            f"  first={seg.node_ids[0]}  last={seg.node_ids[-1]}"
        )


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "annulus_demo.14")
