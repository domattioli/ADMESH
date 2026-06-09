"""Direct stage tests for ``admesh._stages.background_grid`` (spec 012 / #73).

Imports the *canonical* module path (not the ``admesh.background_grid``
shim) so the contract is immune to shim deletion at 1.0.0. The MATLAB
numerical-parity test runs against the stage-02 fixture exported via
``scripts/export_matlab_fixtures.m`` (Octave-compatible; #78).
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

import admesh._stages.background_grid as bg_stage
from admesh._stages.background_grid import BackgroundGrid, create_background_grid
from admesh._stages.domains import UNIT_SQUARE

H0 = 0.1
FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "matlab"
    / "background_grid_unit_square.npz"
)


def test_module_provenance_smoke():
    """Track A: lowest stable contract — provenance docstring (FR-012-2)."""
    assert bg_stage.__doc__, "module must carry a docstring"
    assert re.search(
        r"02_Create_Background_Grid/CreateBackgroundGrid\.m", bg_stage.__doc__
    ), "docstring must cite the MATLAB source per Constitution Principle I"


def test_grid_bbox_covers_domain_plus_padding():
    """FR-012-3: grid extent == domain.bbox expanded by padding."""
    g = create_background_grid(UNIT_SQUARE, H0)
    xmin, ymin, xmax, ymax = UNIT_SQUARE.bbox
    pad = H0  # default padding
    assert g.bbox[0] == pytest.approx(xmin - pad)
    assert g.bbox[1] == pytest.approx(ymin - pad)
    # grid never falls short of the padded box (arange may overshoot by <delta)
    assert g.X.min() == pytest.approx(xmin - pad)
    assert g.Y.min() == pytest.approx(ymin - pad)
    assert g.X.max() >= xmax + pad - 1e-12
    assert g.Y.max() >= ymax + pad - 1e-12


def test_grid_spacing_equals_h0():
    """FR-012-3: Δx == Δy == h0 (res=1)."""
    g = create_background_grid(UNIT_SQUARE, H0)
    assert g.delta == pytest.approx(H0)
    assert np.diff(g.X[0, :]).mean() == pytest.approx(H0)
    assert np.diff(g.Y[:, 0]).mean() == pytest.approx(H0)


def test_grid_is_uniform_both_axes():
    """FR-012-3: per-row/col spacing variance is exactly zero."""
    g = create_background_grid(UNIT_SQUARE, H0)
    assert np.var(np.diff(g.X[0, :])) == pytest.approx(0.0, abs=1e-24)
    assert np.var(np.diff(g.Y[:, 0])) == pytest.approx(0.0, abs=1e-24)
    assert isinstance(g, BackgroundGrid)


def test_res_factor_refines_spacing():
    """res=2 halves the spacing relative to res=1."""
    g1 = create_background_grid(UNIT_SQUARE, H0, res=1)
    g2 = create_background_grid(UNIT_SQUARE, H0, res=2)
    assert g2.delta == pytest.approx(g1.delta / 2)


def test_matlab_parity_unit_square():
    """FR-012-4: bit-stable parity vs MATLAB CreateBackgroundGrid at atol=1e-10."""
    data = np.load(FIXTURE)  # FileNotFoundError until the fixture lands
    g = create_background_grid(UNIT_SQUARE, H0)
    np.testing.assert_allclose(g.X, data["X"], atol=1e-10, rtol=0)
    np.testing.assert_allclose(g.Y, data["Y"], atol=1e-10, rtol=0)
    np.testing.assert_allclose(g.delta, float(data["delta"]), atol=1e-10, rtol=0)
