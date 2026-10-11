<h1 align="center">
  <img src="https://raw.githubusercontent.com/domattioli/ADMESH/main/docs/assets/hero/admesh_delbay_hero.gif" alt="ADMESH meshing Delaware Bay through three stages: initialized point cloud, DistMesh truss-solver relaxation, then FEM smoothing; element color tracks quality from magenta (poor) to cyan (equilateral)." width="100%">
</h1>

<p align="center">
  <strong>An ADvanced, automatic unstructured MESH generator for 2D shallow-water models</strong><br>
  Automatic unstructured mesh generation for shallow-water models, in Python and MATLAB

</p>

<p align="center">
  <strong><a href="https://scholar.google.com/citations?user=IBFSkOcAAAAJ&hl=en">Dominik Mattioli</a><sup>1†</sup>, Colton Conroy, Dustin West, <a href="https://scholar.google.com/citations?user=mYPzjIwAAAAJ&hl=en">Ethan Kubatko</a><sup>2</sup></strong><br>
  <sup>†</sup>Corresponding author | <sup>1</sup>Unaffiliated | <sup>2</sup>Ohio State University (<a href="https://ceg.osu.edu/computational-hydrodynamics-and-informatics-laboratory"><img src="https://img.shields.io/badge/The%20CHIL-a7b1b7?labelColor=ba0c2f&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHJlY3QgeD0iNCIgeT0iMiIgd2lkdGg9IjE2IiBoZWlnaHQ9IjIwIiByeD0iNyIgZmlsbD0iI2ZmZmZmZiIvPjxyZWN0IHg9IjguNSIgeT0iNyIgd2lkdGg9IjciIGhlaWdodD0iMTAiIHJ4PSIzIiBmaWxsPSIjYmEwYzJmIi8+PC9zdmc+" alt="CHIL"></a>)
</p>

<p align="center">
  <a href="https://pypi.org/project/admesh2D/#history"><img src="https://img.shields.io/github/v/release/domattioli/ADMESH?include_prereleases&label=release" alt="Latest release, including pre-releases"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+"></a>
  <a href="https://github.com/domattioli/ADMESH/actions/workflows/tests.yml"><img src="https://github.com/domattioli/ADMESH/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <a href="https://github.com/domattioli/ADMESH/issues"><img src="https://img.shields.io/github/issues/domattioli/ADMESH.svg" alt="Open issues"></a>
  <a href="https://doi.org/10.5281/zenodo.20264085"><img src="https://zenodo.org/badge/DOI/10.5281/zenodo.20264085.svg" alt="DOI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License"></a>
</p>

> **Background:** Two branches of ADMESH descend from the 2012 original by [Conroy et al.](https://github.com/coltonjconroy/ADMESH). The original group's MATLAB line is ADMESH+ v3 ([OSU-CHIL/ADMESH](https://github.com/OSU-CHIL/ADMESH); [10.5281/zenodo.10242565](https://doi.org/10.5281/zenodo.10242565)), maintained by Younghun Kang and Ethan Kubatko ([Kang & Kubatko, 2024](https://doi.org/10.5194/gmd-17-1603-2024)). This repository is the parallel branch: the 2012 library in Python, with the MATLAB source alongside at [`src/matlab/`](src/matlab/).

## Table of Contents

1. [Status & Roadmap](#1-status--roadmap)
2. [Overview](#2-overview)
3. [Installation](#3-installation)
4. [Quick start](#4-quick-start)
5. [Meshes from the Valence registry](#5-meshes-from-the-valence-registry)
6. [Pipeline](#6-pipeline)
7. [Performance](#7-performance)
8. [Limitations](#8-limitations)
9. [Citation](#9-citation)
10. [Documentation, Contributing, License](#10-documentation-contributing-license)

## 1. Status & Roadmap

**Current release: 1.0.0 (2026-10-02). Next: 1.0.5 (unreleased); see [CHANGELOG](CHANGELOG.md).** The public API (`admesh.__all__`, listed in [`docs/api/index.md`](docs/api/index.md)) is fixed for 1.x. The `admesh.<stage>` compatibility modules stay through 1.x and are removed no earlier than 2.0.

- **Roadmap:** 1D–2D constraint extraction (#186); single-mesh parallelization (#216); 3D ADMESH (#220); integration with [QuADMESH](https://github.com/domattioli/QuADMESH) (quads) and [CHILmesh](https://github.com/domattioli/CHILmesh) (mesh data structure and smoothing).

<div align="right"><a href="#table-of-contents"><sub>^ Back to top</sub></a></div>

## 2. Overview

`triangulate()` takes a domain (a `Domain`, TOML or JSON polygon file, `fort.14`, or registry filename) and two edge-length bounds, and returns a validated mesh. Without a size field, the size is uniform at `h_max`. Physics-based sizing and `background="octree"` are opt-in. The 13 numerical stages exist in both Python and MATLAB; a Numba solver replaces the original C MEX.

<div align="right"><a href="#table-of-contents"><sub>^ Back to top</sub></a></div>

## 3. Installation

```bash
pip install admesh2D                 # core: NumPy, SciPy, Numba, Shapely
pip install "admesh2D[viz]"          # + chilmesh for mesh.plot()
```

The PyPI distribution is `admesh2D`; the import name is `admesh`. (`pip install admesh` installs an unrelated STL library.) Requires Python 3.10 or newer. From source: `git clone https://github.com/domattioli/ADMESH.git && cd ADMESH && pip install -e ".[dev]"`.

<div align="right"><a href="#table-of-contents"><sub>^ Back to top</sub></a></div>

## 4. Quick start

```python
import admesh
from admesh import domains

# Built-in domain, uniform sizing at h_max.
mesh = admesh.triangulate(domains.NOTCHED_RECTANGLE, h_max=0.2, h_min=0.02)
mesh.to_fort14("notched.14")
# Re-mesh an existing ADCIRC grid at a new resolution.
old = admesh.read_fort14("legacy.14")
mesh = admesh.triangulate(admesh.Domain.from_mesh(old), h_min=50.0, h_max=2000.0)
```

`mesh` is a frozen `Mesh` dataclass with `nodes`, `elements`, `boundaries`, optional `bathymetry`, and per-element `quality`. Built-in domains: `UNIT_SQUARE`, `UNIT_DISK`, `L_SHAPE`, `ANNULUS`, `NOTCHED_RECTANGLE`. The full call list is in [`docs/api/index.md`](docs/api/index.md).

<div align="right"><a href="#table-of-contents"><sub>^ Back to top</sub></a></div>

## 5. Meshes from the Valence registry

The HTTP registry client ships in admesh2D 1.0.5 (unreleased). Meshes come through Valence, a token-gated mesh service.

Sign in with GitHub at https://valence-api.iqh766c2.workers.dev . A GitHub account at least 30 days old gets a token at once, shown once. Each token allows 500 downloads per token per day (reset at midnight UTC) and expires after one year.

```bash
export VALENCE_TOKEN=<your token>
```

```python
import admesh
domain = admesh.load_domain_from_registry("Block_O.14")
mesh = admesh.triangulate(domain)
```

Each download is checked against its SHA-256 hash. See the [Registry API contract](docs/registry-api-contract.md).

<div align="right"><a href="#table-of-contents"><sub>^ Back to top</sub></a></div>

## 6. Pipeline

`triangulate()` composes the stage modules in `admesh/_stages/`, which match the MATLAB library one to one and are locked.

Domain, then background grid (uniform or octree), then size field (curvature, medial axis, bathymetry, tide; min-stacked), then `distmesh2d` truss relaxation (Numba), then a validated `Mesh` (`fort.14` or `.msh`).

<div align="right"><a href="#table-of-contents"><sub>^ Back to top</sub></a></div>

## 7. Performance

Numba kernels cut end-to-end generation on the Western North Atlantic benchmark from 1257.5 s (v0.2.1) to 47.2 s (v0.5.0), a 26.6x speedup. `triangulate_batch` runs 5.09x faster on 8 workers than a serial loop. Tables, method and reproduction commands: [`docs/BENCHMARK_DELIVERABLE.md`](docs/BENCHMARK_DELIVERABLE.md#numba-kernel-and-batch-meshing-benchmarks).

<div align="right"><a href="#table-of-contents"><sub>^ Back to top</sub></a></div>

## 8. Limitations

- **Triangles only, in 2-D.** For quads use [QuADMESH](https://github.com/domattioli/QuADMESH); for 3-D or anisotropy use Gmsh.
- **The 2012 algorithm as published.** The vector-distance-transform medial axis of [Kang & Kubatko (2024)](https://doi.org/10.5194/gmd-17-1603-2024) is the opt-in `medial_method="vdt"`; the 1D–2D constraint extraction is not implemented.
- **Default sizing is uniform.** The physics-based size contributions are not wired in by default (issue #65).
- **Generated meshes carry no bathymetry**, and fort.14 IBTYPE 3/4/13/24 paired-node and weir columns are not preserved.
- **One process per mesh, CPU only.** The distmesh relaxation dominates wall-clock time on large domains.
- **Browser app:** [admesh.domattioli.com](https://admesh.domattioli.com/) runs ADMESH in the page through Pyodide, without Numba.

<div align="right"><a href="#table-of-contents"><sub>^ Back to top</sub></a></div>

## 9. Citation

- Algorithm: Conroy, C.J., Kubatko, E.J. & West, D.W. (2012). ADMESH: an advanced, automatic unstructured mesh generator for shallow water models. *Ocean Dynamics* 62, 1503–1517. <https://doi.org/10.1007/s10236-012-0574-0>
- This software: Mattioli, D.O., Conroy, C.J., West, D.W., Kubatko, E.J. (2026). ADMESH: automatic unstructured triangular mesh generator for 2D shallow-water models (Python). Zenodo. <https://doi.org/10.5281/zenodo.20264085>
- Upstream MATLAB line: Kang, Y. & Kubatko, E.J. (2024). An automatic mesh generator for coupled 1D–2D hydrodynamic models. *Geoscientific Model Development* 17, 1603–1625. <https://doi.org/10.5194/gmd-17-1603-2024>
- A [`CITATION.cff`](CITATION.cff) feeds GitHub's "Cite this repository" button. Version-specific DOIs are on the [Zenodo record](https://doi.org/10.5281/zenodo.20264085).

<div align="right"><a href="#table-of-contents"><sub>^ Back to top</sub></a></div>

## 10. Documentation, Contributing, License

- **Docs:** [`docs/quickstart.md`](docs/quickstart.md), [`docs/DOMAIN_IO.md`](docs/DOMAIN_IO.md), [`docs/api/`](docs/api/index.md), [`docs/PORTING_NOTES.md`](docs/PORTING_NOTES.md), [`docs/adr/`](docs/adr/), [`docs/gallery/`](docs/gallery/).
- **Contributing:** issues and pull requests on [GitHub](https://github.com/domattioli/ADMESH); see [`CONTRIBUTING.md`](CONTRIBUTING.md). To share a fort.14 mesh, [open an issue in this repository](https://github.com/domattioli/ADMESH/issues/new) (details: [`docs/share-your-mesh.md`](docs/share-your-mesh.md)).
- **Theory:** [Colton Conroy](https://github.com/coltonjconroy) | [Ethan Kubatko](https://ceg.osu.edu/people/kubatko.3). **Upstream MATLAB line:** [Younghun Kang](https://github.com/Younghun-Kang). **This repository:** [Dominik Mattioli](https://github.com/domattioli).

<!-- ack -->
**Acknowledgement.** Code added after the original MATLAB port was written using AI coding tools built on Anthropic and OpenAI models. The 13 ported stages are checked against the MATLAB reference tests.
<!-- /ack -->

**License.** Apache 2.0, see [`LICENSE`](LICENSE).

<div align="right"><a href="#table-of-contents"><sub>^ Back to top</sub></a></div>
