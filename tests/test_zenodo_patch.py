"""Offline tests for ``scripts/zenodo_patch.py``. No network call is made."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "zenodo_patch.py"
PATCH_DIR = SCRIPT.parent.parent / "zenodo" / "patches"


@pytest.fixture(scope="module")
def zp():
    spec = importlib.util.spec_from_file_location("zenodo_patch", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _current(zp, metadata, state="done"):
    return {"conceptdoi": zp.CONCEPT_DOI, "state": state, "metadata": metadata}


def _metadata():
    return {
        "title": "Old title",
        "doi": "10.5281/zenodo.1",
        "prereserve_doi": {"doi": "10.5281/zenodo.1", "recid": 1},
        "version": "v1.0.0",
        "upload_type": "software",
        "dates": [{"type": "accepted", "description": "No date value"}],
        "keywords": ["mesh"],
    }


def test_null_removes_key(zp):
    merged = zp.merge(_metadata(), {"dates": None})
    assert "dates" not in merged
    assert merged["keywords"] == ["mesh"]
    assert merged["version"] == "v1.0.0"


def test_null_on_absent_key_is_a_no_op(zp):
    metadata = _metadata()
    merged = zp.merge(metadata, {"grants": None})
    assert merged == metadata


def test_replacement_still_works_with_removal(zp):
    merged = zp.merge(_metadata(), {"title": "New title", "dates": None})
    assert merged["title"] == "New title"
    assert "dates" not in merged


def test_merge_does_not_change_the_input(zp):
    metadata = _metadata()
    zp.merge(metadata, {"dates": None})
    assert "dates" in metadata


def test_removed_keys_lists_only_null_values(zp):
    assert zp.removed_keys({"grants": None, "title": "x", "dates": None}) == ["dates", "grants"]


@pytest.mark.parametrize(
    "key",
    ["doi", "conceptdoi", "prereserve_doi", "conceptrecid", "version", "upload_type",
     "title", "creators", "description", "publication_date", "access_right"],
)
def test_guarded_keys_cannot_be_removed(zp, key):
    with pytest.raises(zp.PatchError):
        zp.merge(_metadata(), {key: None})


@pytest.mark.parametrize("key", ["doi", "conceptdoi", "prereserve_doi", "version", "upload_type"])
def test_load_patch_refuses_guarded_removal(zp, tmp_path, key):
    path = tmp_path / "1.json"
    path.write_text(json.dumps({key: None}), encoding="utf-8")
    with pytest.raises(zp.PatchError):
        zp.load_patch(path)


def test_load_patch_accepts_removal_of_optional_key(zp, tmp_path):
    path = tmp_path / "1.json"
    path.write_text(json.dumps({"dates": None}), encoding="utf-8")
    assert zp.load_patch(path) == {"dates": None}


def test_dry_run_reports_removal_and_makes_no_write(zp, monkeypatch, capsys, tmp_path):
    (tmp_path / "7.json").write_text(json.dumps({"dates": None, "grants": None}), encoding="utf-8")
    calls = []

    def fake_api(method, url, token, body=None):
        calls.append(method)
        return 200, json.dumps(_current(zp, _metadata(), state="inprogress"))

    monkeypatch.setattr(zp, "api", fake_api)
    zp.run("7", "dry-run", "token-value", patch_dir=tmp_path)
    out = capsys.readouterr().out
    assert calls == ["GET"]
    assert "remove key dates: present, removed" in out
    assert "remove key grants: absent, nothing to remove" in out
    assert '-  "dates": [' in out
    assert "dry-run: no write call was made" in out
    assert "token-value" not in out


def test_apply_sends_metadata_without_removed_key(zp, monkeypatch, tmp_path):
    (tmp_path / "7.json").write_text(json.dumps({"dates": None}), encoding="utf-8")
    sent = []

    def fake_api(method, url, token, body=None):
        sent.append((method, body))
        if method == "GET":
            return 200, json.dumps(_current(zp, _metadata(), state="inprogress"))
        return 200, "{}"

    monkeypatch.setattr(zp, "api", fake_api)
    zp.run("7", "apply", "token-value", patch_dir=tmp_path)
    assert [method for method, _ in sent] == ["GET", "PUT", "POST"]
    body = sent[1][1]["metadata"]
    assert "dates" not in body
    assert body["doi"] == "10.5281/zenodo.1"
    assert body["version"] == "v1.0.0"


@pytest.mark.parametrize("path", sorted(PATCH_DIR.glob("*.json")), ids=lambda p: p.stem)
def test_shipped_patches_load(zp, path):
    patch = zp.load_patch(path)
    for key in zp.removed_keys(patch):
        assert key not in zp.PROTECTED_KEYS and key not in zp.REQUIRED_KEYS
