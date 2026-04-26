"""Tests for ``admesh.boundary_types.BoundaryType`` (v1 public enum)."""

from __future__ import annotations

import pytest

from admesh.boundary_types import BoundaryType


def test_member_int_values():
    assert int(BoundaryType.OPEN) == 0
    assert int(BoundaryType.MAINLAND) == 1
    assert int(BoundaryType.ISLAND) == 11
    assert int(BoundaryType.MAINLAND_FLUX) == 20


@pytest.mark.parametrize(
    "member, expected",
    [
        (BoundaryType.OPEN, 0),
        (BoundaryType.MAINLAND, 1),
        (BoundaryType.ISLAND, 11),
        (BoundaryType.MAINLAND_FLUX, 20),
    ],
)
def test_intenum_compares_equal_to_code(member, expected):
    assert member == expected


def test_wall_is_alias_for_mainland():
    assert BoundaryType.WALL is BoundaryType.MAINLAND
    assert BoundaryType.WALL == BoundaryType.MAINLAND
    assert int(BoundaryType.WALL) == 1


def test_iter_yields_canonical_members_only():
    members = list(BoundaryType)
    assert members == [
        BoundaryType.OPEN,
        BoundaryType.MAINLAND,
        BoundaryType.ISLAND,
        BoundaryType.MAINLAND_FLUX,
    ]
    assert len(members) == 4


def test_lookup_by_name_resolves_alias():
    assert BoundaryType["WALL"] is BoundaryType.MAINLAND
    assert BoundaryType["MAINLAND"] is BoundaryType.MAINLAND


def test_lookup_by_value():
    assert BoundaryType(0) is BoundaryType.OPEN
    assert BoundaryType(1) is BoundaryType.MAINLAND
    assert BoundaryType(11) is BoundaryType.ISLAND
    assert BoundaryType(20) is BoundaryType.MAINLAND_FLUX


def test_unmapped_code_raises_value_error():
    with pytest.raises(ValueError):
        BoundaryType(22)
