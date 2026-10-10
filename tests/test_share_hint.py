"""The share-your-mesh log hint fires once per process and honors the opt-out."""

import logging

import pytest

from admesh.share_hint import maybe_log_share_hint
import admesh.share_hint as hint_mod


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.delenv("ADMESH_NO_SHARE_HINT", raising=False)
    monkeypatch.setattr(hint_mod, "_hint_shown", False)


def _hits(caplog):
    return [r for r in caplog.records if "valence-intake" in r.getMessage()]


def test_hint_emitted_once(caplog):
    with caplog.at_level(logging.INFO, logger="admesh.share_hint"):
        maybe_log_share_hint()
        maybe_log_share_hint()
    assert len(_hits(caplog)) == 1


def test_hint_suppressed_by_env(caplog, monkeypatch):
    monkeypatch.setenv("ADMESH_NO_SHARE_HINT", "1")
    with caplog.at_level(logging.INFO, logger="admesh.share_hint"):
        maybe_log_share_hint()
    assert _hits(caplog) == []


def test_write_fort14_emits_hint_once(caplog, tmp_path):
    import numpy as np
    from admesh.api import Mesh
    from admesh.fort14 import write_fort14

    mesh = Mesh(
        nodes=np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]),
        elements=np.array([[0, 1, 2]]),
    )
    with caplog.at_level(logging.INFO, logger="admesh.share_hint"):
        write_fort14(mesh, tmp_path / "a.14")
        write_fort14(mesh, tmp_path / "b.14")
    assert len(_hits(caplog)) == 1
