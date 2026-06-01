# Quickstart Validation: Spec 022 — Scalable Octree

After implementing the rewrite, run these steps in order to verify correctness + speed.

## 1. Unit smoke test

```bash
cd /home/user/ADMESH
pytest tests/ -q   # existing suite must stay green
```

Expected: all green. Any failure = regression introduced.

## 2. Parity check (spec 021 vs 022)

```python
# run from repo root
import sys; sys.path.insert(0, ".")
from admesh._stages.octree_grid import build_octree
from admesh._stages.octree_medial import size_field_octree
from scripts.render_sizefield_diff import polygon_sdf, river_bay_verts
import numpy as np

verts = river_bay_verts(Hx=24, Hy=14, w=2, river_len=12)
fd = polygon_sdf(verts)

class _D:
    pass
dom = _D(); dom.fd = fd
vx = [v[0] for v in verts]; vy = [v[1] for v in verts]
dom.bbox = (min(vx), min(vy), max(vx), max(vy))

hmin, hmax = 0.5, 5.0
oracle = lambda x, y: max(hmin, min(hmax, 0.6 * abs(fd([[x, y]])[0])))

g = build_octree(dom, h_min=hmin, h_max=hmax, size_oracle=oracle, balance=True)
h, _ = size_field_octree(g, R=2.0, hmin=hmin, hmax=hmax)
print(f"leaves={len(g.leaves)}  h_min={h.min():.3f}  h_max={h.max():.3f}")
# Expected (approximately matching spec 021): ~2900 leaves, h_min~0.5, h_max~5.0
```

## 3. Speed benchmark (US1 + US2)

```bash
python scripts/render_scalability.py
# Expected output: ratio=100 build < 5s, ratio=1000 build < 30s
# Log-log exponent < 1.5
```

## 4. Query speed (US2)

```python
import time, numpy as np
from admesh._stages.octree_grid import build_octree, locate

# ... build a 50k-leaf grid (use ratio=100 river domain) ...
pts = np.random.uniform(-10, 40, (100_000, 2))
t0 = time.time()
for p in pts:
    locate(grid, p)
dt = time.time() - t0
print(f"100k queries: {dt:.2f}s  ({dt/100_000*1e6:.1f} µs/query)")
# Expected: < 1.0 s total, < 10 µs/query
```

## 5. Rendering proof (end-to-end)

```bash
python scripts/render_sizefield_diff.py
# Expected: output/octree_sizefield_diff.png, octree mesh >= 3 river nodes
python scripts/render_octree_proof.py
# Expected: output/octree_proof.png, no errors
```

## 6. Complexity proof

Open `admesh/_stages/octree_grid.py`. Verify:
- No nested loop with both counters growing with `len(nodes)` in `build_octree`.
- No call to `_build_adjacency` inside `_balance_2to1`.
- `locate` uses a while-loop descending children, not a for-loop over all nodes.
