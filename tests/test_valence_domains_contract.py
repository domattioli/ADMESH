"""Contract test for the valence-domains sibling package.

Asserts that the symbols ADMESH imports from `valence_domains` exist with
the expected shape, and that the installed version satisfies the pin
declared in pyproject.toml.

See docs/ADMESH_DOMAINS_CONTRACT.md for the full contract.
"""

from __future__ import annotations

import pytest

valence_domains = pytest.importorskip("valence_domains")


# Lower bound per pyproject.toml; there is no upper cap.
PIN_LOWER = (0, 4, 0)


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split("+")[0].split(".")[:3])


def test_version_within_pin() -> None:
    """Installed valence-domains satisfies the contract."""
    v = _version_tuple(valence_domains.__version__)
    assert PIN_LOWER <= v, (
        f"valence-domains {valence_domains.__version__} below contract pin "
        f">={PIN_LOWER}"
    )


def _callable_attrs(*names: str) -> bool:
    return all(callable(getattr(valence_domains, n, None)) for n in names)


def test_top_level_functions_exist() -> None:
    """At least one lookup route consumed by admesh/_valence_compat.py is present.

    Routes: (a) ``get_group`` + ``list_collections`` + ``list_domains``,
    (b) ``load_manifest``, (c) ``get_domain`` + ``list_domains``.
    """
    routes = {
        "group API": _callable_attrs("get_group", "list_collections", "list_domains"),
        "manifest": _callable_attrs("load_manifest"),
        "domain API": _callable_attrs("get_domain", "list_domains"),
    }
    assert any(routes.values()), (
        f"no supported valence_domains lookup route found ({routes}) — contract "
        f"drift; update docs/ADMESH_DOMAINS_CONTRACT.md and admesh/_valence_compat.py"
    )


def test_dataclasses_exist() -> None:
    """Data classes ADMESH reads from are exported."""
    for name in ("Domain", "Mesh", "BoundingBox"):
        assert hasattr(valence_domains, name), (
            f"valence_domains.{name} missing — contract drift"
        )


def test_list_entries_returns_iterable() -> None:
    """The compat list_entries() runs without raising and returns entries."""
    from admesh import _valence_compat

    entries = _valence_compat.list_entries()
    assert hasattr(entries, "__iter__"), "list_entries() returned non-iterable"
    assert len(list(entries)) > 0, (
        "list_entries() returned empty — registry should ship with at least one entry"
    )


def test_domain_has_expected_attrs() -> None:
    """Registry entries expose the attributes ADMESH reads."""
    from admesh import _valence_compat

    domains = list(_valence_compat.list_entries())
    if not domains:
        pytest.skip("registry is empty; cannot exercise Domain attrs")
    d = domains[0]
    for attr in ("name", "full_name", "meshes"):
        assert hasattr(d, attr), (
            f"valence_domains entry missing attribute {attr!r}"
        )
    # Collections carry no category or continent; Domains carry one of
    # continent (schema 0.4) or region (schema 0.3).
    if hasattr(d, "category"):
        assert hasattr(d, "continent") or hasattr(d, "region"), (
            "valence_domains.Domain has neither 'continent' nor 'region'"
        )


def test_mesh_has_expected_attrs() -> None:
    """valence_domains.Mesh exposes the attributes ADMESH reads."""
    from admesh import _valence_compat

    domains = list(_valence_compat.list_entries())
    meshes: list[object] = []
    for d in domains:
        meshes.extend(getattr(d, "meshes", []))
    if not meshes:
        pytest.skip("no meshes in registry; cannot exercise Mesh attrs")
    m = meshes[0]
    for attr in ("id", "filename", "path"):
        assert hasattr(m, attr), (
            f"valence_domains.Mesh instance missing attribute {attr!r}"
        )
    # exists() and load() should be callable, even if load() requires network.
    assert callable(getattr(m, "exists")), "Mesh.exists is not callable"
    assert callable(getattr(m, "load")), "Mesh.load is not callable"


@pytest.mark.slow
def test_end_to_end_load_domain_from_registry() -> None:
    """Spec 010: full chain `lookup → Mesh.load → read_fort14 → Domain`."""
    pytest.importorskip("huggingface_hub")
    from admesh import load_domain_from_registry
    from admesh.api import Domain

    domain = load_domain_from_registry("BaranjaHill")
    assert isinstance(domain, Domain)
    assert isinstance(domain.bbox, tuple) and len(domain.bbox) == 4
    assert callable(domain.sdf)
