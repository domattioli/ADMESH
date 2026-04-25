"""Structural-validity assertions for the spec-002 release gate.

Per ``specs/002-size-field-defaults/spec.md`` clarification 2 ("a
valid mesh that respects all of the boundaries and meshes the entire
domain"). A mesh is *structurally valid* when:

  (a) every element has strictly positive signed area,
  (b) every triangle centroid lies inside the domain (per the
      domain's signed-distance function), so the mesh "respects" the
      input boundary — no element pokes outside,
  (c) the union of triangle areas covers the input domain to within a
      relative tolerance.

This formulation matches the practical user intent. The contract pseudocode
in ``contracts/python-api-default-stack.md`` proposed an exact-edge-set
check for (b), but that's incompatible with distmesh-style boundary
resampling at non-convex / curved geometry — distmesh redistributes
boundary nodes during force-balance iterations, so input vertex coords
are not preserved verbatim. The centroid-SDF check is what spec-001's
``tests/conftest.py::assert_valid_mesh`` uses for the same reason.

This module is private to the test code (`tests/`-only); it is NOT
part of the public ``admesh`` API.
"""

from __future__ import annotations

import numpy as np

import admesh


# ---------------------------------------------------------------------------
# The public assertion entry point
# ---------------------------------------------------------------------------


def assert_structurally_valid(
    mesh: admesh.Mesh,
    domain: admesh.Domain,
    *,
    tol: float = 1e-9,
    inside_tol: float | None = None,
    coverage_tol: float = 5e-2,
) -> None:
    """Assert spec-002's release gate on (mesh, domain).

    Parameters
    ----------
    mesh, domain
        The (output, input) pair of a `triangulate(...)` call.
    tol
        Geometric tolerance for the area-positivity check. Default
        1e-9.
    inside_tol
        SDF-evaluation tolerance for the centroid-inside-domain check.
        A centroid is "inside" when ``domain.sdf(centroid) <= inside_tol``.
        Defaults to ``mesh-bbox-diag * 1e-2`` — generous enough to
        accept distmesh's geps-level boundary tolerance.
    coverage_tol
        Relative tolerance on the coverage check (c). Default 1e-2.
    """
    # --- (a) Every element has strictly positive signed area. -----------
    pts = mesh.nodes[mesh.elements]   # (E, 3, 2)
    signed_area = 0.5 * (
        (pts[:, 1, 0] - pts[:, 0, 0]) * (pts[:, 2, 1] - pts[:, 0, 1])
        - (pts[:, 2, 0] - pts[:, 0, 0]) * (pts[:, 1, 1] - pts[:, 0, 1])
    )
    n_degen = int((signed_area <= tol).sum())
    assert n_degen == 0, (
        f"{n_degen} degenerate elements (signed_area <= {tol}); "
        f"min={float(signed_area.min()):.3e}"
    )

    if inside_tol is None:
        xs = mesh.nodes[:, 0]
        ys = mesh.nodes[:, 1]
        diag = float(np.hypot(xs.max() - xs.min(), ys.max() - ys.min()))
        inside_tol = max(diag * 1e-2, 1e-9)

    # --- (b) Every mesh node lies inside the domain (per SDF). ---------
    sdf_nodes = domain.sdf(mesh.nodes)
    n_node_outside = int((sdf_nodes > inside_tol).sum())
    if n_node_outside:
        worst_node = float(sdf_nodes.max())
        assert n_node_outside == 0, (
            f"{n_node_outside} of {mesh.n_nodes} mesh nodes outside the "
            f"domain (sdf > {inside_tol:.3e}); worst sdf={worst_node:.3e}"
        )

    # And every triangle's centroid is inside (catches inverted /
    # straddling triangles whose vertices are all just barely inside
    # but whose centroid is outside).
    centroids = (
        mesh.nodes[mesh.elements[:, 0]]
        + mesh.nodes[mesh.elements[:, 1]]
        + mesh.nodes[mesh.elements[:, 2]]
    ) / 3.0
    sdf_centroids = domain.sdf(centroids)
    n_cent_outside = int((sdf_centroids > inside_tol).sum())
    if n_cent_outside:
        worst_cent = float(sdf_centroids.max())
        assert n_cent_outside == 0, (
            f"{n_cent_outside} of {mesh.n_elements} centroids outside "
            f"the domain (sdf > {inside_tol:.3e}); worst sdf={worst_cent:.3e}"
        )

    polygons = getattr(domain, "polygons", None)
    if not polygons:
        # No polygon reference available (e.g. a domain_from_sdf user
        # who didn't supply one). Coverage check (c) is skipped —
        # asserts (a)/(b) are still binding.
        return

    # --- (c) Coverage: union of triangle areas matches domain area. -----
    domain_area = float(sum(p.area for p in polygons))
    mesh_area = float(signed_area.sum())
    if domain_area > 0:
        rel_err = abs(mesh_area - domain_area) / max(domain_area, 1.0)
        assert rel_err < coverage_tol, (
            f"coverage gap: |mesh_area - domain_area| = "
            f"{abs(mesh_area - domain_area):.3e}; "
            f"domain={domain_area:.3e}, mesh={mesh_area:.3e}, "
            f"rel_err={rel_err:.3e}, tol={coverage_tol:.3e}"
        )
