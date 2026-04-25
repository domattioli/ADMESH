<h1 align="center">ADMESH</h1>

<p align="center">
  An advanced, automatic unstructured mesh generator for 2D
  shallow-water models.
</p>

<p align="center">
  <strong>Colton J. Conroy<sup>1</sup>, <a href="https://scholar.google.com/citations?user=mYPzjIwAAAAJ&hl=en">Ethan J. Kubatko</a><sup>1</sup>, Dustin W. West<sup>1</sup></strong><br>
  <sup>1</sup>Computational Hydrodynamics and Informatics Lab (CHIL), The Ohio State University<br>
  <em>Ocean Dynamics</em> 62, 1503–1517 (2012) · <a href="https://doi.org/10.1007/s10236-012-0574-0">doi:10.1007/s10236-012-0574-0</a>
</p>

<p align="center">
  Python implementation maintained by <a href="https://scholar.google.com/citations?user=IBFSkOcAAAAJ&hl=en">Dominik Mattioli</a> (Penn State University).
</p>

<p align="center">
  <img src="papers/fig8_admesh_wnat.png" alt="ADMESH mesh of the Western North Atlantic, Gulf of Mexico, and Caribbean Sea." width="100%">
</p>

---

## Install

> ⚠ PyPI release is not live yet — install from source until v1 ships.

```bash
git clone https://github.com/domattioli/ADMESH.git
cd ADMESH
pip install -e ".[dev]"

# Once v1 is published:
# pip install admesh2D          # core
# pip install admesh2D[viz]     # adds matplotlib for mesh.plot()
```

Requires Python ≥ 3.10. Core dependencies: NumPy, SciPy, Numba, Shapely.

---

## Quickstart

> ⚠ The API below is the **target** v1 surface defined by
> `specs/001-pythonize-and-fort14-integration/`. It is not yet
> implemented. The existing module-level functions
> (`admesh.routine.ADmeshRoutine`, `admesh.distmesh.distmesh2d_admesh`,
> …) remain the production path until v1 lands.

```python
import admesh

domain = admesh.domain_from_polygon([outer_ring_xy, hole_ring_xy])
mesh = admesh.triangulate(domain)
mesh.to_fort14("out.14")
```

`mesh` is a frozen `Mesh` dataclass — typed nodes, elements, boundary
segments (with `BoundaryType` codes), and per-element quality.

### Round-trip with ADCIRC `fort.14`

```python
mesh = admesh.read_fort14("input.14")
mesh.to_fort14("output.14")
assert mesh.equals(admesh.read_fort14("output.14"))
```

### Custom size-field contribution

```python
def refine_near_breaker(pts):
    return 50.0 + 0.2 * np.abs(pts[:, 0] - 1500.0)

mesh = admesh.triangulate(domain, user_contribs=[refine_near_breaker])
```

Built-in size-field stages (curvature, medial axis, bathymetry, tide)
`min`-stack identically to MATLAB. User contributions compose on top via
a user-chosen combiner (default elementwise minimum).

---

## Status

Under construction. The v1 plan and task list live in
`specs/001-pythonize-and-fort14-integration/`. The faithful Python port
of the original 13-stage pipeline is the current production path
(142 tests passing); the Pythonic API and fort.14 I/O above are the v1
deliverables.

## Citation

> Conroy, C.J., Kubatko, E.J., West, D.W. (2012). ADMESH: an advanced,
> automatic unstructured mesh generator for shallow water models.
> *Ocean Dynamics* 62, 1503–1517. <https://doi.org/10.1007/s10236-012-0574-0>

A copy is included at [`papers/Conroy-2012-ADMESH.pdf`](papers/Conroy-2012-ADMESH.pdf).

## Contact

- **Theory** (algorithm, size-field formulation, ADCIRC integration):
  Ethan J. Kubatko — [kubatko.3@osu.edu](mailto:kubatko.3@osu.edu)
- **Code** (this repository): Dominik Mattioli —
  [github.com/domattioli](https://github.com/domattioli)

## License

Apache 2.0 — see `LICENSE`.
