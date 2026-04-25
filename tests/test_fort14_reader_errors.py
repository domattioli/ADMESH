"""Reader-error tests across the malformed fixture corpus (T015).

Each fixture in ``tests/fixtures/fort14/malformed/`` violates exactly
one rule. ``read_fort14`` must raise :class:`Fort14ParseError` with
``line_no``, ``expected``, and ``actual`` populated.
"""

from __future__ import annotations

import pathlib

import pytest

from admesh import Fort14ParseError, read_fort14


_MALFORMED_DIR = (
    pathlib.Path(__file__).parent / "fixtures" / "fort14" / "malformed"
)
_FIXTURES = sorted(
    p for p in _MALFORMED_DIR.glob("*.14") if not p.name.startswith("_")
)


def test_at_least_ten_malformed_fixtures():
    assert len(_FIXTURES) >= 10, (
        f"expected ≥10 malformed fixtures, found {len(_FIXTURES)}: "
        f"{[p.name for p in _FIXTURES]}"
    )


@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda p: p.name)
def test_malformed_fort14_raises_parse_error(fixture: pathlib.Path):
    with pytest.raises(Fort14ParseError) as exc_info:
        read_fort14(fixture)
    err = exc_info.value
    assert err.line_no >= 1, f"{fixture.name}: line_no not populated"
    assert err.expected, f"{fixture.name}: expected not populated"
    # `actual` may be empty for EOF errors — but the attribute must exist.
    assert hasattr(err, "actual")
