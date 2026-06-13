<h1 align="center">ADMESH</h1>

<p align="center">
  <strong>An ADvanced, automatic unstructured MESH generator for 2D shallow-water models.</strong><br>
  A faithful Python port of the MATLAB ADMESH library, with a Pythonic API.
</p>

<p align="center">
  <strong><a href="https://scholar.google.com/citations?user=IBFSkOcAAAAJ&hl=en">Dominik Mattioli</a><sup>1†</sup>, <a href="https://scholar.google.com/citations?user=mYPzjIwAAAAJ&hl=en">Ethan Kubatko</a><sup>2</sup></strong><br>
  <sup>†</sup>Corresponding author | <sup>1</sup>Unaffiliated | <sup>2</sup>Ohio State University (CHIL)
</p>

<p align="center">
  <a href="https://pypi.org/project/admesh2D/"><img src="https://img.shields.io/pypi/v/admesh2D.svg?label=PyPI" alt="PyPI version"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+"></a>
  <a href="https://github.com/domattioli/ADMESH/actions/workflows/tests.yml"><img src="https://github.com/domattioli/ADMESH/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <a href="https://doi.org/10.5281/zenodo.20264101"><img src="https://img.shields.io/badge/DOI-10.5281%2Fzenodo.20264101-blue" alt="DOI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License"></a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/domattioli/ADMESH/main/docs/assets/hero/admesh_delbay_hero.gif" alt="ADMESH meshing Delaware Bay through three stages: initialized point cloud, DistMesh truss-solver relaxation, then FEM smoothing — element color tracks quality from magenta (poor) to cyan (equilateral)." width="100%">
  <br>
  <em>A graded <a href="https://github.com/domattioli/ADMESH-Domains">Delaware Bay</a> mesh — fine in the upper river, coarse in the open bay — evolving through the pipeline: <strong>1.</strong> initialization → <strong>2.</strong> DistMesh truss solver → <strong>3.</strong> FEM smoothing. Element color tracks quality (magenta = poor → cyan = equilateral).</em>
</p>

> **MATLAB users:** This library is the actively-developed successor to the original MATLAB codebase by [Conroy et al.](https://github.com/coltonjconroy/ADMESH) (no longer maintained). An unmaintained copy of that original is kept in-repo at [`src/matlab/`](src/matlab/) for provenance. Version 1.0.0 ships with a MATLAB wrapper of the modernized code (est. Aug 2026).

---

## Table of Contents

- [Why ADMESH](#why-admesh)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Pipeline](#pipeline)
- [Performance](#performance)
- [Status & roadmap](#status--roadmap)
- [Citation](#citation)
- [Contributing](#contributing) · [Documentation](#documentation) · [License](#license)

---

## Why ADMESH

For shallow-water modelers who need ADCIRC-ready meshes from Python:

- **The port does not change your meshes.** Thirteen stages reproduced 1:1 from the OSU CHIL Lab `01_ADMESH_Library`, with a 430-test suite tracking numerical agreement against the MATLAB reference.
- **Native ADCIRC `fort.14` I/O.** Bit-faithful read/mesh/write round-trip, including paired-edge boundary records (IBTYPE 3/4/13/24). ADCIRC format only — not gmsh, not generic.
- **Element size follows the physics.** Size adapts to boundary curvature, channel width, bathymetric gradient, and tidal wavelength through automatic `min`-stack composition; custom contributions layer on top. No hand-tuned scalar.
- **An adaptive background grid for multiscale domains.** `triangulate(background="octree")` refines the size field on a quadtree instead of a uniform grid, concentrating evaluation where the geometry demands it — opt-in; the uniform grid remains the default.
- **Pythonic surface, faithful internals.** `Domain` / `Mesh` / `BoundarySegment` are frozen, typed dataclasses; the numerics stay inside the locked faithful-port modules.

Not the right tool for 3-D, anisotropic, or non-triangular elements — use `gmsh` for those.

## Installation

```bash
pip install admesh2D            # core
pip install admesh2D[viz]       # adds chilmesh for mesh.plot() / plot_quality()
```

> ⚠️ **Install `admesh2D`, not `admesh`.** The distribution name is **`admesh2D`**; the import name stays `admesh` (`import admesh`). `pip install admesh` pulls an unrelated C STL-repair library that needs `admesh/stl.h` at build time and will fail.

Requires Python ≥ 3.10. Core dependencies: NumPy, SciPy, Numba, Shapely. From source:

```bash
git clone https://github.com/domattioli/ADMESH.git
cd ADMESH && pip install -e ".[dev]"
```

## Quick start

```python
import admesh
from admesh import domains

# Uniform sizing
mesh = admesh.triangulate(domains.UNIT_DISK, h_max=0.1)
mesh.to_fort14("disk.14")

# Graded sizing: fine features, coarse interior
mesh = admesh.triangulate(domains.NOTCHED_RECTANGLE, h_max=0.2, h_min=0.02)
mesh.to_fort14("notched.14")
```

`mesh` is a frozen `Mesh` dataclass: typed `nodes`, `elements`, `boundaries` (each a `BoundarySegment` carrying a `BoundaryType` code), optional `bathymetry`, and per-element `quality`. `h_min` / `h_max` set the size bounds; pass a `size_field` callable to grade explicitly. fort.14 boundary labels round-trip through `BoundaryType`, an `IntEnum` over ADCIRC `IBTYPE` codes (`OPEN=0`, `MAINLAND=1`, `ISLAND=11`, `MAINLAND_FLUX=20`); paired-edge and weir codes (3/4/13/24) preserve as plain `int`.

See [`docs/`](docs/) for fort.14 round-trip, re-meshing, custom size-field, and SDF-domain examples.

## Pipeline

`triangulate(...)` runs the 13-stage ADMESH pipeline; a Numba-JIT solver replaces the original C MEX, so there is no compile step at install.

```mermaid
flowchart LR
    A["SDF / fort.14"] --> B["Domain"]
    B --> C["Size field<br>(curvature + medial axis<br>+ bathymetry + tide)"]
    C --> D["distmesh2d<br>(truss equilibrium)"]
    D --> E["Mesh<br>(fort.14 out)"]
```

## Performance

The Numba-JIT SDF kernel and `solve_iter` smoother cut end-to-end mesh generation on the Western North Atlantic benchmark from **1257.5 s to 47.2 s — a 26.7× speedup** at unchanged quality (`mean 0.963`), measured at `hmin=0.05` / `g=0.10` / `niter=120`.

| | v0.2.1 | v0.5.0 (Numba) |
|---|---|---|
| total | 1257.5 s | **47.2 s** |
| nodes / elements | 49 377 / 93 655 | 49 377 / 93 642 |
| mean element quality | 0.963 | 0.962 |

The C++ force kernel and full-stage native rewrite (v1.0.0 / v1.1.0) are in flight; the per-stage breakdown and the version-comparison harness live in [`benchmarks/`](benchmarks/results/). The forward benchmark standard is the [ENPAC 2003](https://github.com/domattioli/ADMESH-Domains) tidal database (272,913 nodes), replacing WNAT for large-domain timing.

Reproduce or extend:

```bash
python benchmarks/compare_versions.py --hist \
    --mesh tests/fixtures/fort14/adcirc_examples/wnat_test.14 \
    --domain benchmarks/data/wnat_onur_boundary.json \
    --hmin 0.05 --g 0.10 --niter 120
```

## Status & roadmap

- **Shipped (v0.2.1).** Pythonic API, fort.14 round-trip, 13-stage faithful port, valence balancing, custom size-field hooks. On [PyPI](https://pypi.org/project/admesh2D/) and archived on [Zenodo](https://doi.org/10.5281/zenodo.20264101).
- **In flight.** Octree adaptive background grid (`background="octree"`); C++ force kernel and native stage rewrite; Gmsh I/O; default size-field-stack consolidation.
- **Next.** Paired-edge IBTYPE 3/4/13/24 promoted to named `BoundaryType` members; hosted mkdocs site.

Open epics live as labeled issues — see [planning-required](https://github.com/domattioli/ADMESH/issues?q=is%3Aissue+label%3Aplanning-required).

## Citation

**Algorithm** (cite the original paper):

> Conroy, C.J., Kubatko, E.J., West, D.W. (2012). ADMESH: an advanced, automatic unstructured mesh generator for shallow water models. *Ocean Dynamics* 62, 1503–1517. <https://doi.org/10.1007/s10236-012-0574-0>

**This software** (cite the archived release):

> Mattioli, D., Conroy, C.J., Kubatko, E.J., West, D.W. (2026). ADMESH: An advanced, automatic unstructured mesh generator for 2D shallow-water models (Python port). Zenodo. <https://doi.org/10.5281/zenodo.20264101>

A [`CITATION.cff`](CITATION.cff) feeds GitHub's "Cite this repository" button; version-specific DOIs are on the [Zenodo record](https://doi.org/10.5281/zenodo.20264101).

## Documentation

API reference lives in the docstrings (`triangulate`, `Domain`, `Mesh`, `BoundarySegment`, `read_fort14` / `write_fort14`, the 13 stage modules). Design notes, the porting log, and domain-format specs are under [`docs/`](docs/) and [`specs/`](specs/); project invariants in [`CONSTITUTION.md`](docs/governance/CONSTITUTION.md).

## Contributing

Issues and pull requests are welcome on [GitHub](https://github.com/domattioli/ADMESH).

- **Theory** (algorithm, size-field formulation, ADCIRC integration): Ethan J. Kubatko — [kubatko.3@osu.edu](mailto:kubatko.3@osu.edu)
- **Python port** (this repository): Dominik Mattioli — [github.com/domattioli](https://github.com/domattioli)

## License

Apache 2.0 — see [`LICENSE`](LICENSE).
