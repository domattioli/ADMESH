# CONTEXT.md — ADMESH (Python port) glossary

Canonical language for this repo. Glossary only — no implementation details.

## Lineage terms

- **ADMESH (2012 original)** — the MATLAB mesh generator described in Conroy, Kubatko & West (2012), *Ocean Dynamics* 62. Source of this repo's port lineage, vendored at `src/matlab/` via `domattioli/QuADMesh-MATLAB`.
- **Conroy repo** — `github.com/coltonjconroy/ADMESH`, the original public MATLAB codebase of ADMESH (2012 original). Itself no longer updated; its lineage continues upstream as ADMESH+ v3.
- **ADMESH+ v3** — the most recent MATLAB ADMESH from the original research group: Kang, Kubatko, Conroy & West, v3.0.1, Zenodo `10.5281/zenodo.10242565` (GitHub `OSU-CHIL/ADMESH`). Adds 1D–2D coupled-model constraint extraction and GUI components. Described in Kang & Kubatko (2024), *Geosci. Model Dev.* 17, `10.5194/gmd-17-1603-2024`.
- **The port (this repo)** — `admesh2D`, an independent Python port of ADMESH (2012 original). NOT derived from ADMESH+ v3; the two are parallel branches of the same 2012 root. Both branches are acknowledged in the README.

## Naming rules

- Never describe this repo as "the successor" to MATLAB ADMESH — ADMESH+ v3 is the original group's active line. This repo is "a Python port of the 2012 original".
- "ADMESH+" refers exclusively to the Kang/Kubatko MATLAB line, never to this package. (QuADMESH+ is a different, unrelated "+": the quad-meshing thesis algorithm.)
