"""ADCIRC v55 fort.14 reader and writer (T023).

Defined by ``specs/001-pythonize-and-fort14-integration/`` —
``contracts/python-api.md`` (signatures) and ``data-model.md`` (entity
shapes). Conversion conventions live strictly inside this module:

- 1-based fort.14 node IDs ↔ 0-based ``Mesh`` indices
- depth (positive-down) on disk ↔ elevation (positive-up) in ``Mesh``

Both conversions happen at this I/O boundary; nothing else in the
package needs to know.

The reader is a single-pass, line-oriented parser that raises
:class:`Fort14ParseError` on the first malformed token. The writer is
deterministic — given the same ``Mesh``, emits byte-identical output.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Iterator

import numpy as np

from admesh.api import BoundarySegment, Mesh
from admesh.boundary_types import BoundaryType

if TYPE_CHECKING:
    from typing import TextIO

__all__ = ["Fort14ParseError", "read_fort14", "write_fort14"]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class Fort14ParseError(ValueError):
    """Raised by :func:`read_fort14` on malformed input.

    Attributes
    ----------
    line_no : int
        1-based line number where the error was detected.
    expected : str
        Short human-readable description of what was expected.
    actual : str
        The offending line content (truncated to 120 chars).
    """

    def __init__(self, line_no: int, expected: str, actual: str) -> None:
        self.line_no = line_no
        self.expected = expected
        self.actual = (actual or "")[:120]
        super().__init__(
            f"fort.14 parse error at line {line_no}: expected {expected}; "
            f"got {self.actual!r}"
        )


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------


class _Cursor:
    """Line-by-line iterator that tracks 1-based line number for errors."""

    __slots__ = ("_lines", "_iter", "line_no")

    def __init__(self, source: "Iterator[str]") -> None:
        # Materialize so we can give meaningful EOF errors.
        self._lines = list(source)
        self._iter = iter(self._lines)
        self.line_no = 0

    def next_line(self, expected: str) -> str:
        try:
            self.line_no += 1
            return next(self._iter)
        except StopIteration:
            raise Fort14ParseError(self.line_no, expected, "<EOF>") from None

    def fail(self, expected: str, actual: str) -> "Fort14ParseError":
        return Fort14ParseError(self.line_no, expected, actual)


def _parse_int(token: str, cursor: _Cursor, expected: str) -> int:
    try:
        return int(token)
    except (TypeError, ValueError):
        raise cursor.fail(expected, token) from None


def _parse_float(token: str, cursor: _Cursor, expected: str) -> float:
    try:
        return float(token)
    except (TypeError, ValueError):
        raise cursor.fail(expected, token) from None


def _open_text(
    path: "str | os.PathLike[str] | TextIO",
) -> tuple["Iterator[str]", "object | None"]:
    """Return a line iterator and a handle to close (or None for buffers)."""
    if hasattr(path, "read"):
        text = path.read()
        if isinstance(text, bytes):
            text = text.decode("utf-8")
        return iter(text.splitlines()), None
    fh = open(os.fspath(path), encoding="utf-8")
    return (line.rstrip("\n") for line in fh), fh


def read_fort14(path: "str | os.PathLike[str] | TextIO") -> Mesh:
    """Parse an ADCIRC v55 fort.14 file into a :class:`Mesh`.

    Applies 1-based → 0-based index conversion and depth → elevation sign
    flip. Unmapped IBTYPE codes are preserved as plain ``int`` values in
    :attr:`BoundarySegment.bc_type`.

    Raises
    ------
    Fort14ParseError
        On malformed input. The exception carries ``line_no``,
        ``expected``, and ``actual``.
    """
    lines, handle = _open_text(path)
    try:
        cursor = _Cursor(lines)
        title = cursor.next_line("AGRID title line").strip()

        header = cursor.next_line("'NE NN' counts line").split()
        if len(header) < 2:
            raise cursor.fail("two integers (NE NN)", " ".join(header))
        n_elements = _parse_int(header[0], cursor, "integer NE")
        n_nodes = _parse_int(header[1], cursor, "integer NN")
        if n_elements < 0 or n_nodes < 0:
            raise cursor.fail(
                "non-negative element/node counts", " ".join(header)
            )

        # Node block: NN lines of "id x y depth"
        nodes = np.empty((n_nodes, 2), dtype=np.float64)
        bathymetry = np.empty(n_nodes, dtype=np.float64)
        for i in range(n_nodes):
            line = cursor.next_line(f"node {i + 1} of {n_nodes}")
            tokens = line.split()
            if len(tokens) < 4:
                raise cursor.fail(
                    "node line 'id x y depth' (4 tokens)", line
                )
            node_id = _parse_int(tokens[0], cursor, "integer node id")
            if node_id != i + 1:
                raise cursor.fail(
                    f"monotonic 1-based node id {i + 1}", tokens[0]
                )
            nodes[i, 0] = _parse_float(tokens[1], cursor, "float x")
            nodes[i, 1] = _parse_float(tokens[2], cursor, "float y")
            # ADCIRC stores depth (positive-down); convert to elevation.
            bathymetry[i] = -_parse_float(tokens[3], cursor, "float depth")

        # Element block: NE lines of "id 3 n1 n2 n3" — 1-based.
        elements = np.empty((n_elements, 3), dtype=np.int64)
        for i in range(n_elements):
            line = cursor.next_line(f"element {i + 1} of {n_elements}")
            tokens = line.split()
            if len(tokens) < 5:
                raise cursor.fail(
                    "element line 'id 3 n1 n2 n3' (5 tokens)", line
                )
            elem_id = _parse_int(tokens[0], cursor, "integer element id")
            if elem_id != i + 1:
                raise cursor.fail(
                    f"monotonic 1-based element id {i + 1}", tokens[0]
                )
            nodes_per_elem = _parse_int(
                tokens[1], cursor, "integer node-count = 3"
            )
            if nodes_per_elem != 3:
                raise cursor.fail(
                    "node-count = 3 (triangle)", tokens[1]
                )
            for j in range(3):
                one_based = _parse_int(
                    tokens[2 + j], cursor, f"integer vertex {j + 1}"
                )
                if not (1 <= one_based <= n_nodes):
                    raise cursor.fail(
                        f"vertex id in [1, {n_nodes}]", tokens[2 + j]
                    )
                elements[i, j] = one_based - 1  # → 0-based

        # Open boundary block.
        n_open_segs_line = cursor.next_line("'NOPE' open-segment count")
        n_open_segs = _parse_int(
            n_open_segs_line.split()[0] if n_open_segs_line.strip() else "",
            cursor,
            "integer NOPE",
        )
        # Total open boundary nodes (informational; we don't validate).
        cursor.next_line("'NETA' total open-boundary node count")

        boundaries: list[BoundarySegment] = []
        for _ in range(n_open_segs):
            seg_line = cursor.next_line("open-segment 'NVDLL [IBTYPE]' line")
            seg_tokens = seg_line.split()
            if not seg_tokens:
                raise cursor.fail(
                    "open-segment node-count line", seg_line
                )
            n_seg_nodes = _parse_int(
                seg_tokens[0], cursor, "integer open-segment node count"
            )
            # IBTYPE optional in open-segment header — defaults to 0 (OPEN).
            bc_code = (
                _parse_int(seg_tokens[1], cursor, "integer IBTYPE")
                if len(seg_tokens) >= 2
                else 0
            )
            ids = np.empty(n_seg_nodes, dtype=np.int64)
            for j in range(n_seg_nodes):
                tok = cursor.next_line(
                    f"open-segment node {j + 1} of {n_seg_nodes}"
                ).split()
                if not tok:
                    raise cursor.fail("open-segment node id", "")
                one_based = _parse_int(
                    tok[0], cursor, "integer node id"
                )
                if not (1 <= one_based <= n_nodes):
                    raise cursor.fail(
                        f"node id in [1, {n_nodes}]", tok[0]
                    )
                ids[j] = one_based - 1
            boundaries.append(
                BoundarySegment(
                    node_ids=ids,
                    bc_type=_coerce_bc(bc_code),
                    is_open=True,
                )
            )

        # Land boundary block.
        n_land_segs_line = cursor.next_line("'NBOU' land-segment count")
        n_land_segs = _parse_int(
            n_land_segs_line.split()[0] if n_land_segs_line.strip() else "",
            cursor,
            "integer NBOU",
        )
        cursor.next_line("'NVEL' total land-boundary node count")

        for _ in range(n_land_segs):
            seg_line = cursor.next_line("land-segment 'NVELL IBTYPE' line")
            seg_tokens = seg_line.split()
            if len(seg_tokens) < 2:
                raise cursor.fail(
                    "land-segment 'NVELL IBTYPE' (2 ints)", seg_line
                )
            n_seg_nodes = _parse_int(
                seg_tokens[0], cursor, "integer land-segment node count"
            )
            bc_code = _parse_int(seg_tokens[1], cursor, "integer IBTYPE")
            ids = np.empty(n_seg_nodes, dtype=np.int64)
            for j in range(n_seg_nodes):
                tok = cursor.next_line(
                    f"land-segment node {j + 1} of {n_seg_nodes}"
                ).split()
                if not tok:
                    raise cursor.fail("land-segment node id", "")
                one_based = _parse_int(
                    tok[0], cursor, "integer node id"
                )
                if not (1 <= one_based <= n_nodes):
                    raise cursor.fail(
                        f"node id in [1, {n_nodes}]", tok[0]
                    )
                ids[j] = one_based - 1
            boundaries.append(
                BoundarySegment(
                    node_ids=ids,
                    bc_type=_coerce_bc(bc_code),
                    is_open=False,
                )
            )

        # Bathymetry: only return when at least one node carries non-zero
        # depth — pure-zero columns are common in synthetic test meshes
        # and we don't want to round-trip a meaningless column.
        bathy_out = bathymetry if np.any(bathymetry != 0.0) else None

        return Mesh(
            nodes=nodes,
            elements=elements,
            boundaries=tuple(boundaries),
            bathymetry=bathy_out,
            quality=None,
            title=title,
        )
    finally:
        if handle is not None:
            handle.close()


def _coerce_bc(code: int) -> "BoundaryType | int":
    """Return :class:`BoundaryType` if mapped, else the raw int."""
    try:
        return BoundaryType(code)
    except ValueError:
        return int(code)


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def write_fort14(
    mesh: Mesh,
    path: "str | os.PathLike[str] | TextIO",
    *,
    precision: int = 6,
) -> None:
    """Serialize ``mesh`` to ADCIRC v55 fort.14 format.

    Applies 0-based → 1-based index conversion and elevation → depth sign
    flip. Coordinates are emitted with ``precision`` decimal places.
    """
    if precision < 1:
        raise ValueError(f"precision must be ≥ 1, got {precision}")

    open_segs = [s for s in mesh.boundaries if s.is_open]
    land_segs = [s for s in mesh.boundaries if not s.is_open]
    bathy = (
        mesh.bathymetry
        if mesh.bathymetry is not None
        else np.zeros(mesh.n_nodes, dtype=np.float64)
    )

    coord_fmt = f"{{:d}} {{:.{precision}f}} {{:.{precision}f}} {{:.{precision}f}}"
    # Open-mode writer
    if hasattr(path, "write"):
        out = path
        close = False
    else:
        out = open(os.fspath(path), "w", encoding="utf-8")
        close = True

    try:
        out.write(f"{mesh.title}\n")
        out.write(f"{mesh.n_elements} {mesh.n_nodes}\n")
        for i in range(mesh.n_nodes):
            out.write(
                coord_fmt.format(
                    i + 1,
                    float(mesh.nodes[i, 0]),
                    float(mesh.nodes[i, 1]),
                    -float(bathy[i]),  # elevation → depth
                )
                + "\n"
            )
        for i in range(mesh.n_elements):
            n0, n1, n2 = mesh.elements[i]
            out.write(
                f"{i + 1} 3 {int(n0) + 1} {int(n1) + 1} {int(n2) + 1}\n"
            )

        n_open_nodes = sum(int(s.node_ids.size) for s in open_segs)
        out.write(f"{len(open_segs)}\n")
        out.write(f"{n_open_nodes}\n")
        for seg in open_segs:
            bc_code = int(seg.bc_type)
            out.write(f"{seg.node_ids.size} {bc_code}\n")
            for nid in seg.node_ids:
                out.write(f"{int(nid) + 1}\n")

        n_land_nodes = sum(int(s.node_ids.size) for s in land_segs)
        out.write(f"{len(land_segs)}\n")
        out.write(f"{n_land_nodes}\n")
        for seg in land_segs:
            bc_code = int(seg.bc_type)
            out.write(f"{seg.node_ids.size} {bc_code}\n")
            for nid in seg.node_ids:
                out.write(f"{int(nid) + 1}\n")
    finally:
        if close:
            out.close()
