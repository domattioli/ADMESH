"""M.4 binding gate — triangulation on all 5 MVP test domains.

For each registered domain in :mod:`admesh.domains`, assert:

- ``admesh.triangulate`` returns a valid mesh (structural +
  geometric checks in :func:`conftest.assert_valid_mesh`).
- ``min_q >= 0.30`` and ``mean_q >= 0.60`` (per
  ``PROJECT_PLAN.md`` MVP acceptance criteria and
  ``docs/session_1_plan.md`` binding gate).

Per-domain ``h0`` and ``niter`` defaults match
``scripts/render_mvp_meshes.py`` so the test suite and the PNG
artifacts agree. If a domain misses the gate, the correct response
is NOT to widen the tolerance — see the falsifier section of
``docs/session_1_plan.md``.
"""

from __future__ import annotations

import pytest

from admesh import domains
from admesh.quality import mesh_quality
from admesh.routine import triangulate

from conftest import assert_valid_mesh

_MVP_CONFIG: dict[str, dict[str, float | int]] = {
    "unit_square":       {"h0": 0.12, "niter": 200},
    "l_shape":           {"h0": 0.15, "niter": 200},
    "unit_disk":         {"h0": 0.15, "niter": 200},
    "annulus":           {"h0": 0.12, "niter": 200},
    "notched_rectangle": {"h0": 0.08, "niter": 200},
}

MIN_Q_GATE = 0.30
MEAN_Q_GATE = 0.60


@pytest.mark.parametrize("name", list(_MVP_CONFIG))
def test_mvp_domain(name: str) -> None:
    dom = domains.ALL[name]
    cfg = _MVP_CONFIG[name]
    p, t = triangulate(
        dom, h0=float(cfg["h0"]), niter=int(cfg["niter"]), seed=0
    )
    assert_valid_mesh(p, t, dom.fd, geps=1e-3 * float(cfg["h0"]))

    min_q, mean_q, _ = mesh_quality(p, t)
    assert min_q >= MIN_Q_GATE, f"{name}: min_q={min_q:.3f} < {MIN_Q_GATE}"
    assert mean_q >= MEAN_Q_GATE, f"{name}: mean_q={mean_q:.3f} < {MEAN_Q_GATE}"
