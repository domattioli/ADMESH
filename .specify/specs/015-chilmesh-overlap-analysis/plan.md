# Spec 015 — Plan

Workflow for the CHILmesh overlap analysis. Doc-only; no code shipping.

## Phase A — Inventory (read-only)

1. **A1. ADMESH module catalog.** Walk `admesh/*.py` (public, non-underscore). For each, capture:
   - Module path
   - One-line purpose (from module docstring or first comment block)
   - Primary public symbols (function/class names listed in `admesh/__init__.py`)
   - Stage classification: `gen` (generator-side), `cons` (consumer-side), `bdry` (boundary)
2. **A2. CHILmesh module catalog.** Source: published README at `https://github.com/domattioli/CHILmesh` + PyPI package page (`chilmesh`). For each public top-level surface element, capture the same fields. Mark `inferred` flag where the source is README rather than direct code read.
3. **A3. Test-seam catalog.** Every test file in `tests/` whose name contains `chilmesh`. Capture: file, what contract it pins, whether it imports CHILmesh at runtime.

Output: `inventory.md` with three sections (A1, A2, A3 tables).

## Phase B — Classification rubric

The three-way rubric for any mesh-touching module:

- **gen (generator-side, ADMESH-owned):** Constructs new mesh topology or geometry from a `Domain` definition. Pure producers. Examples: `triangulate`, `mesh_size`, `distmesh`, `background_grid`, `curvature`, `medial_axis`, `bathymetry`, `domains`, `loaders`, `boundary`, `boundary_types`, `routine`, `in_polygon`, `inpaint`, `distance`, `dominate_tide`, `registry`.
- **cons (consumer-side, candidate-CHILmesh):** Takes an existing mesh and inspects, modifies, scores, or extracts sub-regions. Pure consumers. Examples (candidates): `quality`, `quad_prep`, `viz`, `valence`, `size_field`.
- **bdry (boundary):** Defines the shared data structure that crosses the seam, or I/O against a wire format both sides speak. Examples: `api.py` (defines `Mesh`), `fort14.py` (I/O format).

Edge rules:
- A module that *both* constructs and inspects is **gen** if its primary export is the constructor.
- A module whose only public job is to project ADMESH output into a downstream consumer's expectation is **bdry** (it lives on the wire, not on either side).
- A module that wraps a third-party visualization library (matplotlib, pyvista) is **cons** — it is a *use* of the mesh, not part of mesh generation.

## Phase C — Disposition

For every module classified **cons**, choose one disposition:

- **keep** — stays in `admesh/`. Justification: tight coupling to the generator (e.g. quality metrics used by the smoother's stopping criterion), no parallel implementation in CHILmesh, or maintainer preference for one-stop install. Must cite at least one of those reasons.
- **move-to-chilmesh** — proposed migration target is CHILmesh. Must include:
  - The CHILmesh module path the symbol lands in
  - Deprecation horizon (typically one minor version)
  - A shim plan: `admesh/<module>.py` becomes a thin re-export with `DeprecationWarning` for the deprecation window
  - The follow-up issue number that will execute the move
- **extract-to-shared-lib** — neither repo owns it; a new third package emerges. Must include:
  - Proposed package name
  - Initial contents
  - Both ADMESH and CHILmesh become consumers
  - Justification this is preferable to a one-way move

Every module classified **bdry** gets a contract note: what crosses the wire, what version locks it, where the existing test contract lives.

## Phase D — Decision record

Write `docs/adr/ADR-001-chilmesh-boundary.md` with sections:

1. **Status:** Proposed (becomes Accepted on issue #81 close)
2. **Context:** Why the boundary was previously informal; what triggered the formalization (issue #81).
3. **Decision:** The disposition table from Phase C, condensed.
4. **Consequences:** What this enables (#84, #41, #9 coordination), what it costs (move work, deprecation discipline), what it forecloses (no more silent overlap).
5. **Snapshot:** Date the CHILmesh public surface was inferred. Future revisions verify against that snapshot.

## Phase E — Follow-up issues

For every `move-to-chilmesh` and `extract-to-shared-lib` disposition, file a new issue on `domattioli/ADMESH` with:

- Title: `chore(boundary): move <module> to chilmesh per ADR-001` (or `extract` variant)
- Labels: `planning-required`, `cross-repo`, `severity:low`
- Body: link to ADR-001 + the relevant Phase C row + the deprecation plan
- Estimated effort

Do **not** file issues for `keep` dispositions — those are no-ops captured by the ADR alone.

## Phase F — Closing comment

Post a single comment on issue #81 with:
- Link to ADR-001
- The disposition table (markdown)
- List of follow-up issue numbers
- Recommendation: close #81 once ADR is merged to `daily-maintenance`.

## Architectural decisions to record up-front

1. **CHILmesh is inferred, not read.** This spec does not check out the CHILmesh repo. The inventory snapshot uses public docs only. This keeps spec 015 self-contained and runnable offline.
2. **No code moves in this spec.** Spec 015 is *only* the analysis + ADR + follow-up issues. Every move is a separate future spec, gated on its own issue.
3. **`fort.14` is the locked wire format.** Any disposition that would require changing the `fort.14` contract is out of scope (locked by spec 009 R4 + existing chilmesh-compat tests).
4. **The `Mesh` dataclass stays in ADMESH.** Even if CHILmesh ultimately owns most consumer-side code, the canonical mesh data structure stays generator-side because the generator produces it. CHILmesh consumes it via the public `admesh.Mesh` import or via `fort.14` round-trip.

## What this plan does NOT do

- It does not run any code from CHILmesh.
- It does not modify any module in `admesh/`.
- It does not invent a new wire format.
- It does not promise the maintainer will accept every disposition — the ADR is "Proposed" until issue #81 is closed by the maintainer or by a follow-up review.
