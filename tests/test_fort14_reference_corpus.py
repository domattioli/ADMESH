"""Reference-corpus round-trip tests (T016).

Every fort.14 file under ``tests/fixtures/fort14/adcirc_examples/`` and
``tests/fixtures/fort14/community/`` must parse cleanly and round-trip
without loss. The corpus is open-ended — drop a real ADCIRC mesh in,
the test picks it up automatically. SC-005.
"""

from __future__ import annotations

import io
import pathlib

import numpy as np
import pytest

import admesh


_ROOT = pathlib.Path(__file__).parent / "fixtures" / "fort14"
_REFERENCE_DIRS = (_ROOT / "adcirc_examples", _ROOT / "community")
_FIXTURES = sorted(
    p
    for d in _REFERENCE_DIRS
    for p in d.glob("*.14")
    if not p.name.startswith("_")
)


@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda p: p.name)
def test_reference_fort14_round_trips(fixture: pathlib.Path):
    """Each real-world ADCIRC mesh in the corpus parses + round-trips."""
    mesh = admesh.read_fort14(fixture)
    assert mesh.n_nodes > 0
    assert mesh.n_elements > 0
    assert mesh.elements.min() >= 0
    assert mesh.elements.max() < mesh.n_nodes

    buf = io.StringIO()
    mesh.to_fort14(buf)
    buf.seek(0)
    rt = admesh.read_fort14(buf)

    # Coordinates round-trip within the writer's precision (default 6).
    assert mesh.equals(rt, atol=1e-5), (
        f"{fixture.name}: round-trip equality failed"
    )
    assert np.array_equal(mesh.elements, rt.elements)
    assert len(mesh.boundaries) == len(rt.boundaries)
