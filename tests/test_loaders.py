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
    """Test TOML loader error on missing bbox."""
    toml_content = """
[domain]
name = "bad"

[[domain.rings]]
coords = [[0, 0], [1, 1]]
"""
    file_path = tmp_path / "bad.toml"
    file_path.write_text(toml_content)

    with pytest.raises(ValueError, match="bbox must be a 4-tuple"):
        load_domain_from_toml(file_path)


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
    """Test JSON loader error on missing bbox."""
    json_data = {"name": "bad", "rings": [[[0, 0], [1, 1]]]}
    file_path = tmp_path / "bad.json"
    file_path.write_text(json.dumps(json_data))

    with pytest.raises(ValueError, match="bbox must be a 4-tuple"):
        load_domain_from_json(file_path)


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
