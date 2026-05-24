//! Triangle-quality metrics. Mirrors `admesh._stages.quality.mesh_quality`.
//!
//! Quality = `4*sqrt(3) * area / (l1^2 + l2^2 + l3^2)`. 1.0 = equilateral,
//! 0.0 = degenerate / colinear.

use crate::Point2;
use rayon::prelude::*;

const Q_NORMALISER: f64 = 6.928_203_230_275_509; // 4 * sqrt(3)

/// Compute per-triangle quality + min + mean.
///
/// `nodes[i]` is `[x, y]`; `tris[k]` is `[i, j, l]` (0-based).
///
/// Returns `(min_q, mean_q, per_tri)` matching the Python signature.
pub fn mesh_quality(nodes: &[Point2], tris: &[[usize; 3]]) -> (f64, f64, Vec<f64>) {
    if tris.is_empty() {
        return (0.0, 0.0, vec![]);
    }

    let q: Vec<f64> = tris
        .par_iter()
        .map(|&[i, j, k]| triangle_quality(&nodes[i], &nodes[j], &nodes[k]))
        .collect();

    let mut min_q = f64::INFINITY;
    let mut sum = 0.0;
    for &v in &q {
        if v < min_q {
            min_q = v;
        }
        sum += v;
    }
    let mean = sum / q.len() as f64;
    (min_q, mean, q)
}

#[inline]
fn triangle_quality(a: &Point2, b: &Point2, c: &Point2) -> f64 {
    let ab = [b[0] - a[0], b[1] - a[1]];
    let bc = [c[0] - b[0], c[1] - b[1]];
    let ca = [a[0] - c[0], a[1] - c[1]];
    let l1 = ab[0] * ab[0] + ab[1] * ab[1];
    let l2 = bc[0] * bc[0] + bc[1] * bc[1];
    let l3 = ca[0] * ca[0] + ca[1] * ca[1];
    let denom = l1 + l2 + l3;
    if denom <= 0.0 {
        return 0.0;
    }
    let area2 = ab[0] * (-ca[1]) - ab[1] * (-ca[0]);
    let area = 0.5 * area2.abs();
    Q_NORMALISER * area / denom
}

#[cfg(test)]
mod tests {
    use super::*;
    use approx::assert_abs_diff_eq;

    #[test]
    fn equilateral_has_quality_one() {
        let s = 1.0_f64;
        let h = s * (3.0_f64).sqrt() / 2.0;
        let nodes = vec![[0.0, 0.0], [s, 0.0], [s / 2.0, h]];
        let tris = vec![[0, 1, 2]];
        let (min_q, mean_q, _) = mesh_quality(&nodes, &tris);
        assert_abs_diff_eq!(min_q, 1.0, epsilon = 1e-12);
        assert_abs_diff_eq!(mean_q, 1.0, epsilon = 1e-12);
    }

    #[test]
    fn degenerate_has_quality_zero() {
        let nodes = vec![[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]];
        let tris = vec![[0, 1, 2]];
        let (min_q, _, _) = mesh_quality(&nodes, &tris);
        assert!(min_q.abs() < 1e-12);
    }
}
