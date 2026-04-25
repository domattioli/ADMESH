# Public Python API Contract

**Feature**: 001-pythonize-and-fort14-integration
**Date**: 2026-04-24

This is the contract a v1 release must satisfy. Every function listed here MUST exist with the documented signature. Adding parameters with defaults is non-breaking; removing or renaming is breaking.

---

## Top-level package surface (`admesh`)

```python
# Re-exported from admesh/__init__.py:

from admesh.api import (
    Mesh,
    Domain,
    BoundarySegment,
    triangulate,
    domain_from_polygon,
    domain_from_sdf,
)
from admesh.boundary_types import BoundaryType
from admesh.fort14 import (
    read_fort14,
    write_fort14,
    Fort14ParseError,
)
from admesh.size_field import (
    SizeFieldFn,
    compose_size_field,
)

__all__ = [
    "Mesh", "Domain", "BoundarySegment", "BoundaryType",
    "triangulate", "domain_from_polygon", "domain_from_sdf",
    "read_fort14", "write_fort14", "Fort14ParseError",
    "SizeFieldFn", "compose_size_field",
]
```

---

## Function: `triangulate`

```python
def triangulate(
    domain: Domain,
    *,
    h_max: float | None = None,
    h_min: float | None = None,
    size_field: SizeFieldFn | None = None,
    user_contribs: list[SizeFieldFn] = (),
    combine: Callable[[list[np.ndarray]], np.ndarray] = np.minimum.reduce,
    seed: int | None = None,
    max_iter: int | None = None,
    quality_gate: tuple[float, float] = (0.30, 0.60),
) -> Mesh:
    """
    Generate a triangular mesh on the given domain.

    Parameters
    ----------
    domain : Domain
        Geometric description (SDF + bbox + optional fixed points and BC labels).
    h_max, h_min : float, optional
        Element size bounds. Defaults are derived from the domain bbox.
    size_field : SizeFieldFn, optional
        Pre-composed size field. If None, the built-in stages (curvature, medial,
        bathymetry, tide) are used, composed with `np.minimum.reduce`.
    user_contribs : list[SizeFieldFn], optional
        Phase-2 user size-field contributions. Combined with the Phase-1 built-in
        result via `combine`. See `compose_size_field`.
    combine : Callable, optional
        Phase-2 combiner. Defaults to elementwise minimum.
    seed : int, optional
        Random seed for reproducibility.
    max_iter : int, optional
        Truss-iteration cap. Defaults to MATLAB's value.
    quality_gate : (min_q, mean_q), optional
        Quality thresholds the resulting mesh must satisfy.

    Returns
    -------
    Mesh
        A frozen Mesh dataclass with nodes, elements, boundary segments,
        and per-element quality populated.

    Raises
    ------
    ValueError
        If the quality gate cannot be met within `max_iter` iterations.

    Examples
    --------
    >>> domain = admesh.domain_from_polygon([np.array([...])])
    >>> mesh = admesh.triangulate(domain)
    >>> mesh.to_fort14("out.14")
    """
```

---

## Class: `Mesh`

See `data-model.md` for full field definitions. Methods on `Mesh`:

```python
def to_fort14(self, path: str | os.PathLike | TextIO) -> None:
    """Write this mesh to a fort.14 file or text-mode buffer.

    Applies 0-based → 1-based index conversion and elevation → depth sign flip.
    """

def plot(self, ax=None, **kwargs):
    """Draw the mesh using matplotlib.

    Raises
    ------
    ImportError
        If matplotlib is not installed. Install with `pip install admesh2D[viz]`.
    """

def equals(self, other: Mesh, *, atol: float = 1e-10, rtol: float = 0.0) -> bool:
    """Tolerance-aware equality check for round-trip tests.

    Connectivity (elements, BC labels) compared exactly; coordinates and
    bathymetry compared with the given tolerances.
    """

def __repr__(self) -> str: ...
def __str__(self) -> str: ...
```

---

## Function: `read_fort14`

```python
def read_fort14(path: str | os.PathLike | TextIO) -> Mesh:
    """
    Parse an ADCIRC v55 fort.14 file into a Mesh.

    Applies 1-based → 0-based index conversion and depth → elevation sign flip.
    Unmapped IBTYPE codes are preserved as numeric values in BoundarySegment.bc_type.

    Raises
    ------
    Fort14ParseError
        If the file is malformed. The exception carries .line_no, .expected, .actual.
    """
```

---

## Function: `write_fort14`

```python
def write_fort14(mesh: Mesh, path: str | os.PathLike | TextIO) -> None:
    """
    Serialize a Mesh to ADCIRC v55 fort.14 format.

    Identical behavior to `mesh.to_fort14(path)`. Provided as a free function
    for callers who prefer that style.
    """
```

---

## Class: `Fort14ParseError`

```python
class Fort14ParseError(ValueError):
    """Raised by read_fort14 on malformed input.

    Attributes
    ----------
    line_no : int
        1-based line number where the error was detected.
    expected : str
        Short human-readable description of what was expected.
    actual : str
        The offending line content (truncated to 120 chars).
    """
    def __init__(self, line_no: int, expected: str, actual: str): ...
```

---

## Function: `compose_size_field`

```python
def compose_size_field(
    builtins: list[SizeFieldFn],
    user_contribs: list[SizeFieldFn] = (),
    combine: Callable[[list[np.ndarray]], np.ndarray] = np.minimum.reduce,
) -> SizeFieldFn:
    """
    Compose a size field from built-in stages and user contributions.

    Two-phase semantics:
    - Phase 1: `np.minimum.reduce` over `[f(pts) for f in builtins]` (always min-stack;
      Constitution Principle I — non-negotiable).
    - Phase 2: `combine([phase1_result, *user_contrib_results])` (default min).

    Returns a callable `(N, 2) -> (N,)` suitable for passing to `triangulate(size_field=...)`.
    """
```

---

## Domain builders

```python
def domain_from_polygon(
    rings: list[np.ndarray],
    *,
    pfix: np.ndarray | None = None,
    bc_segments: tuple[BoundarySegment, ...] = (),
) -> Domain:
    """
    Build a Domain from a list of polygon rings (outer ring first, holes following).

    Each ring is an (M, 2) float array of (x, y) vertices. The SDF is constructed
    via Shapely; the bbox is computed from the ring extents.
    """

def domain_from_sdf(
    sdf: Callable[[np.ndarray], np.ndarray],
    bbox: tuple[float, float, float, float],
    *,
    pfix: np.ndarray | None = None,
    pts: np.ndarray | None = None,
    bc_segments: tuple[BoundarySegment, ...] = (),
) -> Domain:
    """
    Build a Domain from a user-supplied SDF callable and an explicit bbox.
    """
```

---

## Backward-compatibility surface (faithful-port — UNCHANGED)

The following modules retain their existing public symbols. No symbol is removed; no signature changes. This list is illustrative — the binding contract is: **the existing 142-test suite passes without modification.**

```python
admesh.routine.ADmeshRoutine
admesh.background_grid.create_background_grid
admesh.distance.signed_distance_function
admesh.curvature.curvature_function
admesh.medial_axis.medial_axis_function
admesh.bathymetry.bathymetry_function
admesh.dominate_tide.dominate_tide_function
admesh.boundary.enforce_boundary_conditions
admesh.boundary.create_polygon_structure
admesh.mesh_size.mesh_size_function
admesh.distmesh.distmesh2d_admesh
admesh.distmesh.fixmesh
admesh.quality.mesh_quality
admesh.in_polygon.in_polygon
admesh.inpaint.inpaint_nans
admesh.domains.*
```

Tests covering these symbols (`tests/test_<stage>.py`, `tests/test_matlab_port.py`, `tests/test_mvp_domains.py`, `tests/test_smoke.py`) are not modified by this feature.
