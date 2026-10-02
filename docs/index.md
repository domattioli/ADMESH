# ADMESH

**A**dvanced, automatic, unstructured **MESH** generator for 2D shallow-water
models. This package is a modernized Python version of the MATLAB ADMESH of
Conroy, Kubatko and West (*Ocean Dynamics* 62, 1503–1517, 2012;
[doi:10.1007/s10236-012-0574-0](https://doi.org/10.1007/s10236-012-0574-0)).

ADMESH takes a 2D domain and returns a triangular mesh for shallow-water
models such as ADCIRC. The domain can be a polygon ring (or rings with
holes), an ADCIRC `fort.14` file, or a registry id.

What the package contains:

- **The 2012 method, stage by stage.** The 13 stage modules port the MATLAB
  library function by function. Tests check each stage against reference
  fixtures exported from the MATLAB source.
- **A small public API.** `Domain`, `Mesh` and `triangulate` cover the usual
  path from a domain to a mesh.
- **File input and output.** The package reads and writes ADCIRC `fort.14`
  and Gmsh 2.2 ASCII `.msh`. Loaders build a `Domain` from TOML, JSON or
  `fort.14` files.
- **Size-field composition.** `compose_size_field` combines several
  mesh-size contributions into one field.
- **Batch meshing.** `triangulate_batch` meshes several domains in parallel
  worker processes.
- **Speed.** Numba compiles the hot kernels. An optional C++ accelerator
  runs the distmesh relaxation; without it, the package uses the Python and
  Numba code.
- **A browser app.** [admesh.domattioli.com](https://admesh.domattioli.com/)
  runs the package in the page. Files stay on your computer.

## Install

```bash
pip install admesh2D                 # core: NumPy, SciPy, Numba, Shapely
pip install "admesh2D[viz]"          # + chilmesh for mesh.plot()
pip install "admesh2D[registry]"     # + huggingface_hub for registry downloads
```

The PyPI distribution is `admesh2D`. The import name is `admesh`.
Requires Python 3.10 or newer. From a clone: `pip install -e ".[dev]"`.

## Three-line quickstart

```python
import admesh

domain = admesh.load_domain_from_fort14("coast.14")
mesh = admesh.triangulate(domain)
mesh.to_fort14("out.14")
```

See **[Quickstart](quickstart.md)** for the full walk-through (size-field
contributions, registry loading, quality gates, round-trip with ADCIRC).

## API

Public surface, listed by area:

| Function                     | Returns         | Purpose                                  |
|------------------------------|-----------------|------------------------------------------|
| [`triangulate`](api/triangulate.md) | `Mesh`         | Build a triangular mesh on a `Domain` |
| [`Mesh`](api/types.md), [`Domain`](api/types.md), [`BoundarySegment`](api/types.md), [`BoundaryType`](api/types.md) | dataclasses | Core data types |
| [`read_fort14` / `write_fort14`](api/io.md) | `Mesh` / file | ADCIRC `fort.14` round-trip |
| [`compose_size_field`](api/size_field.md) | `SizeFieldFn` | Combine multiple size-field contributions |
| [`mesh_quality`, `right_iso_quality`](api/quality.md) | float, float, array | Per-element quality metrics |
| [`smooth_for_quadrangulation`](api/quality.md) | `(p, t)` | Right-isoceles preprocessor for tri→quad fusion |
| [`load_domain_from_fort14`, `..._json`, `..._toml`, `..._registry`](api/loaders.md) | `Domain` | Build a `Domain` from a file or the registry |
| [`balance_valence_triangles`](api/valence.md) | `BalanceResult` | Edge-flip pass to balance node valence |

The 13 faithful-port stage modules (`admesh.curvature`, `admesh.distmesh`,
`admesh.medial_axis`, etc.) are accessible by direct import but carry no
semver guarantee on internal signatures — they are numerical translations
of the MATLAB reference and may evolve as the port is refined.

## Project state

- **Maturity**: 1.0.0b1, beta. The public API is fixed for 1.x.
- **License**: Apache-2.0.
- **Repository**: [github.com/domattioli/ADMESH](https://github.com/domattioli/ADMESH).
- **Sibling registry**: [github.com/domattioli/ADMESH-Domains](https://github.com/domattioli/ADMESH-Domains) — federated mesh metadata + HuggingFace-mirrored data files.

## Citing

If ADMESH contributes to a publication, please cite the original Ocean Dynamics paper:

> Conroy, C. J., Kubatko, E. J., & West, D. W. (2012). ADMESH: an
> advanced, automatic unstructured mesh generator for shallow water
> models. *Ocean Dynamics*, 62, 1503–1517.
> [doi:10.1007/s10236-012-0574-0](https://doi.org/10.1007/s10236-012-0574-0)
