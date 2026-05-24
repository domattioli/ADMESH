//! Size-field composition stages — curvature, bathymetry, dominate_tide.
//!
//! Faithful Rust ports of `admesh._stages.{curvature, bathymetry, dominate_tide}`.
//! All work on grid-shape `Array2<f64>` (rows = LY, cols = LX) using the
//! same MATLAB-faithful formulas the Python port uses.
//!
//! Composition convention (Constitution Principle I): each `apply_*`
//! function returns `min(h_new, h0)` element-wise. Stages compose by
//! threading the result through the next stage's `h0` argument.

use crate::stages::grad_sdf;
use ndarray::{Array2, ArrayView2};

const GRAD_EPS: f64 = 1e-3;
const G_GRAV: f64 = 9.81;

// ───────────────────────────────────────────────────────────────────────────
// curvature — κ = ∇·(∇D/|∇D|) on the SDF level sets
// ───────────────────────────────────────────────────────────────────────────

/// Curvature of the level sets of a sampled SDF.
/// Mirrors `admesh._stages.curvature.curvature_grid`.
///
/// Cells with `|∇D| < grad_eps` are masked to NaN.
pub fn curvature_grid(d: ArrayView2<f64>, delta: f64, grad_eps: f64) -> Array2<f64> {
    let (gx, gy) = grad_sdf(d, delta);
    let (ny, nx) = (d.nrows(), d.ncols());
    let mut nx_arr = Array2::<f64>::zeros((ny, nx));
    let mut ny_arr = Array2::<f64>::zeros((ny, nx));
    let mut mask = Array2::<bool>::default((ny, nx));
    for j in 0..ny {
        for i in 0..nx {
            let m = (gx[(j, i)] * gx[(j, i)] + gy[(j, i)] * gy[(j, i)]).sqrt();
            if m < grad_eps {
                mask[(j, i)] = true;
            } else {
                nx_arr[(j, i)] = gx[(j, i)] / m;
                ny_arr[(j, i)] = gy[(j, i)] / m;
            }
        }
    }
    let (dnx_dx, _) = grad_sdf(nx_arr.view(), delta);
    let (_, dny_dy) = grad_sdf(ny_arr.view(), delta);
    let mut kappa = Array2::<f64>::zeros((ny, nx));
    for j in 0..ny {
        for i in 0..nx {
            if mask[(j, i)] {
                kappa[(j, i)] = f64::NAN;
            } else {
                kappa[(j, i)] = dnx_dx[(j, i)] + dny_dy[(j, i)];
            }
        }
    }
    kappa
}

/// Compose κ-driven size-reduction into `h0`. Faithful port of
/// `admesh._stages.curvature.apply_curvature`.
pub fn apply_curvature(
    h0: ArrayView2<f64>,
    d: ArrayView2<f64>,
    delta: f64,
    k_per_radian: f64,
    g: f64,
    hmax: f64,
    hmin: f64,
) -> Array2<f64> {
    let (gx, gy) = grad_sdf(d, delta);
    let (ny, nx) = (d.nrows(), d.ncols());

    // Normalised gradient direction (only used where |∇D| > 0).
    let mut nx_arr = Array2::<f64>::zeros((ny, nx));
    let mut ny_arr = Array2::<f64>::zeros((ny, nx));
    for j in 0..ny {
        for i in 0..nx {
            let m = (gx[(j, i)] * gx[(j, i)] + gy[(j, i)] * gy[(j, i)]).sqrt();
            if m > 0.0 {
                nx_arr[(j, i)] = gx[(j, i)] / m;
                ny_arr[(j, i)] = gy[(j, i)] / m;
            }
        }
    }
    let (dnx_dx, _) = grad_sdf(nx_arr.view(), delta);
    let (_, dny_dy) = grad_sdf(ny_arr.view(), delta);

    let k_over_pi = k_per_radian / std::f64::consts::PI;
    let mut h_curve = Array2::<f64>::from_elem((ny, nx), hmax);

    for j in 0..ny {
        for i in 0..nx {
            let d_ji = d[(j, i)];
            if d_ji.abs() > 2.0 * hmin {
                continue;
            }
            let kappa = (dnx_dx[(j, i)] + dny_dy[(j, i)]).abs();
            let h_band = if kappa > 1e-12 {
                ((1.0 + kappa * d_ji.abs()) / (k_over_pi * kappa)).abs() - g * d_ji
            } else {
                hmax
            };
            h_curve[(j, i)] = h_band.clamp(hmin, hmax);
        }
    }

    // min(h_curve, h0)
    let mut out = h0.to_owned();
    for j in 0..ny {
        for i in 0..nx {
            out[(j, i)] = out[(j, i)].min(h_curve[(j, i)]);
        }
    }
    out
}

// ───────────────────────────────────────────────────────────────────────────
// bathymetry — h_bathy = s · |Z| / |∇Z|
// ───────────────────────────────────────────────────────────────────────────

/// Apply bathymetry-driven mesh-size contribution.
/// Faithful port of `admesh._stages.bathymetry.apply_bathymetry`.
pub fn apply_bathymetry(
    h0: ArrayView2<f64>,
    d: ArrayView2<f64>,
    z: ArrayView2<f64>,
    delta: f64,
    s: f64,
    hmin: f64,
    hmax: f64,
    mask_boundary_band: bool,
) -> Array2<f64> {
    assert_eq!(h0.shape(), d.shape());
    assert_eq!(h0.shape(), z.shape());
    let (ny, nx) = (z.nrows(), z.ncols());

    // 4th-order central difference of Z (interior only; MATLAB leaves
    // borders at 0). Reuses grad_sdf which already implements this stencil
    // with proper border handling. Take only the interior 4th-order
    // contribution by zeroing the 2nd-order border bands.
    let mut grad_bx = Array2::<f64>::zeros((ny, nx));
    let mut grad_by = Array2::<f64>::zeros((ny, nx));
    if nx >= 5 && ny >= 5 {
        for j in 2..ny - 2 {
            for i in 2..nx - 2 {
                grad_bx[(j, i)] = (z[(j, i - 2)] - 8.0 * z[(j, i - 1)]
                    + 8.0 * z[(j, i + 1)] - z[(j, i + 2)])
                    / (12.0 * delta);
                grad_by[(j, i)] = (z[(j - 2, i)] - 8.0 * z[(j - 1, i)]
                    + 8.0 * z[(j + 1, i)] - z[(j + 2, i)])
                    / (12.0 * delta);
            }
        }
    }

    let mut h_bathy = Array2::<f64>::from_elem((ny, nx), hmax);
    for j in 0..ny {
        for i in 0..nx {
            let gm = (grad_bx[(j, i)] * grad_bx[(j, i)]
                + grad_by[(j, i)] * grad_by[(j, i)])
                .sqrt();
            let val = if gm > 0.0 {
                s * z[(j, i)].abs() / gm
            } else {
                hmax
            };
            h_bathy[(j, i)] = if val.is_finite() {
                val.clamp(hmin, hmax)
            } else {
                hmax
            };

            if mask_boundary_band && d[(j, i)] >= -4.0 * hmin {
                h_bathy[(j, i)] = hmax;
            }
        }
    }

    // min(h_bathy, h0)
    let mut out = h0.to_owned();
    for j in 0..ny {
        for i in 0..nx {
            out[(j, i)] = out[(j, i)].min(h_bathy[(j, i)]);
        }
    }
    out
}

// ───────────────────────────────────────────────────────────────────────────
// dominate_tide — h_tide = (T / sz) · √(g · |Z|)
// ───────────────────────────────────────────────────────────────────────────

/// Apply tidal-wavelength mesh-size contribution.
/// Faithful port of `admesh._stages.dominate_tide.apply_tide`.
pub fn apply_tide(
    h0: ArrayView2<f64>,
    z: ArrayView2<f64>,
    tide_period: f64,
    tide_value: f64,
    hmin: f64,
    hmax: f64,
) -> Array2<f64> {
    assert_eq!(h0.shape(), z.shape());
    assert!(tide_value > 0.0, "tide_value must be positive");
    let (ny, nx) = (z.nrows(), z.ncols());
    let factor = tide_period / tide_value;

    let mut h_tide = Array2::<f64>::zeros((ny, nx));
    for j in 0..ny {
        for i in 0..nx {
            let v = factor * (G_GRAV * z[(j, i)].abs()).sqrt();
            h_tide[(j, i)] = if v == 0.0 { hmax } else { v.clamp(hmin, hmax) };
        }
    }
    let mut out = h0.to_owned();
    for j in 0..ny {
        for i in 0..nx {
            out[(j, i)] = out[(j, i)].min(h_tide[(j, i)]);
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use approx::assert_abs_diff_eq;

    #[test]
    fn curvature_of_disk_is_finite() {
        // SDF for unit disk: f(x,y) = sqrt(x² + y²) − 1. Curvature of
        // level set should equal 1/r at radius r (positive for outward
        // normal). Sample on 21x21 grid over [-1.5, 1.5].
        let n = 21;
        let mut d = Array2::<f64>::zeros((n, n));
        let h = 3.0 / (n as f64 - 1.0);
        for j in 0..n {
            for i in 0..n {
                let x = -1.5 + i as f64 * h;
                let y = -1.5 + j as f64 * h;
                d[(j, i)] = (x * x + y * y).sqrt() - 1.0;
            }
        }
        let kappa = curvature_grid(d.view(), h, 1e-3);
        // Interior values (away from |D|≈0) finite (not NaN)
        let mut any_finite = false;
        for j in 5..n - 5 {
            for i in 5..n - 5 {
                if kappa[(j, i)].is_finite() {
                    any_finite = true;
                }
            }
        }
        assert!(any_finite);
    }

    #[test]
    fn apply_tide_constant_depth() {
        let h0 = Array2::<f64>::from_elem((4, 4), 1000.0);
        let z = Array2::<f64>::from_elem((4, 4), 10.0); // 10 m depth
        let h = apply_tide(h0.view(), z.view(), 43200.0, 30.0, 10.0, 5000.0);
        // h_tide = (43200/30) · √(9.81·10) = 1440 · 9.905 = 14264 → clamped to hmax=5000.
        for &v in &h {
            assert_abs_diff_eq!(v, 1000.0, epsilon = 1e-6); // min(5000, 1000) = 1000
        }
    }

    #[test]
    fn apply_tide_dry_cells_keep_hmax() {
        let h0 = Array2::<f64>::from_elem((3, 3), 500.0);
        let z = Array2::<f64>::zeros((3, 3));
        let h = apply_tide(h0.view(), z.view(), 43200.0, 30.0, 10.0, 1000.0);
        for &v in &h {
            assert_abs_diff_eq!(v, 500.0, epsilon = 1e-12);
        }
    }

    #[test]
    fn apply_bathymetry_flat_z_keeps_h0() {
        let h0 = Array2::<f64>::from_elem((6, 6), 100.0);
        let d = Array2::<f64>::from_elem((6, 6), -10.0); // interior
        let z = Array2::<f64>::from_elem((6, 6), 50.0); // flat
        let h = apply_bathymetry(h0.view(), d.view(), z.view(),
            1.0, 0.5, 10.0, 1000.0, false);
        // ∇Z = 0 → h_bathy = hmax → min(hmax, 100) = 100 everywhere.
        for &v in &h {
            assert_abs_diff_eq!(v, 100.0, epsilon = 1e-12);
        }
    }
}
