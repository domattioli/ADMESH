"""fort.14 round-trip tests on the 5 MVP domains (T014)."""

from __future__ import annotations

import io

import numpy as np
import pytest

import admesh
from admesh.domains import ALL as DOMAIN_REGISTRY


_MVP = {
    "unit_square":       {"h_max": 0.12, "max_iter": 200},
    "l_shape":           {"h_max": 0.15, "max_iter": 200},
    "unit_disk":         {"h_max": 0.15, "max_iter": 200},
    "annulus":           {"h_max": 0.12, "max_iter": 200},
    "notched_rectangle": {"h_max": 0.08, "max_iter": 200},
}


@pytest.mark.parametrize("name", list(_MVP))
def test_fort14_roundtrip_via_buffer(name: str) -> None:
    port_dom = DOMAIN_REGISTRY[name]
    pfix = port_dom.fixed_points if port_dom.fixed_points.size else None
    domain = admesh.domain_from_sdf(sdf=port_dom.fd, bbox=port_dom.bbox, pfix=pfix)
    # Spec-001 round-trip baseline: opt out of spec-002's default stack
    # so the legacy uniform-`h` quality envelope still holds.
    mesh = admesh.triangulate(
        domain,
        seed=0,
        enable_curvature=False,
        enable_medial_axis=False,
        **_MVP[name],
    )

    buf = io.StringIO()
    mesh.to_fort14(buf)
    buf.seek(0)
    rt = admesh.read_fort14(buf)

    assert mesh.equals(rt, atol=1e-5)
    # Connectivity exact.
    assert np.array_equal(mesh.elements, rt.elements)
    # BC labels preserved per segment.
    assert len(mesh.boundaries) == len(rt.boundaries)
    for a, b in zip(mesh.boundaries, rt.boundaries):
        assert int(a.bc_type) == int(b.bc_type)
        assert a.is_open == b.is_open
        assert np.array_equal(a.node_ids, b.node_ids)


def test_fort14_roundtrip_via_path(tmp_path) -> None:
    port_dom = DOMAIN_REGISTRY["unit_square"]
    domain = admesh.domain_from_sdf(
        sdf=port_dom.fd, bbox=port_dom.bbox,
        pfix=port_dom.fixed_points,
    )
    mesh = admesh.triangulate(
        domain,
        h_max=0.12,
        max_iter=200,
        seed=0,
        enable_curvature=False,
        enable_medial_axis=False,
    )

    out = tmp_path / "mesh.14"
    mesh.to_fort14(out)
    rt = admesh.read_fort14(out)
    assert mesh.equals(rt, atol=1e-5)
