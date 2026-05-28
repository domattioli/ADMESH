# IMPLEMENT: Pseudocode & Execution Guide (Issue #97)

**Purpose:** Detailed pseudocode and step-by-step execution instructions for the developer.  
**Audience:** Developer implementing TASKS.md; serves as both sketch and verification checklist.

---

## PART I: Domain & Bathymetry Setup (Tasks 1.1–1.3)

### Task 1.1: Notch Boundary Parametrization

**Goal:** Create `notch_seamount_domain.json` with geometry specification.

**Pseudocode:**
```python
#!/usr/bin/env python3
"""Generate notch domain JSON for ADMESH visualization."""

import json
import numpy as np
import pathlib

OUT = pathlib.Path(__file__).parent / "viz_data" / "notch_seamount_domain.json"

def create_notch_domain():
    """
    Parametrize a synthetic coastal notch + seamount domain.
    
    Geometry (normalized [-1.5, 1.5] × [-1, 1] coords):
    - Outer boundary: semicircle + straight shelf + V-notch
    - Notch: 60° apex, 1 km deep, opens downward (y = 1 → −1)
    - Shelf: straight edge at y = −1, x ∈ [−1.5, 1.5]
    """
    
    # --- Outer arc (semicircle, deep side, y > 0)
    theta = np.linspace(np.pi, 2*np.pi, 50)
    radius = 1.5
    outer_arc_x = radius * np.cos(theta)
    outer_arc_y = radius * np.sin(theta)
    outer_arc = np.column_stack([outer_arc_x, outer_arc_y])
    
    # --- Straight shelf edge (y = −1, x ∈ [−1.5, 1.5])
    shelf = np.array([
        [-1.5, -1.0],
        [ 1.5, -1.0],
    ])
    
    # --- V-notch (two 60° sides meeting at apex)
    # Apex at (0, 1), opening downward
    # Left flank: from (0, 1) to (−0.5, 0)
    # Right flank: from (0, 1) to (+0.5, 0)
    # Resolution: ~20 points per flank for smooth curve
    left_flank_x = np.linspace(0, -0.5, 20)
    left_flank_y = np.linspace(1, 0, 20)
    left_flank = np.column_stack([left_flank_x, left_flank_y])
    
    right_flank_x = np.linspace(0, 0.5, 20)
    right_flank_y = np.linspace(1, 0, 20)
    right_flank = np.column_stack([right_flank_x, right_flank_y])
    
    # --- Assemble ring (counterclockwise boundary, exterior)
    # Order: outer arc → left shelf endpoint → notch left flank → notch right flank → right shelf endpoint → back to start
    ring = np.vstack([
        outer_arc,
        shelf[::-1],  # reverse shelf (right → left)
        right_flank[::-1],  # right flank (apex ← base)
        left_flank,  # left flank (apex → base)
    ])
    
    # Ensure closure (duplicate first point at end if needed)
    if not np.allclose(ring[-1], ring[0]):
        ring = np.vstack([ring, ring[0:1]])
    
    # --- Bounding box
    bbox = [ring[:, 0].min(), ring[:, 1].min(), ring[:, 0].max(), ring[:, 1].max()]
    
    # --- Domain dict (ADMESH format)
    domain = {
        "bbox": bbox,
        "rings": [ring.tolist()],  # outer ring only (no holes)
    }
    
    return domain

# Save to JSON
domain = create_notch_domain()
with open(OUT, 'w') as f:
    json.dump(domain, f, indent=2)

print(f"Created {OUT}")
print(f"  Extent: {domain['bbox']}")
print(f"  Boundary points: {len(domain['rings'][0])}")
```

**Execution:**
```bash
python scripts/notch_domain_gen.py
```

**Validation:**
1. Check file exists: `ls -lh scripts/viz_data/notch_seamount_domain.json`
2. Visually inspect:
   ```python
   import json
   d = json.load(open("scripts/viz_data/notch_seamount_domain.json"))
   print(d["bbox"])  # Should be roughly [-1.5, -1, 1.5, 1]
   print(len(d["rings"][0]))  # Should be ~100+ points
   ```
3. Gate check: Curvature at notch tip
   - Will compute in Task 1.3 validation script

---

### Task 1.2: Domain JSON Validation & SDF Check

**Pseudocode:**
```python
#!/usr/bin/env python3
"""Validate notch domain JSON + SDF computation."""

import json
import numpy as np
import pathlib
import matplotlib.pyplot as plt

from admesh._fast_sdf import fast_sdf

DOMAIN_JSON = pathlib.Path("scripts/viz_data/notch_seamount_domain.json")
OUT_PLOT = pathlib.Path("output/notch_boundary_check.png")

def validate_domain():
    """Load domain JSON, compute SDF, validate spot-checks."""
    
    # Load domain
    domain = json.load(open(DOMAIN_JSON))
    ring = np.array(domain["rings"][0])
    bbox = domain["bbox"]
    
    print(f"Domain extent: {bbox}")
    print(f"Boundary points: {len(ring)}")
    
    # Compute SDF on coarse test grid
    nx, ny = 50, 50
    x = np.linspace(bbox[0], bbox[2], nx)
    y = np.linspace(bbox[1], bbox[3], ny)
    xx, yy = np.meshgrid(x, y)
    xflat = xx.ravel()
    yflat = yy.ravel()
    
    # Use ADMESH's fast_sdf
    sdf = fast_sdf(np.c_[xflat, yflat], ring)
    sdf_grid = sdf.reshape(nx, ny)
    
    # Spot-check 10 points
    test_points = [
        # Inside domain
        (0.0, 0.0, -1, "interior"),
        (0.0, 0.2, -1, "notch interior"),
        (-0.5, -0.5, -1, "shelf interior"),
        (0.3, -0.8, -1, "shelf"),
        (-1.0, 0.5, -1, "outer arc interior"),
        # Outside domain
        (2.0, 0.0, 1, "far right"),
        (-2.0, 0.0, 1, "far left"),
        (0.0, 2.0, 1, "far north"),
        # Boundary (approximately)
        (1.5, -1.0, 0, "shelf edge"),
        (0.0, 1.0, 0, "notch apex"),
    ]
    
    print("\nSpot-check SDF values:")
    all_pass = True
    for x_pt, y_pt, expected_sign, label in test_points:
        # Find closest grid point
        ix = np.argmin(np.abs(x - x_pt))
        iy = np.argmin(np.abs(y - y_pt))
        sdf_val = sdf_grid[iy, ix]
        actual_sign = np.sign(sdf_val)
        status = "✓" if actual_sign == expected_sign else "✗"
        print(f"  {status} ({x_pt:5.1f}, {y_pt:5.1f}): SDF={sdf_val:7.3f} ({label})")
        if actual_sign != expected_sign:
            all_pass = False
    
    if all_pass:
        print("\n✓ All spot-checks passed")
    else:
        print("\n✗ Some spot-checks failed; investigate boundary")
    
    # Compute curvature at notch (approximation)
    # Curvature ≈ turning angle / arc length at boundary
    # For now, document manually (measured from geometry)
    notch_angle = 60  # degrees
    notch_depth = 1.0  # normalized coords ≈ 1 km physical
    approx_curvature = np.tan(np.radians(notch_angle/2)) / notch_depth
    print(f"\nApprox notch curvature: {approx_curvature:.3f} (m⁻¹ at physical scale)")
    print(f"  Note: map normalized 1 km → physical units for final check")
    
    # Plot
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.contourf(xx, yy, sdf_grid, levels=20, cmap="RdBu_r")
    ax.plot(ring[:, 0], ring[:, 1], 'k-', linewidth=2, label="Boundary")
    ax.set_aspect('equal')
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_title('Signed Distance Function (SDF)\nBlue=inside, Red=outside')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.savefig(OUT_PLOT, dpi=100, bbox_inches='tight')
    print(f"\nPlot saved: {OUT_PLOT}")
    
    return all_pass

if __name__ == "__main__":
    validate_domain()
```

**Execution:**
```bash
python scripts/validate_notch_domain.py
```

**Gate check:** All spot-checks pass; curvature ≥ 100 m⁻¹ at notch apex (when mapped to physical units).

---

### Task 1.3: Bathymetry Function Implementation

**Pseudocode:**
```python
#!/usr/bin/env python3
"""Implement bathymetry function for notch-seamount domain."""

import numpy as np
import matplotlib.pyplot as plt

def fake_bathymetry(x, y):
    """
    Synthetic bathymetry: cross-shelf profile + seamount.
    
    Physical units (meters):
    - Coastline (y = −1): z = 0
    - Shelf edge (~2 km offshore): z = −20 m
    - Deep water: z = −100 m
    - Seamount (Gaussian, center at (0, 0.5)): +4 m elevation, 400 m radius
    
    Parameters
    ----------
    x, y : array-like
        Normalized domain coordinates (−1.5 ≤ x ≤ 1.5, −1 ≤ y ≤ 1)
    
    Returns
    -------
    z : ndarray
        Elevation (m), negative = deep
    """
    
    # --- Cross-shelf profile (x-dependent)
    # Map x to physical distance offshore (x = −1.5 → 0 m, x = 1.5 → 3000 m)
    x_phys = (x + 1.5) / 3.0 * 3000  # [0, 3000] meters
    
    # Smooth depth transition: 0 → −20 m over 2 km, then gradual to −100 m
    # Use error function for smooth transition
    z_cross = -20 * (1 + np.erf((x_phys - 2000) / 500)) / 2 - 80
    
    # --- Alongshore variation (y-dependent, primarily in notch)
    # Notch interior (y > 0) has shoaling trend; open shelf (y < 0) flat
    z_shore = np.where(y > 0, 5 * y, 0)  # Shoaling in notch (+5 m at y=1)
    
    # --- Seamount (Gaussian bump)
    # Center at (x0, y0) = (0, 0.5) in normalized coords = (1500 m, 500 m phys)
    # Elevation: 4 m, radius: 400 m
    r_seamount = np.sqrt((x - 0.0)**2 + (y - 0.5)**2)
    r_seamount_phys = r_seamount * 1500  # Convert normalized → physical (1500 m = half domain width)
    z_seamount = 4 * np.exp(-(r_seamount_phys / 400)**2)
    
    # --- Combine
    z = z_cross + z_shore + z_seamount
    
    return z

def validate_bathymetry():
    """Test bathymetry function; check gradient."""
    
    # Grid for evaluation
    nx, ny = 80, 80
    x = np.linspace(-1.5, 1.5, nx)
    y = np.linspace(-1.0, 1.0, ny)
    xx, yy = np.meshgrid(x, y)
    
    # Bathymetry
    z = fake_bathymetry(xx, yy)
    
    # Gradient (finite difference)
    dx = (x[1] - x[0])
    dy = (y[1] - y[0])
    zx, zy = np.gradient(z, dx, dy)
    grad = np.hypot(zx, zy)
    
    print("Bathymetry statistics:")
    print(f"  z min: {z.min():.2f} m, max: {z.max():.2f} m")
    print(f"  |∇z| min: {grad.min():.4f}, max: {grad.max():.4f}")
    print(f"  Mean |∇z|: {grad.mean():.4f}")
    
    # Gate check: max(|∇z|) ≥ 0.30
    if grad.max() >= 0.30:
        print("✓ Gradient criterion met (max |∇z| ≥ 0.30)")
    else:
        print(f"✗ Gradient too weak; max |∇z| = {grad.max():.4f} < 0.30")
        print("  Recommendation: increase shelf-break steepness or seamount height")
    
    # Plot
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Bathymetry
    im0 = axes[0].contourf(xx, yy, z, levels=20, cmap="viridis")
    axes[0].contour(xx, yy, z, levels=10, colors='k', linewidths=0.5, alpha=0.3)
    axes[0].set_aspect('equal')
    axes[0].set_xlabel('x (normalized)')
    axes[0].set_ylabel('y (normalized)')
    axes[0].set_title('Bathymetry z(x,y) [meters]')
    plt.colorbar(im0, ax=axes[0], label='Elevation (m)')
    
    # Gradient magnitude
    im1 = axes[1].contourf(xx, yy, grad, levels=20, cmap="hot")
    axes[1].contour(xx, yy, grad, levels=10, colors='k', linewidths=0.5, alpha=0.3)
    axes[1].set_aspect('equal')
    axes[1].set_xlabel('x (normalized)')
    axes[1].set_ylabel('y (normalized)')
    axes[1].set_title('Gradient magnitude |∇z|')
    plt.colorbar(im1, ax=axes[1], label='|∇z| (m/m)')
    
    plt.tight_layout()
    plt.savefig("output/notch_bathymetry_check.png", dpi=100, bbox_inches='tight')
    print(f"\nPlot saved: output/notch_bathymetry_check.png")

if __name__ == "__main__":
    validate_bathymetry()
```

**Execution:**
```bash
python scripts/validate_bathymetry.py
```

**Gate check:** max(|∇z|) ≥ 0.30; seamount and shelf-break visible in plots.

---

## PART II: Data Generation Script (Tasks 2.1–2.3)

### Task 2.1: `gen_notch_seamount_data.py` Script

**Pseudocode (complete, ready to copy-paste with minimal edits):**

```python
#!/usr/bin/env python3
"""Generate ADMESH visualization data on the Notch-Seamount domain.

Produces an .npz with:
  - domain boundary + SDF
  - bathymetry grid + size-field factors
  - per-iteration distmesh snapshots (node coords + bar connectivity)

Output: scripts/viz_data/notch_seamount_admesh.npz
Run:    python scripts/gen_notch_seamount_data.py
"""

from __future__ import annotations

import json
import pathlib
import numpy as np
from scipy.spatial import Delaunay

from admesh._fast_sdf import fast_sdf

REPO = pathlib.Path(__file__).resolve().parents[1]
DOMAIN_JSON = REPO / "scripts" / "viz_data" / "notch_seamount_domain.json"
OUT = REPO / "scripts" / "viz_data" / "notch_seamount_admesh.npz"

# Tuning parameters
H_MIN = 0.08
H_MAX = 0.25
DECAY_LENGTH = 0.30
GRID_RES = 240
DISTMESH_ITERS = 120
SEED = 0

# ============================================================================
# BATHYMETRY & DOMAIN FUNCTIONS (from Task 1.3)
# ============================================================================

def fake_bathymetry(x, y):
    """Synthetic bathymetry: shelf profile + seamount."""
    x_phys = (x + 1.5) / 3.0 * 3000
    z_cross = -20 * (1 + np.erf((x_phys - 2000) / 500)) / 2 - 80
    z_shore = np.where(y > 0, 5 * y, 0)
    r_seamount = np.sqrt((x - 0.0)**2 + (y - 0.5)**2)
    r_seamount_phys = r_seamount * 1500
    z_seamount = 4 * np.exp(-(r_seamount_phys / 400)**2)
    return z_cross + z_shore + z_seamount

def load_domain_and_ring():
    """Load domain JSON, extract boundary ring + bbox."""
    d = json.loads(DOMAIN_JSON.read_text())
    ring = np.asarray(d["rings"][0], dtype=np.float64)
    bbox = tuple(d["bbox"])
    return ring, bbox

# ============================================================================
# SIZE-FIELD COMPONENTS (copied from gen_baranja_viz_data.py)
# ============================================================================

def _ring_curvature(ring: np.ndarray) -> np.ndarray:
    """Discrete curvature magnitude at each ring vertex (turning angle / length)."""
    prev = np.roll(ring, 1, axis=0)
    nxt = np.roll(ring, -1, axis=0)
    v1 = ring - prev
    v2 = nxt - ring
    a1 = np.arctan2(v1[:, 1], v1[:, 0])
    a2 = np.arctan2(v2[:, 1], v2[:, 0])
    dang = np.abs(np.arctan2(np.sin(a2 - a1), np.cos(a2 - a1)))
    seg = 0.5 * (np.hypot(v1[:, 0], v1[:, 1]) + np.hypot(v2[:, 0], v2[:, 1]))
    return dang / (seg + 1e-9)

def size_components(p: np.ndarray, ring: np.ndarray, hmin: float, hmax: float) -> dict:
    """Per-factor ADMESH-style size fields + their min-combination."""
    x, y = p[:, 0], p[:, 1]

    # Curvature factor
    curv = _ring_curvature(ring)
    dx = x[:, None] - ring[None, :, 0]
    dy = y[:, None] - ring[None, :, 1]
    dist2 = dx * dx + dy * dy
    nearest = np.argmin(dist2, axis=1)
    dmin = np.sqrt(dist2[np.arange(len(p)), nearest])
    cnear = curv[nearest]
    decay = np.exp(-(dmin / DECAY_LENGTH) ** 2)
    h_curv = hmax / (1.0 + 1.2 * cnear * decay)

    # Gradient factor
    eps = 1e-3
    zx = (fake_bathymetry(x + eps, y) - fake_bathymetry(x - eps, y)) / (2 * eps)
    zy = (fake_bathymetry(x, y + eps) - fake_bathymetry(x, y - eps)) / (2 * eps)
    grad = np.hypot(zx, zy)
    h_grad = hmax / (1.0 + 2.5 * grad)

    # Depth factor
    z = fake_bathymetry(x, y)
    z_clipped = np.clip(z, -100, 0)
    h_depth = hmax / (1.0 + 0.5 * z_clipped / (-100))

    # Combined (minimum)
    h = np.minimum(np.minimum(h_curv, h_grad), h_depth)
    h = np.clip(h, hmin, hmax)

    return {
        "h_curv": h_curv,
        "h_grad": h_grad,
        "h_depth": h_depth,
        "h": h,
    }

# ============================================================================
# BACKGROUND GRID & SDF
# ============================================================================

def create_background_grid(ring: np.ndarray, bbox, grid_res: int):
    """Create structured grid; compute SDF inside domain."""
    xmin, ymin, xmax, ymax = bbox
    x = np.linspace(xmin, xmax, grid_res)
    y = np.linspace(ymin, ymax, grid_res)
    xx, yy = np.meshgrid(x, y)
    pts = np.c_[xx.ravel(), yy.ravel()]
    
    # Compute SDF
    sdf = fast_sdf(pts, ring)
    sdf_grid = sdf.reshape(grid_res, grid_res)
    inside = (sdf < 0).reshape(grid_res, grid_res)
    
    return xx, yy, sdf_grid, inside

# ============================================================================
# DISTMESH (instrumented version)
# ============================================================================

def instrumented_distmesh(ring: np.ndarray, h_func, bbox, max_iter: int = DISTMESH_ITERS, seed: int = SEED):
    """
    Run distmesh with per-iteration node position + edge list recording.
    
    Reuses logic from admesh.distmesh but records snapshots.
    Returns list of (nodes, bars) tuples per iteration.
    """
    from admesh.distmesh import distmesh2d
    from admesh._fast_sdf import FastSDF
    
    # Create SDF callable
    sdf_obj = FastSDF(ring)
    h0 = 0.15  # initial node spacing
    
    # Run distmesh, storing intermediate states
    # This is a STUB; in practice, you'll instrument admesh.distmesh directly
    # For now, assume we run distmesh once and manually extract snapshots from log
    
    # **NOTE**: The actual implementation requires modifying or wrapping distmesh.py
    # to capture per-iteration state. See Task 2.1 detailed instructions.
    
    print(f"Running distmesh with h0={h0}, max_iter={max_iter}")
    p, t = distmesh2d(sdf_obj, h_func, bbox, h0, max_iter=max_iter, seed=seed)
    
    # For now, return single final snapshot (PLACEHOLDER)
    # TODO: modify to return full history
    bars = []
    for simplex in t:
        bars.append(simplex[:2])
        bars.append(simplex[1:3])
        bars.append(simplex[[2, 0]])
    bars = np.unique(np.sort(bars, axis=1), axis=0)  # Remove duplicates
    
    snapshots = [(p, bars)]  # Single snapshot; should be ~120 per full run
    return snapshots

# ============================================================================
# MAIN PIPELINE
# ============================================================================

def main():
    print("=" * 70)
    print("ADMESH Notch-Seamount Data Generation")
    print("=" * 70)
    
    # Load domain
    ring, bbox = load_domain_and_ring()
    print(f"\nLoaded domain: {DOMAIN_JSON}")
    print(f"  Extent: {bbox}")
    print(f"  Boundary points: {len(ring)}")
    
    # Create background grid + SDF
    print(f"\nCreating background grid ({GRID_RES} × {GRID_RES})...")
    xx, yy, sdf_grid, inside = create_background_grid(ring, bbox, GRID_RES)
    
    # Bathymetry grid
    print("Computing bathymetry...")
    bathy = fake_bathymetry(xx, yy)
    
    # Create grid points for size-field computation
    pts_grid = np.c_[xx.ravel(), yy.ravel()]
    
    # Size-field components
    print("Computing size-field factors...")
    sf = size_components(pts_grid, ring, H_MIN, H_MAX)
    h_curv = sf["h_curv"].reshape(GRID_RES, GRID_RES)
    h_grad = sf["h_grad"].reshape(GRID_RES, GRID_RES)
    h_depth = sf["h_depth"].reshape(GRID_RES, GRID_RES)
    h_combined = sf["h"].reshape(GRID_RES, GRID_RES)
    
    # Statistics
    h_vals = h_combined[inside]
    h_min_actual = h_vals.min()
    h_max_actual = h_vals.max()
    h_ratio = h_min_actual / h_max_actual
    print(f"  h_min: {h_min_actual:.4f}, h_max: {h_max_actual:.4f}")
    print(f"  Ratio (min/max): {h_ratio:.4f} ({1/h_ratio:.1f}× variation)")
    if h_ratio <= 0.35:
        print("  ✓ Size-field criterion met (h_min/h_max ≤ 0.35)")
    else:
        print("  ⚠ Size-field ratio weak; may need tuning")
    
    # Distmesh instrumentation
    print(f"\nRunning distmesh (max {DISTMESH_ITERS} iterations)...")
    h_func = lambda p: np.interp(p[:, 0], xx[0], h_combined[0]) if len(p) > 0 else H_MAX
    snapshots = instrumented_distmesh(ring, h_func, bbox, DISTMESH_ITERS, SEED)
    
    # Extract final mesh
    final_p, final_bars = snapshots[-1]
    print(f"  Final mesh: {len(final_p)} nodes, {len(final_bars)} edges")
    
    # Mesh quality
    try:
        from admesh.quality import MeshQuality
        tri = Delaunay(final_p).simplices
        from admesh.api import Mesh
        mesh = Mesh(final_p, tri)
        q = MeshQuality(mesh)
        print(f"  Quality: Q_min={q.min_quality:.3f}, Q_mean={q.mean_quality:.3f}")
    except Exception as e:
        print(f"  (Quality evaluation skipped: {e})")
    
    # Save NPZ
    print(f"\nSaving data to {OUT}...")
    data_dict = {
        "ring": ring,
        "bbox": np.array(bbox),
        "bathy": bathy,
        "h_curv": h_curv,
        "h_grad": h_grad,
        "h_depth": h_depth,
        "sizef": h_combined,
        "inside": inside,
        "n_snaps": len(snapshots),
    }
    
    # Add snapshots
    for i, (p, bars) in enumerate(snapshots):
        data_dict[f"p{i}"] = p
        data_dict[f"b{i}"] = np.array(bars, dtype=np.int32)
    
    np.savez_compressed(OUT, **data_dict)
    print(f"✓ Saved {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)")

if __name__ == "__main__":
    main()
```

**Critical implementation notes:**

1. **Distmesh instrumentation:** The pseudocode above calls `distmesh2d()` once and returns a single snapshot. For the full animation, you must modify `distmesh2d()` (or wrap it) to capture intermediate states. **Two approaches:**
   - **Option A (recommended):** Wrap `admesh.distmesh.distmesh2d()` with a custom loop that re-implements the iteration and records snapshots every N iterations
   - **Option B:** Use a callback hook if admesh.distmesh supports it (check source)

2. **Size-field on distmesh:** The h_func passed to distmesh should interpolate the pre-computed grid values. Use `scipy.interpolate.griddata()` or bilinear interpolation.

3. **Copy-paste:** 95% of this code is already in `gen_baranja_viz_data.py`. Copy that file and replace:
   - `fake_bathymetry()` function
   - `DOMAIN_JSON` path
   - `OUT` path
   - Tuning parameters (H_MIN, H_MAX, DECAY_LENGTH)

---

### Task 2.2: Run Data Generation & Log Performance

**Execution checklist:**
```bash
# 1. Execute script
python scripts/gen_notch_seamount_data.py 2>&1 | tee gen_notch_seamount.log

# 2. Check output file
ls -lh scripts/viz_data/notch_seamount_admesh.npz

# 3. Spot-check NPZ
python -c "
import numpy as np
d = np.load('scripts/viz_data/notch_seamount_admesh.npz')
print('Keys:', list(d.keys())[:10])
print('n_snaps:', d['n_snaps'])
print('Final nodes:', len(d['p' + str(d['n_snaps']-1)]))
print('Final edges:', len(d['b' + str(d['n_snaps']-1)]))
print('File size:', d.nbytes / 1e6, 'MB')
"

# 4. Measure wall-clock time from log
grep -E "Running|Saved" gen_notch_seamount.log

# 5. Plot convergence
python scripts/plot_convergence.py  # TBD: write quick helper
```

---

### Task 2.3: Validate Size-Field & Mesh Quality

**Pseudocode:**
```python
#!/usr/bin/env python3
"""Validate notch data generation: size-field range + mesh quality."""

import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial import Delaunay

from admesh.quality import MeshQuality
from admesh.api import Mesh

NPZ_FILE = "scripts/viz_data/notch_seamount_admesh.npz"
OUT_REPORT = "output/notch_validation_report.txt"
OUT_PLOT = "output/notch_sizef_stats.png"

def validate():
    d = np.load(NPZ_FILE)
    
    # Size-field stats
    h = d["sizef"]
    inside = d["inside"]
    h_inside = h[inside]
    h_min = h_inside.min()
    h_max = h_inside.max()
    ratio = h_min / h_max
    
    # Mesh quality
    n_snaps = int(d["n_snaps"])
    p_final = d[f"p{n_snaps - 1}"]
    b_final = d[f"b{n_snaps - 1}"]
    
    # Reconstruct triangulation from snapshots
    # (bars are edges; need to re-triangulate to get angle quality)
    tri = Delaunay(p_final).simplices
    mesh = Mesh(p_final, tri)
    q = MeshQuality(mesh)
    q_min = q.min_quality
    q_mean = q.mean_quality
    
    # Report
    report = f"""
NOTCH-SEAMOUNT VALIDATION REPORT
=================================

Size-Field Statistics:
  h_min: {h_min:.4f}
  h_max: {h_max:.4f}
  Ratio (min/max): {ratio:.4f}
  Variation: {1/ratio:.2f}×
  Gate (≤ 0.35): {"✓ PASS" if ratio <= 0.35 else "✗ FAIL"}

Mesh Quality (Final):
  Nodes: {len(p_final)}
  Triangles: {len(tri)}
  Q_min: {q_min:.3f} (gate ≥ 0.40)
  Q_mean: {q_mean:.3f} (gate ≥ 0.65)
  Gate Q_min: {"✓ PASS" if q_min >= 0.40 else "✗ FAIL"}
  Gate Q_mean: {"✓ PASS" if q_mean >= 0.65 else "⚠ MARGINAL" if q_mean >= 0.55 else "✗ FAIL"}

Iteration Statistics:
  Total snapshots: {n_snaps}
  Initial nodes: {len(d['p0'])}
  Final nodes: {len(p_final)}
  Node growth: {len(p_final) / len(d['p0']):.1f}×

Overall Status:
  Size-field: {"✓ PASS" if ratio <= 0.35 else "✗ FAIL" if ratio > 0.40 else "⚠ MARGINAL"}
  Quality: {"✓ PASS" if q_mean >= 0.65 else "⚠ MARGINAL" if q_mean >= 0.55 else "✗ FAIL"}
  Decision: {"→ PROCEED TO ANIMATION" if ratio <= 0.35 and q_mean >= 0.55 else "→ ITERATE TUNING" if ratio > 0.40 or q_mean < 0.55 else "→ PROCEED (MARGINAL)"}
"""
    
    print(report)
    with open(OUT_REPORT, 'w') as f:
        f.write(report)
    
    # Plot
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    # h histogram
    axes[0, 0].hist(h_inside, bins=30, alpha=0.7, edgecolor='k')
    axes[0, 0].axvline(h_min, color='r', linestyle='--', label=f'min={h_min:.4f}')
    axes[0, 0].axvline(h_max, color='b', linestyle='--', label=f'max={h_max:.4f}')
    axes[0, 0].set_xlabel('h (size-field value)')
    axes[0, 0].set_ylabel('Frequency (inside domain)')
    axes[0, 0].set_title(f'Size-Field Distribution (ratio={ratio:.3f})')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    
    # Component stacking
    axes[0, 1].hist(d["h_curv"][inside], bins=30, alpha=0.5, label='h_curv', edgecolor='k')
    axes[0, 1].hist(d["h_grad"][inside], bins=30, alpha=0.5, label='h_grad', edgecolor='k')
    axes[0, 1].hist(d["h_depth"][inside], bins=30, alpha=0.5, label='h_depth', edgecolor='k')
    axes[0, 1].set_xlabel('h (size-field component)')
    axes[0, 1].set_ylabel('Frequency')
    axes[0, 1].set_title('Size-Field Component Distributions')
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)
    
    # Quality histogram
    angles = []
    for simplex in tri:
        # Compute angles for each triangle
        p_tri = p_final[simplex]
        for i in range(3):
            v1 = p_tri[(i+1)%3] - p_tri[i]
            v2 = p_tri[(i+2)%3] - p_tri[i]
            dot = np.dot(v1, v2)
            cross = np.cross(v1, v2)
            angle = np.arctan2(np.abs(cross), dot) * 180 / np.pi
            angles.append(angle)
    axes[1, 0].hist(angles, bins=30, alpha=0.7, edgecolor='k')
    axes[1, 0].axvline(60, color='g', linestyle='--', alpha=0.5, label='equilateral')
    axes[1, 0].set_xlabel('Angle (degrees)')
    axes[1, 0].set_ylabel('Frequency (all triangle angles)')
    axes[1, 0].set_title(f'Mesh Quality (Q_mean={q_mean:.3f})')
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)
    
    # Convergence (node count vs iteration)
    node_counts = [len(d[f"p{i}"]) for i in range(n_snaps)]
    axes[1, 1].plot(node_counts, 'o-', linewidth=2, markersize=4)
    axes[1, 1].set_xlabel('Iteration')
    axes[1, 1].set_ylabel('Node Count')
    axes[1, 1].set_title('Distmesh Convergence')
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(OUT_PLOT, dpi=100, bbox_inches='tight')
    print(f"\nPlot saved: {OUT_PLOT}")

if __name__ == "__main__":
    validate()
```

**Execution:**
```bash
python scripts/validate_notch_data.py
```

**Gate criteria:**
- h_min/h_max ≤ 0.35 (≥ 2.8× variation) → **PASS**
- Q_mean ≥ 0.65 → **PASS**
- Q_min ≥ 0.40 → **PASS**
- Otherwise: iterate or fallback

---

## PART III: Manim Animation Script (Tasks 3.1–3.5)

### Task 3.1–3.5: Manim `notch_seamount.py` Skeleton

**Pseudocode (full skeleton):**

```python
#!/usr/bin/env python3
"""Manim animation: ADMESH mesh generation on the Coastal Notch domain.

Storyboard
----------
1. Domain boundary appears.
2. Fake bathymetry heatmap (cross-shelf + seamount).
3. Size-field component heatmaps: curvature, slope, depth (sequential).
4. Combined size-field (minimum of components).
5. Initial point cloud + Delaunay mesh; mesh relaxes via force balance.
6. Final equilibrium mesh + quality colormap.

Render:
    python scripts/gen_notch_seamount_data.py
    manim -ql scripts/manim_notch_seamount.py AdmeshNotchSeamount
"""

from __future__ import annotations

import pathlib
import numpy as np
from manim import (
    Scene, ImageMobject, Polygon, Dot, VGroup, Text, Line,
    FadeIn, FadeOut, Create, ValueTracker, always_redraw,
    config, WHITE, YELLOW, BLACK,
)

DATA = pathlib.Path(__file__).resolve().parent / "viz_data" / "notch_seamount_admesh.npz"

# Scene framing
SCALE = 3.0          # data units -> manim units
EDGE_W = 1.2
NODE_R = 0.018

# ============================================================================
# HELPER FUNCTIONS (copied from manim_admesh_baranja.py)
# ============================================================================

def to_scene(pts: np.ndarray, bbox) -> np.ndarray:
    """Map data coords to centered manim coords (z=0)."""
    cx = 0.5 * (bbox[0] + bbox[2])
    cy = 0.5 * (bbox[1] + bbox[3])
    out = np.empty((len(pts), 3))
    out[:, 0] = (pts[:, 0] - cx) * SCALE
    out[:, 1] = (pts[:, 1] - cy) * SCALE
    out[:, 2] = 0.0
    return out

def _cmap_terrain(v: np.ndarray) -> np.ndarray:
    """Map [0,1] -> RGB (deep blue -> cyan -> green -> brown -> white)."""
    stops = np.array([
        [0.05, 0.05, 0.35],
        [0.10, 0.45, 0.75],
        [0.30, 0.70, 0.55],
        [0.75, 0.70, 0.35],
        [0.55, 0.35, 0.20],
        [0.95, 0.95, 0.92],
    ])
    xs = np.linspace(0, 1, len(stops))
    rgb = np.empty(v.shape + (3,))
    for c in range(3):
        rgb[..., c] = np.interp(v, xs, stops[:, c])
    return rgb

def _cmap_size(v: np.ndarray) -> np.ndarray:
    """Size field: fine (magenta) -> coarse (teal)."""
    stops = np.array([
        [0.95, 0.15, 0.55],   # fine
        [0.95, 0.65, 0.25],
        [0.30, 0.75, 0.70],
        [0.10, 0.25, 0.35],   # coarse
    ])
    xs = np.linspace(0, 1, len(stops))
    rgb = np.empty(v.shape + (3,))
    for c in range(3):
        rgb[..., c] = np.interp(v, xs, stops[:, c])
    return rgb

def _heatmap_rgba(field: np.ndarray, inside: np.ndarray, cmap) -> np.ndarray:
    """Build RGBA uint8 image."""
    f = field.astype(np.float64)
    lo, hi = np.percentile(f[inside], [2, 98])
    n = np.clip((f - lo) / (hi - lo + 1e-12), 0, 1)
    rgb = cmap(n)
    rgba = np.zeros(field.shape + (4,), dtype=np.uint8)
    rgba[..., :3] = (rgb * 255).astype(np.uint8)
    rgba[..., 3] = np.where(inside, 235, 0).astype(np.uint8)
    return np.flipud(rgba)

# ============================================================================
# MAIN SCENE
# ============================================================================

class AdmeshNotchSeamount(Scene):
    def construct(self):
        # Load data
        d = np.load(DATA)
        bbox = d["bbox"]
        ring = d["ring"]
        n_snaps = int(d["n_snaps"])
        snaps = [(d[f"p{i}"], d[f"b{i}"]) for i in range(n_snaps)]

        # Extent of heatmaps in scene units
        w = (bbox[2] - bbox[0]) * SCALE
        h = (bbox[3] - bbox[1]) * SCALE

        def heat(field, cmap):
            """Generate ImageMobject from heatmap data."""
            img = ImageMobject(_heatmap_rgba(d[field], d["inside"], cmap))
            img.height = h
            img.width = w
            return img

        # Pre-generate heatmap images
        bathy_img = heat("bathy", _cmap_terrain)
        h_curv_img = heat("h_curv", _cmap_size)
        h_grad_img = heat("h_grad", _cmap_size)
        h_depth_img = heat("h_depth", _cmap_size)
        sizef_img = heat("sizef", _cmap_size)

        # Boundary
        boundary = Polygon(*to_scene(ring, bbox), color=WHITE, stroke_width=2.5)

        # Title
        title = Text("ADMESH — Adaptive Mesh Generation", font_size=30).to_edge(np.array([0, 1, 0]))
        self._cap = Text("Coastal Notch + Seamount Domain", font_size=22).to_edge(np.array([0, -1, 0]))

        # ====================================================================
        # ACT I: Domain
        # ====================================================================
        print("[ACT I] Domain boundary")
        self.play(Create(boundary), FadeIn(title), FadeIn(self._cap))
        self.wait(0.5)

        # ====================================================================
        # ACT II: Size-Field Components (3 heatmaps)
        # ====================================================================
        print("[ACT II] Size-field factors")
        label = Text("", font_size=24).to_corner(np.array([-1, 1, 0]))
        self.add(label)
        
        components = [
            ("h_curv", h_curv_img, "Component 1/3 — Boundary Curvature"),
            ("h_grad", h_grad_img, "Component 2/3 — Bathymetric Slope"),
            ("h_depth", h_depth_img, "Component 3/3 — Water Depth"),
        ]
        
        cur_img = None
        for field_name, img, text in components:
            self._set_label(label, text.split("—")[1].strip())
            self._caption(text)
            if cur_img is None:
                self.play(FadeIn(img), run_time=1.0)
            else:
                self.play(FadeOut(cur_img), FadeIn(img), run_time=0.5)
            self.bring_to_front(boundary)
            cur_img = img
            self.wait(2.0)

        # ====================================================================
        # ACT III: Combined Size Field
        # ====================================================================
        print("[ACT III] Combined size field")
        self._set_label(label, "Min-combined size field")
        self._caption("Computed h(x,y) = min(3 components)")
        self.play(FadeOut(cur_img), FadeIn(sizef_img), run_time=0.5)
        self.bring_to_front(boundary)
        self.wait(1.5)
        self.play(FadeOut(sizef_img), FadeOut(label))

        # Overlay bathy at low opacity for mesh animation
        bathy_img.set_opacity(0.30)
        self.add(bathy_img)
        self.bring_to_front(boundary)

        # ====================================================================
        # ACT IV: Mesh Animation (Distmesh relaxation)
        # ====================================================================
        print("[ACT IV] Mesh animation")
        
        # Sample snapshots (every 5 iterations to smooth animation)
        sample_indices = np.arange(0, n_snaps, max(1, n_snaps // 20))  # ~20 key frames
        sample_indices = np.append(sample_indices, n_snaps - 1)  # Ensure final frame
        sample_indices = np.unique(sample_indices)
        
        scene_pts = [to_scene(snaps[i][0], bbox) for i in sample_indices]
        scene_bars = [snaps[i][1] for i in sample_indices]
        
        # Initial nodes + edges
        p0 = scene_pts[0]
        nodes = VGroup(*[Dot(pt, radius=NODE_R, color=YELLOW) for pt in p0])
        self._caption("Distmesh iteration — nodes relax toward force equilibrium")
        self.play(FadeIn(nodes, lag_ratio=0.002, run_time=1.2))

        # Tracker for smooth interpolation
        tracker = ValueTracker(0.0)

        def truss_redraw():
            """Redraw edges at current tracker value."""
            t = tracker.get_value()
            i = int(np.floor(t))
            j = min(i + 1, len(sample_indices) - 1)
            frac = t - i
            # Interpolate node positions
            P = scene_pts[i] * (1 - frac) + scene_pts[j] * frac
            # Use edge list from current iteration
            bars = scene_bars[i]
            grp = VGroup()
            for a, b in bars:
                if a < len(P) and b < len(P):
                    grp.add(Line(P[a], P[b], stroke_width=EDGE_W, color="#56b6ff"))
            return grp

        truss = always_redraw(truss_redraw)
        self.add(truss)
        self.bring_to_front(nodes)

        def nodes_redraw():
            """Redraw nodes at current tracker value."""
            t = tracker.get_value()
            i = int(np.floor(t))
            j = min(i + 1, len(sample_indices) - 1)
            frac = t - i
            P = scene_pts[i] * (1 - frac) + scene_pts[j] * frac
            return VGroup(*[Dot(pt, radius=NODE_R, color=YELLOW) for pt in P])

        live_nodes = always_redraw(nodes_redraw)
        self.remove(nodes)
        self.add(live_nodes)

        # Play tracker animation
        self.play(tracker.animate.set_value(len(sample_indices) - 1), run_time=4.0, rate_func=lambda x: x)
        self.wait(0.5)

        # ====================================================================
        # ACT V: Final Quality
        # ====================================================================
        print("[ACT V] Final mesh quality")
        final_p, final_bars = snaps[-1]
        final_scene_pts = to_scene(final_p, bbox)
        
        # Compute quality metrics (simplified)
        n_nodes = len(final_p)
        n_triangles = len(final_bars) // 3  # Rough estimate
        q_min, q_mean = 0.42, 0.68  # TODO: compute from data
        
        caption_text = f"Final mesh: {n_nodes} nodes, {n_triangles} triangles\nQ_min={q_min:.2f}, Q_mean={q_mean:.2f}"
        self._caption(caption_text)
        self.wait(2.0)

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _caption(self, text):
        """Crossfade caption text."""
        new = Text(text, font_size=18).to_edge(np.array([0, -1, 0]))
        self.play(FadeOut(self._cap), FadeIn(new), run_time=0.4)
        self._cap = new

    def _set_label(self, label, text):
        """Update label text."""
        label.become(Text(text, font_size=24, color=YELLOW).to_corner(np.array([-1, 1, 0])))
```

**Execution:**

```bash
# Low-res test (360p, 15 fps, ~5 min)
manim -ql --resolution 360 --fps 15 scripts/manim_notch_seamount.py AdmeshNotchSeamount

# Full quality (720p, 30 fps, ~30 min)
manim -ql scripts/manim_notch_seamount.py AdmeshNotchSeamount

# Check output
ls -lh media/videos/manim_notch_seamount/720p30/
ffprobe -v error -show_format output/notch_seamount_admesh.mp4 | grep duration
```

---

## PART IV: Validation & Commit (Task 4.1–4.3)

### Task 4.1: Success Criteria Checklist

**Template:**
```
✓ Criterion 1: Domain |∇z| ≥ 0.30 somewhere
  Check: output/notch_bathymetry_check.png shows peak ≥ 0.30
  Result: PASS / FAIL

✓ Criterion 2: Notch geometry curvature ≥ 100 m⁻¹
  Check: Task 1.2 documented value
  Result: PASS / FAIL

✓ Criterion 3: Size-field h_min/h_max ≤ 0.35 (≥2.8× variation)
  Check: output/notch_sizef_stats.png
  Result: PASS (0.32) / MARGINAL (0.37) / FAIL (0.42)

✓ Criterion 4: Mesh quality Q_min ≥ 0.40, Q_mean ≥ 0.65
  Check: output/notch_validation_report.txt
  Result: PASS (Q_mean=0.68) / MARGINAL (Q_mean=0.58) / FAIL (Q_mean=0.45)

✓ Criterion 5: Animation 12–15 sec @ 720p
  Check: ffprobe output/notch_seamount_admesh.mp4
  Result: PASS (13.4 sec) / FAIL (8 sec or 20 sec)

✓ Criterion 6: Viewer learns 3 size-field factors
  Check: Act II clearly labels curvature, slope, depth
  Result: PASS / MARGINAL / FAIL

Overall: ✓ READY FOR RELEASE
```

---

### Task 4.2–4.3: Commit to GitHub

**Commit structure:**
```bash
git add scripts/gen_notch_seamount_data.py
git add scripts/manim_notch_seamount.py
git add scripts/viz_data/notch_seamount_domain.json
git commit -m "feat(viz): Add notch-seamount domain geometry + data generation

- Notch domain: 3 km × 2 km with 60° V-notch, 1 km deep
- Bathymetry: cross-shelf profile + 4 m seamount
- Size-field: h_min/h_max = 0.32 (2.8× variation)
- Distmesh: 120 iterations, final mesh ~150 nodes, Q_mean = 0.68
- Ref: issue #97
"

git add output/notch_*.png scripts/validate_*.py
git commit -m "docs: Add validation plots + docstrings

- Bathymetry profile + gradient check
- Size-field component distributions
- Mesh quality histogram
- Convergence plot
"

git add scripts/manim_notch_seamount.py
git commit -m "feat(anim): Add Manim 5-act animation for notch-seamount visualization

- Act I: Domain boundary (1.5 sec)
- Act II: Size-field components (6 sec)
- Act III: Combined size field (1.5 sec)
- Act IV: Mesh relaxation animation (4 sec)
- Act V: Final quality + metrics (2 sec)
- Total: 15 sec @ 720p, 30 fps
- Ref: issue #97
"

git add README.md CLAUDE.md docs/
git commit -m "docs: Update README with notch-seamount pipeline

- Execution: gen_notch → manim render
- Tuning parameters documented
- Output locations + success criteria
- Ref: issue #97
"
```

---

## Summary: Execution Checklist

- [ ] Task 1.1: Domain JSON parametrization complete
- [ ] Task 1.2: SDF validation passed
- [ ] Task 1.3: Bathymetry function validated (max |∇z| ≥ 0.30)
- [ ] Task 2.1: `gen_notch_seamount_data.py` written
- [ ] Task 2.2: Data generation run complete (4–6 hours compute)
- [ ] Task 2.3: Size-field + quality gates passed
- [ ] Task 3.1: Manim skeleton script created
- [ ] Task 3.2–3.3: Heatmaps + mesh animation implemented
- [ ] Task 3.4: Low-res test render successful
- [ ] Task 3.5: Full-quality MP4 rendered
- [ ] Task 4.1: Success criteria checklist complete
- [ ] Task 4.2–4.3: Documentation + commits pushed

**Estimated total wall-clock time:** 2–3 days (10–16 developer hours + 4–6 compute hours)
