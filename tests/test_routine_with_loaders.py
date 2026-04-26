"""End-to-end tests for triangulate() with domain loaders."""

import json
from pathlib import Path

import numpy as np
import pytest

from admesh import Mesh, load_domain_from_json, triangulate


@pytest.fixture
def sample_domain(tmp_path):
    """Create a simple square domain for testing."""
    json_data = {"bbox": [-1.0, -1.0, 1.0, 1.0], "rings": [[[-1, -1], [1, -1], [1, 1], [-1, 1]]]}
    p = tmp_path / "square.json"
    p.write_text(json.dumps(json_data))
    return load_domain_from_json(p)


@pytest.fixture
def sample_json_domain_file(tmp_path):
    """Create a JSON domain file."""
    json_data = {
        "name": "test_square",
        "bbox": [-1.0, -1.0, 1.0, 1.0],
        "rings": [[[-1, -1], [1, -1], [1, 1], [-1, 1]]],
    }
    file_path = tmp_path / "domain.json"
    file_path.write_text(json.dumps(json_data))
    return file_path


def test_triangulate_with_domain_object(sample_domain):
    """Test triangulate() with Domain object (backward compatibility)."""
    mesh = triangulate(sample_domain, h_max=0.2)

    assert isinstance(mesh, Mesh)
    assert mesh.n_nodes > 0
    assert mesh.n_elements > 0


def test_triangulate_with_json_file(sample_json_domain_file):
    """Test triangulate() accepts JSON file path."""
    mesh = triangulate(str(sample_json_domain_file), h_max=0.2)

    assert isinstance(mesh, Mesh)
    assert mesh.n_nodes > 0
    assert mesh.n_elements > 0


def test_triangulate_with_path_object(sample_json_domain_file):
    """Test triangulate() accepts pathlib.Path object."""
    mesh = triangulate(sample_json_domain_file, h_max=0.2)

    assert isinstance(mesh, Mesh)
    assert mesh.n_nodes > 0
    assert mesh.n_elements > 0


def test_triangulate_with_invalid_file():
    """Test triangulate() raises error for non-existent file."""
    with pytest.raises(ValueError, match="not found"):
        triangulate("nonexistent_domain.json", h_max=0.2)


def test_triangulate_with_unknown_format(tmp_path):
    """Test triangulate() raises error for unknown file format."""
    unknown_file = tmp_path / "domain.xyz"
    unknown_file.write_text("some data")

    with pytest.raises(ValueError, match="Unknown domain file format"):
        triangulate(str(unknown_file), h_max=0.2)


def test_triangulate_default_params(sample_domain):
    """Test triangulate() with default parameters."""
    mesh = triangulate(sample_domain)

    assert isinstance(mesh, Mesh)
    assert mesh.n_nodes > 0


def test_triangulate_custom_h_max(sample_domain):
    """Test triangulate() with custom h_max parameter."""
    mesh1 = triangulate(sample_domain, h_max=0.1)
    mesh2 = triangulate(sample_domain, h_max=0.3)

    # Finer mesh should have more nodes
    assert mesh1.n_nodes > mesh2.n_nodes


def test_triangulate_with_toml_file(tmp_path):
    """Test triangulate() with TOML file."""
    toml_content = """
[domain]
name = "test"
bbox = [-1.0, -1.0, 1.0, 1.0]

[[domain.rings]]
coords = [[-1, -1], [1, -1], [1, 1], [-1, 1]]
"""
    toml_file = tmp_path / "domain.toml"
    toml_file.write_text(toml_content)

    mesh = triangulate(str(toml_file), h_max=0.2)

    assert mesh.n_nodes > 0
    assert mesh.n_elements > 0
