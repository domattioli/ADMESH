"""Diagnose whether the WNAT fixture contains Bermuda as a topological feature.

Issue #12 ("WNAT fresh mesh missing Bermuda boundary feature") asks whether
``tests/fixtures/fort14/adcirc_examples/wnat_test.14`` actually carries
Bermuda as a hole/island, or whether the fixture is a coarse pedagogical
mesh that omits small islands. This script answers that question against
the committed fixture (or any fort.14 you point it at) by checking three
independent signals near (-64.78, 32.30):

    1. Declared boundary segments in the fort.14 header.
    2. Topological boundary edges (edges shared by exactly one triangle).
    3. Bathymetry near the target — shallow/positive elevation would
       indicate a sub-aerial feature; deep open-ocean values rule it out.

Run::

    python scripts/diagnose_wnat_bermuda.py
    python scripts/diagnose_wnat_bermuda.py path/to/other.14
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np

import admesh


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "fort14"
    / "adcirc_examples"
    / "wnat_test.14"
)
BERMUDA = np.array([-64.78, 32.30])
RADIUS_DEG = 1.5


def _topological_boundary_nodes(elements: np.ndarray) -> set[int]:
    edge_count: dict[tuple[int, int], int] = {}
    for tri in elements:
        a, b, c = int(tri[0]), int(tri[1]), int(tri[2])
        for u, v in ((a, b), (b, c), (c, a)):
            key = (u, v) if u < v else (v, u)
            edge_count[key] = edge_count.get(key, 0) + 1
    nodes: set[int] = set()
    for (u, v), count in edge_count.items():
        if count == 1:
            nodes.add(u)
            nodes.add(v)
    return nodes


def diagnose(path: pathlib.Path) -> int:
    print(f"Fixture: {path}")
    mesh = admesh.read_fort14(path)
    print(
        f"  n_nodes={mesh.n_nodes}, n_elements={mesh.n_elements}, "
        f"declared boundaries in header={mesh.n_boundaries}"
    )
    print(
        f"  bbox: x [{mesh.nodes[:, 0].min():.3f}, {mesh.nodes[:, 0].max():.3f}], "
        f"y [{mesh.nodes[:, 1].min():.3f}, {mesh.nodes[:, 1].max():.3f}]"
    )

    d = np.linalg.norm(mesh.nodes - BERMUDA, axis=1)
    near_idx = np.where(d < RADIUS_DEG)[0]
    print(
        f"\n[1] Nodes within {RADIUS_DEG}° of Bermuda {tuple(BERMUDA)}: "
        f"{len(near_idx)}"
    )

    boundary_nodes = _topological_boundary_nodes(mesh.elements)
    on_boundary = boundary_nodes.intersection(near_idx.tolist())
    print(
        f"[2] Of those, on a topological boundary edge "
        f"(edge in exactly 1 triangle): {len(on_boundary)}"
    )

    if mesh.bathymetry is not None and len(near_idx) > 0:
        z = mesh.bathymetry[near_idx]
        print(
            f"[3] Mesh-elevation samples near Bermuda "
            f"(positive-up per Mesh contract): "
            f"min={z.min():.1f}, mean={z.mean():.1f}, max={z.max():.1f}"
        )
    else:
        print("[3] No bathymetry available.")

    if not on_boundary:
        b_nodes_arr = np.array(sorted(boundary_nodes), dtype=int)
        if b_nodes_arr.size:
            b_d = np.linalg.norm(mesh.nodes[b_nodes_arr] - BERMUDA, axis=1)
            nearest = int(b_nodes_arr[int(b_d.argmin())])
            print(
                f"\nNearest topological-boundary node to Bermuda: "
                f"{nearest} at ({mesh.nodes[nearest, 0]:.3f}, "
                f"{mesh.nodes[nearest, 1]:.3f}), "
                f"distance {b_d.min():.3f}°"
            )

    print()
    if on_boundary:
        print("VERDICT: Bermuda IS topologically present in this fixture.")
        return 0
    else:
        print("VERDICT: Bermuda is NOT topologically present.")
        print(
            "  The mesh is fully connected through the Bermuda region; "
            "the round-trip cannot recover what the source does not carry."
        )
        return 1


def main(argv: list[str]) -> int:
    path = pathlib.Path(argv[1]) if len(argv) > 1 else DEFAULT_FIXTURE
    if not path.exists():
        print(f"error: {path} does not exist", file=sys.stderr)
        return 2
    return diagnose(path)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
