#!/usr/bin/env python3
"""Build the browser app and the documentation into ``web_dist/``.

Output layout (served by Cloudflare Pages)::

    web_dist/
        index.html, app.js, worker.js, _redirects   copied from web/
        wheels/<pure wheel>, wheels/manifest.json   pure py3-none-any wheel
        docs/                                       mkdocs site

The wheel is built with ``ADMESH_NO_CPP=1`` so it carries no compiled
extension and installs in Pyodide. The script exits non-zero when the wheel
is not tagged ``py3-none-any`` or when ``web/_redirects`` misses a page that
is listed in the ``mkdocs.yml`` navigation.

Usage
-----
    python scripts/build_web.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DIST = ROOT / "web_dist"
DOCS_SITE_URL = "https://admesh.domattioli.com/docs/"


def _run(cmd: list[str], env: dict[str, str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)


def build_wheel() -> Path:
    wheels = DIST / "wheels"
    wheels.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, ADMESH_NO_CPP="1")
    cmd = [sys.executable, "-m", "build", "--wheel", "--outdir", str(wheels)]
    _run(cmd, env)
    found = sorted(wheels.glob("*.whl"))
    if len(found) != 1:
        raise SystemExit(f"expected exactly one wheel in {wheels}, found {len(found)}")
    wheel = found[0]
    if not wheel.name.endswith("-py3-none-any.whl"):
        raise SystemExit(f"wheel is not py3-none-any: {wheel.name}")
    return wheel


def write_manifest(wheel: Path) -> None:
    parts = wheel.name[: -len(".whl")].split("-")
    manifest = {"wheel": wheel.name, "version": parts[1]}
    (wheel.parent / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def nav_urls(nav: list) -> list[str]:
    """Return the site-relative URL of every local page in a mkdocs nav."""
    urls: list[str] = []
    for item in nav:
        value = next(iter(item.values())) if isinstance(item, dict) else item
        if isinstance(value, list):
            urls.extend(nav_urls(value))
        elif isinstance(value, str) and not re.match(r"^[a-z]+://", value):
            if value.endswith(".md"):
                page = value[: -len(".md")]
                if page.endswith("index"):
                    page = page[: -len("index")]
                urls.append("/" + page.rstrip("/") + "/" if page.strip("/") else "/")
            else:
                directory = value.rsplit("/", 1)[0] if "/" in value else ""
                urls.append("/" + directory + "/" if directory else "/")
    return urls


def check_redirects() -> None:
    config = yaml.safe_load((ROOT / "mkdocs.yml").read_text())
    wanted = [u for u in nav_urls(config["nav"]) if u != "/"]
    text = (WEB / "_redirects").read_text()
    missing = [u for u in wanted if f"{u.rstrip('/')} " not in text]
    if missing:
        raise SystemExit(f"web/_redirects misses nav pages: {missing}")


def build_docs() -> None:
    tmp = ROOT / "mkdocs.web.tmp.yml"
    tmp.write_text(f"INHERIT: mkdocs.yml\nsite_url: {DOCS_SITE_URL}\n")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(ROOT / "src"), env.get("PYTHONPATH")]))
    try:
        _run(
            [sys.executable, "-m", "mkdocs", "build", "-f", str(tmp), "-d", str(DIST / "docs")],
            env,
        )
    finally:
        tmp.unlink(missing_ok=True)


def main() -> None:
    check_redirects()
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copytree(WEB, DIST, dirs_exist_ok=True)
    wheel = build_wheel()
    write_manifest(wheel)
    build_docs()
    print(f"built {DIST} with {wheel.name}")


if __name__ == "__main__":
    main()
