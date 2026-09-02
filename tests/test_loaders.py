"""Tests for domain loaders (TOML, JSON, fort.14)."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from admesh import (
    load_domain_from_fort14,
    load_domain_from_json,
    load_domain_from_toml,
)
from admesh.api import Domain


@pytest.fixture
def sample_toml_file(tmp_path):
    """Create a temporary TOML domain file."""
    toml_content = """
[domain]
name = "test_square"
bbox = [-1.0, -1.0, 1.0, 1.0]

[[domain.rings]]
coords = [[-1, -1], [1, -1], [1, 1], [-1, 1]]

[[domain.fixed_points]]
coords = [[-1, -1], [1, 1]]
"""
    file_path = tmp_path / "test_domain.toml"
    file_path.write_text(toml_content)
    return file_path


@pytest.fixture
def sample_json_file(tmp_path):
    """Create a temporary JSON domain file."""
    json_data = {
        "name": "test_circle",
        "bbox": [-1.0, -1.0, 1.0, 1.0],
        "rings": [[[-1, 0], [-0.707, -0.707], [0, -1], [0.707, -0.707], [1, 0], [0.707, 0.707], [0, 1], [-0.707, 0.707]]],
        "fixed_points": [[-1, 0], [1, 0]],
    }
    file_path = tmp_path / "test_domain.json"
    file_path.write_text(json.dumps(json_data))
    return file_path


def test_load_domain_from_toml(sample_toml_file):
    """Test TOML domain loader."""
    domain = load_domain_from_toml(sample_toml_file)

    assert isinstance(domain, Domain)
    assert domain.bbox == (-1.0, -1.0, 1.0, 1.0)
    assert domain.pfix is not None
    assert domain.pfix.shape == (2, 2)
    assert callable(domain.sdf)


def test_load_domain_from_json(sample_json_file):
    """Test JSON domain loader."""
    domain = load_domain_from_json(sample_json_file)

    assert isinstance(domain, Domain)
    assert domain.bbox == (-1.0, -1.0, 1.0, 1.0)
    assert domain.pfix is not None
    assert domain.pfix.shape == (2, 2)
    assert callable(domain.sdf)


def test_toml_missing_bbox(tmp_path):
    """Test TOML loader auto-computes bbox when omitted (issue #205)."""
    toml_content = """
[domain]
name = "auto"

[[domain.rings]]
coords = [[0, 0], [1, 0], [1, 1], [0, 1]]
"""
    file_path = tmp_path / "auto.toml"
    file_path.write_text(toml_content)

    # Should auto-compute bbox from ring extent
    domain = load_domain_from_toml(file_path)
    assert domain.bbox == (0.0, 0.0, 1.0, 1.0)


def test_toml_missing_rings(tmp_path):
    """Test TOML loader error on missing rings."""
    toml_content = """
[domain]
name = "bad"
bbox = [-1, -1, 1, 1]
"""
    file_path = tmp_path / "bad.toml"
    file_path.write_text(toml_content)

    with pytest.raises(ValueError, match="rings must contain"):
        load_domain_from_toml(file_path)


def test_json_missing_bbox(tmp_path):
    """Test JSON loader auto-computes bbox when omitted (issue #205)."""
    json_data = {"name": "auto", "rings": [[[0, 0], [1, 0], [1, 1], [0, 1]]]}
    file_path = tmp_path / "auto.json"
    file_path.write_text(json.dumps(json_data))

    # Should auto-compute bbox from ring extent
    domain = load_domain_from_json(file_path)
    assert domain.bbox == (0.0, 0.0, 1.0, 1.0)


def test_sdf_evaluation(sample_toml_file):
    """Test that loaded domain SDF evaluates correctly."""
    domain = load_domain_from_toml(sample_toml_file)

    # Point inside the square
    p_inside = np.array([[0.0, 0.0]])
    d_inside = domain.sdf(p_inside)
    assert d_inside[0] < 0, "Point inside should have negative distance"

    # Point outside the square
    p_outside = np.array([[2.0, 2.0]])
    d_outside = domain.sdf(p_outside)
    assert d_outside[0] > 0, "Point outside should have positive distance"


def test_load_domain_from_json_no_fixed_points(tmp_path):
    """Test JSON loader with no fixed points."""
    json_data = {
        "name": "simple",
        "bbox": [0.0, 0.0, 1.0, 1.0],
        "rings": [[[0, 0], [1, 0], [1, 1], [0, 1]]],
    }
    file_path = tmp_path / "simple.json"
    file_path.write_text(json.dumps(json_data))

    domain = load_domain_from_json(file_path)

    assert domain.pfix is None
    assert domain.bbox == (0.0, 0.0, 1.0, 1.0)


def test_load_domain_from_toml_no_fixed_points(tmp_path):
    """Test TOML loader with no fixed points."""
    toml_content = """
[domain]
name = "simple"
bbox = [0.0, 0.0, 1.0, 1.0]

[[domain.rings]]
coords = [[0, 0], [1, 0], [1, 1], [0, 1]]
"""
    file_path = tmp_path / "simple.toml"
    file_path.write_text(toml_content)

    domain = load_domain_from_toml(file_path)

    assert domain.pfix is None
    assert domain.bbox == (0.0, 0.0, 1.0, 1.0)


def test_load_domain_from_fort14():
    """Test fort.14 loader with land boundaries."""
    fixture_path = "tests/fixtures/fort14/adcirc_examples/wetting_and_drying_test.14"
    domain = load_domain_from_fort14(fixture_path)

    assert isinstance(domain, Domain)
    assert callable(domain.sdf)
    assert len(domain.bbox) == 4
    assert domain.bbox[0] < domain.bbox[2], "bbox min_x < max_x"
    assert domain.bbox[1] < domain.bbox[3], "bbox min_y < max_y"

    assert domain.pfix is not None
    assert domain.pfix.shape == (3, 2)

    # Test SDF evaluation at bbox center
    cx = (domain.bbox[0] + domain.bbox[2]) / 2
    cy = (domain.bbox[1] + domain.bbox[3]) / 2
    p_center = np.array([[cx, cy]])
    d_center = domain.sdf(p_center)
    assert d_center[0] < 0, "Point at bbox center should be inside domain"


def test_load_domain_from_fort14_no_land_boundary():
    """Test fort.14 loader error when no land boundary exists."""
    fixture_path = "tests/fixtures/fort14/adcirc_examples/wnat_test.14"

    with pytest.raises(ValueError, match="No land boundary"):
        load_domain_from_fort14(fixture_path)


def test_json_missing_rings(tmp_path):
    """Test JSON loader error on missing rings."""
    json_data = {"name": "bad", "bbox": [0, 0, 1, 1]}
    file_path = tmp_path / "bad.json"
    file_path.write_text(json.dumps(json_data))

    with pytest.raises(ValueError, match="rings must contain at least one ring"):
        load_domain_from_json(file_path)


def test_toml_declared_bbox_overrides_ring_extent(tmp_path):
    """Test that declared bbox in TOML overrides ring extent (issue #205)."""
    # Ring is small square [0,0]x[1,1], but bbox declares larger extent
    toml_content = """
[domain]
name = "test_override"
bbox = [-2.0, -2.0, 3.0, 3.0]

[[domain.rings]]
coords = [[0, 0], [1, 0], [1, 1], [0, 1]]
"""
    file_path = tmp_path / "override.toml"
    file_path.write_text(toml_content)

    domain = load_domain_from_toml(file_path)

    # bbox should be the declared one, not the ring extent
    assert domain.bbox == (-2.0, -2.0, 3.0, 3.0)


def test_json_declared_bbox_overrides_ring_extent(tmp_path):
    """Test that declared bbox in JSON overrides ring extent (issue #205)."""
    # Ring is small square [0,0]x[1,1], but bbox declares larger extent
    json_data = {
        "name": "test_override",
        "bbox": [-2.0, -2.0, 3.0, 3.0],
        "rings": [[[0, 0], [1, 0], [1, 1], [0, 1]]],
    }
    file_path = tmp_path / "override.json"
    file_path.write_text(json.dumps(json_data))

    domain = load_domain_from_json(file_path)

    # bbox should be the declared one, not the ring extent
    assert domain.bbox == (-2.0, -2.0, 3.0, 3.0)


def test_toml_bbox_auto_computed_when_omitted(tmp_path):
    """Test that bbox is auto-computed from rings when omitted from TOML."""
    toml_content = """
[domain]
name = "auto_bbox"

[[domain.rings]]
coords = [[0, 0], [2, 0], [2, 3], [0, 3]]
"""
    file_path = tmp_path / "auto.toml"
    file_path.write_text(toml_content)

    domain = load_domain_from_toml(file_path)

    # bbox should be computed from ring extent: xmin=0, ymin=0, xmax=2, ymax=3
    assert domain.bbox == (0.0, 0.0, 2.0, 3.0)


def test_json_bbox_auto_computed_when_omitted(tmp_path):
    """Test that bbox is auto-computed from rings when omitted from JSON."""
    json_data = {
        "name": "auto_bbox",
        "rings": [[[0, 0], [2, 0], [2, 3], [0, 3]]],
    }
    file_path = tmp_path / "auto.json"
    file_path.write_text(json.dumps(json_data))

    domain = load_domain_from_json(file_path)

    # bbox should be computed from ring extent: xmin=0, ymin=0, xmax=2, ymax=3
    assert domain.bbox == (0.0, 0.0, 2.0, 3.0)


def test_toml_invalid_bbox_xmin_greater_xmax(tmp_path):
    """Test TOML loader raises ValueError for invalid bbox (xmin >= xmax)."""
    toml_content = """
[domain]
name = "bad_bbox"
bbox = [1.0, -1.0, 0.0, 1.0]

[[domain.rings]]
coords = [[0, 0], [1, 0], [1, 1], [0, 1]]
"""
    file_path = tmp_path / "bad.toml"
    file_path.write_text(toml_content)

    with pytest.raises(ValueError, match="xmin.*must be.*xmax"):
        load_domain_from_toml(file_path)


def test_json_invalid_bbox_ymin_greater_ymax(tmp_path):
    """Test JSON loader raises ValueError for invalid bbox (ymin >= ymax)."""
    json_data = {
        "name": "bad_bbox",
        "bbox": [-1.0, 1.0, 1.0, 0.0],  # ymin > ymax
        "rings": [[[0, 0], [1, 0], [1, 1], [0, 1]]],
    }
    file_path = tmp_path / "bad.json"
    file_path.write_text(json.dumps(json_data))

    with pytest.raises(ValueError, match="ymin.*must be.*ymax"):
        load_domain_from_json(file_path)
