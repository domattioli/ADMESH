"""Tests for ADMESH-Domains registry integration."""

import pytest

from admesh.api import Domain
from admesh.registry import (
    _convert_to_admesh_domain,
    list_available_domains,
    load_domain_from_registry,
    load_domain_with_metadata,
)


def test_load_domain_from_registry_without_admesh_domains():
    """Test that ImportError is raised when admesh-domains not installed."""
    # This test assumes admesh-domains is not installed for testing
    # In a real scenario, if admesh-domains IS installed, this test should be skipped
    try:
        import admesh_domains  # noqa: F401
        pytest.skip("admesh-domains is installed; skipping import error test")
    except ImportError:
        with pytest.raises(ImportError, match="admesh-domains package required"):
            load_domain_from_registry("test-mesh")


def test_list_available_domains_without_admesh_domains():
    """Test that ImportError is raised for list_available_domains when admesh-domains not installed."""
    try:
        import admesh_domains  # noqa: F401
        pytest.skip("admesh-domains is installed; skipping import error test")
    except ImportError:
        with pytest.raises(ImportError, match="admesh-domains package required"):
            list_available_domains()


def test_load_domain_with_metadata_without_admesh_domains():
    """Test that ImportError is raised for load_domain_with_metadata when admesh-domains not installed."""
    try:
        import admesh_domains  # noqa: F401
        pytest.skip("admesh-domains is installed; skipping import error test")
    except ImportError:
        with pytest.raises(ImportError, match="admesh-domains package required"):
            load_domain_with_metadata("test-mesh")


def test_convert_to_admesh_domain_with_rings():
    """Test conversion of domain object with rings attribute."""
    class MockDomainWithRings:
        rings = [[[0, 0], [1, 0], [1, 1], [0, 1]]]
        bbox = (0, 0, 1, 1)
        fixed_points = None

    mock_domain = MockDomainWithRings()
    domain = _convert_to_admesh_domain(mock_domain)

    assert isinstance(domain, Domain)
    assert domain.bbox == (0, 0, 1, 1)
    assert callable(domain.sdf)


def test_convert_to_admesh_domain_missing_rings():
    """Test conversion fails with missing rings."""
    class MockDomainBad:
        pass

    mock_domain = MockDomainBad()

    with pytest.raises(ValueError, match="rings"):
        _convert_to_admesh_domain(mock_domain)


def test_convert_to_admesh_domain_with_fixed_points():
    """Test conversion preserves fixed points."""
    import numpy as np

    class MockDomain:
        rings = [[[0, 0], [1, 0], [1, 1], [0, 1]]]
        bbox = (0, 0, 1, 1)
        fixed_points = [[0, 0], [1, 1]]

    mock_domain = MockDomain()
    domain = _convert_to_admesh_domain(mock_domain)

    assert domain.pfix is not None
    assert isinstance(domain.pfix, np.ndarray)


def test_convert_to_admesh_domain_auto_bbox():
    """Test that bbox is computed from rings if not provided."""
    class MockDomain:
        rings = [[[0, 0], [2, 0], [2, 2], [0, 2]]]
        bbox = None
        fixed_points = None

    mock_domain = MockDomain()
    domain = _convert_to_admesh_domain(mock_domain)

    assert domain.bbox == (0, 0, 2, 2)


# ---------------------------------------------------------------------------
# Spec 010 — positive-path tests against admesh-domains 0.3.x
# ---------------------------------------------------------------------------


def test_list_available_domains_nonempty():
    """`list_available_domains()` returns a non-empty mapping (offline-safe)."""
    pytest.importorskip("admesh_domains")
    domains = list_available_domains()
    assert isinstance(domains, dict)
    assert len(domains) > 0
    assert all(isinstance(k, str) for k in domains.keys())
    assert all(isinstance(v, str) for v in domains.values())


@pytest.mark.slow
def test_load_domain_from_registry_baranja_hill():
    """End-to-end: registry lookup → download → fort.14 → Domain."""
    pytest.importorskip("admesh_domains")
    pytest.importorskip("huggingface_hub")
    domain = load_domain_from_registry("BaranjaHill")
    assert isinstance(domain, Domain)
    assert isinstance(domain.bbox, tuple)
    assert len(domain.bbox) == 4
    assert callable(domain.sdf)


@pytest.mark.slow
def test_load_domain_with_metadata_baranja_hill():
    """`load_domain_with_metadata` returns `(Domain, dict)` with provenance."""
    pytest.importorskip("admesh_domains")
    pytest.importorskip("huggingface_hub")
    domain, meta = load_domain_with_metadata("BaranjaHill")
    assert isinstance(domain, Domain)
    assert isinstance(meta, dict)
    assert "bounding_box" in meta
