"""Faithful-port stage modules — internal, numerically frozen.

This subpackage contains the 14 modules that translate
``QuADMesh-MATLAB/01_ADMESH_Library/`` at pin commit ``19b2eb9`` plus the
small number of v1 additions tightly coupled to the port
(``distmesh.distmesh2d_admesh``, ``distmesh.MeshOutput``,
``quality.right_iso_quality``).

Their public-style top-level imports (``apply_curvature``,
``apply_medial_axis``, ``mesh_quality``, ``triangulate``, etc.) remain
accessible via backward-compatible stubs at the old paths
(``admesh/<name>.py``) until ADMESH 1.0.0. New code SHOULD prefer the
canonical paths under ``admesh._stages``.

See ``specs/009-release-readiness-for-0.1.0/CONSTITUTION-AMENDMENT.md``
(proposed Constitution Article VIII) for the rationale.
"""

__all__: list[str] = []
