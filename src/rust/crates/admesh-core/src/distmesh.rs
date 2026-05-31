//! `distmesh2d` — force-equilibrium triangulator (Persson & Strang, 2004).
//!
//! Faithful Rust port of `admesh._stages.distmesh.distmesh2d`. Identical
//! force model, identical stopping criteria, identical boundary
//! projection. Backend differences:
//!   * Delaunay: `spade` instead of Qhull/scipy → same connectivity,
//!     possibly different ordering.
//!   * Force assembly: `rayon` parallel reduction (Python uses
//!     `np.add.at` serial scatter).
//!   * RNG: `rand_pcg::Pcg64` seeded explicitly (Python uses NumPy
//!     PCG64 default). Seeds will NOT match bit-for-bit between
//!     languages but distributions are equivalent.

use crate::{delaunay_triangulate, Bbox, Point2, Sdf};
use rand::Rng;
use rand_pcg::Pcg64;
use rand::SeedableRng;
use rayon::prelude::*;
use std::collections::HashSet;

/// Output of [`distmesh2d`].
#[derive(Debug, Clone)]
pub struct Mesh {
    pub nodes: Vec<Point2>,
    pub elements: Vec<[usize; 3]>,
}

#[derive(Debug, Clone, Copy)]
pub struct Diagnostic {
    pub iter: usize,
    pub n_pts: usize,
    pub n_elements: usize,
    pub max_disp: f64,
    pub n_outside: usize,
}

#[derive(Debug, Clone)]
pub struct DistmeshConfig {
    pub h0: f64,
    pub bbox: Bbox,
    pub pfix: Vec<Point2>,
    pub dptol: f64,
    pub ttol: f64,
    pub f_scale: f64,
    pub delta_t: f64,
    pub geps_factor: f64,
    pub niter: usize,
    pub seed: u64,
    pub return_diagnostics: bool,
}

impl Default for DistmeshConfig {
    fn default() -> Self {
        Self {
            h0: 0.1,
            bbox: (-1.0, -1.0, 1.0, 1.0),
            pfix: vec![],
            dptol: 1e-3,
            ttol: 0.1,
            f_scale: 1.2,
            delta_t: 0.2,
            geps_factor: 1e-3,
            niter: 500,
            seed: 0,
            return_diagnostics: false,
        }
    }
}

/// `fh = None` → uniform size field (constant 1).
type SizeFn<'a> = Option<&'a (dyn Fn(&[Point2]) -> Vec<f64> + Sync)>;

/// Generate triangular mesh on domain `fd` with target spacing `cfg.h0`.
///
/// Returns the converged `Mesh` plus optional diagnostics.
pub fn distmesh2d(
    fd: &dyn Sdf,
    fh: SizeFn,
    cfg: &DistmeshConfig,
) -> (Mesh, Vec<Diagnostic>) {
    let geps = cfg.geps_factor * cfg.h0;
    let deps = f64::EPSILON.sqrt() * cfg.h0;
    let mut rng = Pcg64::seed_from_u64(cfg.seed);

    // 1. Initial lattice (equilateral-triangle) + drop points outside domain.
    let mut p = initial_distribution(cfg.bbox, cfg.h0);
    let d_init = fd.eval(&p);
    p = p.into_iter().zip(d_init).filter(|(_, d)| *d < geps).map(|(q, _)| q).collect();

    // 2. Probability-based rejection by fh.
    if let Some(f) = fh {
        let r = f(&p);
        let r0 = r.iter().cloned().fold(f64::INFINITY, f64::min);
        if r0 > 0.0 {
            p = p
                .into_iter()
                .zip(r)
                .filter(|(_, ri)| rng.gen::<f64>() < (r0 / ri).powi(2))
                .map(|(q, _)| q)
                .collect();
        }
    }

    // 3. Insert fixed points first (indices 0..nfix; never moved).
    let nfix = cfg.pfix.len();
    if nfix > 0 {
        // Drop free points coincident with fixed points
        let fixed = &cfg.pfix;
        let geps_sq = geps * geps;
        p.retain(|q| {
            !fixed
                .iter()
                .any(|f| (q[0] - f[0]).powi(2) + (q[1] - f[1]).powi(2) <= geps_sq)
        });
        let mut combined = Vec::with_capacity(nfix + p.len());
        combined.extend_from_slice(fixed);
        combined.extend(p);
        p = combined;
    }

    let mut pold: Vec<Point2> = vec![[f64::INFINITY, f64::INFINITY]; p.len()];
    let mut t: Vec<[usize; 3]> = vec![];
    let mut bars: Vec<[usize; 2]> = vec![];
    let mut diagnostics = Vec::new();

    for k in 0..cfg.niter {
        // Re-triangulate if any node moved more than ttol*h0.
        let moved_max = p
            .iter()
            .zip(pold.iter())
            .map(|(a, b)| (((a[0] - b[0]).powi(2) + (a[1] - b[1]).powi(2)).sqrt()) / cfg.h0)
            .fold(0.0_f64, f64::max);

        if moved_max > cfg.ttol {
            pold = p.clone();
            let all_t = match delaunay_triangulate(&p) {
                Ok(v) => v,
                Err(_) => break,
            };
            // Centroid-filter: keep only triangles whose centroid is inside domain.
            let centroids: Vec<Point2> = all_t
                .iter()
                .map(|&[i, j, l]| {
                    [
                        (p[i][0] + p[j][0] + p[l][0]) / 3.0,
                        (p[i][1] + p[j][1] + p[l][1]) / 3.0,
                    ]
                })
                .collect();
            let cd = fd.eval(&centroids);
            t = all_t
                .into_iter()
                .zip(cd)
                .filter(|(_, d)| *d < -geps)
                .map(|(tri, _)| tri)
                .collect();

            // Build unique bars (sorted vertex pairs).
            let mut bar_set: HashSet<[usize; 2]> = HashSet::with_capacity(t.len() * 3);
            for &[a, b, c] in &t {
                let mut e = [a, b]; e.sort_unstable(); bar_set.insert(e);
                let mut e = [a, c]; e.sort_unstable(); bar_set.insert(e);
                let mut e = [b, c]; e.sort_unstable(); bar_set.insert(e);
            }
            bars = bar_set.into_iter().collect();
        }

        if bars.is_empty() {
            break;
        }

        // Truss forces: F = max(L0 - L, 0) along each bar.
        let bar_data: Vec<([f64; 2], f64)> = bars
            .par_iter()
            .map(|&[i, j]| {
                let vec = [p[i][0] - p[j][0], p[i][1] - p[j][1]];
                let l = (vec[0] * vec[0] + vec[1] * vec[1]).sqrt();
                (vec, l)
            })
            .collect();

        // Mid-bar size field evaluation (uniform=1 if fh=None).
        let midpoints: Vec<Point2> = bars
            .iter()
            .map(|&[i, j]| {
                [
                    0.5 * (p[i][0] + p[j][0]),
                    0.5 * (p[i][1] + p[j][1]),
                ]
            })
            .collect();
        let hbars: Vec<f64> = match fh {
            Some(f) => f(&midpoints),
            None => vec![1.0; midpoints.len()],
        };

        // L0 = hbars * Fscale * sqrt(sum(L^2) / sum(hbars^2))
        let l_sq_sum: f64 = bar_data.iter().map(|(_, l)| l * l).sum();
        let h_sq_sum: f64 = hbars.iter().map(|h| h * h).sum();
        let scale = cfg.f_scale * (l_sq_sum / h_sq_sum).sqrt();

        // Accumulate forces. Serial scatter (parallel scatter needs atomics
        // or per-thread buffers — sequential is plenty fast at N≤1e6).
        let mut ftot = vec![[0.0_f64; 2]; p.len()];
        for ((&[i, j], (vec, l)), hb) in bars.iter().zip(bar_data.iter()).zip(hbars.iter()) {
            let l0 = hb * scale;
            let force = (l0 - l).max(0.0);
            if *l > 0.0 {
                let fx = force * vec[0] / l;
                let fy = force * vec[1] / l;
                ftot[i][0] += fx;
                ftot[i][1] += fy;
                ftot[j][0] -= fx;
                ftot[j][1] -= fy;
            }
        }

        // Zero force at fixed points.
        for f in ftot.iter_mut().take(nfix) {
            *f = [0.0, 0.0];
        }

        // Euler step + boundary projection for points drifted outside.
        let mut p_new: Vec<Point2> = p
            .iter()
            .zip(ftot.iter())
            .map(|(q, f)| [q[0] + cfg.delta_t * f[0], q[1] + cfg.delta_t * f[1]])
            .collect();

        let d_new = fd.eval(&p_new);
        let outside_idx: Vec<usize> = d_new
            .iter()
            .enumerate()
            .filter(|(_, d)| **d > 0.0)
            .map(|(i, _)| i)
            .collect();

        if !outside_idx.is_empty() {
            // Project back along -grad(fd) using finite differences.
            let po: Vec<Point2> = outside_idx.iter().map(|&i| p_new[i]).collect();
            let po_dx: Vec<Point2> = po.iter().map(|p| [p[0] + deps, p[1]]).collect();
            let po_dy: Vec<Point2> = po.iter().map(|p| [p[0], p[1] + deps]).collect();
            let d_po = fd.eval(&po);
            let d_dx = fd.eval(&po_dx);
            let d_dy = fd.eval(&po_dy);
            for (k_idx, &i) in outside_idx.iter().enumerate() {
                let dx = (d_dx[k_idx] - d_po[k_idx]) / deps;
                let dy = (d_dy[k_idx] - d_po[k_idx]) / deps;
                let denom = dx * dx + dy * dy;
                if denom > 0.0 {
                    let shift_x = d_po[k_idx] * dx / denom;
                    let shift_y = d_po[k_idx] * dy / denom;
                    p_new[i][0] -= shift_x;
                    p_new[i][1] -= shift_y;
                }
            }
        }

        // Stopping criterion on interior nodes.
        let max_d = if nfix < p_new.len() {
            p_new
                .iter()
                .zip(p.iter())
                .skip(nfix)
                .map(|(a, b)| ((a[0] - b[0]).powi(2) + (a[1] - b[1]).powi(2)).sqrt())
                .fold(0.0_f64, f64::max)
        } else {
            0.0
        };

        if cfg.return_diagnostics {
            diagnostics.push(Diagnostic {
                iter: k,
                n_pts: p_new.len(),
                n_elements: t.len(),
                max_disp: max_d / cfg.h0,
                n_outside: outside_idx.len(),
            });
        }

        if nfix < p_new.len() && max_d / cfg.h0 < cfg.dptol {
            p = p_new;
            break;
        }

        p = p_new;
    }

    // Final retriangulation + ocean filter (mirrors Python lines 240-245).
    if p.len() >= 3 {
        if let Ok(all_t) = delaunay_triangulate(&p) {
            let centroids: Vec<Point2> = all_t
                .iter()
                .map(|&[i, j, l]| {
                    [
                        (p[i][0] + p[j][0] + p[l][0]) / 3.0,
                        (p[i][1] + p[j][1] + p[l][1]) / 3.0,
                    ]
                })
                .collect();
            let cd = fd.eval(&centroids);
            t = all_t
                .into_iter()
                .zip(cd)
                .filter(|(_, d)| *d < -geps)
                .map(|(tri, _)| tri)
                .collect();
        }
    }

    (Mesh { nodes: p, elements: t }, diagnostics)
}

/// Equilateral-triangle lattice covering bbox (port of MATLAB `_initial_distribution`).
fn initial_distribution(bbox: Bbox, h0: f64) -> Vec<Point2> {
    let (xmin, ymin, xmax, ymax) = bbox;
    let dy = h0 * (3.0_f64).sqrt() / 2.0;
    let mut pts = Vec::new();
    let nx = ((xmax - xmin) / h0).ceil() as usize + 1;
    let ny = ((ymax - ymin) / dy).ceil() as usize + 1;
    for j in 0..ny {
        let y = ymin + j as f64 * dy;
        if y > ymax + 0.5 * h0 {
            break;
        }
        let offset = if j % 2 == 1 { h0 / 2.0 } else { 0.0 };
        for i in 0..nx {
            let x = xmin + i as f64 * h0 + offset;
            if x > xmax + 0.5 * h0 {
                break;
            }
            pts.push([x, y]);
        }
    }
    pts
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::sdf::{unit_disk_sdf, SdfFn};
    use crate::mesh_quality;

    #[test]
    fn meshes_unit_disk() {
        let sdf = SdfFn(unit_disk_sdf);
        let cfg = DistmeshConfig {
            h0: 0.2,
            bbox: (-1.2, -1.2, 1.2, 1.2),
            niter: 100,
            seed: 42,
            ..Default::default()
        };
        let (mesh, _) = distmesh2d(&sdf, None, &cfg);
        assert!(mesh.nodes.len() > 30);
        assert!(mesh.elements.len() > 30);
        let (min_q, mean_q, _) = mesh_quality(&mesh.nodes, &mesh.elements);
        assert!(mean_q > 0.6, "mean quality {} below target", mean_q);
        assert!(min_q > 0.1, "min quality {} too low", min_q);
    }
}
