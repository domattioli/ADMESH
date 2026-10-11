# Public API

`triangulate()` is the entry point. The package also ships the surrounding workflow. Every name below is exported in `admesh.__all__`.

| Need | Call | Notes |
|---|---|---|
| Size control | `h_min`, `h_max`, `size_field=`, `user_contribs=`, `combine=`, `medial_method=` | The default is uniform at `h_max`. `compose_size_field` composes stage-module contributions (curvature, medial axis, bathymetry, tide) and custom callables that map `(N, 2)` points to edge length. `medial_method` is `None` by default. It adds a channel-width contribution from one of three medial-axis methods: `"grid"`, `"octree"` or `"vdt"`. |
| Multiscale domains | `background="octree"` | Evaluates the size field on a quadtree with leaf-graph gradient limiting. The default is `"uniform"`. |
| Reproducibility | `seed=`, `initial_points=`, `max_iter=`, `ttol=`, `dptol=` | Warm-start from a previous point set. Iteration stops at `max_iter`, `dptol`, or an empty edge set. |
| Many meshes | `triangulate_batch(domains, n_jobs=None, **kwargs)` | Runs `triangulate` on a process pool and returns meshes in input order, identical to a serial loop. Parallel runs need picklable domains: paths, registry filenames, or a `Domain` with a module-level SDF. `n_jobs=1` runs in-process. |
| Quality gate | `quality_gate=(min_q, mean_q)` | The default is `(0.30, 0.60)`. A mesh below it raises `ValueError`. Pass `(0.0, 0.0)` to disable. |
| ADCIRC I/O | `read_fort14`, `write_fort14`, `Mesh.to_fort14` | Round-trips nodes, elements, and boundary segments. `Fort14ParseError` reports line, expected, actual. |
| Gmsh I/O | `read_msh`, `write_msh`, `Mesh.to_msh` | Gmsh 2.2 ASCII. Boundary labels map to `BoundaryType`. `GmshParseError` reports malformed input. |
| Domain sources | `load_domain_from_{toml,json,fort14,registry}`, `list_available_domains` | A path or registry filename may also be passed to `triangulate()` directly. Formats in [DOMAIN_IO.md](../DOMAIN_IO.md). |
| Quality metrics | `mesh_quality`, `right_iso_quality` | Equilateral and right-isosceles targets. |
| Valence balancing | `balance_valence_triangles`, `compute_valence`, `get_valence_report` | Edge flipping toward degree-6 interior nodes, quality-guarded. |
| Quad preparation | `smooth_for_quadrangulation` | Right-isosceles smoother for downstream tri-to-quad fusion (CHILmesh, OceanMesh2D, ADCIRC v55+). |
| Plotting (`[viz]`) | `Mesh.plot`, `Mesh.plot_quality`, `Mesh.plot_layers` | Delegates to CHILmesh. Returns a Matplotlib axis. |

![Block-O before and after smooth_for_quadrangulation](https://raw.githubusercontent.com/domattioli/ADMESH/main/docs/gallery/block_o_before_after.png)

`smooth_for_quadrangulation` on the Block-O fixture (2,811 nodes): right-isosceles quality rises from 0.498 to 0.672 with connectivity unchanged.

Detailed pages: [triangulate](triangulate.md), [types](types.md), [I/O](io.md), [loaders](loaders.md), [quality](quality.md), [size field](size_field.md).
