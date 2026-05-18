# ADMESH

**A**dvanced, automatic, unstructured **MESH** generator for 2D shallow-water
domains — a Python port of the original MATLAB `01_ADMESH_Library` (Conroy,
Kubatko, & West, *Ocean Dynamics* 62, 2012;
[DOI 10.1007/s10236-012-0574-0](https://doi.org/10.1007/s10236-012-0574-0)).

ADMESH consumes a 2D domain — a polygon ring (or rings with holes), an
ADCIRC `fort.14` file, or a `admesh-domains` registry id — and produces a
triangular mesh ready for shallow-water simulation (ADCIRC, SCHISM, etc.).

## Install

> 🚧 **0.1.0 is in progress** — the headline default-size-field stack
> still fails its Tier-1 / Tier-2 release-gate tests against real coastal
> fixtures ([issue #10](https://github.com/domattioli/ADMESH/issues/10)).
> Until 0.1.0 ships, install from source.

```bash
pip install -e ".[dev]"            # from a clone (development)
pip install admesh2D               # core (when 0.1.0 ships)
pip install admesh2D[viz]          # add matplotlib for mesh.plot()
```

Requires Python ≥ 3.10. Core deps: NumPy, SciPy, Numba, Shapely,
`admesh-domains`.

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
of the MATLAB reference and may evolve as the port is refined. See
[Constitution](governance/CONSTITUTION.md) Article II.1.

## Project state

- **Maturity**: pre-0.1.0; first PyPI tag tracked by [spec 009](https://github.com/domattioli/ADMESH/blob/daily-issue-fixing/specs/009-release-readiness-for-0.1.0/spec.md).
- **License**: Apache-2.0.
- **Repository**: [github.com/domattioli/ADMESH](https://github.com/domattioli/ADMESH).
- **Sibling registry**: [github.com/domattioli/ADMESH-Domains](https://github.com/domattioli/ADMESH-Domains) — federated mesh metadata + HuggingFace-mirrored data files.

## Citing

If ADMESH contributes to a publication, please cite the original Ocean Dynamics paper:

> Conroy, C. J., Kubatko, E. J., & West, D. W. (2012). ADMESH: an
> advanced, automatic unstructured mesh generator for shallow water
> models. *Ocean Dynamics*, 62, 1503–1517.
> [doi:10.1007/s10236-012-0574-0](https://doi.org/10.1007/s10236-012-0574-0)
