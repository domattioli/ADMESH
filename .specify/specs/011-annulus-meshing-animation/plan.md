# Spec 011 — Implementation plan

## Phase order

### Phase 1 — Render script skeleton

1. Create `scripts/render_annulus_animation.py` with the top-of-file
   docstring, imports (`numpy`, `matplotlib`, `matplotlib.animation`,
   `admesh`), and the `IterationSweepCapture` helper class (see
   below).
2. Pin a small `mpl.rcParams` block at module top so the figure style
   is reproducible across Matplotlib versions.

### Phase 2 — Frame capture

1. `IterationSweepCapture` exposes `.frames` — a list of `(p, t, k)`
   tuples. Internally:
   - `caps = [1, 2, 4, 8, 16, 32, 48, 64, 96, 128, 160, 200]`
   - For each cap, call
     `admesh.triangulate(ANNULUS, h_max=0.12, max_iter=cap, seed=0)`
     and append `(mesh.nodes, mesh.elements, cap)`.
2. Dedupe consecutive frames where `mesh.nodes.shape[0]` and
   `mesh.elements.shape[0]` are equal AND `np.allclose(p_prev, p_curr)`
   — the relaxation has plateaued; no animation benefit to duplicates.

### Phase 3 — Frame renderer

1. `render_frame(ax, p, t, k, n_pts, n_tri) -> None`:
   - Clear axes (`ax.clear()`).
   - Draw outer/inner boundary circles via `np.linspace(0, 2π, 200)`.
   - `ax.triplot(p[:, 0], p[:, 1], t, lw=0.6, color="#1f77b4")`.
   - `ax.plot(p[:, 0], p[:, 1], "o", ms=2.0, color="#ff7f0e")`.
   - `ax.set_xlim(-1.1, 1.1)`, `ax.set_ylim(-1.1, 1.1)`,
     `ax.set_aspect("equal")`, `ax.set_axis_off()`.
   - `ax.set_title(f"iter {k} · {n_pts} pts · {n_tri} tri")`.

### Phase 4 — Encoding

1. GIF via `matplotlib.animation.PillowWriter(fps=12)`. After save,
   re-open with `PIL.Image` and re-save with `optimize=True,
   save_all=True, loop=0` to compress.
2. MP4 via `matplotlib.animation.FFMpegWriter(fps=12, bitrate=800)`.
   Wrap in `try/except FileNotFoundError` so missing `ffmpeg` skips
   gracefully with a logged warning.
3. Both files land in `papers/`.

### Phase 5 — README embed

1. Find the Quickstart code block in `README.md` (the
   `mesh.to_fort14("disk.14")` line).
2. Insert the new `### Meshing in action` subsection immediately
   after the closing fence.
3. Use the raw-GitHubusercontent URL pinned to `main` (the artifact
   will be on `main` after merge).

### Phase 6 — Verification

1. `python scripts/render_annulus_animation.py` runs to completion.
2. `ls -lh papers/annulus_meshing.*` shows GIF ≤ 60 KB.
3. Open the README on GitHub (after push) to confirm the embed
   renders. Use a temporary `?v=1` query-string cache buster if
   regenerating.

## File-by-file diff sketch

### `scripts/render_annulus_animation.py` (new, ~120 lines)

```python
"""Render an annulus-meshing animation for the README.

Sweeps `admesh.triangulate(..., max_iter=k)` for an exponentially
spaced sequence of k values to capture frames without modifying
distmesh2d. See specs/011-annulus-meshing-animation/spec.md.

Dependencies (dev/docs only):
  pip install matplotlib pillow            # GIF
  ffmpeg on PATH (optional)                # MP4
"""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np

import admesh
from admesh import domains

CAPS = [1, 2, 4, 8, 16, 32, 48, 64, 96, 128, 160, 200]
H_MAX = 0.12
SEED = 0
OUT_DIR = Path(__file__).resolve().parents[1] / "papers"

# ... (full body per Phase 2-4)
```

### `papers/annulus_meshing.gif` (new artifact)
### `papers/annulus_meshing.mp4` (new artifact, optional)

### `README.md`

```diff
 mesh.to_fort14("disk.14")
 ```
+
+### Meshing in action
+
+The annulus domain in motion — distmesh2d's force-balance relaxation
+finds a high-quality unstructured mesh in ~200 iterations.
+
+<img src="https://raw.githubusercontent.com/domattioli/ADMESH/main/papers/annulus_meshing.gif" alt="ADMESH annulus meshing animation" width="60%">
```

## Risks revisited (operational)

- If `papers/` doesn't exist or isn't tracked by `.gitignore`, verify
  in Phase 1.
- If `optimize=True` GIF compression still produces > 60 KB, drop
  `CAPS` to 8 entries (1, 4, 16, 32, 64, 128, 160, 200).
- If `triangulate` accepts `max_iter` but ignores `seed` (legacy
  signature drift), update the helper to plumb the seed via the
  underlying `distmesh2d` call (private path; document the kludge).

## Done definition

Spec 011 is **done** when:
- [ ] Script committed and runnable.
- [ ] GIF + (optional) MP4 committed to `papers/`.
- [ ] README embeds the GIF in Quickstart.
- [ ] Issue #70 closed with a "resolved by spec 011" comment + commit
      SHA.
