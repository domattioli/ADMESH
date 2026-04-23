"""Convert MATLAB fixture .mat files to .npz for pytest consumption.

The MATLAB side (``scripts/export_matlab_fixtures.m``) writes
``.mat`` files into ``tests/fixtures/<stage>/<case>.mat``. This
script walks that tree and emits sibling ``<case>.npz`` files with
the same keys, adjusting for the MATLAB ↔ Python conventions:

- MATLAB 1-based connectivity indices are converted to 0-based.
  Any key matching ``t``, ``t_cleaned``, ``t_constrained``, or ``C``
  is treated as a connectivity / edge table and decremented by 1.
- No shape transpose: ``save(...,'-v7')`` already writes arrays in a
  layout ``scipy.io.loadmat`` returns as row-major NumPy.

Run:
    python scripts/mat_to_npz.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.io import loadmat

ROOT = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

_INDEX_KEYS = {"t", "t_cleaned", "t_constrained", "c"}


def _convert_one(mat_path: Path) -> Path:
    data = loadmat(mat_path, squeeze_me=True)
    out = {}
    for k, v in data.items():
        if k.startswith("__"):
            continue
        arr = np.asarray(v)
        if k.lower() in _INDEX_KEYS and np.issubdtype(arr.dtype, np.integer):
            arr = arr - 1  # MATLAB 1-based → Python 0-based
        out[k] = arr
    npz_path = mat_path.with_suffix(".npz")
    np.savez(npz_path, **out)
    return npz_path


def main() -> None:
    mats = list(ROOT.rglob("*.mat"))
    if not mats:
        print(f"No .mat fixtures found under {ROOT}")
        return
    for m in mats:
        out = _convert_one(m)
        print(f"{m.relative_to(ROOT)} → {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
