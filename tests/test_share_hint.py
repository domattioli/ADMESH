"""The share-your-mesh stderr hint prints once per process and honors the opt-out."""

import pytest

from admesh.share_hint import maybe_log_share_hint
import admesh.share_hint as hint_mod


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.delenv("ADMESH_NO_SHARE_HINT", raising=False)
    monkeypatch.setattr(hint_mod, "_hint_shown", False)


def test_hint_emitted_once(capsys):
    maybe_log_share_hint()
    maybe_log_share_hint()
    assert capsys.readouterr().err.count("valence-intake") == 1


def test_hint_suppressed_by_env(capsys, monkeypatch):
    monkeypatch.setenv("ADMESH_NO_SHARE_HINT", "1")
    maybe_log_share_hint()
    assert capsys.readouterr().err == ""


def test_write_fort14_emits_hint_once(capsys, tmp_path):
    import numpy as np
    from admesh.api import Mesh
    from admesh.fort14 import write_fort14

    mesh = Mesh(
        nodes=np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]),
        elements=np.array([[0, 1, 2]]),
    )
    write_fort14(mesh, tmp_path / "a.14")
    write_fort14(mesh, tmp_path / "b.14")
    assert capsys.readouterr().err.count("valence-intake") == 1
