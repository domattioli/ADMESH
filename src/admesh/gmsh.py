"""Gmsh ``.msh`` (ASCII v2.2) reader and writer.

Sibling format to :mod:`admesh.fort14` (issue #5). Gmsh and ADCIRC share
the same node + triangle-element model; Gmsh *physical groups* play the
role fort.14's IBTYPE codes play for boundary labelling.

Conventions, confined to this I/O boundary:

- 1-based Gmsh node IDs ↔ 0-based :class:`~admesh.api.Mesh` indices.
- Node ``z`` carries :class:`~admesh.api.Mesh` bathymetry (elevation,
  positive-up); a mesh with no bathymetry writes ``z = 0`` and reads
  back ``bathymetry=None``.
- Each boundary segment becomes its own dim-1 physical group named
  ``<label>_<segindex>`` so order and per-segment identity round-trip.
  ``<label>`` maps to a :class:`~admesh.boundary_types.BoundaryType`
  via :data:`LABEL_TO_BC` (``open`` ↔ OPEN, ``mainland`` ↔ MAINLAND,
  ``island`` ↔ ISLAND, ``mainland_flux`` ↔ MAINLAND_FLUX). Unmapped
  ADCIRC codes round-trip as a plain ``int`` via the ``bc<code>`` name,
  mirroring fort.14's unmapped-code handling. ``is_open`` is ``True``
  only for OPEN segments.
- Triangles are emitted under a single dim-2 physical group ``domain``.

Only ASCII format 2.2 is supported; the reader raises
:class:`GmshParseError` on a binary or v4 header rather than guessing.
The writer is deterministic — identical ``Mesh`` in, byte-identical
output.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Iterator

import numpy as np

from admesh.api import BoundarySegment, Mesh
from admesh.boundary_types import BoundaryType

if TYPE_CHECKING:
    from typing import TextIO

__all__ = ["GmshParseError", "read_msh", "write_msh", "LABEL_TO_BC"]

# Gmsh element type codes (ASCII v2.2 spec, §9.1): 2-node line, 3-node triangle.
_GMSH_LINE = 1
_GMSH_TRI = 2

# label ↔ BoundaryType. is_open is True only for OPEN.
LABEL_TO_BC: dict[str, BoundaryType] = {
    "open": BoundaryType.OPEN,
    "mainland": BoundaryType.MAINLAND,
    "island": BoundaryType.ISLAND,
    "mainland_flux": BoundaryType.MAINLAND_FLUX,
}
_BC_TO_LABEL: dict[int, str] = {
    int(BoundaryType.OPEN): "open",
    int(BoundaryType.MAINLAND): "mainland",
    int(BoundaryType.ISLAND): "island",
    int(BoundaryType.MAINLAND_FLUX): "mainland_flux",
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class GmshParseError(ValueError):
    """Raised by :func:`read_msh` on malformed or unsupported input.

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
            f".msh parse error at line {line_no}: expected {expected}; "
            f"got {self.actual!r}"
        )


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------


class _Cursor:
    """Line iterator tracking a 1-based line number for error messages."""

    __slots__ = ("_iter", "line_no")

    def __init__(self, source: "Iterator[str]") -> None:
        self._iter = iter(list(source))
        self.line_no = 0

    def next_line(self, expected: str) -> str:
        try:
            self.line_no += 1
            return next(self._iter)
        except StopIteration:
            raise GmshParseError(self.line_no, expected, "<EOF>") from None

    def fail(self, expected: str, actual: str) -> "GmshParseError":
        return GmshParseError(self.line_no, expected, actual)


def _open_text(
    path: "str | os.PathLike[str] | TextIO",
) -> tuple["Iterator[str]", "object | None"]:
    if hasattr(path, "read"):
        text = path.read()
        if isinstance(text, bytes):
            text = text.decode("utf-8")
        return iter(text.splitlines()), None
    fh = open(os.fspath(path), encoding="utf-8")
    return (line.rstrip("\n") for line in fh), fh


def _label_to_bc(label: str) -> tuple["BoundaryType | int", bool]:
    """Map a physical-group base label to (bc_type, is_open)."""
    if label in LABEL_TO_BC:
        bc = LABEL_TO_BC[label]
        return bc, bc is BoundaryType.OPEN
    if label.startswith("bc"):
        try:
            return int(label[2:]), False
        except ValueError:
            pass
    raise ValueError(f"unrecognized boundary physical-group label: {label!r}")


def read_msh(path: "str | os.PathLike[str] | TextIO") -> Mesh:
    """Read a Gmsh ASCII v2.2 ``.msh`` file into a :class:`Mesh`.

    Triangles become ``Mesh.elements`` (0-based); dim-1 physical groups
    become ordered :class:`BoundarySegment` records; node ``z`` becomes
    ``bathymetry`` when any value is non-zero.
    """
    lines, handle = _open_text(path)
    cursor = _Cursor(lines)
    try:
        names: dict[int, str] = {}
        coords: dict[int, tuple[float, float, float]] = {}
        tris: list[tuple[int, int, int]] = []
        # physical tag -> ordered list of (a, b) 0-based line endpoints
        lines_by_tag: dict[int, list[tuple[int, int]]] = {}
        saw_nodes = False

        while True:
            try:
                line = cursor.next_line("$EndElements")
            except GmshParseError:
                break
            line = line.strip()
            if not line:
                continue
            if line == "$MeshFormat":
                hdr = cursor.next_line("version_number file_type data_size").split()
                if not hdr or not hdr[0].startswith("2"):
                    raise cursor.fail("ASCII format 2.x header", " ".join(hdr))
                if len(hdr) >= 2 and hdr[1] != "0":
                    raise cursor.fail("ASCII file_type 0 (binary unsupported)", hdr[1])
                _expect_end(cursor, "$EndMeshFormat")
            elif line == "$PhysicalNames":
                n = _parse_int(cursor.next_line("physical-name count"), cursor)
                for _ in range(n):
                    parts = cursor.next_line("dim tag \"name\"").split(maxsplit=2)
                    if len(parts) < 3:
                        raise cursor.fail("dim tag \"name\"", " ".join(parts))
                    tag = _parse_int(parts[1], cursor)
                    names[tag] = parts[2].strip().strip('"')
                _expect_end(cursor, "$EndPhysicalNames")
            elif line == "$Nodes":
                saw_nodes = True
                n = _parse_int(cursor.next_line("node count"), cursor)
                for _ in range(n):
                    p = cursor.next_line("id x y z").split()
                    if len(p) < 4:
                        raise cursor.fail("id x y z", " ".join(p))
                    nid = _parse_int(p[0], cursor)
                    coords[nid] = (
                        _parse_float(p[1], cursor),
                        _parse_float(p[2], cursor),
                        _parse_float(p[3], cursor),
                    )
                _expect_end(cursor, "$EndNodes")
            elif line == "$Elements":
                n = _parse_int(cursor.next_line("element count"), cursor)
                for _ in range(n):
                    p = cursor.next_line("id type n_tags ...").split()
                    if len(p) < 3:
                        raise cursor.fail("id type n_tags ...", " ".join(p))
                    etype = _parse_int(p[1], cursor)
                    n_tags = _parse_int(p[2], cursor)
                    tags = [_parse_int(t, cursor) for t in p[3 : 3 + n_tags]]
                    conn = [_parse_int(t, cursor) for t in p[3 + n_tags :]]
                    if etype == _GMSH_TRI:
                        if len(conn) != 3:
                            raise cursor.fail("3 triangle node ids", " ".join(p))
                        tris.append((conn[0], conn[1], conn[2]))
                    elif etype == _GMSH_LINE:
                        if len(conn) != 2:
                            raise cursor.fail("2 line node ids", " ".join(p))
                        phys = tags[0] if tags else 0
                        lines_by_tag.setdefault(phys, []).append((conn[0], conn[1]))
                    # Other element types (points, quads, …) ignored for MVP.
                _expect_end(cursor, "$EndElements")
            # Unknown sections are skipped silently (Gmsh forward-compat).

        if not saw_nodes:
            raise cursor.fail("a $Nodes section", "<none>")

        return _assemble_mesh(coords, tris, lines_by_tag, names, cursor)
    finally:
        if handle is not None and hasattr(handle, "close"):
            handle.close()


def _assemble_mesh(coords, tris, lines_by_tag, names, cursor) -> Mesh:
    # Remap 1-based (possibly sparse) Gmsh node ids to dense 0-based.
    ordered_ids = sorted(coords)
    remap = {gid: i for i, gid in enumerate(ordered_ids)}
    nodes = np.array([coords[g][:2] for g in ordered_ids], dtype=np.float64)
    z = np.array([coords[g][2] for g in ordered_ids], dtype=np.float64)

    elements = (
        np.array([[remap[a], remap[b], remap[c]] for a, b, c in tris], dtype=np.int64)
        if tris
        else np.empty((0, 3), dtype=np.int64)
    )

    boundaries: list[BoundarySegment] = []
    # Reconstruct each dim-1 group in physical-tag order; chain its lines.
    for tag in sorted(lines_by_tag):
        name = names.get(tag, f"bc{tag}")
        base = name.rsplit("_", 1)[0] if name.rsplit("_", 1)[-1].isdigit() else name
        try:
            bc_type, is_open = _label_to_bc(base)
        except ValueError:
            # Foreign / unrecognized label: preserve the physical tag as a
            # plain int code (mirrors fort.14's unmapped-IBTYPE handling).
            bc_type, is_open = tag, False
        seg_lines = lines_by_tag[tag]
        chain = [remap[seg_lines[0][0]]]
        for a, b in seg_lines:
            chain.append(remap[b])
        boundaries.append(
            BoundarySegment(
                node_ids=np.array(chain, dtype=np.int64),
                bc_type=bc_type,
                is_open=is_open,
            )
        )

    bathymetry = z if np.any(z != 0.0) else None
    return Mesh(
        nodes=nodes,
        elements=elements,
        boundaries=tuple(boundaries),
        bathymetry=bathymetry,
    )


def _expect_end(cursor: _Cursor, marker: str) -> None:
    got = cursor.next_line(marker).strip()
    if got != marker:
        raise cursor.fail(marker, got)


def _parse_int(token: str, cursor: _Cursor) -> int:
    try:
        return int(token.split()[0]) if token.strip() else int(token)
    except (TypeError, ValueError, IndexError):
        raise cursor.fail("an integer", token) from None


def _parse_float(token: str, cursor: _Cursor) -> float:
    try:
        return float(token)
    except (TypeError, ValueError):
        raise cursor.fail("a float", token) from None


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def write_msh(
    mesh: Mesh,
    path: "str | os.PathLike[str] | TextIO",
    *,
    precision: int = 6,
) -> None:
    """Serialize ``mesh`` to Gmsh ASCII v2.2.

    Emits a dim-2 ``domain`` physical group for the triangles and one
    dim-1 group per boundary segment (``<label>_<index>``). Node ``z``
    carries bathymetry/elevation (``0`` when unset).
    """
    if precision < 1:
        raise ValueError(f"precision must be ≥ 1, got {precision}")

    bathy = (
        mesh.bathymetry
        if mesh.bathymetry is not None
        else np.zeros(mesh.n_nodes, dtype=np.float64)
    )

    # Allocate physical tags: 1 = domain surface, 2.. = boundary segments.
    phys: list[tuple[int, int, str]] = [(2, 1, "domain")]  # (dim, tag, name)
    seg_tags: list[int] = []
    label_counts: dict[str, int] = {}
    for seg in mesh.boundaries:
        code = int(seg.bc_type)
        label = _BC_TO_LABEL.get(code, f"bc{code}")
        idx = label_counts.get(label, 0)
        label_counts[label] = idx + 1
        tag = len(phys) + 1
        phys.append((1, tag, f"{label}_{idx}"))
        seg_tags.append(tag)

    coord_fmt = f"{{:d}} {{:.{precision}f}} {{:.{precision}f}} {{:.{precision}f}}"

    if hasattr(path, "write"):
        out, close = path, False
    else:
        out, close = open(os.fspath(path), "w", encoding="utf-8"), True

    try:
        out.write("$MeshFormat\n2.2 0 8\n$EndMeshFormat\n")

        out.write("$PhysicalNames\n")
        out.write(f"{len(phys)}\n")
        for dim, tag, name in phys:
            out.write(f'{dim} {tag} "{name}"\n')
        out.write("$EndPhysicalNames\n")

        out.write("$Nodes\n")
        out.write(f"{mesh.n_nodes}\n")
        for i in range(mesh.n_nodes):
            out.write(
                coord_fmt.format(
                    i + 1,
                    float(mesh.nodes[i, 0]),
                    float(mesh.nodes[i, 1]),
                    float(bathy[i]),
                )
                + "\n"
            )
        out.write("$EndNodes\n")

        # Count elements: triangles + boundary line segments.
        n_line_elems = sum(max(int(s.node_ids.size) - 1, 0) for s in mesh.boundaries)
        out.write("$Elements\n")
        out.write(f"{mesh.n_elements + n_line_elems}\n")
        eid = 0
        for i in range(mesh.n_elements):
            eid += 1
            n0, n1, n2 = mesh.elements[i]
            out.write(
                f"{eid} {_GMSH_TRI} 2 1 1 "
                f"{int(n0) + 1} {int(n1) + 1} {int(n2) + 1}\n"
            )
        for seg, tag in zip(mesh.boundaries, seg_tags):
            ids = seg.node_ids
            for k in range(int(ids.size) - 1):
                eid += 1
                out.write(
                    f"{eid} {_GMSH_LINE} 2 {tag} {tag} "
                    f"{int(ids[k]) + 1} {int(ids[k + 1]) + 1}\n"
                )
        out.write("$EndElements\n")
    finally:
        if close:
            out.close()
