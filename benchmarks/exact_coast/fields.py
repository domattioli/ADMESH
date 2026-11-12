"""Shared size field: build once with admesh, sample on a grid, read back everywhere.

Saved file ``fields/<domain>.npz`` holds
  x : (nx,) grid x coordinates, ascending, uniform spacing
  y : (ny,) grid y coordinates, ascending, uniform spacing
  H : (ny, nx) target element size h(x, y); H[j, i] is at (x[i], y[j])
  base_H : scalar, the base size used to build it (hmax = base_H, hmin = base_H/8)
Construction (matches admesh.api channel_refine branch):
  limit_gradient(build_h(PortDomain, base=H, medial_scale=0.3, curvature_scale=0.5,
                         hmin=H/8, hmax=H), bbox, g=0.2)
Every tool, ADMESH included, reads the grid through GridField (bilinear, clamped
to the grid at its edges), so they all see identical values.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

FIELD_DIR = Path(__file__).resolve().parent / "fields"


class GridField:
    """Bilinear interpolator over a regular grid; callable on (N,2) arrays or scalars.

    ``scale`` multiplies the result (used for the node-budget factor s).
    """

    def __init__(self, x, y, H, scale: float = 1.0):
        self.x = np.asarray(x, float)
        self.y = np.asarray(y, float)
        self.H = np.asarray(H, float)
        self.scale = float(scale)
        self.x0, self.y0 = float(self.x[0]), float(self.y[0])
        self.dx = float(self.x[1] - self.x[0])
        self.dy = float(self.y[1] - self.y[0])
        self.nx, self.ny = len(self.x), len(self.y)

    @classmethod
    def load(cls, path, scale: float = 1.0) -> "GridField":
        d = np.load(path)
        return cls(d["x"], d["y"], d["H"], scale)

    def scaled(self, s: float) -> "GridField":
        return GridField(self.x, self.y, self.H, s)

    def __call__(self, pts):
        p = np.atleast_2d(np.asarray(pts, float))
        fx = np.clip((p[:, 0] - self.x0) / self.dx, 0, self.nx - 1)
        fy = np.clip((p[:, 1] - self.y0) / self.dy, 0, self.ny - 1)
        i = np.minimum(fx.astype(int), self.nx - 2)
        j = np.minimum(fy.astype(int), self.ny - 2)
        tx, ty = fx - i, fy - j
        H = self.H
        v = (H[j, i] * (1 - tx) * (1 - ty) + H[j, i + 1] * tx * (1 - ty)
             + H[j + 1, i] * (1 - tx) * ty + H[j + 1, i + 1] * tx * ty)
        return v * self.scale

    def at(self, x: float, y: float) -> float:
        """Scalar path with the same arithmetic (used by the Gmsh callback)."""
        fx = min(max((x - self.x0) / self.dx, 0.0), self.nx - 1.0)
        fy = min(max((y - self.y0) / self.dy, 0.0), self.ny - 1.0)
        i = min(int(fx), self.nx - 2)
        j = min(int(fy), self.ny - 2)
        tx, ty = fx - i, fy - j
        H = self.H
        return self.scale * (H[j, i] * (1 - tx) * (1 - ty) + H[j, i + 1] * tx * (1 - ty)
                             + H[j + 1, i] * (1 - tx) * ty + H[j + 1, i + 1] * tx * ty)


def build_field(name: str, rings, base_H: float, max_cells: float = 2.0e6) -> Path:
    """Build the shared size field for ``rings`` and save it to fields/<name>.npz."""
    from admesh._stages.domains import Domain as PortDomain
    from admesh._stages.mesh_size import build_h
    from admesh.loaders import _shapely_sdf
    from admesh.size_field import limit_gradient

    allp = np.vstack(rings)
    pad = 0.0
    bbox = (allp[:, 0].min() - pad, allp[:, 1].min() - pad,
            allp[:, 0].max() + pad, allp[:, 1].max() + pad)
    pd = PortDomain(name=name, fd=_shapely_sdf(rings), bbox=bbox,
                    fixed_points=np.empty((0, 2)))
    h = build_h(pd, base=base_H, medial_scale=0.3, curvature_scale=0.5,
                hmin=base_H / 8.0, hmax=base_H)
    fh = limit_gradient(h, bbox, g=0.2)
    w, hh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    step = base_H / 8.0
    while (w / step) * (hh / step) > max_cells:
        step *= 1.25
    nx, ny = int(np.ceil(w / step)) + 1, int(np.ceil(hh / step)) + 1
    xs = np.linspace(bbox[0], bbox[2], nx)
    ys = np.linspace(bbox[1], bbox[3], ny)
    X, Y = np.meshgrid(xs, ys)
    H = np.asarray(fh(np.c_[X.ravel(), Y.ravel()]), float).reshape(ny, nx)
    FIELD_DIR.mkdir(exist_ok=True)
    path = FIELD_DIR / f"{name}.npz"
    np.savez_compressed(path, x=xs, y=ys, H=H, base_H=base_H)
    return path
