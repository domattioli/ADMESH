"""boundary="fixed" with loader-built domains: rings, holes, fallback warning."""

from __future__ import annotations

import json
import warnings
from collections import Counter

import numpy as np
import pytest
from scipy.spatial import cKDTree

import admesh
from admesh.fort14 import read_fort14, write_fort14
from admesh.loaders import (
    _domain_from_polygon,
    load_domain_from_fort14,
    load_domain_from_json,
    load_domain_from_toml,
)

OUTER = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=float)
HOLE = np.array([[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]], dtype=float)


def _boundary_nodes(m):
    e = np.sort(np.vstack([m.elements[:, [0, 1]], m.elements[:, [1, 2]],
                           m.elements[:, [2, 0]]]), axis=1)
    cnt = Counter(map(tuple, e))
    return np.unique([v for k, n in cnt.items() if n == 1 for v in k])


def _areas(m):
    a, b, c = (m.nodes[m.elements[:, i]] for i in range(3))
    return 0.5 * ((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1])
                  - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1]))


def _check_fixed(m, verts):
    assert (cKDTree(m.nodes).query(verts)[0] < 1e-9).all()  # every vertex kept
    assert (np.abs(_areas(m)) > 0).all()
    bnd = m.nodes[_boundary_nodes(m)]
    # every boundary node lies on the input rings, i.e. it is a ring node
    return bnd


def test_domain_holes_default_empty():
    assert admesh.Domain(sdf=lambda p: np.zeros(len(p)), bbox=(0, 0, 1, 1)).holes == ()


def _write_toml(path):
    def c(r):
        return "[" + ", ".join(f"[{x}, {y}]" for x, y in r) + "]"
    path.write_text(
        "[domain]\n[[domain.rings]]\ncoords = " + c(OUTER)
        + "\n[[domain.rings]]\ncoords = " + c(HOLE) + "\n"
    )


@pytest.mark.parametrize("fmt", ["json", "toml"])
def test_polygon_file_with_hole_fixed(tmp_path, fmt):
    if fmt == "json":
        p = tmp_path / "d.json"
        p.write_text(json.dumps({"rings": [OUTER.tolist(), HOLE.tolist()]}))
        dom = load_domain_from_json(p)
    else:
        p = tmp_path / "d.toml"
        _write_toml(p)
        dom = load_domain_from_toml(p)
    assert len(dom.pts) == 4 and len(dom.holes) == 1
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        m = admesh.triangulate(dom, h_max=0.15, boundary="fixed", quality_gate=(0, 0))
    verts = np.vstack([OUTER, HOLE])
    bnd = _check_fixed(m, verts)
    ring_nodes_ok = np.minimum(
        _ring_dist(OUTER, bnd), _ring_dist(HOLE, bnd)
    )
    assert (ring_nodes_ok < 1e-9).all()  # no boundary node off the rings
    # every outer and hole ring node (incl. relaxed fill) is a boundary node
    on_outer = _ring_dist(OUTER, m.nodes) < 1e-9
    on_hole = _ring_dist(HOLE, m.nodes) < 1e-9
    assert len(bnd) == int(on_outer.sum() + on_hole.sum())
    assert on_hole.sum() >= 4 and on_outer.sum() >= 4


def _ring_dist(ring, xy):
    a, b = ring, np.roll(ring, -1, axis=0)
    d = b - a
    w = xy[:, None, :] - a[None]
    t = np.clip((w * d[None]).sum(2) / (d ** 2).sum(1)[None], 0, 1)
    q = a[None] + t[..., None] * d[None]
    return np.linalg.norm(xy[:, None, :] - q, axis=2).min(axis=1)


def test_fort14_roundtrip_fixed(tmp_path):
    src = admesh.triangulate(
        _domain_from_polygon([OUTER, HOLE]), h_max=0.12, quality_gate=(0, 0)
    )
    p = tmp_path / "rt.14"
    write_fort14(src, p)
    mesh = read_fort14(p)
    dom = load_domain_from_fort14(p)
    assert len(dom.pts) > 4 and len(dom.holes) == 1
    m = admesh.triangulate(dom, h_max=0.12, boundary="fixed", quality_gate=(0, 0))
    verts = np.vstack([dom.pts, *dom.holes])
    _check_fixed(m, verts)
    # all input boundary vertices of the file are retained
    ids = np.concatenate([s.node_ids for s in mesh.boundaries if not s.is_open])
    assert (cKDTree(m.nodes).query(mesh.nodes[ids])[0] < 1e-9).all()


def test_ringless_domain_fixed_warns():
    dom = admesh.Domain(
        sdf=lambda p: np.max(np.abs(np.asarray(p) - 0.5), axis=1) - 0.5,
        bbox=(0.0, 0.0, 1.0, 1.0),
    )
    with pytest.warns(UserWarning, match="falls back to free|falling back to free"):
        admesh.triangulate(dom, h_max=0.2, boundary="fixed", quality_gate=(0, 0))


def test_fort14_without_land_segment_derives_rings_from_mesh(tmp_path):
    """wnat_test.14 flags no closed land segment: rings come from mesh edges."""
    import pathlib
    src = pathlib.Path(__file__).parent / "fixtures/fort14/adcirc_examples/wnat_test.14"
    dom = load_domain_from_fort14(src)
    assert dom.pts is not None and len(dom.pts) >= 3
    h = max(dom.bbox[2] - dom.bbox[0], dom.bbox[3] - dom.bbox[1]) / 12
    m = admesh.triangulate(dom, h_max=h, quality_gate=(0.0, 0.0), boundary="fixed")
    verts = np.vstack([dom.pts] + [np.asarray(r) for r in dom.holes])
    bnd = _check_fixed(m, verts)
    assert (cKDTree(verts).query(bnd)[0] < 1e-9).all()


@pytest.mark.slow
def test_enpac_fixed_mode_valid():
    """ENPAC 2003 coast (10k-vertex ring): fixed mode keeps every vertex."""
    import pathlib
    src = pathlib.Path(__file__).parent.parent / "benchmarks/data/enpac_boundary.json"
    if not src.exists():
        pytest.skip("ENPAC boundary data not present")
    dom = load_domain_from_json(src)
    m = admesh.triangulate(dom, h_max=0.5, h_min=0.125, quality_gate=(0.0, 0.0),
                           boundary="fixed")
    verts = np.vstack([dom.pts] + [np.asarray(r) for r in dom.holes])
    bnd = _check_fixed(m, verts)
    assert (np.abs(dom.sdf(bnd)) < 1e-6).all()  # boundary nodes lie on the rings
