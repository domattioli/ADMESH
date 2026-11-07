"""Benchmark domains for the exact-coast challenge.

Every domain is a list of rings: ``rings[0]`` is the outer boundary and
``rings[1:]`` are holes.  Rings are open (first vertex is not repeated) and
are used as given, never smoothed or resampled.  ``H`` is the base (maximum)
element size used to build the shared size field; it was picked so the
ADMESH mesh has roughly 1k to 5k nodes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import os

import numpy as np

REPO = Path(__file__).resolve().parents[2]
WNAT = REPO / "tests/fixtures/fort14/adcirc_examples/wnat_test.14"
# Block_O.14 is not vendored; point ADMESH_BLOCK_O at a local copy (skipped if missing).
BLOCK_O = Path(os.environ.get("ADMESH_BLOCK_O", str(REPO / "benchmarks/exact_coast/data/Block_O.14")))

# Notched rectangle, copied from scripts/render_boundary_relax.py (RING).
NOTCHED_RING = np.array(
    [
        [0.0, 0.0], [4.0, 0.0], [4.0, 1.6], [3.3, 1.7], [3.0, 2.0],
        [2.15, 2.0], [2.15, 1.35], [1.85, 1.35], [1.85, 2.0],
        [1.2, 2.0], [0.9, 1.75], [0.4, 1.9], [0.0, 1.5],
    ]
)


def _circle(r: float, n: int, cw: bool = False) -> np.ndarray:
    th = 2 * np.pi * np.arange(n) / n
    if cw:
        th = th[::-1]
    return np.c_[r * np.cos(th), r * np.sin(th)]


def notched() -> list[np.ndarray]:
    return [NOTCHED_RING.copy()]


def annulus(n_outer: int, n_inner: int) -> list[np.ndarray]:
    return [_circle(1.0, n_outer), _circle(0.4, n_inner, cw=True)]


def narrow_inlet() -> list[np.ndarray]:
    """2x1 box with a 0.06-wide, 0.6-deep inlet cut into the top edge."""
    return [np.array([
        [0.0, 0.0], [2.0, 0.0], [2.0, 1.0], [1.03, 1.0], [1.03, 0.4],
        [0.97, 0.4], [0.97, 1.0], [0.0, 1.0],
    ])]


def island_chain() -> list[np.ndarray]:
    """3x1.5 box with 4 small polygon islands (triangle, square, pentagon, hexagon-ish)."""
    box = np.array([[0.0, 0.0], [3.0, 0.0], [3.0, 1.5], [0.0, 1.5]])

    def poly(cx, cy, r, n, rot=0.0):
        th = rot + 2 * np.pi * np.arange(n)[::-1] / n  # clockwise
        return np.c_[cx + r * np.cos(th), cy + r * np.sin(th)]

    return [
        box,
        poly(0.6, 0.7, 0.18, 3),
        poly(1.3, 0.9, 0.15, 4, 0.3),
        poly(2.0, 0.6, 0.20, 5, 0.1),
        poly(2.5, 1.0, 0.12, 7),
    ]


def _fort14(path: Path) -> list[np.ndarray]:
    from admesh.fort14 import read_fort14
    from admesh.loaders import _fort14_rings

    return [np.asarray(r, float) for r in _fort14_rings(read_fort14(path))]


def get_domains() -> dict[str, dict]:
    """name -> {rings, H, note}.  Missing optional files are skipped by the runner."""
    out: dict[str, dict] = {
        "notched": dict(rings=notched(), H=0.12),
        "annulus64": dict(rings=annulus(64, 32), H=0.05),
        "annulus32": dict(rings=annulus(32, 16), H=0.05),
        "narrow_inlet": dict(rings=narrow_inlet(), H=0.05),
        "island_chain": dict(rings=island_chain(), H=0.07),
    }
    out["wnat"] = dict(rings=None, H=1.6, path=WNAT)
    out["block_o"] = dict(rings=None, H=1.0, path=BLOCK_O)
    return out


def load_real(name: str, spec: dict) -> dict | None:
    """Fill rings for a fort.14-backed domain; None (with a note) if file missing."""
    p = spec["path"]
    if not Path(p).exists():
        print(f"[skip] {name}: {p} not found", file=sys.stderr)
        return None
    spec = dict(spec)
    rings = _fort14(Path(p))
    spec["rings"], spec["note"] = clean_rings(rings)
    return spec


def clean_rings(rings: list[np.ndarray]) -> tuple[list[np.ndarray], str]:
    """Return a valid simple polygon's rings.

    Mesh-derived boundary loops can pinch (two loops or one loop touching at a
    shared node), which is not a simple polygon and breaks every constrained
    mesher.  If the input is already valid it is returned untouched.  Otherwise
    ``shapely.make_valid`` is applied and the largest resulting polygon is
    kept; its vertices are a subset of the original vertices.
    """
    import shapely
    from shapely.geometry import Polygon

    P = Polygon(rings[0], rings[1:])
    if P.is_valid:
        return rings, "valid as loaded"
    V = shapely.make_valid(P)
    parts = list(V.geoms) if hasattr(V, "geoms") else [V]
    parts = [g for g in parts if g.geom_type == "Polygon"]
    big = max(parts, key=lambda g: g.area)
    out = [np.asarray(big.exterior.coords)[:-1]]
    out += [np.asarray(h.coords)[:-1] for h in big.interiors]
    note = (
        f"loaded rings were not a simple polygon (pinch points); make_valid + largest piece "
        f"kept: area {P.area:.2f} -> {big.area:.2f}, {len(rings)} -> {len(out)} rings, "
        f"{len(parts) - 1} small pieces dropped"
    )
    return out, note
