"""Re-triangulate the WNAT (Western North Atlantic) domain with admesh2D.

WNAT is a classic ADCIRC stress-test domain — Hagen et al.'s shelf-and-
ocean mesh covering the Gulf of Mexico, Caribbean, and US East Coast.
The included reference fixture (``tests/fixtures/fort14/adcirc_examples/
wnat_test.14``, ~10K nodes) is the small variant distributed widely
with ADMESH tutorials.

This script:

1. Reads the reference WNAT fort.14.
2. Verifies the round-trip through admesh2D's reader/writer.
3. Derives the outer-ring boundary from the triangulation (since the
   header declares 0 open + 0 land segments).
4. Builds a polygon ``Domain`` from that boundary.
5. Coarsely re-triangulates it via ``admesh.triangulate``.
6. Writes the new mesh to ``wnat_admesh.14`` and prints stats for both.

Usage:
    python scripts/wnat_demo.py [reference.14] [output.14] [h_max_degrees]

Defaults:
    reference  = tests/fixtures/fort14/adcirc_examples/wnat_test.14
    output     = wnat_admesh.14
    h_max_deg  = 1.5  (degrees of lon/lat — coarse uniform sizing)

The full quality re-mesh of WNAT requires the size-field stack
(curvature + medial axis + bathymetry-aware sizing) which lands in
spec 001 Phase 5. Until then this script is a *uniform* re-mesh — it
proves the pipeline runs end-to-end on a 10K-node real-world domain
but is not a quality replacement for the upstream Hagen mesh.
"""

from __future__ import annotations

import pathlib
import sys
import time

import numpy as np

import admesh
from admesh.api import _derive_boundary_segments


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_REF = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "fort14"
    / "adcirc_examples"
    / "wnat_test.14"
)


def _outer_ring_xy(mesh: admesh.Mesh) -> np.ndarray:
    """Return the (M, 2) coordinates of the longest boundary ring."""
    if mesh.boundaries:
        rings = sorted(
            mesh.boundaries, key=lambda s: s.node_ids.size, reverse=True
        )
        ids = rings[0].node_ids
    else:
        # Header didn't declare boundaries — derive from connectivity.
        derived = _derive_boundary_segments(mesh.elements, mesh.nodes)
        if not derived:
            raise RuntimeError("could not derive boundary from mesh")
        ids = derived[0].node_ids
    return mesh.nodes[ids]


def main(
    ref_path: str = str(DEFAULT_REF),
    out_path: str = "wnat_admesh.14",
    h_max_deg: float = 1.5,
) -> None:
    print(f"=== WNAT re-triangulation demo ===\n")
    print(f"reference: {ref_path}")
    print(f"output:    {out_path}")
    print(f"h_max:     {h_max_deg}° (lon/lat)\n")

    # 1) Read the reference mesh.
    t0 = time.perf_counter()
    ref = admesh.read_fort14(ref_path)
    t_read = time.perf_counter() - t0
    print(f"[1/5] read in {t_read:.2f}s — {repr(ref)}")
    print(f"      bbox: x=[{ref.nodes[:,0].min():.2f}, {ref.nodes[:,0].max():.2f}]"
          f"  y=[{ref.nodes[:,1].min():.2f}, {ref.nodes[:,1].max():.2f}]")
    if ref.bathymetry is not None:
        print(
            f"      bathymetry (positive-up internal): "
            f"[{ref.bathymetry.min():.1f}, {ref.bathymetry.max():.1f}] m"
        )

    # 2) Round-trip sanity.
    import io as _io
    buf = _io.StringIO()
    ref.to_fort14(buf)
    buf.seek(0)
    rt = admesh.read_fort14(buf)
    print(f"[2/5] round-trip equal: {ref.equals(rt, atol=1e-5)}\n")

    # 3) Derive the outer ring.
    ring = _outer_ring_xy(ref)
    # distmesh wants the ring in CCW orientation; flip if signed area < 0.
    signed_area = 0.5 * np.sum(
        ring[:-1, 0] * ring[1:, 1] - ring[1:, 0] * ring[:-1, 1]
    )
    if signed_area < 0:
        ring = ring[::-1]
    print(
        f"[3/5] outer ring: {len(ring)} vertices, "
        f"oriented {'CCW' if signed_area >= 0 else 'CCW (flipped)'}"
    )

    # 4) Build domain + triangulate.
    domain = admesh.domain_from_polygon([ring])
    print(f"[4/5] triangulating … (this may take a minute on the full ring)")
    t0 = time.perf_counter()
    new = admesh.triangulate(
        domain,
        h_max=h_max_deg,
        max_iter=80,
        seed=0,
        # Loose gate — uniform re-mesh of a complex coastline isn't going
        # to clear 0.30 / 0.60 without a real size field.
        quality_gate=(0.10, 0.40),
    )
    t_tri = time.perf_counter() - t0
    print(f"      triangulated in {t_tri:.2f}s — {repr(new)}\n")

    # 5) Write the new mesh.
    new = admesh.Mesh(
        nodes=new.nodes,
        elements=new.elements,
        boundaries=new.boundaries,
        quality=new.quality,
        title=f"WNAT re-meshed by admesh2D h_max={h_max_deg}deg",
    )
    new.to_fort14(out_path)
    print(f"[5/5] wrote {out_path}\n")

    # Summary table.
    print("Summary:")
    print(f"  reference: {ref.n_nodes:>6d} nodes  {ref.n_elements:>6d} elements")
    print(f"  re-meshed: {new.n_nodes:>6d} nodes  {new.n_elements:>6d} elements")
    if new.quality is not None:
        print(
            f"             min_q={new.quality.min():.2f}  "
            f"mean_q={new.quality.mean():.2f}  "
            f"max_q={new.quality.max():.2f}"
        )


if __name__ == "__main__":
    args = sys.argv[1:]
    ref = args[0] if len(args) > 0 else str(DEFAULT_REF)
    out = args[1] if len(args) > 1 else "wnat_admesh.14"
    h = float(args[2]) if len(args) > 2 else 1.5
    main(ref, out, h)
