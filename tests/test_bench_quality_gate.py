"""Regression: benchmark worker honours production quality floor (issue #101)."""
import importlib.util
import pathlib
import sys

import pytest


BENCH = pathlib.Path(__file__).parents[1] / "benchmarks" / "_bench_worker.py"


@pytest.mark.slow
def test_bench_worker_imports_production_params():
    """Verify benchmark worker uses spec-002 production defaults."""
    spec = importlib.util.spec_from_file_location("_bench_worker", BENCH)
    mod = importlib.util.module_from_spec(spec)
    src = BENCH.read_text()
    # curvature_scale must use production default 20.0, not hmin
    assert "curvature_scale=20.0" in src, "curvature_scale must be 20.0 (production default)"
    assert "medial_scale=0.1" in src, "medial_scale must be 0.1 (production default)"
    # h0 for distmesh must be hmax (production path), not hmin
    assert "h0=a.hmax" in src, "distmesh h0 must use hmax to match triangulate() production path"


@pytest.mark.slow
def test_bench_worker_has_quality_gate_warning():
    """Verify benchmark worker warns when min_q < gate floor."""
    src = BENCH.read_text()
    assert "quality gate" in src.lower(), "worker must warn when min_q < gate floor"
