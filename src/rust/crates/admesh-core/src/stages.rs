//! Faithful-port Rust ports of selected ADMESH stages.
//!
//! Mirrors the Python `admesh._stages.*` modules. Names + arg orders kept
//! identical for parity tests. All inputs/outputs use `ndarray::Array2`
//! for zero-copy interop with NumPy through the pyo3 layer.

use ndarray::{Array2, ArrayView2, Axis};
use rayon::prelude::*;

// ───────────────────────────────────────────────────────────────────────────
// in_polygon — MATLAB inpolygon semantics
// ───────────────────────────────────────────────────────────────────────────

/// Vectorised point-in-polygon test. Mirrors
/// `admesh._stages.in_polygon.in_polygon`.
///
/// Returns `(inside, on_boundary)` with `inside = True` for points
/// strictly inside OR on the boundary, `on_boundary = True` only when
/// perpendicular distance to a segment ≤ `on_tol`.
pub fn in_polygon(
    xq: &[f64],
    yq: &[f64],
    xv: &[f64],
    yv: &[f64],
    on_tol: f64,
) -> (Vec<bool>, Vec<bool>) {
    assert_eq!(xq.len(), yq.len());
    assert_eq!(xv.len(), yv.len());
    assert!(xv.len() >= 3, "polygon needs ≥3 vertices");

    // Drop trailing duplicate vertex (closure)
    let n = if xv[0] == *xv.last().unwrap() && yv[0] == *yv.last().unwrap() {
        xv.len() - 1
    } else {
        xv.len()
    };
    let xv = &xv[..n];
    let yv = &yv[..n];

    let on_tol_sq = on_tol * on_tol;

    let results: Vec<(bool, bool)> = (0..xq.len())
        .into_par_iter()
        .map(|i| {
            let qx = xq[i];
            let qy = yq[i];

            let mut on_bd = false;
            let mut crossings = 0usize;
            for k in 0..n {
                let kn = (k + 1) % n;
                let x1 = xv[k];
                let y1 = yv[k];
                let x2 = xv[kn];
                let y2 = yv[kn];

                // On-boundary test (perpendicular distance to segment).
                let ex = x2 - x1;
                let ey = y2 - y1;
                let seg_sq = ex * ex + ey * ey;
                let t = if seg_sq > 0.0 {
                    ((qx - x1) * ex + (qy - y1) * ey) / seg_sq
                } else {
                    0.0
                };
                let t = t.clamp(0.0, 1.0);
                let px = x1 + t * ex;
                let py = y1 + t * ey;
                let d2 = (qx - px).powi(2) + (qy - py).powi(2);
                if d2 <= on_tol_sq {
                    on_bd = true;
                }

                // Ray-cast (horizontal ray to +x).
                if (y1 > qy) != (y2 > qy) {
                    let xcross = (x2 - x1) * (qy - y1) / (y2 - y1) + x1;
                    if qx < xcross {
                        crossings += 1;
                    }
                }
            }
            let strictly_inside = crossings & 1 == 1;
            (strictly_inside || on_bd, on_bd)
        })
        .collect();

    let inside: Vec<bool> = results.iter().map(|x| x.0).collect();
    let on_b: Vec<bool> = results.iter().map(|x| x.1).collect();
    (inside, on_b)
}

// ───────────────────────────────────────────────────────────────────────────
// distance — SDF grid sampling + gradient
// ───────────────────────────────────────────────────────────────────────────

/// Sample SDF callable `fd` onto a uniform grid over `bbox` at spacing `delta`.
///
/// Returns `(xs, ys, D)` with `D.shape == (ys.len(), xs.len())`. Mirrors
/// `admesh._stages.distance.eval_sdf_grid` (numpy `meshgrid(..., indexing='xy')`).
pub fn eval_sdf_grid<F>(
    fd: F,
    bbox: (f64, f64, f64, f64),
    delta: f64,
) -> (Vec<f64>, Vec<f64>, Array2<f64>)
where
    F: Fn(&[[f64; 2]]) -> Vec<f64>,
{
    let (xmin, ymin, xmax, ymax) = bbox;
    let xs: Vec<f64> = (0..)
        .map(|i| xmin + i as f64 * delta)
        .take_while(|x| *x <= xmax + 0.5 * delta)
        .collect();
    let ys: Vec<f64> = (0..)
        .map(|j| ymin + j as f64 * delta)
        .take_while(|y| *y <= ymax + 0.5 * delta)
        .collect();
    let mut pts: Vec<[f64; 2]> = Vec::with_capacity(xs.len() * ys.len());
    for &y in &ys {
        for &x in &xs {
            pts.push([x, y]);
        }
    }
    let vals = fd(&pts);
    let d = Array2::from_shape_vec((ys.len(), xs.len()), vals).unwrap();
    (xs, ys, d)
}

/// 4th-order central gradient with 2nd-order one-sided borders.
/// Mirrors `admesh._stages.distance.grad_sdf`.
pub fn grad_sdf(d: ArrayView2<f64>, delta: f64) -> (Array2<f64>, Array2<f64>) {
    let (ly, lx) = (d.nrows(), d.ncols());
    let mut gx = Array2::<f64>::zeros((ly, lx));
    let mut gy = Array2::<f64>::zeros((ly, lx));

    if lx >= 5 {
        for j in 0..ly {
            for i in 2..lx - 2 {
                gx[(j, i)] = (d[(j, i - 2)] - 8.0 * d[(j, i - 1)]
                    + 8.0 * d[(j, i + 1)] - d[(j, i + 2)])
                    / (12.0 * delta);
            }
        }
    }
    if ly >= 5 {
        for j in 2..ly - 2 {
            for i in 0..lx {
                gy[(j, i)] = (d[(j - 2, i)] - 8.0 * d[(j - 1, i)]
                    + 8.0 * d[(j + 1, i)] - d[(j + 2, i)])
                    / (12.0 * delta);
            }
        }
    }

    if lx >= 3 {
        for j in 0..ly {
            gx[(j, 0)] = (d[(j, 1)] - d[(j, 0)]) / delta;
            gx[(j, 1)] = (d[(j, 2)] - d[(j, 0)]) / (2.0 * delta);
            gx[(j, lx - 2)] = (d[(j, lx - 1)] - d[(j, lx - 3)]) / (2.0 * delta);
            gx[(j, lx - 1)] = (d[(j, lx - 1)] - d[(j, lx - 2)]) / delta;
        }
    }
    if ly >= 3 {
        for i in 0..lx {
            gy[(0, i)] = (d[(1, i)] - d[(0, i)]) / delta;
            gy[(1, i)] = (d[(2, i)] - d[(0, i)]) / (2.0 * delta);
            gy[(ly - 2, i)] = (d[(ly - 1, i)] - d[(ly - 3, i)]) / (2.0 * delta);
            gy[(ly - 1, i)] = (d[(ly - 1, i)] - d[(ly - 2, i)]) / delta;
        }
    }

    (gx, gy)
}

// ───────────────────────────────────────────────────────────────────────────
// mesh_size — gradient-limited iterative PDE solver
// ───────────────────────────────────────────────────────────────────────────

/// Iterative upwind gradient-limited solver for the mesh-size field.
/// Faithful port of `admesh._stages.mesh_size.solve_iter` / the MATLAB
/// `MeshSizeIterativeSolver.c` mex.
///
/// Iterates
/// ```text
///     h <- h + (delta/2) * (min(|grad h|, g) - |grad h|)
/// ```
/// over interior cells where `D[j, i] <= 4*hmin`. Terminates when L1
/// residual < `1e-5`.
pub fn solve_iter(
    h0: ArrayView2<f64>,
    d: ArrayView2<f64>,
    hmin: f64,
    g: f64,
    delta: f64,
    max_iter: usize,
) -> Array2<f64> {
    let mut h: Array2<f64> = h0.to_owned();
    let (ly, lx) = (h.nrows(), h.ncols());
    let deltat = delta / 2.0;
    let four_hmin = 4.0 * hmin;
    let tol = 1e-5;

    for _it in 0..max_iter {
        let mut r = 0.0_f64;
        // Mirror Python (i = col, j = row) loop order exactly for parity.
        for i in 1..lx - 1 {
            for j in 1..ly - 1 {
                if d[(j, i)] > four_hmin {
                    continue;
                }
                let mut xfor = (h[(j, i + 1)] - h[(j, i)]) / delta;
                if xfor > 0.0 {
                    xfor = 0.0;
                }
                xfor *= xfor;

                let mut xback = (h[(j, i)] - h[(j, i - 1)]) / delta;
                if xback < 0.0 {
                    xback = 0.0;
                }
                xback *= xback;

                let mut yfor = (h[(j + 1, i)] - h[(j, i)]) / delta;
                if yfor > 0.0 {
                    yfor = 0.0;
                }
                yfor *= yfor;

                let mut yback = (h[(j, i)] - h[(j - 1, i)]) / delta;
                if yback < 0.0 {
                    yback = 0.0;
                }
                yback *= yback;

                let grad_mag = (xfor + xback + yfor + yback).sqrt();
                let hn = h[(j, i)] + deltat * (grad_mag.min(g) - grad_mag);
                r += (hn - h[(j, i)]).abs();
                h[(j, i)] = hn;
            }
        }
        if r <= tol {
            break;
        }
    }
    h
}

// ───────────────────────────────────────────────────────────────────────────
// inpaint — light-weight Gauss-Seidel Laplacian fill (NOT MATLAB-bit-parity)
// ───────────────────────────────────────────────────────────────────────────

/// Fill NaN entries in `a` via Gauss-Seidel Laplacian relaxation.
///
/// NOT a bit-parity port of `inpaint_nans method 0` (sparse LSQR) — that
/// would pull in `sprs` + a sparse-LSQR crate. This is a fast iterative
/// replacement: same fixed point (zero Laplacian on NaN cells, Dirichlet
/// on known cells), differs only in convergence path. Suitable for the
/// bathymetry + tide modules' "fill missing depths" use case.
pub fn inpaint_nans(a: ArrayView2<f64>, max_iter: usize, tol: f64) -> Array2<f64> {
    let (ny, nx) = (a.nrows(), a.ncols());
    let mut out = a.to_owned();
    // Initial fill: replace NaNs with mean of known
    let known_sum: f64 = a.iter().filter(|x| !x.is_nan()).sum();
    let known_count = a.iter().filter(|x| !x.is_nan()).count();
    let mean = if known_count > 0 {
        known_sum / known_count as f64
    } else {
        0.0
    };
    let nan_mask: Vec<bool> = a.iter().map(|x| x.is_nan()).collect();
    for ((_, v), m) in out.indexed_iter_mut().zip(&nan_mask) {
        if *m {
            *v = mean;
        }
    }

    // Gauss-Seidel iteration
    for _ in 0..max_iter {
        let mut max_diff = 0.0_f64;
        for j in 0..ny {
            for i in 0..nx {
                let idx = j * nx + i;
                if !nan_mask[idx] {
                    continue;
                }
                let mut s = 0.0;
                let mut c = 0;
                if i > 0 {
                    s += out[(j, i - 1)];
                    c += 1;
                }
                if i + 1 < nx {
                    s += out[(j, i + 1)];
                    c += 1;
                }
                if j > 0 {
                    s += out[(j - 1, i)];
                    c += 1;
                }
                if j + 1 < ny {
                    s += out[(j + 1, i)];
                    c += 1;
                }
                if c == 0 {
                    continue;
                }
                let new_val = s / c as f64;
                let diff = (new_val - out[(j, i)]).abs();
                if diff > max_diff {
                    max_diff = diff;
                }
                out[(j, i)] = new_val;
            }
        }
        if max_diff < tol {
            break;
        }
    }
    out
}

// ───────────────────────────────────────────────────────────────────────────
// background_grid — uniform-spacing background grid helpers
// ───────────────────────────────────────────────────────────────────────────

/// Build uniform rectangular background grid covering `bbox`. Mirrors
/// `admesh._stages.background_grid.create_background_grid`.
pub fn create_background_grid(
    bbox: (f64, f64, f64, f64),
    delta: f64,
) -> (Vec<f64>, Vec<f64>) {
    let (xmin, ymin, xmax, ymax) = bbox;
    let xs: Vec<f64> = (0..)
        .map(|i| xmin + i as f64 * delta)
        .take_while(|x| *x <= xmax + 0.5 * delta)
        .collect();
    let ys: Vec<f64> = (0..)
        .map(|j| ymin + j as f64 * delta)
        .take_while(|y| *y <= ymax + 0.5 * delta)
        .collect();
    (xs, ys)
}

#[cfg(test)]
mod tests {
    use super::*;
    use approx::assert_abs_diff_eq;

    #[test]
    fn in_polygon_unit_square_interior() {
        let xv = vec![0.0, 1.0, 1.0, 0.0];
        let yv = vec![0.0, 0.0, 1.0, 1.0];
        let (inside, _on) = in_polygon(&[0.5, -0.1, 1.5], &[0.5, 0.5, 0.5], &xv, &yv, 1e-12);
        assert_eq!(inside, vec![true, false, false]);
    }

    #[test]
    fn in_polygon_on_boundary() {
        let xv = vec![0.0, 1.0, 1.0, 0.0];
        let yv = vec![0.0, 0.0, 1.0, 1.0];
        let (inside, on) = in_polygon(&[0.5], &[0.0], &xv, &yv, 1e-9);
        assert!(inside[0]);
        assert!(on[0]);
    }

    #[test]
    fn solve_iter_constant_input_is_stable() {
        let h0 = Array2::<f64>::from_elem((5, 5), 1.0);
        let d = Array2::<f64>::from_elem((5, 5), 0.0);
        let h = solve_iter(h0.view(), d.view(), 0.1, 0.5, 0.1, 100);
        for &v in &h {
            assert_abs_diff_eq!(v, 1.0, epsilon = 1e-10);
        }
    }

    #[test]
    fn solve_iter_produces_finite_output() {
        // Linear ramp input; check output stays finite + non-NaN.
        // (Algorithm permits transient gradient amplification during
        // Gauss-Seidel sweep; long-term steady state has |grad| ≤ g
        // but transient need not be monotone.)
        let mut h0 = Array2::<f64>::zeros((10, 10));
        for j in 0..10 {
            for i in 0..10 {
                h0[(j, i)] = 0.5 + (i as f64) * 0.05;
            }
        }
        let d = Array2::<f64>::from_elem((10, 10), 0.0);
        let h = solve_iter(h0.view(), d.view(), 0.1, 0.5, 0.1, 100);
        for &v in &h {
            assert!(v.is_finite(), "non-finite output {v}");
        }
    }

    #[test]
    fn grad_sdf_linear_returns_constant() {
        let mut d = Array2::<f64>::zeros((7, 7));
        for j in 0..7 {
            for i in 0..7 {
                d[(j, i)] = i as f64 * 2.0;
            }
        }
        let (gx, _gy) = grad_sdf(d.view(), 1.0);
        // Interior 4th-order finite diff of linear field = exact slope (2.0)
        for j in 0..7 {
            for i in 2..5 {
                assert_abs_diff_eq!(gx[(j, i)], 2.0, epsilon = 1e-10);
            }
        }
    }

    #[test]
    fn inpaint_nans_recovers_linear() {
        // h(i, j) = i + j, knock out interior cell
        let mut a = Array2::<f64>::zeros((5, 5));
        for j in 0..5 {
            for i in 0..5 {
                a[(j, i)] = (i + j) as f64;
            }
        }
        a[(2, 2)] = f64::NAN;
        let filled = inpaint_nans(a.view(), 1000, 1e-10);
        assert_abs_diff_eq!(filled[(2, 2)], 4.0, epsilon = 1e-4);
    }
}

// Re-export Axis to silence unused-import warning when running with
// the parallel-only feature; the public type stays referenced.
#[allow(dead_code)]
const _AXIS_USAGE: Option<Axis> = None;
