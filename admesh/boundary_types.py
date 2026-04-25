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
    EXTERNAL_BARRIER
        ADCIRC code 3 — external weir / barrier with crest elevation
        and sub/super-critical weir coefficients (single-node record;
        spec 002).
    EXTERNAL_BARRIER_FLUX
        ADCIRC code 4 — external paired-edge barrier with crest +
        coefficients (paired-node record; spec 002).
    INTERNAL_BARRIER_PIPE
        ADCIRC code 13 — internal barrier with pipe / culvert
        coefficients (single-node record; spec 002).
    INTERNAL_BARRIER
        ADCIRC code 24 — internal barrier with paired-node + crest +
        super-critical flow coefficients (paired-node record; spec 002).

    Notes
    -----
    Codes outside this set are preserved on round-trip as plain
    ``int`` values in ``BoundarySegment.bc_type``. Use
    ``isinstance(bc, BoundaryType)`` to discriminate the named-vs-numeric
    case. Paired-edge / barrier records carry extra columns in
    :attr:`BoundarySegment.barrier_data` and
    :attr:`BoundarySegment.paired_node_ids` per
    ``specs/002-size-field-defaults/contracts/fort14-paired-edge.md``.
    """

    OPEN = 0
    MAINLAND = 1
    ISLAND = 11
    MAINLAND_FLUX = 20
    WALL = 1
    # Spec 002 — paired-edge / barrier IBTYPEs.
    EXTERNAL_BARRIER = 3
    EXTERNAL_BARRIER_FLUX = 4
    INTERNAL_BARRIER_PIPE = 13
    INTERNAL_BARRIER = 24
