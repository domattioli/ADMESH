<h1 align="center">ADMESH</h1>

<p align="center">
  <strong>An advanced, automatic unstructured mesh generator for 2D shallow-water models.</strong><br>
  Python port of the MATLAB ADMESH library, with native ADCIRC <code>fort.14</code> round-trip and a Pythonic API.
</p>

<p align="center">
  <a href="https://pypi.org/project/admesh2D/"><img src="https://img.shields.io/pypi/v/admesh2D.svg?label=PyPI" alt="PyPI version"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+"></a>
  <a href="https://doi.org/10.5281/zenodo.20264101"><img src="https://img.shields.io/badge/DOI-10.5281%2Fzenodo.20264101-blue" alt="DOI"></a>
  <a href="https://github.com/domattioli/ADMESH/issues"><img src="https://img.shields.io/github/issues/domattioli/ADMESH.svg" alt="Open issues"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License"></a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/domattioli/ADMESH/main/papers/fig8_admesh_wnat.png" alt="ADMESH mesh of the Western North Atlantic, Gulf of Mexico, and Caribbean Sea." width="100%">
  <br>
  <em>Western North Atlantic / Gulf / Caribbean — meshed with curvature-driven sizing and dominant-tide refinement.</em>
</p>

---

## Contents

- [Why ADMESH](#why-admesh)
- [Install](#install)
- [Quickstart](#quickstart)
- [The pipeline](#the-pipeline)
- [Boundary types](#boundary-types)
- [Status &amp; roadmap](#status--roadmap)
- [Documentation](#documentation)
- [Citation](#citation)
- [Upstream &amp; related projects](#upstream--related-projects)
- [Contact](#contact)
- [License](#license)

---

## Why ADMESH

For shallow-water modelers who need ADCIRC-ready meshes from Python:

- **MATLAB-faithful port.** 13 stages reproduced 1:1 from the OSU CHIL Lab `01_ADMESH_Library`, with numerical agreement tracked by a 250+ test suite. Switching from MATLAB to this library does not change your meshes.
- **Native ADCIRC `fort.14` I/O.** Read, mesh, write — bit-faithful round-trip including paired-edge boundary records (IBTYPE 3 / 4 / 13 / 24).
- **Curvature + medial-axis + bathymetry + tide-aware sizing.** Size field is a `min`-stack of physical drivers, not a hand-tuned scalar. Custom contributions compose on top.
- **Pythonic surface, faithful internals.** `Domain` / `Mesh` / `BoundarySegment` are frozen dataclasses with typed fields; the gnarly numerics stay inside the faithful-port modules and stay testable.
- **Cross-repo by design.** Pairs with [ADMESH-Domains](https://github.com/domattioli/ADMESH-Domains) (mesh registry) and the upstream MATLAB reference for lineage tracking.

Not the right tool if you need 3-D, anisotropic, or non-triangular elements — use `gmsh` for those.

## Install

```bash
pip install admesh2D            # core
pip install admesh2D[viz]       # adds matplotlib for mesh.plot()
```

From source:

```bash
git clone https://github.com/domattioli/ADMESH.git
cd ADMESH
pip install -e ".[dev]"
```

Requires Python ≥ 3.10. Core deps: NumPy, SciPy, Numba, Shapely. The import name is `admesh` (the `admesh2D` on PyPI is the distribution name — the `admesh` namespace on PyPI is an unrelated STL library).

**Install hiccups** (Numba on Apple Silicon, SciPy wheels on older Python): see [open issues](https://github.com/domattioli/ADMESH/issues) and file a new one if you hit a fresh failure.

## Quickstart

### Built-in domain

```python
import admesh
from admesh import domains

mesh = admesh.triangulate(domains.UNIT_DISK, h_max=0.1)
mesh.to_fort14("disk.14")
```

`mesh` is a frozen `Mesh` dataclass — typed `nodes`, `elements`, `boundaries` (each a `BoundarySegment` with a `BoundaryType` code), optional `bathymetry`, per-element `quality`.

### Round-trip with ADCIRC `fort.14`

```python
import admesh

mesh = admesh.read_fort14("input.14")
mesh.to_fort14("output.14")
assert mesh.equals(admesh.read_fort14("output.14"))     # bit-faithful
```

### Re-mesh an existing fort.14

```python
import admesh
from admesh.api import Domain

source = admesh.read_fort14("coarse.14")
domain = Domain.from_mesh(source)
refined = admesh.triangulate(domain, h_max=500.0, h_min=50.0)
refined.to_fort14("refined.14")
```

### Custom size-field contribution

```python
import numpy as np
import admesh

def refine_near_breaker(pts: np.ndarray) -> np.ndarray:
    return 50.0 + 0.2 * np.abs(pts[:, 0] - 1500.0)

mesh = admesh.triangulate(
    "coast.14",
    user_contribs=(refine_near_breaker,),
)
```

Built-in size-field stages (curvature, medial axis, bathymetry, tide) `min`-stack identically to MATLAB. User contributions compose on top via `combine=` (default: elementwise minimum).

### Build a `Domain` directly from an SDF

```python
import numpy as np
from admesh.api import Domain, triangulate

def sdf_disk(p: np.ndarray) -> np.ndarray:
    return np.linalg.norm(p, axis=1) - 1.0

mesh = triangulate(Domain(sdf=sdf_disk, bbox=(-1, -1, 1, 1)), h_max=0.1)
```

## The pipeline

Each call to `triangulate(...)` flows through the 13-stage ADMESH pipeline (faithful port of the MATLAB modules under `01_ADMESH_Library`):

| # | Stage | Module | Purpose |
|---|---|---|---|
| 1 | Distance | `admesh.distance` | Signed-distance grid from the domain SDF |
| 2 | Curvature | `admesh.curvature` | Refines near sharp boundary curvature |
| 3 | Medial axis | `admesh.medial_axis` | Adds sizing pressure in narrow channels |
| 4 | Bathymetry | `admesh.bathymetry` | Element size scales with depth gradient |
| 5 | Dominant tide | `admesh.dominate_tide` | Resolves tidal wavelength on the shelf |
| 6 | Boundary | `admesh.boundary` | Enforces BC labels at boundary edges |
| 7 | Mesh size | `admesh.mesh_size` | Numba-JIT iterative solver (`min`-stack) |
| 8 | distmesh2d | `admesh.distmesh` | Truss-equilibrium point placement |
| 9 | Quality | `admesh.quality` | Per-element shape metric, gate at q ≥ 0.3 |
| 10 | In-polygon | `admesh.in_polygon` | Winding-number containment tests |
| 11 | Inpaint | `admesh.inpaint` | Fills NaN holes in bathymetry / size grids |
| 12 | Background grid | `admesh.background_grid` | Anisotropic background field |
| 13 | Valence | `admesh.valence` | Edge-flip rebalancing (new in 0.2.0, issue #27) |

The Numba-JIT iterative solver replaces the C MEX from the MATLAB original — no compile step at install time.

## Boundary types

`BoundaryType` is an `IntEnum` over the ADCIRC `IBTYPE` codes that the fort.14 reader/writer names. Unmapped codes round-trip as plain `int` on `BoundarySegment.bc_type`.

| Code | Name | Meaning |
|---|---|---|
| 0 | `OPEN` | Open ocean / external water |
| 1 | `MAINLAND` (alias `WALL`) | Mainland boundary, no normal flux |
| 11 | `ISLAND` | Island boundary |
| 20 | `MAINLAND_FLUX` | Mainland with specified normal flux |
| 3 / 4 / 13 / 24 | (preserved as `int`) | Paired-edge / weir-type — read and written faithfully, not yet named in the enum |
| other | (preserved as `int`) | Round-tripped, not interpreted |

```python
from admesh import BoundaryType, read_fort14

mesh = read_fort14("coast.14")
for seg in mesh.boundaries:
    if seg.bc_type == BoundaryType.ISLAND:
        ...
```

## Status & roadmap

- **Shipped (v0.2.1).** Pythonic API + fort.14 round-trip + 13-stage faithful port + valence balancing + custom size-field hooks. Published to [PyPI](https://pypi.org/project/admesh2D/) and archived on [Zenodo](https://doi.org/10.5281/zenodo.20264101).
- **In flight.** Spec 009 release-readiness (CI workflows, mkdocs site, stage-module reorg into `admesh/_stages/`). Spec 008 Gmsh I/O.
- **Next.** Default size-field stack consolidation, paired-edge IBTYPE 3 / 4 / 13 / 24 promoted to named `BoundaryType` members, downstream consumer migration (`MADMESHR`, `CHILMESH`).

Open epics live as labeled issues — see [planning-required](https://github.com/domattioli/ADMESH/issues?q=is%3Aissue+label%3Aplanning-required).

## Documentation

- API reference: docstrings on `Domain`, `Mesh`, `BoundarySegment`, `triangulate`, `read_fort14`, `write_fort14`, and the 13 stage modules.
- Architecture + porting notes: [`docs/`](docs/) (governance, persistence journal, porting notes, domain I/O).
- Specs (design + acceptance criteria for each feature): [`specs/`](specs/).
- Constitution (project principles + faithful-port invariants): [`docs/governance/CONSTITUTION.md`](docs/governance/CONSTITUTION.md).
- A mkdocs site with auto-generated API reference lands with spec 009 R3.

## Citation

**Algorithm / theory** (cite the original paper):

> Conroy, C.J., Kubatko, E.J., West, D.W. (2012). ADMESH: an advanced, automatic unstructured mesh generator for shallow water models. *Ocean Dynamics* 62, 1503–1517. <https://doi.org/10.1007/s10236-012-0574-0>

**This software** (cite the archived release):

> Mattioli, D., Conroy, C.J., Kubatko, E.J., West, D.W. (2026). ADMESH: An advanced, automatic unstructured mesh generator for 2D shallow-water models (Python port). Zenodo. <https://doi.org/10.5281/zenodo.20264101>

The DOI `10.5281/zenodo.20264101` resolves to the latest release; version-specific DOIs are listed on the [Zenodo record](https://doi.org/10.5281/zenodo.20264101). A [`CITATION.cff`](CITATION.cff) is provided at the repo root for tools that consume it (GitHub's "Cite this repository" button, Zotero, etc.). Paper copy: [`papers/Conroy-2012-ADMESH.pdf`](papers/Conroy-2012-ADMESH.pdf).

## Upstream & related projects

- **[coltonjconroy/ADMESH](https://github.com/coltonjconroy/ADMESH)** — reference MATLAB implementation, maintained by the original author. New functionality is pulled across as it lands upstream.
- **[ADMESH-Domains](https://github.com/domattioli/ADMESH-Domains)** — federated registry of ADCIRC-compatible meshes for discovery, lineage tracking, and community contribution. Built as a companion to this library.

## Contact

- **Theory** (algorithm, size-field formulation, ADCIRC integration): Ethan J. Kubatko — [kubatko.3@osu.edu](mailto:kubatko.3@osu.edu)
- **Python port** (this repository): Dominik Mattioli — [github.com/domattioli](https://github.com/domattioli)

## License

Apache 2.0 — see [`LICENSE`](LICENSE).
