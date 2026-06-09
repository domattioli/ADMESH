"""Pin the ADMESH public-API surface for MADMESHing unification (issue #143).

MADMESHing (https://github.com/domattioli/MADMESHing) depends on stable
imports and signatures from ADMESH:
  - `from admesh import Domain, triangulate`
  - `from admesh import read_fort14`

This contract test fails CI if those symbols move, change signature, or are
removed from `__all__`. Ensures MADMESHing's monte_carlo.py + wnat_*
modules stay unbroken across ADMESH versions.

Reference: domattioli/ADMESH#143
"""

from __future__ import annotations

import dataclasses
import inspect


def test_unification_surface_importable():
    """Domain, triangulate, read_fort14 are importable from admesh."""
    from admesh import Domain, read_fort14, triangulate

    assert Domain is not None
    assert triangulate is not None
    assert read_fort14 is not None


def test_unification_surface_in_all():
    """Domain, triangulate, read_fort14 are in admesh.__all__."""
    import admesh

    expected = {"Domain", "triangulate", "read_fort14"}
    assert expected.issubset(set(admesh.__all__))


def test_canonical_modules():
    """Symbols live in pinned canonical modules (api.py, fort14.py)."""
    from admesh import Domain, read_fort14, triangulate

    assert Domain.__module__ == "admesh.api", (
        f"Domain must live in admesh.api, found in {Domain.__module__}"
    )
    assert triangulate.__module__ == "admesh.api", (
        f"triangulate must live in admesh.api, found in {triangulate.__module__}"
    )
    assert read_fort14.__module__ == "admesh.fort14", (
        f"read_fort14 must live in admesh.fort14, found in {read_fort14.__module__}"
    )


def test_triangulate_signature():
    """triangulate() has required signature for MADMESHing.

    MADMESHing calls: triangulate(domain, h_max=..., h_min=..., quality_gate=...)
    """
    from admesh import triangulate

    sig = inspect.signature(triangulate)
    params = sig.parameters

    # First positional param: 'domain'
    param_list = list(params.keys())
    assert param_list[0] == "domain", (
        f"First param must be 'domain', got {param_list[0]}"
    )

    # Verify keyword-only params exist and are keyword-only
    assert "h_max" in params, "Missing 'h_max' parameter"
    assert params["h_max"].kind == inspect.Parameter.KEYWORD_ONLY, (
        "h_max must be KEYWORD_ONLY"
    )

    assert "h_min" in params, "Missing 'h_min' parameter"
    assert params["h_min"].kind == inspect.Parameter.KEYWORD_ONLY, (
        "h_min must be KEYWORD_ONLY"
    )

    assert "quality_gate" in params, "Missing 'quality_gate' parameter"
    assert params["quality_gate"].kind == inspect.Parameter.KEYWORD_ONLY, (
        "quality_gate must be KEYWORD_ONLY"
    )


def test_read_fort14_signature():
    """read_fort14() has exactly one parameter: path."""
    from admesh import read_fort14

    sig = inspect.signature(read_fort14)
    params = sig.parameters

    assert len(params) == 1, (
        f"read_fort14 must have exactly 1 parameter, got {len(params)}: {list(params.keys())}"
    )
    assert "path" in params, (
        f"Parameter must be named 'path', got {list(params.keys())[0]}"
    )


def test_domain_dataclass_fields():
    """Domain is a dataclass with at least {sdf, bbox} fields.

    MADMESHing constructs Domain(sdf=..., bbox=...) and passes to triangulate().
    """
    from admesh import Domain

    # Check it's a dataclass
    assert dataclasses.is_dataclass(Domain), (
        "Domain must be a dataclass (has __dataclass_fields__)"
    )

    # Check required fields exist
    field_names = {f.name for f in dataclasses.fields(Domain)}
    required = {"sdf", "bbox"}
    assert required.issubset(field_names), (
        f"Domain missing required fields {required - field_names}"
    )
