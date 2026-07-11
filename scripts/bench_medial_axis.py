"""Runtime + robustness baseline for grid-based medial-axis path (`_stages/medial_axis.py`).
Issue #200 / #186 T4 evaluation follow-up. Additive benchmark tooling — reads locked module,
does not modify it.
"""

import os
import json
import time
import numpy as np

from admesh.medial_axis import medial_distance_fmm, medial_axis_mask
from admesh._stages.distance import eval_sdf_grid
from admesh import domains


def rect_sdf(p, hx=1.0, hy=0.05):
    """Signed distance to axis-aligned rectangle."""
    dx = np.abs(p[:, 0]) - hx
    dy = np.abs(p[:, 1]) - hy
    ax = np.maximum(dx, 0.0)
    ay = np.maximum(dy, 0.0)
    outside = np.hypot(ax, ay)
    inside = np.minimum(np.maximum(dx, dy), 0.0)
    return outside + inside


def main():
    part_a = []
    part_b = []

    # PART A: runtime + accuracy vs δ
    print("=" * 90)
    print("PART A: Runtime + Accuracy vs Grid Resolution δ")
    print("=" * 90)
    print(f"{'Domain':<12} {'δ':<8} {'grid_cells':<12} {'secs':<10} {'max_err':<12} {'err/δ':<10}")
    print("-" * 90)

    for domain_name, domain_obj, analytic_fn in [
        ("UNIT_DISK", domains.UNIT_DISK, lambda r: r),
        ("ANNULUS", domains.ANNULUS, lambda r: np.abs(r - 0.7))
    ]:
        for delta in [0.08, 0.04, 0.02, 0.01, 0.005]:
            times = []
            X, Y, med = None, None, None
            for _ in range(3):
                start = time.perf_counter()
                X, Y, med = medial_distance_fmm(domain_obj.fd, domain_obj.bbox, delta)
                elapsed = time.perf_counter() - start
                times.append(elapsed)
            min_time = min(times)

            grid_cells = X.size
            r = np.hypot(X, Y)
            analytic = analytic_fn(r)

            if domain_name == "UNIT_DISK":
                band = (r > 0.2) & (r < 0.8) & np.isfinite(med)
            else:
                band = (r > 0.5) & (r < 0.9) & np.isfinite(med)

            if band.any():
                max_err = float(np.max(np.abs(med[band] - analytic[band])))
                err_over_delta = max_err / delta
            else:
                max_err, err_over_delta = np.nan, np.nan

            part_a.append({
                "domain": domain_name,
                "delta": float(delta),
                "grid_cells": int(grid_cells),
                "secs": float(min_time),
                "max_err": float(max_err),
                "err_over_delta": float(err_over_delta)
            })

            print(f"{domain_name:<12} {delta:<8.3f} {grid_cells:<12} {min_time:<10.4f} "
                  f"{max_err:<12.6f} {err_over_delta:<10.4f}")

    # PART B: thin-channel robustness
    print("\n" + "=" * 90)
    print("PART B: Thin-Channel Robustness (horizontal rectangle)")
    print("=" * 90)
    print(f"{'δ':<10} {'w/δ ratio':<15} {'ma_cells':<12} {'detected':<10}")
    print("-" * 90)

    bbox = (-1.2, -0.3, 1.2, 0.3)
    w = 0.05

    for delta in [0.1, 0.05, 0.02, 0.01]:
        X, Y, D = eval_sdf_grid(rect_sdf, bbox, delta)
        ma = medial_axis_mask(D, delta)

        ratio = w / delta
        ma_cells = int(ma.sum())
        detected = bool(ma.any())

        part_b.append({
            "delta": float(delta),
            "ratio_w_over_delta": float(ratio),
            "ma_cells": int(ma_cells),
            "detected": bool(detected)
        })

        print(f"{delta:<10.3f} {ratio:<15.2f} {ma_cells:<12} {str(detected):<10}")

    # Write JSON
    output_dir = "/home/user/ADMESH/output"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "T4_medial_baseline.json")
    with open(output_file, "w") as f:
        json.dump({"part_a": part_a, "part_b": part_b}, f, indent=2)

    print("\n" + "=" * 90)
    print(f"Baseline written to {output_file}")
    print("=" * 90)


if __name__ == "__main__":
    main()
