//! Signed-distance functions.
//!
//! Mirrors the SDF callable contract from `admesh._stages.domains.Domain.fd`:
//! negative inside, positive outside, zero on boundary. Vectorised — takes
//! `&[Point2]` slice, returns `Vec<f64>` of same length.

use crate::{Bbox, Point2};
use ndarray::Array2;

/// Object-safe SDF trait. Implement for analytical or grid-interpolated SDFs.
pub trait Sdf: Sync + Send {
    fn eval(&self, pts: &[Point2]) -> Vec<f64>;

    /// Single-point convenience.
    fn eval_one(&self, p: Point2) -> f64 {
        self.eval(std::slice::from_ref(&p))[0]
    }
}

/// Concrete callable wrapper — wraps a closure into [`Sdf`].
pub struct SdfFn<F>(pub F)
where
    F: Fn(&[Point2]) -> Vec<f64> + Sync + Send;

impl<F> Sdf for SdfFn<F>
where
    F: Fn(&[Point2]) -> Vec<f64> + Sync + Send,
{
    #[inline]
    fn eval(&self, pts: &[Point2]) -> Vec<f64> {
        (self.0)(pts)
    }
}

/// Bilinear-interpolated SDF from a precomputed grid. Mirrors the
/// scipy `RegularGridInterpolator` pattern used in the Python rasterised
/// SDF demo (see ADMESH-Domains `wnat_mesh_v3.py`).
///
/// Storage convention: `grid[(iy, ix)]` with `ys` strictly ascending in
/// `[ymin, ymax]` and `xs` ascending in `[xmin, xmax]`. Out-of-bbox
/// queries return `fill_value`.
pub struct RasterSdf {
    pub xs: Vec<f64>,
    pub ys: Vec<f64>,
    pub values: Array2<f64>, // shape (ny, nx)
    pub fill_value: f64,
}

impl RasterSdf {
    pub fn new(xs: Vec<f64>, ys: Vec<f64>, values: Array2<f64>, fill_value: f64) -> Self {
        assert_eq!(values.shape(), [ys.len(), xs.len()]);
        Self { xs, ys, values, fill_value }
    }

    pub fn bbox(&self) -> Bbox {
        (
            *self.xs.first().unwrap(),
            *self.ys.first().unwrap(),
            *self.xs.last().unwrap(),
            *self.ys.last().unwrap(),
        )
    }

    #[inline]
    fn locate(axis: &[f64], v: f64) -> Option<(usize, f64)> {
        if v < axis[0] || v > *axis.last().unwrap() {
            return None;
        }
        // axis is monotone ascending and uniform-ish — binary search
        let idx = match axis.binary_search_by(|x| x.partial_cmp(&v).unwrap()) {
            Ok(i) => i.min(axis.len().saturating_sub(2)),
            Err(i) => i.saturating_sub(1).min(axis.len().saturating_sub(2)),
        };
        let dx = axis[idx + 1] - axis[idx];
        if dx <= 0.0 {
            return None;
        }
        let t = (v - axis[idx]) / dx;
        Some((idx, t))
    }
}

impl Sdf for RasterSdf {
    fn eval(&self, pts: &[Point2]) -> Vec<f64> {
        pts.iter()
            .map(|p| {
                let (x, y) = (p[0], p[1]);
                let lx = Self::locate(&self.xs, x);
                let ly = Self::locate(&self.ys, y);
                match (lx, ly) {
                    (Some((ix, tx)), Some((iy, ty))) => {
                        // Bilinear
                        let v00 = self.values[(iy, ix)];
                        let v10 = self.values[(iy, ix + 1)];
                        let v01 = self.values[(iy + 1, ix)];
                        let v11 = self.values[(iy + 1, ix + 1)];
                        let a = v00 * (1.0 - tx) + v10 * tx;
                        let b = v01 * (1.0 - tx) + v11 * tx;
                        a * (1.0 - ty) + b * ty
                    }
                    _ => self.fill_value,
                }
            })
            .collect()
    }
}

/// Built-in: unit-disk SDF `|p| - 1`.
pub fn unit_disk_sdf(pts: &[Point2]) -> Vec<f64> {
    pts.iter().map(|p| (p[0] * p[0] + p[1] * p[1]).sqrt() - 1.0).collect()
}

/// Built-in: unit-square SDF on `[-1, 1] × [-1, 1]`. Matches MATLAB drectangle.
pub fn unit_square_sdf(pts: &[Point2]) -> Vec<f64> {
    pts.iter()
        .map(|p| {
            let dx = (p[0].abs() - 1.0).max(0.0);
            let dy = (p[1].abs() - 1.0).max(0.0);
            let outside = (dx * dx + dy * dy).sqrt();
            let inside = (p[0].abs() - 1.0).max(p[1].abs() - 1.0).min(0.0);
            outside + inside
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use approx::assert_abs_diff_eq;

    #[test]
    fn unit_disk_origin_is_minus_one() {
        assert_abs_diff_eq!(unit_disk_sdf(&[[0.0, 0.0]])[0], -1.0, epsilon = 1e-12);
    }

    #[test]
    fn unit_disk_boundary_is_zero() {
        assert_abs_diff_eq!(unit_disk_sdf(&[[1.0, 0.0]])[0], 0.0, epsilon = 1e-12);
    }

    #[test]
    fn raster_sdf_interpolates() {
        let xs = vec![0.0, 1.0];
        let ys = vec![0.0, 1.0];
        let values = Array2::from_shape_vec((2, 2), vec![0.0, 1.0, 2.0, 3.0]).unwrap();
        let sdf = RasterSdf::new(xs, ys, values, f64::NAN);
        // (0.5, 0.5) → bilinear avg of corners = (0+1+2+3)/4 = 1.5
        assert_abs_diff_eq!(sdf.eval(&[[0.5, 0.5]])[0], 1.5, epsilon = 1e-12);
    }
}
