//! ADMESH 2D unstructured-mesh generator — Rust port.
//!
//! Mirrors the faithful Python port in `admesh/_stages/`. Public surface:
//!   - [`Sdf`] trait + [`RasterSdf`]: signed-distance functions.
//!   - [`distmesh2d`]: force-equilibrium triangulator (Persson & Strang 2004).
//!   - [`mesh_quality`]: per-triangle equilateral-area ratio.
//!   - [`Mesh`]: output node/element arrays.
//!
//! Numerical parity target: identical to `admesh.distmesh.distmesh2d` to 1e-9.

pub mod delaunay;
pub mod distmesh;
pub mod quality;
pub mod sdf;

pub use delaunay::delaunay_triangulate;
pub use distmesh::{distmesh2d, Diagnostic, DistmeshConfig, Mesh};
pub use quality::mesh_quality;
pub use sdf::{RasterSdf, Sdf, SdfFn};

#[derive(thiserror::Error, Debug)]
pub enum AdmeshError {
    #[error("invalid bbox: {0}")]
    InvalidBbox(String),
    #[error("degenerate point set: {0}")]
    DegeneratePoints(String),
    #[error("delaunay failure: {0}")]
    DelaunayFailed(String),
}

pub type Result<T> = std::result::Result<T, AdmeshError>;

pub type Bbox = (f64, f64, f64, f64); // (xmin, ymin, xmax, ymax)
pub type Point2 = [f64; 2];
