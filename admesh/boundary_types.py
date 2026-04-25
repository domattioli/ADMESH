"""Public boundary-type enum for the v1 Pythonic API surface.

Defined in ``specs/001-pythonize-and-fort14-integration/data-model.md``
under FR-022. The enum values are the ADCIRC ``IBTYPE`` codes for the
v1-supported set; numeric round-trip preserves any other code via
``BoundarySegment.bc_type: BoundaryType | int``.

This module is **strictly additive** to the faithful-port surface. The
existing ``admesh.boundary.BoundaryType`` (``OPEN`` / ``WALL``) lives in
the faithful-port module and is untouched. The two enums share integer
values (``OPEN == 0``, ``WALL == 1``), so callers can compare across
them when they need to.
"""

from __future__ import annotations

from enum import IntEnum

__all__ = ["BoundaryType"]


class BoundaryType(IntEnum):
    """v1 ADCIRC boundary-condition codes recognized by ``admesh.fort14``.

    ``IntEnum`` so each member compares equal to its ADCIRC numeric
    code: ``BoundaryType.OPEN == 0`` is ``True``. The fort.14 writer can
    emit codes via ``int(bc)`` without a side table.

    Members
    -------
    OPEN
        ADCIRC code 0 — open ocean / external water.
    MAINLAND
        ADCIRC code 1 — mainland boundary, no normal flux.
    ISLAND
        ADCIRC code 11 — island boundary.
    MAINLAND_FLUX
        ADCIRC code 20 — mainland with normal-flux specified.
    WALL
        Alias for ``MAINLAND`` (same int value). Retained because the
        faithful-port surface uses the name ``WALL`` for ADCIRC code 1.

    Notes
    -----
    Codes outside this set are preserved on round-trip as plain
    ``int`` values in ``BoundarySegment.bc_type``. Use
    ``isinstance(bc, BoundaryType)`` to discriminate the named-vs-numeric
    case.
    """

    OPEN = 0
    MAINLAND = 1
    ISLAND = 11
    MAINLAND_FLUX = 20
    WALL = 1
