# Constitution Amendment Proposal: Public Surface / Faithful-Port-Internals Split

**Spec**: `specs/009-release-readiness-for-0.1.0/`
**Filed**: 2026-05-15
**Status**: **PRE-APPROVED** by maintainer (`@domattioli`) in spec 009 clarification round C2 ("2" = amendment passes, proceed directly to reorg)

## Background

The ADMESH Constitution (`docs/governance/CONSTITUTION.md`, v1.0.2) Principle I
("Faithful Port Before Optimization") and Article II.1 ("Stage modules numerically
frozen against the MATLAB reference") establish that the 13 faithful-port stage
modules — `background_grid`, `bathymetry`, `boundary`, `curvature`, `distance`,
`distmesh`, `domains`, `dominate_tide`, `in_polygon`, `inpaint`, `medial_axis`,
`mesh_size`, `quality`, and `routine` — are bit-for-bit translations of MATLAB
sources at commit pin `19b2eb9`. They are not part of the public, semver-guarded
API surface.

However, the current package layout puts these 13 modules at the top of
`admesh/` alongside the v1 additive public surface (`api`, `fort14`, `loaders`,
`registry`, `quad_prep`, `valence`, `size_field`, `viz`, `boundary_types`).
`admesh/__init__.py::__all__` lists them — but only as bare names, not actually
imported into the namespace, so `from admesh import curvature` already fails today.

This ambiguity:

1. Makes API documentation impossible to navigate (mkdocstrings would crawl
   everything; users can't tell what they should depend on vs. what is
   numerically frozen).
2. Risks accidental coupling — third-party consumers might import
   `admesh.distmesh.distmesh2d` directly and treat its signature as semver-stable.
3. Conflicts with the Constitution's intent: stage modules are MATLAB ports,
   not Python idioms, and their signatures may change as the port is refined.

## Proposal

Add a new article to the Constitution making the public/internal split explicit
in the package layout.

### Article VIII — Public Surface / Faithful-Port Internals (proposed v1.0.3)

> The ADMESH package distinguishes a **public surface** from
> **faithful-port internals**.
>
> 1. The **public surface** lives at the top of `admesh/`:
>    `admesh/api.py`, `admesh/fort14.py`, `admesh/loaders.py`,
>    `admesh/registry.py`, `admesh/quad_prep.py`, `admesh/valence.py`,
>    `admesh/size_field.py`, `admesh/viz.py`, `admesh/boundary_types.py`.
>    Symbols re-exported from `admesh/__init__.py` constitute the
>    semver-guarded API. Removals or signature-breaking changes require a
>    minor-version bump pre-1.0 or a major-version bump post-1.0.
>
> 2. The **faithful-port internals** live at `admesh/_stages/` (the leading
>    underscore is the standard Python convention for "do not depend on me").
>    These are the 13 modules ported from `01_ADMESH_Library/` at the pinned
>    MATLAB commit. Their internal signatures may change as the port is refined
>    or as MATLAB divergences are documented in `docs/PORTING_NOTES.md`.
>
> 3. Backward-compatible stub re-exports at the old paths (`admesh/curvature.py`,
>    `admesh/distmesh.py`, etc.) MUST be preserved until ADMESH 1.0.0 to avoid
>    breaking any pre-0.1.0 callers that depended on the flat layout. Each stub
>    is a single line: `from admesh._stages.<name> import *`. Stubs may be
>    deleted at 1.0.0 with a documented deprecation cycle.
>
> 4. The `admesh/__init__.py::__all__` list MUST contain only public-surface
>    symbols. Stage module names MUST NOT appear in `__all__` (their internal
>    status is conveyed by the `_stages` prefix).
>
> 5. The contract test (`tests/test_admesh_domains_contract.py`) and the docstring
>    completeness test (`tests/test_docstring_completeness.py`) iterate over
>    `admesh.__all__` to enforce these invariants automatically.

### Implementation (spec 009 tasks T021 and T022)

1. **Move** the 13 stage modules from `admesh/<name>.py` to
   `admesh/_stages/<name>.py` (mechanical `git mv`).
2. **Create** `admesh/_stages/__init__.py` declaring `__all__ = []` and a
   one-paragraph docstring marking the subpackage internal.
3. **Replace** each old path with a 1-line stub:
   ```python
   from admesh._stages.<name> import *  # noqa: F401,F403
   ```
4. **Update** all cross-imports inside `admesh/` to reference `admesh._stages.<name>`
   so the codebase itself uses the canonical paths.
5. **Edit** `admesh/__init__.py::__all__` to drop the stage names.
6. **Run** the full test suite; verify backward-compat — all existing
   `from admesh.curvature import apply_curvature` patterns must continue to
   work without modification.

### Out of scope

- Deprecating any public-surface symbol.
- Renaming any stage module.
- Removing the stub re-exports before 1.0.0.
- Reorganizing the `admesh/_stages/` interior (sub-grouping by phase, etc.).

## Maintainer sign-off

Pre-approved by `@domattioli` in spec 009 clarification round C2 ("2 — Amendment
passes, proceed directly to reorg") — see commit `e5ce51b` on branch
`009-release-readiness-for-0.1.0` for the clarification context.

Implementation lands as part of the same branch.
