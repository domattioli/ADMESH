"""Build the Western North Atlantic (WNAT) example for the browser app.

Reads the WNAT test mesh through the public admesh API, takes the outline of
the wet mesh (outer ring plus island rings) and writes it as a JSON domain
(docs/DOMAIN_IO.md, "JSON Format") together with a manifest used by web/app.js.

Pipeline, all deterministic:
  1. read_fort14 and merge the triangles with shapely.unary_union, which
     gives a valid polygon even where the raw boundary walk pinches;
  2. smooth the outline by a morphological opening followed by a closing of
     radius SMOOTH_DEG degrees. This removes channels, inlets and land
     bridges narrower than 2 * SMOOTH_DEG, where a coarse mesh would pinch
     the boundary. Keep the largest polygon and drop islands smaller than
     MIN_ISLAND_AREA (square degrees);
  3. simplify with Douglas-Peucker, tolerance SIMPLIFY_TOL degrees,
     preserving topology;
  4. round to COORD_DECIMALS decimals, orient the outer ring counter-clockwise
     and the islands clockwise, and require a valid polygon.

Run from the repository root:  python scripts/make_web_example_wnat.py
"""

from __future__ import annotations

import json
from pathlib import Path

from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

import admesh

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "fixtures" / "fort14" / "adcirc_examples" / "wnat_test.14"
OUT_DIR = ROOT / "web" / "examples"

SMOOTH_DEG = 0.25
MIN_ISLAND_AREA = 0.02
SIMPLIFY_TOL = 0.02
COORD_DECIMALS = 3

H_MIN = 0.3
H_MAX = 0.5
ATTRIBUTION = "Western North Atlantic, after Hagen et al., public domain."


def _ring(coords) -> list[list[float]]:
    pts = [[round(float(x), COORD_DECIMALS), round(float(y), COORD_DECIMALS)] for x, y in coords]
    return pts[:-1] if pts[0] == pts[-1] else pts


def build_polygon() -> Polygon:
    mesh = admesh.read_fort14(SOURCE)
    tris = [Polygon(mesh.nodes[t]) for t in mesh.elements]
    merged = unary_union(tris)
    merged = merged.buffer(-SMOOTH_DEG).buffer(2 * SMOOTH_DEG).buffer(-SMOOTH_DEG)
    polys = [merged] if merged.geom_type == "Polygon" else list(merged.geoms)
    outline = max(polys, key=lambda p: p.area)
    islands = [Polygon(r) for r in outline.interiors if Polygon(r).area >= MIN_ISLAND_AREA]
    poly = Polygon(outline.exterior, [i.exterior for i in islands])
    poly = poly.simplify(SIMPLIFY_TOL, preserve_topology=True)
    rounded = Polygon(_ring(poly.exterior.coords), [_ring(r.coords) for r in poly.interiors])
    if not rounded.is_valid:
        raise SystemExit("simplified WNAT polygon is not valid")
    return orient(rounded, sign=1.0)


def main() -> None:
    poly = build_polygon()
    rings = [_ring(poly.exterior.coords)] + [_ring(r.coords) for r in poly.interiors]
    xmin, ymin, xmax, ymax = poly.bounds
    domain = {
        "name": "wnat",
        "bbox": [round(xmin, COORD_DECIMALS), round(ymin, COORD_DECIMALS),
                 round(xmax, COORD_DECIMALS), round(ymax, COORD_DECIMALS)],
        "rings": rings,
    }
    manifest = {
        "examples": [
            {
                "id": "wnat",
                "label": "Western North Atlantic (WNAT)",
                "file": "wnat.json",
                "h_min": H_MIN,
                "h_max": H_MAX,
                "attribution": ATTRIBUTION,
            }
        ]
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "wnat.json").write_text(json.dumps(domain, separators=(",", ":")) + "\n")
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"rings={len(rings)} points={sum(len(r) for r in rings)} bbox={domain['bbox']}")


if __name__ == "__main__":
    main()
