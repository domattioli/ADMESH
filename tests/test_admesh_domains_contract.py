"""Contract test for the admesh-domains sibling package.

Asserts that the symbols ADMESH imports from `admesh_domains` exist with
the expected shape, and that the installed version satisfies the pin
declared in pyproject.toml.

See docs/ADMESH_DOMAINS_CONTRACT.md for the full contract.
"""

from __future__ import annotations

import pytest

admesh_domains = pytest.importorskip("admesh_domains")


# Pin per docs/ADMESH_DOMAINS_CONTRACT.md and pyproject.toml.
PIN_LOWER = (0, 3, 0)
PIN_UPPER_EXCLUSIVE = (0, 4, 0)


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split("+")[0].split(".")[:3])


def test_version_within_pin() -> None:
    """Installed admesh-domains satisfies the pin >=0.3.0,<0.4."""
    v = _version_tuple(admesh_domains.__version__)
    assert PIN_LOWER <= v < PIN_UPPER_EXCLUSIVE, (
        f"admesh-domains {admesh_domains.__version__} outside contract pin "
        f">={PIN_LOWER},<{PIN_UPPER_EXCLUSIVE}"
    )


def test_top_level_functions_exist() -> None:
    """Top-level functions consumed by admesh/registry.py are present."""
    for name in ("get_domain", "list_domains"):
        assert hasattr(admesh_domains, name), (
            f"admesh_domains.{name} missing — contract drift; update "
            f"docs/ADMESH_DOMAINS_CONTRACT.md and admesh/registry.py"
        )
        assert callable(getattr(admesh_domains, name)), (
            f"admesh_domains.{name} exists but is not callable"
        )


def test_dataclasses_exist() -> None:
    """Data classes ADMESH reads from are exported."""
    for name in ("Domain", "Mesh", "BoundingBox"):
        assert hasattr(admesh_domains, name), (
            f"admesh_domains.{name} missing — contract drift"
        )


def test_list_domains_returns_iterable() -> None:
    """list_domains() runs without raising and returns something iterable."""
    domains = admesh_domains.list_domains()
    assert hasattr(domains, "__iter__"), (
        "admesh_domains.list_domains() returned non-iterable"
    )
    domains_list = list(domains)
    assert len(domains_list) > 0, (
        "admesh_domains.list_domains() returned empty — registry "
        "should ship with at least one entry"
    )


def test_domain_has_expected_attrs() -> None:
    """admesh_domains.Domain exposes the attributes ADMESH reads."""
    domains = list(admesh_domains.list_domains())
    if not domains:
        pytest.skip("registry is empty; cannot exercise Domain attrs")
    d = domains[0]
    for attr in ("name", "full_name", "category", "region", "meshes"):
        assert hasattr(d, attr), (
            f"admesh_domains.Domain instance missing attribute {attr!r}"
        )


def test_mesh_has_expected_attrs() -> None:
    """admesh_domains.Mesh exposes the attributes ADMESH reads."""
    domains = list(admesh_domains.list_domains())
    meshes: list[object] = []
    for d in domains:
        meshes.extend(getattr(d, "meshes", []))
    if not meshes:
        pytest.skip("no meshes in registry; cannot exercise Mesh attrs")
    m = meshes[0]
    for attr in ("id", "filename", "path"):
        assert hasattr(m, attr), (
            f"admesh_domains.Mesh instance missing attribute {attr!r}"
        )
    # exists() and load() should be callable, even if load() requires network.
    assert callable(getattr(m, "exists")), "Mesh.exists is not callable"
    assert callable(getattr(m, "load")), "Mesh.load is not callable"


@pytest.mark.slow
def test_end_to_end_load_domain_from_registry() -> None:
    """Spec 010: full chain `get_domain → Mesh.load → read_fort14 → Domain`."""
    pytest.importorskip("huggingface_hub")
    from admesh import load_domain_from_registry
    from admesh.api import Domain

    domain = load_domain_from_registry("BaranjaHill")
    assert isinstance(domain, Domain)
    assert isinstance(domain.bbox, tuple) and len(domain.bbox) == 4
    assert callable(domain.sdf)
