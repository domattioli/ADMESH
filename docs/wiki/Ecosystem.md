# Ecosystem

ADMESH does not exist in isolation. This page maps the surrounding
projects — what each one is, how it relates to this repo, and where
each one is going.

For ADMESH's own roadmap, see [Roadmap](Roadmap.md). For the cross-repo
project-plan synthesis (CHILmesh's 12-month modernisation,
MADMESHR's path to publication, ADMESH-Domains' registry buildout),
see the **Cross-repo plans** section below.

---

## Upstream — the original ADMESH

### [`coltonjconroy/ADMESH`](https://github.com/coltonjconroy/ADMESH)

The canonical MATLAB implementation by the original authors
(Conroy / Kubatko / West, OSU CHIL). May carry features beyond what
this Python port currently covers — new functionality is adopted
here as it is pulled across.

**Citation** —
Conroy, C.J., Kubatko, E.J., West, D.W. (2012).
*ADMESH: an advanced, automatic unstructured mesh generator for
shallow water models.* Ocean Dynamics 62, 1503–1517.
[doi:10.1007/s10236-012-0574-0](https://doi.org/10.1007/s10236-012-0574-0).

A copy of the paper lives at
[`papers/Conroy-2012-ADMESH.pdf`](https://github.com/domattioli/ADMESH/blob/main/papers/Conroy-2012-ADMESH.pdf).

### [`domattioli/QuADMesh-MATLAB`](https://github.com/domattioli/QuADMesh-MATLAB)

The MATLAB codebase this Python port is built from, pinned at commit
`19b2eb9`. A **parallel version** that shares a common ancestor with
[`coltonjconroy/ADMESH`](https://github.com/coltonjconroy/ADMESH)
rather than being a strict fork — the lineage is fuzzy. Adds
quadrilateral-meshing extensions on top of the triangular pipeline.
The Python port covers the triangular side only — `tri2quad` is out
of scope for v1.

---

## Downstream — what consumes ADMESH meshes

### [ADCIRC](https://adcirc.org/)

The shallow-water solver these meshes feed. ADMESH's native I/O
format is ADCIRC's `fort.14`. Compatibility with ADCIRC is the
**primary correctness criterion for the I/O layer** — see the
[fort.14 cheat sheet](fort14-Cheat-Sheet.md).

ADCIRC source: [`adcirc/adcirc-cg`](https://github.com/adcirc/adcirc-cg).

---

## Sibling projects (Python, same authors, CHIL lineage)

### [`domattioli/CHILmesh`](https://github.com/domattioli/CHILmesh) — mesh data structure + smoother

**Status**: v0.1.1 (alpha) on PyPI as
[`chilmesh`](https://pypi.org/project/chilmesh/). Phased v0.2.0 plan
in flight; see Cross-repo plans below.

Python package for **representing and post-processing** triangular,
quadrilateral, and mixed-element 2D meshes for hydrodynamic domains.
Where ADMESH **generates** triangular meshes from a domain, CHILmesh
**holds** any 2D mesh once you have one — from any source — and
provides:

- A `delaunayTriangulation()`-inspired API over points, edges,
  elements, and a novel layer-based view of 2D meshes.
- FEM-based and geometric mesh smoothing.
- Element-quality evaluation (angular skewness for tris and quads).
- `fort.14` input / output for ADCIRC.

The two compose: ADMESH produces the triangular mesh through the
faithful MATLAB-port stack; CHILmesh wraps the result for quality
analysis or smoothing, and is also the natural data structure for
mixed-element output from MADMESHR.

### [`domattioli/MADMESHR`](https://github.com/domattioli/MADMESHR) — RL-based mixed-element generator

**Status**: MVP / proof-of-concept. Not yet on PyPI. Constitution
v2.0.0; thesis document published.

An advancing-front mesh **generator** that learns the
element-extraction policy with reinforcement learning (Soft
Actor-Critic, per [Pan et al. 2023](https://www.sciencedirect.com/science/article/pii/S0893608022004154)).
The agent observes a boundary loop and picks an action from a
continuous space (`element type × angle × distance`), producing tri,
quad, and mixed meshes on arbitrary 2D domains — a different
paradigm than ADMESH's deterministic distmesh-based triangulation.

**Long-term positioning relative to this repo is intentionally
undecided.** Two viable shapes:

1. **MADMESHR deprecates ADMESH** — becomes the one-stop shop for
   triangular, quadrilateral, and mixed-element meshes, with the
   ADMESH triangular code path folded in (or replaced by the RL
   policy).
2. **MADMESHR is a sibling** — you use ADMESH to build triangles
   deterministically, then reach for MADMESHR when you need a
   quad-dominant or fully mixed mesh.

The choice likely waits until ADMESH 0.1.0 ships and there is real
usage data on which split is more useful to maintain. Either way,
ADMESH's faithful-port invariant
([Constitution Article II](https://github.com/domattioli/ADMESH/blob/main/docs/governance/CONSTITUTION.md))
holds — MADMESHR concepts do not bleed into the 13 locked stage
modules.

### [`domattioli/ADMESH-Domains`](https://github.com/domattioli/ADMESH-Domains) — mesh + domain registry

**Status**: on PyPI as
[`admesh-domains`](https://pypi.org/project/admesh-domains/), with
[HuggingFace dataset](https://huggingface.co/datasets/domattioli/ADMESH-Domains)
mirror live and a GitHub-pages site at
[domattioli.github.io/ADMESH-Domains](https://domattioli.github.io/ADMESH-Domains/).
This is **no longer the nascent concept it was in the early roadmap**
— it is the operational fixture library for ADMESH itself. Originally
scoped as spec-005 inside ADMESH; spun out and now ~30 numbered specs
deep on its own.

Curated catalog of coastal-simulation meshes with:

- Python loader (`from admesh_domains import find_meshes, get_mesh, test_meshes`).
- HuggingFace dataset mirror (Parquet sidecar + auto-generated card).
- PR-based contribution workflow with CI validation.
- Interactive browse / search / preview site.

ADMESH's Tier-1 and Tier-2 test fixtures (`wetting_and_drying_test.14`,
`wnat_test.14`) live in this registry rather than being re-collected
in the ADMESH repo.

### `admesh-segmenter` *(planned)*

Composable mesh sub-region selection. Crop a continental-scale mesh
to a sub-domain with proper boundary recovery. Will live in its own
repo. **Tracking:** [#9](https://github.com/domattioli/ADMESH/issues/9).

---

## How they relate

```
        Conroy / Kubatko / West (OSU CHIL, 2012)
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
   coltonjconroy/ADMESH      domattioli/QuADMesh-MATLAB
   (MATLAB, canonical        (MATLAB, @19b2eb9 — parallel
    upstream)                 version + quad extensions)
                                       │
                                       │ Python port (this repo)
                                       ▼
                  ┌──────────────────────────────────┐
                  │      domattioli/ADMESH           │
                  │  (Python — triangles only)       │
                  └──────────────────────────────────┘
                       │                │
                       │                │ test fixtures + reference meshes
                       │                ▼
                       │      ┌─────────────────────────┐
                       │      │ domattioli/ADMESH-      │
                       │      │ Domains  (PyPI + HF +   │
                       │      │ pages site)             │
                       │      └─────────────────────────┘
                       │
                       │ writes fort.14 directly,
                       │ or hands the mesh to CHILmesh
                       │ for smoothing / quality / I/O
                       ▼
            ┌──────────────────────────┐
            │ domattioli/CHILmesh      │     ←──┐
            │ (PyPI: chilmesh — data   │        │
            │  structure + smoother    │        │ Wraps any 2D mesh
            │  for tri / quad / mixed) │        │ from any source —
            └────────┬─────────────────┘        │ including:
                     │                          │
                     ▼                          │
            adcirc/adcirc-cg                    │
            (shallow-water solver)              │
                                                │
                                                │
            ┌──────────────────────────┐        │
            │ domattioli/MADMESHR      │  ──────┘
            │ (RL-based mixed-element  │
            │  generator, MVP/PoC)     │
            └──────────────────────────┘
```

---

## Cross-repo plans

The four repos do not move independently — they share authors and a
single ecosystem. Each carries its own roadmap; the synthesis below
is the one you would build from reading all four.

### Near term (Q2–Q3 2026)

| Repo | Headline | Reference |
|---|---|---|
| ADMESH | 0.1.0 PyPI tag — close [#10](https://github.com/domattioli/ADMESH/issues/10), [#11](https://github.com/domattioli/ADMESH/issues/11), [#12](https://github.com/domattioli/ADMESH/issues/12); un-xfail Tier-1 / Tier-2 | [Roadmap](Roadmap.md) + `docs/governance/PROJECT_PLAN.md` |
| CHILmesh | Phase 0 → Phase 1 planning, 16 GitHub issues filed, stakeholder coordination underway | [`.planning/project_plan.md`](https://github.com/domattioli/CHILmesh/blob/main/.planning/project_plan.md) |
| ADMESH-Domains | Specs #29 (mesh-strategy comparison), #30 (compare-mesh UI), #27 (site prune) in flight | [`specs/`](https://github.com/domattioli/ADMESH-Domains/tree/main/specs) |
| MADMESHR | Path to first PyPI release — production hardening of MVP | repo `README.md` + thesis |

### Medium term (Q4 2026 – Q1 2027)

| Repo | Headline |
|---|---|
| ADMESH | Specs 003 (outer-ring sort, closes 0.1.0), 007 (1D boundary seeding), 008 (Gmsh I/O), then 004 (quad-prep smoother) |
| CHILmesh | v0.2.0 — data-structure modernization + bridge architecture across MADMESHR / ADMESH / ADMESH-Domains. 1.5×+ performance target on large meshes. Clear bridge interfaces. Zero breaking changes to public API. |
| ADMESH-Domains | Continued registry growth + dataset-quality automation (Tier-2 boundary matcher, domain auto-suggester) |
| MADMESHR | Settle the deprecate-or-sibling question with ADMESH based on usage data from ADMESH 0.1.0 |

### Long term (post-Q1 2027)

| Topic | Across |
|---|---|
| Acceleration (GPU + parallel CPU) | ADMESH + MADMESHR; deferred until 0.1.0 ADMESH benchmarks exist |
| Smart AI indexing of registry | ADMESH-Domains (concept; unfiled) |
| 3D-element extension | ADMESH (concept; unfiled; naming undecided) |
| SDF-coupled FEM smoother | ADMESH (sequenced after quad-prep so the smoother surfaces can unify) |
| `admesh-segmenter` sibling | New repo; depends on ADMESH |

---

## Where the split arrow in the lineage diagram comes from

The split arrow at the top of the lineage diagram reflects that
[`coltonjconroy/ADMESH`](https://github.com/coltonjconroy/ADMESH) and
[`domattioli/QuADMesh-MATLAB`](https://github.com/domattioli/QuADMesh-MATLAB)
likely share Conroy / Kubatko / West's original code as a common
ancestor rather than one being a fork of the other. The MATLAB
genealogy is not fully linear.
