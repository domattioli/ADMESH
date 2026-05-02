<h1 align="center">ADMESH: An ADvanced, automatic unstructured MESH generator for 2D shallow-water models.</h1>

<p align="center">
  <strong><a href="https://github.com/coltonjconroy">Colton J. Conroy</a><sup>1</sup>, <a href="https://scholar.google.com/citations?user=mYPzjIwAAAAJ&hl=en">Ethan J. Kubatko</a><sup>1</sup>, Dustin W. West<sup>1</sup></strong><br>
  <sup>1</sup>Computational Hydrodynamics and Informatics Lab (CHIL), The Ohio State University<br>
  <em>Ocean Dynamics</em> 62, 1503–1517 (2012) · <a href="https://doi.org/10.1007/s10236-012-0574-0">doi:10.1007/s10236-012-0574-0</a>
</p>

<p align="center">
  Python implementation maintained by <a href="https://scholar.google.com/citations?user=IBFSkOcAAAAJ&hl=en">Dominik Mattioli</a> (Penn State University).
</p>

<p align="center">
  <a href="https://pypi.org/project/admesh2D/"><img src="https://img.shields.io/pypi/v/admesh2D.svg?label=PyPI" alt="PyPI version"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License"></a>
  <a href="https://github.com/domattioli/ADMESH/releases/tag/v0.1.0"><img src="https://img.shields.io/github/v/release/domattioli/ADMESH?include_prereleases" alt="Latest Release"></a>
</p>

<p align="center">
  <img src="papers/fig8_admesh_wnat.png" alt="ADMESH mesh of the Western North Atlantic, Gulf of Mexico, and Caribbean Sea." width="100%">
</p>

<p align="center">
  <a href="https://pypi.org/project/admesh2D/"><img alt="PyPI" src="https://img.shields.io/pypi/v/admesh2D.svg?style=flat-square"></a>
  <img alt="Status" src="https://img.shields.io/badge/status-beta-yellow?style=flat-square">
</p>

---

## Install

> 🚧 **0.1.0 in progress.** Spec 002 lands the default size-field stack
> + ADCIRC paired-edge BC support; the first PyPI tag follows when the
> Tier-2 / WNAT structural-validity gate is green
> ([issue #10](https://github.com/domattioli/ADMESH/issues/10)).
> Until then, install from source.

```bash
pip install admesh2D            # core (when 0.1.0 ships)
pip install admesh2D[viz]       # adds matplotlib for mesh.plot()
```

From source (current):

```bash
git clone https://github.com/domattioli/ADMESH.git
cd ADMESH
pip install -e ".[dev]"
```

Requires Python ≥ 3.10. Core dependencies: NumPy, SciPy, Numba, Shapely.

---

## Quickstart

> 🚧 The `triangulate()` defaults are stabilizing across spec 002.
> The 3-line idiom below works today; advanced kwargs
> (`enable_curvature`, `enable_medial_axis`, `bathymetry`,
> `tide_period`, `default_depth`, …) are documented in
> `specs/002-size-field-defaults/contracts/python-api-default-stack.md`.

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
`specs/001-pythonize-and-fort14-integration/` (shipped) and
`specs/002-size-field-defaults/` (in progress — wires the
MATLAB-faithful size-field stack as the default Phase-1 in
`triangulate()` + extends fort.14 for IBTYPE 3 / 4 / 13 / 24
paired-edge BC records). The faithful Python port of the original
13-stage pipeline is the production path (now 250+ tests passing);
the Pythonic API + fort.14 I/O are the 0.1.0 deliverables.

## Upstream

The reference MATLAB implementation is
[`coltonjconroy/ADMESH`](https://github.com/coltonjconroy/ADMESH),
maintained by the original author. That repository may carry features
beyond what this port currently covers; new functionality is adopted
here as it's pulled across.

## Related projects

- **[ADMESH-Domains](https://github.com/domattioli/ADMESH-Domains)** —
  federated registry of ADCIRC-compatible meshes (domains) for
  discovery, lineage tracking, and community contribution. Built as a
  companion to this library.

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
