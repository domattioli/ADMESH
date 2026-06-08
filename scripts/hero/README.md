# Hero animation — Delaware Bay

Generates the README hero showing a graded **Delaware Bay** mesh evolving
through ADMESH's pipeline:

1. **Initialized** — rough, size-aware scatter inside the real Delaware
   Bay / River outline.
2. **Truss solver** — DistMesh force balance relaxes nodes toward
   elements sized by the graded size function `h(x)`.
3. **FEM smoothed** — Laplacian / FEM smoothing peaks element quality.

Triangles are colored by quality (red = poor → green = equilateral), and
node motion is interpolated continuously between precomputed keyframes.

The domain outline is the real Delaware Bay mesh registered in the sibling
[`ADMESH-Domains`](https://github.com/domattioli/ADMESH-Domains) repo
(`registry_data/meshes/Deleware_Bay_hmin_100_hmax_20000.14`). The graded
size function is parameterized by the three classic DistMesh / ADMESH
hyperparameters:

| param  | meaning                                   |
|--------|-------------------------------------------|
| `hmin` | smallest target edge length (river/coast) |
| `hmax` | largest target edge length (open bay)     |
| `g`    | gradient limit, `|∇h| ≤ g` (size growth)  |

## Files

- `precompute_delbay_stages.py` — reads the real domain, builds the graded
  size field, runs the truss + smoothing trajectories, writes
  `delbay_stages.npz` (+ caches `delbay_ring.npy`).
- `delbay_hero.py` — Manim scene that reads the `.npz` and renders.
- `delbay_stages.npz` / `delbay_ring.npy` — committed precompute output so
  the hero is reproducible without the sibling repo checked out.

## Regenerate

Manim needs system libs (`libcairo2-dev libpango1.0-dev ffmpeg`) plus a
Python venv:

```bash
python3 -m venv .manimenv && source .manimenv/bin/activate
pip install manim scipy shapely numpy

# 1. precompute the staged node trajectories
python scripts/hero/precompute_delbay_stages.py

# 2. render MP4 (1080p, 30 fps)
manim -qh --fps 30 -o admesh_delbay_hero.mp4 scripts/hero/delbay_hero.py DelawareBayHero

# 3. derive an optimized looping GIF from the MP4
mp4=media/videos/delbay_hero/1080p30/admesh_delbay_hero.mp4
ffmpeg -y -i "$mp4" -vf "fps=15,scale=900:-1:flags=lanczos,palettegen=stats_mode=diff" /tmp/pal.png
ffmpeg -y -i "$mp4" -i /tmp/pal.png \
  -lavfi "fps=15,scale=900:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3" \
  docs/assets/hero/admesh_delbay_hero.gif
cp "$mp4" docs/assets/hero/admesh_delbay_hero.mp4
```

The rendered assets live in [`docs/assets/hero/`](../../docs/assets/hero/)
and are referenced from the top-level `README.md`.
