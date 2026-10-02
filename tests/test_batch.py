"""Batch triangulation over a process pool (issue #99, phase P2).

:func:`admesh.triangulate_batch` must return exactly what a sequential
loop of :func:`admesh.triangulate` calls returns, in input order. The
pool is an execution detail; it must never change a mesh.
"""

from __future__ import annotations

import numpy as np
import pytest

import admesh
from admesh import Domain
from admesh.domains import ALL as DOMAIN_REGISTRY

_NAMES = ("unit_square", "l_shape", "unit_disk")
_KW = {"h_max": 0.15, "max_iter": 200, "seed": 0}


def _domains():
    return [DOMAIN_REGISTRY[n] for n in _NAMES]


def _assert_same_mesh(a: admesh.Mesh, b: admesh.Mesh) -> None:
    np.testing.assert_array_equal(a.nodes, b.nodes)
    np.testing.assert_array_equal(a.elements, b.elements)
    np.testing.assert_array_equal(a.quality, b.quality)
    # BoundarySegment holds an ndarray, so dataclass == is ambiguous.
    assert len(a.boundaries) == len(b.boundaries)
    for sa, sb in zip(a.boundaries, b.boundaries):
        np.testing.assert_array_equal(sa.node_ids, sb.node_ids)
        assert sa.bc_type == sb.bc_type
        assert sa.is_open == sb.is_open


def test_exported_from_package() -> None:
    assert "triangulate_batch" in admesh.__all__
    assert callable(admesh.triangulate_batch)


def test_empty_input_returns_empty_list() -> None:
    assert admesh.triangulate_batch([], n_jobs=2) == []


@pytest.mark.parametrize("n_jobs", [0, -1])
def test_invalid_n_jobs_raises(n_jobs: int) -> None:
    with pytest.raises(ValueError, match="n_jobs"):
        admesh.triangulate_batch(_domains(), n_jobs=n_jobs)


def test_parallel_matches_sequential() -> None:
    expected = [admesh.triangulate(d, **_KW) for d in _domains()]
    got = admesh.triangulate_batch(_domains(), n_jobs=2, **_KW)
    assert len(got) == len(expected)
    for a, b in zip(got, expected):
        _assert_same_mesh(a, b)


def test_order_is_preserved() -> None:
    doms = _domains()
    fwd = admesh.triangulate_batch(doms, n_jobs=2, **_KW)
    rev = admesh.triangulate_batch(doms[::-1], n_jobs=2, **_KW)
    for a, b in zip(fwd, rev[::-1]):
        _assert_same_mesh(a, b)


def test_n_jobs_one_runs_in_process_and_accepts_lambdas() -> None:
    # A lambda SDF cannot cross a process boundary, but n_jobs=1 never
    # spawns a worker, so it must work exactly like triangulate().
    dom = Domain(sdf=lambda p: np.max(np.abs(p - 0.5), axis=1) - 0.5, bbox=(0.0, 0.0, 1.0, 1.0))
    (mesh,) = admesh.triangulate_batch([dom], n_jobs=1, **_KW)
    _assert_same_mesh(mesh, admesh.triangulate(dom, **_KW))


def test_unpicklable_domain_raises_before_pool() -> None:
    bad = Domain(sdf=lambda p: np.hypot(p[:, 0], p[:, 1]) - 1.0, bbox=(-1.0, -1.0, 1.0, 1.0))
    with pytest.raises(TypeError, match=r"index 1"):
        admesh.triangulate_batch([DOMAIN_REGISTRY["unit_square"], bad], n_jobs=2, **_KW)


def test_worker_exception_propagates() -> None:
    with pytest.raises(ValueError, match="Domain file not found"):
        admesh.triangulate_batch(
            [DOMAIN_REGISTRY["unit_square"], "does/not/exist.toml"], n_jobs=2, **_KW
        )
