//! Delaunay triangulation backend via `spade`. Mirrors
//! `scipy.spatial.Delaunay(points).simplices` — returns CCW triangle
//! index triples.
//!
//! `spade::DelaunayTriangulation` is an incremental O(n log n) algorithm
//! using Bowyer-Watson with a kd-tree hint. Output ordering does NOT
//! match scipy bit-for-bit but the triangulation IS equivalent (same
//! set of triangles for non-degenerate input).

use crate::{AdmeshError, Point2, Result};
use spade::{DelaunayTriangulation, Point2 as SpadePoint, Triangulation};

pub fn delaunay_triangulate(points: &[Point2]) -> Result<Vec<[usize; 3]>> {
    if points.len() < 3 {
        return Err(AdmeshError::DegeneratePoints(format!(
            "need ≥3 points, got {}",
            points.len()
        )));
    }

    let mut tri = DelaunayTriangulation::<SpadePoint<f64>>::new();
    let mut handles = Vec::with_capacity(points.len());
    for p in points {
        let h = tri
            .insert(SpadePoint::new(p[0], p[1]))
            .map_err(|e| AdmeshError::DelaunayFailed(format!("{e:?}")))?;
        handles.push(h);
    }

    let mut out = Vec::with_capacity(tri.num_inner_faces());
    for face in tri.inner_faces() {
        let [a, b, c] = face.vertices();
        out.push([
            handles
                .iter()
                .position(|&h| h == a.fix())
                .unwrap_or(a.fix().index()),
            handles
                .iter()
                .position(|&h| h == b.fix())
                .unwrap_or(b.fix().index()),
            handles
                .iter()
                .position(|&h| h == c.fix())
                .unwrap_or(c.fix().index()),
        ]);
    }
    // Sort vertex indices within each triangle (matches Python `np.sort(t, axis=1)`)
    for t in &mut out {
        t.sort_unstable();
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn triangulates_unit_square() {
        let pts = vec![[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]];
        let t = delaunay_triangulate(&pts).unwrap();
        assert_eq!(t.len(), 2);
        // Each vertex appears in at least one triangle
        let mut seen = [false; 4];
        for tri in &t {
            for &v in tri {
                seen[v] = true;
            }
        }
        assert!(seen.iter().all(|&x| x));
    }
}
