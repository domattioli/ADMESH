"""Docstring completeness gate for the public surface.

Asserts every callable in `admesh.__all__` has a docstring containing
the NumPy-style sections this project commits to: a short summary plus
either `Parameters`/`Returns` (functions) or attribute documentation
(classes / dataclasses). At least one runnable `Examples` block is
recommended but not strictly required for very small wrappers.

Per spec 009 R3 (FR-025). The Parameters/Returns gate was a soft
warning (skip) through the 0.1.0 tag; the public-surface backlog
reached zero past the planned 0.2.0 tightening, so the gate is now a
hard assertion (current version 0.5.x).
"""

from __future__ import annotations

import inspect

import pytest

import admesh


# Symbols that are intentionally trivial / re-exports without their own docs.
_DOCSTRING_EXEMPT: set[str] = {
    # SizeFieldFn is a Callable type alias; the alias itself has no docstring.
    "SizeFieldFn",
}


def _is_documentable(obj: object) -> bool:
    """Functions, classes, and methods get docstring checks; type aliases skip."""
    return inspect.isfunction(obj) or inspect.isclass(obj) or inspect.ismethod(obj)


@pytest.fixture(scope="module")
def public_symbols() -> dict[str, object]:
    """Resolve every name in `admesh.__all__` to its object."""
    return {name: getattr(admesh, name) for name in admesh.__all__}


def test_all_public_symbols_resolve(public_symbols: dict[str, object]) -> None:
    """Every name listed in `__all__` exists on the admesh namespace."""
    missing = [
        name for name, obj in public_symbols.items() if obj is None
    ]
    assert not missing, f"admesh.__all__ contains unresolvable names: {missing}"


def test_documentable_symbols_have_docstrings(
    public_symbols: dict[str, object],
) -> None:
    """Every documentable public symbol has a non-empty docstring."""
    undocumented: list[str] = []
    for name, obj in public_symbols.items():
        if name in _DOCSTRING_EXEMPT:
            continue
        if not _is_documentable(obj):
            continue
        doc = inspect.getdoc(obj)
        if not doc or not doc.strip():
            undocumented.append(name)
    assert not undocumented, (
        f"public symbols missing docstrings: {undocumented} — "
        f"add NumPy-style docstrings per spec 009 FR-025"
    )


def test_callable_docstrings_have_parameters_or_returns(
    public_symbols: dict[str, object],
) -> None:
    """Functions and methods reference `Parameters`, `Returns`, or `Yields`.

    Bare summaries are accepted for nullary callables and trivial property-style
    methods. The gate fires when the callable takes arguments and the docstring
    lacks any of the NumPy sectional headers that mkdocstrings renders.
    """
    weak: list[str] = []
    for name, obj in public_symbols.items():
        if name in _DOCSTRING_EXEMPT:
            continue
        if not inspect.isfunction(obj):
            # Classes are covered by test_documentable_symbols_have_docstrings.
            continue
        sig = inspect.signature(obj)
        takes_args = any(
            p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
            for p in sig.parameters.values()
        )
        if not takes_args:
            continue
        doc = inspect.getdoc(obj) or ""
        if not any(
            section in doc
            for section in ("Parameters", "Returns", "Yields", "Raises")
        ):
            weak.append(name)
    # Hard gate: every public callable taking arguments must reference a
    # NumPy sectional header. The backlog reached zero past the 0.2.0 tag,
    # so the former soft-skip is now an assertion — this guards against a
    # silent regression when a new public callable is added without sections.
    assert not weak, (
        f"{len(weak)} public callables lack Parameters/Returns sections: {weak}. "
        f"Add NumPy-style Parameters/Returns/Yields/Raises per spec 009 FR-025."
    )
