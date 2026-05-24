//! Python bindings — drop-in replacement for `admesh._stages.distmesh.distmesh2d`.

use admesh_core::{
    delaunay_triangulate, distmesh2d, mesh_quality, DistmeshConfig, Point2, RasterSdf, Sdf,
};
use ndarray::Array2;
use numpy::{IntoPyArray, PyArray1, PyArray2, PyReadonlyArray1, PyReadonlyArray2};
use pyo3::prelude::*;

/// Wrap a Python callable into an `Sdf`. The callable receives a
/// 2D numpy array `(N, 2)` of points and must return a 1D array of length N.
struct PyCallableSdf {
    py_fn: Py<PyAny>,
}

impl Sdf for PyCallableSdf {
    fn eval(&self, pts: &[Point2]) -> Vec<f64> {
        Python::with_gil(|py| {
            let flat: Vec<f64> = pts.iter().flat_map(|p| [p[0], p[1]]).collect();
            let arr = Array2::from_shape_vec((pts.len(), 2), flat).unwrap();
            let np_arr = arr.into_pyarray_bound(py);
            let res = self.py_fn.call1(py, (np_arr,)).expect("SDF callback failed");
            // Accept (N,) or (N,1) numpy arrays.
            if let Ok(a1) = res.extract::<PyReadonlyArray1<f64>>(py) {
                return a1.as_array().iter().copied().collect();
            }
            if let Ok(a2) = res.extract::<PyReadonlyArray2<f64>>(py) {
                return a2.as_array().iter().copied().collect();
            }
            panic!("SDF must return numpy float64 array (shape (N,) or (N,1))");
        })
    }
}

#[pyfunction]
#[pyo3(signature = (fd, fh, h0, bbox, pfix, dptol, ttol, f_scale, delta_t, geps_factor, niter, seed))]
#[allow(clippy::too_many_arguments)]
fn distmesh2d_rs(
    py: Python<'_>,
    fd: Py<PyAny>,
    fh: Option<Py<PyAny>>,
    h0: f64,
    bbox: (f64, f64, f64, f64),
    pfix: Option<PyReadonlyArray2<f64>>,
    dptol: f64,
    ttol: f64,
    f_scale: f64,
    delta_t: f64,
    geps_factor: f64,
    niter: usize,
    seed: u64,
) -> PyResult<(Py<PyArray2<f64>>, Py<PyArray2<i64>>)> {
    let pfix_vec: Vec<Point2> = pfix
        .map(|a| {
            a.as_array()
                .rows()
                .into_iter()
                .map(|r| [r[0], r[1]])
                .collect()
        })
        .unwrap_or_default();

    let cfg = DistmeshConfig {
        h0,
        bbox,
        pfix: pfix_vec,
        dptol,
        ttol,
        f_scale,
        delta_t,
        geps_factor,
        niter,
        seed,
        return_diagnostics: false,
    };

    let sdf = PyCallableSdf { py_fn: fd };
    let fh_callable: Option<Box<dyn Fn(&[Point2]) -> Vec<f64> + Sync>> = fh.map(|f| {
        Box::new(move |pts: &[Point2]| -> Vec<f64> {
            Python::with_gil(|py| {
                let flat: Vec<f64> = pts.iter().flat_map(|p| [p[0], p[1]]).collect();
                let arr = Array2::from_shape_vec((pts.len(), 2), flat).unwrap();
                let np_arr = arr.into_pyarray_bound(py);
                let res = f.call1(py, (np_arr,)).expect("size-field callback failed");
                if let Ok(a1) = res.extract::<PyReadonlyArray1<f64>>(py) {
                    return a1.as_array().iter().copied().collect();
                }
                if let Ok(a2) = res.extract::<PyReadonlyArray2<f64>>(py) {
                    return a2.as_array().iter().copied().collect();
                }
                panic!("size-field must return numpy float64 array");
            })
        }) as Box<dyn Fn(&[Point2]) -> Vec<f64> + Sync>
    });
    let fh_ref: Option<&(dyn Fn(&[Point2]) -> Vec<f64> + Sync)> =
        fh_callable.as_deref();

    let (mesh, _) = py.allow_threads(|| distmesh2d(&sdf, fh_ref, &cfg));

    let n = mesh.nodes.len();
    let m = mesh.elements.len();
    let nodes_flat: Vec<f64> = mesh.nodes.iter().flat_map(|p| [p[0], p[1]]).collect();
    let elems_flat: Vec<i64> = mesh
        .elements
        .iter()
        .flat_map(|t| [t[0] as i64, t[1] as i64, t[2] as i64])
        .collect();

    let nodes_arr = Array2::from_shape_vec((n, 2), nodes_flat).unwrap();
    let elems_arr = Array2::from_shape_vec((m, 3), elems_flat).unwrap();
    Ok((nodes_arr.into_pyarray_bound(py).into(), elems_arr.into_pyarray_bound(py).into()))
}

#[pyfunction]
fn delaunay_rs(
    py: Python<'_>,
    points: PyReadonlyArray2<f64>,
) -> PyResult<Py<PyArray2<i64>>> {
    let pts: Vec<Point2> = points
        .as_array()
        .rows()
        .into_iter()
        .map(|r| [r[0], r[1]])
        .collect();
    let t = delaunay_triangulate(&pts).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("delaunay failed: {e}"))
    })?;
    let flat: Vec<i64> = t
        .into_iter()
        .flat_map(|tri| [tri[0] as i64, tri[1] as i64, tri[2] as i64])
        .collect();
    let n = flat.len() / 3;
    let arr = Array2::from_shape_vec((n, 3), flat).unwrap();
    Ok(arr.into_pyarray_bound(py).into())
}

#[pyfunction]
fn mesh_quality_rs(
    py: Python<'_>,
    nodes: PyReadonlyArray2<f64>,
    tris: PyReadonlyArray2<i64>,
) -> PyResult<(f64, f64, Py<numpy::PyArray1<f64>>)> {
    let pts: Vec<Point2> = nodes
        .as_array()
        .rows()
        .into_iter()
        .map(|r| [r[0], r[1]])
        .collect();
    let tris_vec: Vec<[usize; 3]> = tris
        .as_array()
        .rows()
        .into_iter()
        .map(|r| [r[0] as usize, r[1] as usize, r[2] as usize])
        .collect();
    let (min_q, mean_q, per_tri) = mesh_quality(&pts, &tris_vec);
    let arr = PyArray1::from_vec_bound(py, per_tri);
    Ok((min_q, mean_q, arr.into()))
}

/// Native-SDF distmesh: SDF lives entirely in Rust as a [`RasterSdf`].
/// Zero Python callbacks during the inner loop → upper-bound speedup.
#[pyfunction]
#[pyo3(signature = (xs, ys, sdf_grid, h0, bbox, pfix, dptol, ttol, f_scale, delta_t, geps_factor, niter, seed))]
#[allow(clippy::too_many_arguments)]
fn distmesh2d_native_rs(
    py: Python<'_>,
    xs: PyReadonlyArray1<f64>,
    ys: PyReadonlyArray1<f64>,
    sdf_grid: PyReadonlyArray2<f64>,
    h0: f64,
    bbox: (f64, f64, f64, f64),
    pfix: Option<PyReadonlyArray2<f64>>,
    dptol: f64,
    ttol: f64,
    f_scale: f64,
    delta_t: f64,
    geps_factor: f64,
    niter: usize,
    seed: u64,
) -> PyResult<(Py<PyArray2<f64>>, Py<PyArray2<i64>>)> {
    let xs_vec: Vec<f64> = xs.as_array().iter().copied().collect();
    let ys_vec: Vec<f64> = ys.as_array().iter().copied().collect();
    let sg = sdf_grid.as_array();
    let grid_arr = ndarray::Array2::from_shape_vec(
        (sg.shape()[0], sg.shape()[1]),
        sg.iter().copied().collect(),
    ).map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("grid shape: {e}")))?;
    let sdf = RasterSdf::new(xs_vec, ys_vec, grid_arr, 1.0);

    let pfix_vec: Vec<Point2> = pfix
        .map(|a| a.as_array().rows().into_iter().map(|r| [r[0], r[1]]).collect())
        .unwrap_or_default();

    let cfg = DistmeshConfig {
        h0, bbox, pfix: pfix_vec, dptol, ttol, f_scale, delta_t, geps_factor,
        niter, seed, return_diagnostics: false,
    };

    let (mesh, _) = py.allow_threads(|| distmesh2d(&sdf, None, &cfg));

    let n = mesh.nodes.len();
    let m = mesh.elements.len();
    let nf: Vec<f64> = mesh.nodes.iter().flat_map(|p| [p[0], p[1]]).collect();
    let ef: Vec<i64> = mesh.elements.iter().flat_map(|t| [t[0] as i64, t[1] as i64, t[2] as i64]).collect();
    Ok((
        ndarray::Array2::from_shape_vec((n, 2), nf).unwrap().into_pyarray_bound(py).into(),
        ndarray::Array2::from_shape_vec((m, 3), ef).unwrap().into_pyarray_bound(py).into(),
    ))
}

#[pymodule]
fn admesh_rs(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(distmesh2d_rs, m)?)?;
    m.add_function(wrap_pyfunction!(distmesh2d_native_rs, m)?)?;
    m.add_function(wrap_pyfunction!(delaunay_rs, m)?)?;
    m.add_function(wrap_pyfunction!(mesh_quality_rs, m)?)?;
    Ok(())
}
