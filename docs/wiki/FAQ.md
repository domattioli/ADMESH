# FAQ

## Why is the PyPI package called `admesh2D` and not `admesh`?

The name `admesh` is already taken on PyPI by an unrelated package
that has nothing to do with this project. To avoid confusion, this
project distributes as **`admesh2D`** on PyPI, while the importable
Python module is still `import admesh`.

```bash
pip install admesh2D            # the package on PyPI
```

```python
import admesh                   # the module name in your code
```

If you find a PyPI page titled `admesh` (no `2D` suffix), it isn't
this project — don't install it expecting ADCIRC mesh generation.

A possible future 3D-element extension of this project is on the
[Roadmap](Roadmap.md) as a post-v1 placeholder. Whether it ships under
`admesh3D` or some other name hasn't been decided.

## Why a Python port at all?

The MATLAB original is excellent for research but expensive to deploy
and hard to compose with the rest of the scientific-Python stack
(NumPy, Numba, SciPy, Shapely, xarray). A Python port lets ADMESH
plug into pipelines that already exist around ADCIRC pre / post-
processing, opens it to users without a MATLAB licence, and makes
parallel / GPU acceleration paths tractable (see
[#8](https://github.com/domattioli/ADMESH/issues/8)).

## How does this differ from `coltonjconroy/ADMESH`?

[`coltonjconroy/ADMESH`](https://github.com/coltonjconroy/ADMESH) is
the canonical MATLAB implementation, maintained by the original
authors. This repo is a Python port maintained by Dominik Mattioli
(Penn State). Where the two diverge:

- **Language**: Python + NumPy + Numba vs. MATLAB.
- **Faithfulness**: per the
  [constitution](https://github.com/domattioli/ADMESH/blob/main/docs/governance/CONSTITUTION.md)
  Article II, the 13 stage modules stay numerically identical to the
  MATLAB reference; the Pythonic API in `api.py` is additive.
- **Coverage**: the Python port covers the triangular pipeline only.
  `tri2quad` and the quadrilateral extensions in
  [`domattioli/QuADMesh-MATLAB`](https://github.com/domattioli/QuADMesh-MATLAB)
  are out of scope for v1.

## Why no quadrilateral meshing?

The MATLAB `tri2quad` and quad pipeline live in
[`domattioli/QuADMesh-MATLAB`](https://github.com/domattioli/QuADMesh-MATLAB)
(the source MATLAB codebase) and are scoped out of v1 to keep the
first PyPI release tightly focused on the triangular path that ADCIRC
and the 2012 ADMESH paper describe.

For quad / mixed work in Python, two sibling projects already cover
the space (see [Ecosystem](Ecosystem.md)):

- [**`chilmesh`**](https://pypi.org/project/chilmesh/) — published
  Python data structure + FEM smoother + `fort.14` I/O for tri /
  quad / mixed meshes. Wraps an ADMESH output (or any source) for
  smoothing, quality analysis, and ADCIRC export.
- [**MADMESHR**](https://github.com/domattioli/MADMESHR) — RL-based
  *generator* of tri / quad / mixed meshes from a domain. MVP /
  PoC stage; not yet on PyPI.

A native quad path inside ADMESH itself may land as a later spec
(see [`specs/004-quad-prep-smoother/`](https://github.com/domattioli/ADMESH/tree/main/specs/004-quad-prep-smoother)
for the preparatory triangle-smoother spec) once the triangular
release is stable, depending on whether the work is better served by
extending this repo or by leaving it to the siblings.

## Why no GPU yet?

Acceleration work is post-v1, tracked by
[#8](https://github.com/domattioli/ADMESH/issues/8). The 0.1.0
release prioritises *correctness vs. the MATLAB reference* over
*speed*. Once the structural-validity gates are passing and we have
a real benchmark fixture, GPU and CPU-parallel paths become
candidate specs.

## Why no C extensions? The MATLAB has `MeshSizeIterativeSolver.c`.

[Constitution Article II](https://github.com/domattioli/ADMESH/blob/main/docs/governance/CONSTITUTION.md)
forbids C extensions in the first cut to keep the install path
trivial (`pip install` with no compiler toolchain required) and to
keep the source readable by users who don't speak C. Numba `@njit`
gives us comparable performance for the iterative solver — see
[`admesh/mesh_size.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/mesh_size.py).
A C-extension path may be revisited post-v1 if profiling justifies
it.

## What's the status of the 0.1.0 PyPI release?

Tracked on the [Roadmap](Roadmap.md) page and in
[`docs/governance/PROJECT_PLAN.md`](https://github.com/domattioli/ADMESH/blob/main/docs/governance/PROJECT_PLAN.md).
Three open release-blockers:
[#10](https://github.com/domattioli/ADMESH/issues/10),
[#11](https://github.com/domattioli/ADMESH/issues/11),
[#12](https://github.com/domattioli/ADMESH/issues/12).

## Where do I find test fixtures / reference meshes?

The Tier-2 fixture (Western North Atlantic) and other reference
meshes live in [ADMESH-Domains](https://github.com/domattioli/ADMESH-Domains)
— a sibling registry with PyPI package, HuggingFace mirror, and
GitHub-pages browse site. Use:

```bash
pip install admesh-domains[hf]
```

```python
from admesh_domains import get_mesh
wnat = get_mesh("wnat_test")
```

See the [Ecosystem](Ecosystem.md) page for the wider context.

## Can I help?

Yes — see [Contributing](Contributing.md). Issues labelled `severity:low`
or `post-v1` (#5, #6, #8, #9) are good places to start scoping
discussions; release-blockers (#10, #11, #12) are deep in spec-002
territory and benefit most from authors familiar with the size-field
stack.

## Where do I report bugs?

[GitHub Issues](https://github.com/domattioli/ADMESH/issues). Please
include a minimal `fort.14` (or the call sequence with synthetic
inputs) that reproduces, plus the failing test or assertion.

## Where do I learn the concepts (distmesh, SDF, medial axis, BC types)?

[Concepts](Concepts.md). One-page primer covering the size field,
signed-distance functions, distmesh's force-based iteration, the
medial-axis contribution, ADCIRC BC types, and mesh-quality metrics.
