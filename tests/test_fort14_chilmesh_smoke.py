"""Optional chilmesh-installed smoke test (T033).

Skips cleanly when chilmesh is not on the dev machine. When it is
installed, exercise ``chilmesh.ChilMesh.from_fort14`` against an
admesh2D-produced file and confirm boundary structure matches.

Layered as a separate file (not glued into ``test_fort14_chilmesh_compat.py``)
so collection in vanilla CI is unaffected.

Relationship to ``test_fort14_chilmesh_compat.py`` (per audit #75):
- This file is the **real third-party interop** lane — requires
  ``chilmesh`` installed, hits its ``from_fort14`` reader, exits
  cleanly when the dep is missing.
- ``test_fort14_chilmesh_compat.py`` is the **self-consistency proxy**
  lane — uses only admesh's own reader/writer; runs in vanilla CI
  and asserts the round-trip preserves boundary identity. The
  hypothesis is that a clean self-consistent file is also chilmesh-
  readable, but we verify the second leg here when chilmesh is
  available.

Keep both: they cover different failure modes.
"""

from __future__ import annotations

import io

import numpy as np
import pytest

import admesh
from admesh import BoundarySegment, BoundaryType, Mesh

# Skip the whole module when chilmesh isn't importable.
chilmesh = pytest.importorskip("chilmesh")


def _hand_built_mesh() -> Mesh:
    nodes = np.array(
        [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], dtype=np.float64
    )
    elements = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
    seg_open = BoundarySegment(
        node_ids=np.array([0, 1], dtype=np.int64),
        bc_type=BoundaryType.OPEN,
        is_open=True,
    )
    seg_main = BoundarySegment(
        node_ids=np.array([1, 2, 3, 0], dtype=np.int64),
        bc_type=BoundaryType.MAINLAND,
        is_open=False,
    )
    return Mesh(
        nodes=nodes, elements=elements, boundaries=(seg_open, seg_main),
    )


def test_chilmesh_can_read_admesh_output(tmp_path):
    """admesh writes → chilmesh reads → node/element counts agree."""
    mesh = _hand_built_mesh()
    out = tmp_path / "admesh_out.14"
    mesh.to_fort14(out)

    cm = chilmesh.CHILmesh.read_from_fort14(str(out))

    points = np.asarray(cm.points)
    connectivity = np.asarray(cm.connectivity_list)
    assert points.shape[0] == mesh.n_nodes
    assert connectivity.shape[0] == mesh.n_elements

    # Node coordinates round-trip (first two columns are x, y).
    np.testing.assert_allclose(points[:, :2], mesh.nodes, atol=1e-9)
