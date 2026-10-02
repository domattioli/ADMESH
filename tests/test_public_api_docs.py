"""Every public name in ``admesh.__all__`` is documented.

A name counts as documented when it appears as a whole word in ``README.md``
or in a page under ``docs/api/``. This keeps the README API table, the API
reference pages and ``__all__`` from drifting apart.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import admesh

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
API_DIR = REPO_ROOT / "docs" / "api"


def _expand_braces(text: str) -> str:
    """Expand ``prefix_{a,b}`` shorthand so ``load_domain_from_{toml,json}`` counts."""

    def repl(m: re.Match[str]) -> str:
        prefix, options = m.group(1), m.group(2).split(",")
        return " ".join(prefix + opt.strip() for opt in options)

    return re.sub(r"(\w+)\{([\w,\s]+)\}", repl, text)


def _doc_text() -> str:
    if not README.is_file() or not API_DIR.is_dir():
        pytest.skip("README.md or docs/api not present (installed-package run)")
    parts = [README.read_text(encoding="utf-8")]
    parts += [p.read_text(encoding="utf-8") for p in sorted(API_DIR.glob("*.md"))]
    return _expand_braces("\n".join(parts))


@pytest.mark.parametrize("name", sorted(admesh.__all__))
def test_public_name_is_documented(name: str) -> None:
    text = _doc_text()
    assert re.search(rf"(?<![\w.]){re.escape(name)}(?!\w)", text), (
        f"admesh.{name} is in __all__ but not in README.md or docs/api/*.md"
    )


def test_every_public_name_has_an_api_page_entry() -> None:
    if not API_DIR.is_dir():
        pytest.skip("docs/api not present (installed-package run)")
    api_text = "\n".join(p.read_text(encoding="utf-8") for p in API_DIR.glob("*.md"))
    documented = set(re.findall(r"^::: admesh\.(\w+)\s*$", api_text, flags=re.M))
    missing = sorted(set(admesh.__all__) - documented)
    extra = sorted(documented - set(admesh.__all__))
    assert not missing, f"__all__ names without a '::: admesh.<name>' entry in docs/api: {missing}"
    assert not extra, f"docs/api documents names not in __all__: {extra}"


def test_all_names_resolve() -> None:
    missing = [n for n in admesh.__all__ if not hasattr(admesh, n)]
    assert not missing, f"__all__ names not defined on admesh: {missing}"
