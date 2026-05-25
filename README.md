<h1 align="center">ADMESH</h1>

<p align="center">
  <strong>Build and re-mesh ADCIRC domains — size-field-driven unstructured mesh generation with <code>fort.14</code> round-tripping.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/admesh2D/"><img src="https://img.shields.io/pypi/v/admesh2D.svg?label=PyPI" alt="PyPI version"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+"></a>
  <a href="https://github.com/domattioli/ADMESH/actions/workflows/tests.yml"><img src="https://github.com/domattioli/ADMESH/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <a href="https://doi.org/10.5281/zenodo.20264101"><img src="https://img.shields.io/badge/DOI-10.5281%2Fzenodo.20264101-blue" alt="DOI"></a>
  <a href="https://github.com/domattioli/ADMESH/issues"><img src="https://img.shields.io/github/issues/domattioli/ADMESH.svg" alt="Open issues"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License"></a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/domattioli/ADMESH/main/papers/fig8_admesh_wnat.png" alt="ADMESH mesh of the Western North Atlantic, Gulf of Mexico, and Caribbean Sea." width="100%">
  <br>
  <em>The size function (red = fine, blue = coarse) drives node placement; force-balance relaxation pushes element quality toward equilateral.</em>
</p>

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

```python
import admesh
from admesh import domains

mesh = admesh.triangulate(domains.UNIT_DISK, h_max=0.1)
mesh.to_fort14("disk.14")
```

`mesh` is a frozen `Mesh` dataclass — typed `nodes`, `elements`, `boundaries` (each a `BoundarySegment` with a `BoundaryType` code), optional `bathymetry`, per-element `quality`. Regenerate the hero animation via `python scripts/render_annulus_animation.py` (needs `matplotlib` + `pillow`; optional `ffmpeg` for MP4).

<p align="center">
  <img src="https://raw.githubusercontent.com/domattioli/ADMESH/main/papers/quickstart_notched.png" alt="Triangulation of the notched_rectangle MVP domain at h=0.04." width="60%">
  <br>
  <em>Notched-rectangle domain, meshed at <code>h=0.04</code> with the default curvature + medial-axis size-field stack.</em>
</p>

See [`docs/`](docs/) for fort.14 round-trip, re-mesh, custom size-field, and SDF-domain examples.

## Pipeline

```mermaid
flowchart LR
    A["SDF / fort.14"] --> B["Domain"]
    B --> C["Size field\n(curvature + medial axis\n+ bathy + tide)"]
    C --> D["distmesh2d\n(truss equilibrium)"]
    D --> E["Mesh\n(fort.14 out)"]
```

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

## Performance

Per-stage timings on the **WNAT (Hagen)** domain — a 144-ring Western North Atlantic coastline (Gulf of Mexico + Caribbean + US East Coast). Size-field parameters are derived from the original ADCIRC mesh (`wnat_test.14`): `hmin=0.119`, `hmax=0.967`, `g=0.21`. `hmin` is the *finest real element* — the minimum edge length after dropping the bottom 0.1% as sliver outliers — so the re-mesh resolves the coast/shelf to the same floor the original mesh was built to (these params reproduce its ~18.8k-element count, mean quality 0.94). Both columns run the identical pipeline at a fixed `niter=120` so the numbers isolate per-call cost. `v0.5.0` is still pure Python — the speedup comes from a Numba-JIT uniform-grid SDF kernel (`_fast_sdf.py`) replacing the shapely/scipy SDF, plus the Numba `solve_iter` size-field smoother.

| Algorithm step | v0.2.1 (original Python) | v0.5.0 (Numba-optimized Python) | speedup |
|---|---|---|---|
| domain load + SDF build | 0.018 | 0.018 | 1.0x |
| SDF grid eval (`eval_sdf_grid`) | 1.497 | 0.277 | 5.4x |
| curvature (`apply_curvature`) | 0.002 | 0.003 | 0.9x |
| medial axis (`apply_medial_axis`) | 0.466 | 0.423 | 1.1x |
| grading solve (`solve_iter`, g) | 0.484 | 0.006 | 75.4x |
| size-field build (subtotal) | 2.450 | 0.709 | 3.5x |
| distmesh (point gen + relax) | 292.0 | 9.077 | 32.2x |
| quality (`mesh_quality`) | 0.002 | 0.002 | 1.0x |
| **TOTAL** | **294.5 s** | **9.8 s** | **30.0x** |

|  | v0.2.1 | v0.5.0 |
|---|---|---|
| nodes | 10473 | 10473 |
| elements | 18843 | 18845 |
| Min. Elem Quality | 0.020 | 0.023 |
| Mean Elem Quality | 0.940 | 0.940 |
| StDev Elem Quality | 0.088 | 0.087 |

Output meshes are statistically identical (same node count, same quality distribution) — the optimization is speed-only:

![WNAT re-mesh quality comparison](output/wnat_quality_comparison.png)

Reproduce or extend across new versions:

```bash
python benchmarks/compare_versions.py \
    --mesh tests/fixtures/fort14/adcirc_examples/wnat_test.14 \
    --domain benchmarks/data/wnat_onur_boundary.json \
    --ref v0.2.1="v0.2.1 (original Python)" \
    --ref current="v0.5.0 (Numba-optimized Python)" \
    --niter 120 --hist
```

Add a `--ref <tag>="<label>"` per version to compare; the table writes to `benchmarks/results/version_comparison.md`.

## Ecosystem

| Repo | Role |
|---|---|
| [CHILmesh](https://github.com/domattioli/CHILmesh) | Core engine — ADMESH consumes it for adjacency, smoothing, and quality analysis |
| [ADMESH-Domains](https://github.com/domattioli/ADMESH-Domains) | Curated ADCIRC mesh registry; pairs with ADMESH for discovery and contribution |
| [QuADMesh](https://github.com/domattioli/QuADMesh) | Quad counterpart — converts ADMESH triangulations to quadrilateral meshes |
| [MADMESHing](https://github.com/domattioli/MADMESHing) | Benchmark harness comparing ADMESH (control tri) vs quad generators |

**Upstream MATLAB reference**: [coltonjconroy/ADMESH](https://github.com/coltonjconroy/ADMESH) — maintained by the original authors; new functionality pulled across as it lands.

*[DomI](https://github.com/domattioli/DomI) provides dev-session skills and governance for all repos.*

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

## Contributing

Contributions and bug reports are welcome — open an issue or pull request on [GitHub](https://github.com/domattioli/ADMESH).

**Theory** (algorithm, size-field formulation, ADCIRC integration): Ethan J. Kubatko — [kubatko.3@osu.edu](mailto:kubatko.3@osu.edu) / **Python port** (this repository): Dominik Mattioli — [github.com/domattioli](https://github.com/domattioli)

## License

Apache 2.0 — see [`LICENSE`](LICENSE).
