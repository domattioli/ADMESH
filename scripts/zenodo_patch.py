#!/usr/bin/env python3
"""Patch the metadata of one Zenodo record from ``zenodo/patches/<id>.json``.

The patch file holds only the top-level metadata keys to change. The script
reads the current deposit, replaces those keys, prints a unified diff of the
metadata and, in ``apply`` mode only, edits and republishes the record.
``discard`` mode drops an open edit of the record and changes nothing else.

Environment:
    ZENODO_TOKEN  Zenodo access token. Sent only in an Authorization header.
    RECORD_ID     Record id; must match a file in ``zenodo/patches/``.
    MODE          ``dry-run`` (default), ``apply`` or ``discard``.

The standard library is the only dependency.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://zenodo.org/api/deposit/depositions"
CONCEPT_DOI = "10.5281/zenodo.20264085"
PROTECTED_KEYS = ("doi", "prereserve_doi", "conceptdoi", "conceptrecid")
PATCH_DIR = Path(__file__).resolve().parent.parent / "zenodo" / "patches"


class PatchError(Exception):
    """A check failed; nothing was written."""


def api(method, url, token, body=None):
    """Send one request and return ``(status, response_text)``."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/json")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


def validate_record_id(record_id, patch_dir=PATCH_DIR):
    if not re.fullmatch(r"[0-9]+", record_id or ""):
        raise PatchError("record_id must be digits only")
    path = Path(patch_dir) / f"{record_id}.json"
    if not path.is_file():
        raise PatchError(f"no patch file for record {record_id}")
    return path


def load_patch(path):
    patch = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(patch, dict) or not patch:
        raise PatchError("patch must be a non-empty JSON object")
    refused = [key for key in PROTECTED_KEYS if key in patch]
    if refused:
        raise PatchError(f"patch carries protected keys: {', '.join(refused)}")
    return patch


def merge(current_metadata, patch):
    """Replace only the patch's top-level keys in the current metadata."""
    merged = dict(current_metadata)
    merged.update(patch)
    return merged


def check_guards(current, merged):
    """Raise before any write if identifiers change or the concept differs."""
    if current.get("conceptdoi") != CONCEPT_DOI:
        raise PatchError(
            f"concept DOI is {current.get('conceptdoi')!r}, expected {CONCEPT_DOI!r}"
        )
    metadata = current.get("metadata", {})
    changed = [key for key in PROTECTED_KEYS if merged.get(key) != metadata.get(key)]
    if changed:
        raise PatchError(f"merged metadata changes protected keys: {', '.join(changed)}")


def metadata_diff(current_metadata, merged):
    def dump(value):
        return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False).splitlines()

    return "\n".join(
        difflib.unified_diff(dump(current_metadata), dump(merged), "current", "merged", lineterm="")
    )


def write_call(mode, method, url, token, body=None, required="apply"):
    """Run one write request; refuse unless mode is exactly ``required``."""
    if mode != required:
        raise PatchError(f"write call attempted outside {required} mode")
    status, text = api(method, url, token, body)
    print(f"{method} {url} -> {status}")
    if not 200 <= status < 300:
        print(text)
        raise PatchError(f"{method} {url} failed with status {status}")
    return text


def run(record_id, mode, token, patch_dir=PATCH_DIR):
    if mode not in ("dry-run", "apply", "discard"):
        raise PatchError("mode must be dry-run, apply or discard")
    if not token:
        raise PatchError("ZENODO_TOKEN is not set")
    path = validate_record_id(record_id, patch_dir)
    patch = load_patch(path)
    url = f"{API}/{record_id}"

    status, text = api("GET", url, token)
    if not 200 <= status < 300:
        print(text)
        raise PatchError(f"GET {url} failed with status {status}")
    current = json.loads(text)
    in_edit = current.get("state") == "inprogress"
    print(f"record {record_id}: state {current.get('state')}, open edit: {'yes' if in_edit else 'no'}")

    if mode == "discard":
        if current.get("conceptdoi") != CONCEPT_DOI:
            raise PatchError(
                f"concept DOI is {current.get('conceptdoi')!r}, expected {CONCEPT_DOI!r}"
            )
        if not in_edit:
            print("discard: the record has no open edit; no write call was made")
            return
        write_call(mode, "POST", f"{url}/actions/discard", token, required="discard")
        print(f"record {record_id}: open edit discarded")
        return

    merged = merge(current.get("metadata", {}), patch)
    check_guards(current, merged)

    metadata = current.get("metadata", {})
    print("dates: " + json.dumps(metadata.get("dates"), ensure_ascii=False))
    print("grants: " + json.dumps(metadata.get("grants"), ensure_ascii=False))
    print(f"record {record_id}: patch keys {', '.join(sorted(patch))}")
    print(metadata_diff(current.get("metadata", {}), merged) or "(no change)")
    if mode == "dry-run":
        print("dry-run: no write call was made")
        return

    if in_edit:
        print("the record already has an open edit; skipping actions/edit")
    else:
        write_call(mode, "POST", f"{url}/actions/edit", token)
    write_call(mode, "PUT", url, token, {"metadata": merged})
    write_call(mode, "POST", f"{url}/actions/publish", token)
    print(f"record {record_id}: metadata published")


def main():
    try:
        run(
            os.environ.get("RECORD_ID", ""),
            os.environ.get("MODE", "dry-run"),
            os.environ.get("ZENODO_TOKEN", ""),
        )
    except (PatchError, urllib.error.URLError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
