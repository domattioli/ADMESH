"""Sign-check the 5 test-domain SDFs."""

import numpy as np
import pytest

from admesh import domains


INTERIOR_PROBES: dict[str, tuple[float, float]] = {
    "unit_square": (0.0, 0.0),
    "l_shape": (-0.5, 0.5),
    "unit_disk": (0.1, -0.2),
    "annulus": (0.7, 0.0),  # between r=0.4 and r=1.0
    "notched_rectangle": (0.5, 0.0),
}

EXTERIOR_PROBES: dict[str, tuple[float, float]] = {
    "unit_square": (2.0, 2.0),
    "l_shape": (0.5, 0.5),  # inside the notch → outside the L
    "unit_disk": (2.0, 2.0),
    "annulus": (0.0, 0.0),  # inside the hole
    "notched_rectangle": (0.0, 0.4),  # inside the notch
}

BOUNDARY_PROBES: dict[str, tuple[float, float]] = {
    "unit_square": (0.5, 0.0),
    "l_shape": (-1.0, 0.0),
    "unit_disk": (1.0, 0.0),
    "annulus": (1.0, 0.0),
    "notched_rectangle": (1.0, 0.0),
}


@pytest.mark.parametrize("name", list(INTERIOR_PROBES.keys()))
def test_interior_probe_is_negative(name: str) -> None:
    d = domains.ALL[name]
    assert d(INTERIOR_PROBES[name])[0] < 0.0


@pytest.mark.parametrize("name", list(EXTERIOR_PROBES.keys()))
def test_exterior_probe_is_positive(name: str) -> None:
    d = domains.ALL[name]
    assert d(EXTERIOR_PROBES[name])[0] > 0.0


@pytest.mark.parametrize("name", list(BOUNDARY_PROBES.keys()))
def test_boundary_probe_is_near_zero(name: str) -> None:
    d = domains.ALL[name]
    val = d(BOUNDARY_PROBES[name])[0]
    assert abs(val) < 1e-9


def test_all_registry_populated() -> None:
    assert set(domains.ALL) == {
        "unit_square", "l_shape", "unit_disk", "annulus", "notched_rectangle"
    }


def test_sdf_vectorized() -> None:
    d = domains.UNIT_DISK
    p = np.array([[0.0, 0.0], [0.5, 0.0], [1.0, 0.0], [2.0, 0.0]])
    vals = d(p)
    assert vals.shape == (4,)
    np.testing.assert_allclose(vals, [-1.0, -0.5, 0.0, 1.0], atol=1e-12)


def test_domain_dataclass_fixed_points_default() -> None:
    # Domains without explicit fixed_points (disk, annulus) get an empty array.
    assert domains.UNIT_DISK.fixed_points.shape == (0, 2)
    assert domains.ANNULUS.fixed_points.shape == (0, 2)
    assert domains.UNIT_SQUARE.fixed_points.shape == (4, 2)


@pytest.mark.parametrize("name", ["unit_square", "l_shape", "notched_rectangle"])
def test_fixed_points_lie_on_boundary(name: str) -> None:
    dom = domains.ALL[name]
    if dom.fixed_points.size == 0:
        return
    d = dom.fd(dom.fixed_points)
    np.testing.assert_allclose(d, 0.0, atol=1e-9,
        err_msg=f"{name}: fixed_points not on boundary")
