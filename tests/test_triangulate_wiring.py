"""Spec 025 / #65: Domain.bathymetry plumbing (Steps 1+2).

Step 3 (wire build_h() as triangulate() default) stays DEFERRED — the production
size-field stack degrades MVP convex-domain min_q 0.30 -> 0.22, below the
advisory quality_gate smoke default (CONSTITUTION Article V.5, #140 — advisory,
NOT constitutional) + spec 025 AC-005/AC-006. Operator closed #65 leaving Step 3
unwired by design choice (not a constitutional bar). The xfail test below pins
the intended Step-3 contract for if/when the operator opts in.
"""
from __future__ import annotations

import numpy as np
import pytest

import admesh
from admesh.api import Domain


def _unit_square_domain() -> Domain:
    def sdf(p):
        p = np.asarray(p, dtype=float)
        dx = np.maximum(0 - p[:, 0], p[:, 0] - 1)
        dy = np.maximum(0 - p[:, 1], p[:, 1] - 1)
        outside = np.hypot(np.maximum(dx, 0), np.maximum(dy, 0))
        inside = np.minimum(np.maximum(dx, dy), 0)
        return outside + inside
    return Domain(sdf=sdf, bbox=(0.0, 0.0, 1.0, 1.0))


# --- Step 1: Domain.bathymetry field (shipped) -----------------------------

def test_domain_bathymetry_field_default():
    """Domain gains an optional bathymetry field defaulting to None."""
    d = _unit_square_domain()
    assert d.bathymetry is None


# --- Step 2: Domain.from_mesh bathymetry extraction (shipped) ---------------

def test_from_mesh_no_bathymetry_is_none():
    """from_mesh on a mesh without bathymetry yields Domain.bathymetry is None."""
    sq = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=float)
    nodes = np.vstack([sq, [[0.5, 0.5]]])
    elems = np.array([[0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4]], dtype=np.int64)
    mesh = admesh.Mesh(nodes=nodes, elements=elems)
    dom = Domain.from_mesh(mesh)
    assert dom.bathymetry is None


def test_from_mesh_bathymetry_populated():
    """from_mesh extracts a NearestNDInterpolator when mesh carries bathymetry."""
    from scipy.interpolate import NearestNDInterpolator
    sq = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=float)
    nodes = np.vstack([sq, [[0.5, 0.5]]])
    elems = np.array([[0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4]], dtype=np.int64)
    bathy = np.array([1.0, 2.0, 3.0, 4.0, 2.5])
    mesh = admesh.Mesh(nodes=nodes, elements=elems, bathymetry=bathy)
    dom = Domain.from_mesh(mesh)
    assert isinstance(dom.bathymetry, NearestNDInterpolator)
    q = dom.bathymetry(np.array([[0.5, 0.5]]))
    assert np.isfinite(q).all()


# --- Step 3: triangulate() wires build_h (DEFERRED — see module docstring) --

@pytest.mark.xfail(reason="spec 025 Step 3 deferred by design (#65 closed unwired): "
                          "production stack lowers convex-domain min_q below the "
                          "advisory quality_gate default (Article V.5, #140)", strict=False)
def test_triangulate_calls_build_h():
    import admesh._stages.mesh_size as ms
    called = {}
    orig = ms.build_h

    def spy(domain, **kw):
        called.update(kw)
        return orig(domain, **kw)

    mp = pytest.MonkeyPatch()
    mp.setattr(ms, "build_h", spy)
    try:
        admesh.triangulate(_unit_square_domain(), h_max=0.2)
    finally:
        mp.undo()
    assert called.get("curvature_scale") == 20.0
    assert called.get("medial_scale") == 0.1
