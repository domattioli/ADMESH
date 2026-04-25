"""Tests for ``admesh.boundary_types.BoundaryType`` (v1 public enum)."""

from __future__ import annotations

import pytest

from admesh.boundary_types import BoundaryType


def test_member_int_values():
    assert int(BoundaryType.OPEN) == 0
    assert int(BoundaryType.MAINLAND) == 1
    assert int(BoundaryType.ISLAND) == 11
    assert int(BoundaryType.MAINLAND_FLUX) == 20
    # Spec 002 — paired-edge / barrier IBTYPEs.
    assert int(BoundaryType.EXTERNAL_BARRIER) == 3
    assert int(BoundaryType.EXTERNAL_BARRIER_FLUX) == 4
    assert int(BoundaryType.INTERNAL_BARRIER_PIPE) == 13
    assert int(BoundaryType.INTERNAL_BARRIER) == 24


@pytest.mark.parametrize(
    "member, expected",
    [
        (BoundaryType.OPEN, 0),
        (BoundaryType.MAINLAND, 1),
        (BoundaryType.ISLAND, 11),
        (BoundaryType.MAINLAND_FLUX, 20),
        (BoundaryType.EXTERNAL_BARRIER, 3),
        (BoundaryType.EXTERNAL_BARRIER_FLUX, 4),
        (BoundaryType.INTERNAL_BARRIER_PIPE, 13),
        (BoundaryType.INTERNAL_BARRIER, 24),
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
    # Spec 001 + spec 002 canonical members.
    assert members == [
        BoundaryType.OPEN,
        BoundaryType.MAINLAND,
        BoundaryType.ISLAND,
        BoundaryType.MAINLAND_FLUX,
        BoundaryType.EXTERNAL_BARRIER,
        BoundaryType.EXTERNAL_BARRIER_FLUX,
        BoundaryType.INTERNAL_BARRIER_PIPE,
        BoundaryType.INTERNAL_BARRIER,
    ]
    assert len(members) == 8


def test_lookup_by_name_resolves_alias():
    assert BoundaryType["WALL"] is BoundaryType.MAINLAND
    assert BoundaryType["MAINLAND"] is BoundaryType.MAINLAND


def test_lookup_by_value():
    assert BoundaryType(0) is BoundaryType.OPEN
    assert BoundaryType(1) is BoundaryType.MAINLAND
    assert BoundaryType(11) is BoundaryType.ISLAND
    assert BoundaryType(20) is BoundaryType.MAINLAND_FLUX
    assert BoundaryType(3) is BoundaryType.EXTERNAL_BARRIER
    assert BoundaryType(4) is BoundaryType.EXTERNAL_BARRIER_FLUX
    assert BoundaryType(13) is BoundaryType.INTERNAL_BARRIER_PIPE
    assert BoundaryType(24) is BoundaryType.INTERNAL_BARRIER


def test_unmapped_code_raises_value_error():
    # IBTYPE 22 is unmapped (preserved as plain int on round-trip).
    with pytest.raises(ValueError):
        BoundaryType(22)
    # IBTYPE 99 also unmapped.
    with pytest.raises(ValueError):
        BoundaryType(99)
