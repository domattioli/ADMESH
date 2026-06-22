# Phase 0 Research: Default Size-Field Stack

**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)
**Date**: 2026-04-25

This document resolves the design unknowns the spec flagged for `/speckit-plan` lock-in. Six decisions, each in the "Decision / Rationale / Alternatives considered" format.

---

## Decision 1 — Default-depth constant for `tide_period` without bathymetry

**Decision**: Add a new `triangulate()` kwarg `default_depth: float = 1.0` (metres). When `tide_period` is set and `Domain.bathymetry` is `None`, the tide stage runs with a constant depth of `default_depth` everywhere. A `UserWarning` fires at warning level, naming the kwarg the user can set to silence it (or supply real bathymetry).

**Rationale**:
- Constant `1.0 m` keeps the tide stage producing *some* tide-driven sizing rather than silently dropping the user's intent (per `/speckit-clarify` Q3 resolution).
- `1.0 m` is small enough that the resulting tide-driven `h_tide` value is the smallest-magnitude reasonable contribution — the warning surfaces "you're not getting much from the tide stage; supply real bathymetry for a meaningful refinement".
- Caller-overridable: a user with synthetic bathymetry constraints can pass `default_depth=10.0` (or any positive number) and the stage uses that.
- A kwarg with a documented default is both backward-compatible (existing callers don't see it) and discoverable (shows up in `help(triangulate)`).

**Alternatives considered**:
- `h_max`-derived (`default_depth = h_max`): scale-linked, but couples a sizing knob to a depth knob across unrelated physical units. Rejected.
- Domain-bbox-derived (`default_depth = bbox_diagonal × 0.01`): too clever; would make warnings non-deterministic across domains. Rejected.
- Hard error when `tide_period` is set without bathymetry: rejected by the user during `/speckit-clarify`.
- Silent skip without warning: rejected by the user during `/speckit-clarify`.

---

## Decision 2 — Paired-edge BoundarySegment data shape (IBTYPE 3, 4, 13, 24)

**Decision**: Extend the existing `BoundarySegment` dataclass with two optional fields, both defaulting to `None`:

```python
@dataclass(frozen=True, slots=True)
class BoundarySegment:
    node_ids: np.ndarray              # existing; (N,) int64
    bc_type: BoundaryType | int       # existing
    is_open: bool                     # existing
    paired_node_ids: np.ndarray | None = None    # NEW; (N,) int64 for paired-edge BCs
    barrier_data: np.ndarray | None = None       # NEW; (N, K) float64 for crest+coefficients
```

For non-paired BCs (the existing OPEN, MAINLAND, ISLAND, MAINLAND_FLUX cases), both new fields are `None`. For IBTYPE 3 / 4 (single-node external weir/barrier with crest data), `paired_node_ids` is `None` and `barrier_data` carries `(N, 3)` columns: `(crest_elev, coef_subcritical, coef_supercritical)`. For IBTYPE 24 / 25 (paired-node internal barrier), `paired_node_ids` carries the second-side node IDs and `barrier_data` carries `(N, 5)` columns: `(crest_elev, coef_sub, coef_super, ?, ?)` per ADCIRC v55 grammar.

**Rationale**:
- Optional fields preserve backward compat: existing `BoundarySegment(node_ids=..., bc_type=..., is_open=...)` constructors keep working unchanged.
- Flat segment list (not a sub-type hierarchy) keeps `Mesh.boundaries: tuple[BoundarySegment, ...]` consumable by callers without isinstance branching.
- `barrier_data` is a 2D array (one row per node) so the existing N-aligned iteration patterns extend naturally — the K-column shape varies by BC type but is documented per IBTYPE.
- IBTYPE-determined column count is captured in a `_BARRIER_COLUMNS_BY_IBTYPE` constant module-level for reader/writer parity.

**Alternatives considered**:
- Separate `PairedBoundarySegment` subclass: rejected — forces every consumer to isinstance-discriminate, breaks `Mesh.boundaries` flat-iteration ergonomics, complicates `Mesh.equals`.
- Stuff paired data into a single `weir_payload: dict | None`: rejected — typed numpy arrays are more inspectable and serializable than dicts, and we already use ndarrays everywhere else.
- New `Barrier` dataclass referenced by `BoundarySegment.barrier: Barrier | None`: defensible, but premature factoring — three optional fields on the existing dataclass keep the diff small and the consumer code unchanged.

---

## Decision 3 — `BoundaryType` enum extension (IBTYPE 3, 4, 13, 24)

**Decision**: Add four new members to the `BoundaryType` enum in `admesh/boundary_types.py`:

```python
class BoundaryType(IntEnum):
    OPEN = 0
    MAINLAND = 1
    ISLAND = 11
    MAINLAND_FLUX = 20
    WALL = 1                      # existing alias
    EXTERNAL_BARRIER = 3          # NEW — single-node external weir + crest
    EXTERNAL_BARRIER_FLUX = 4     # NEW — single-node external barrier with normal flow
    INTERNAL_BARRIER = 24         # NEW — paired-node internal barrier with supercritical flow
    INTERNAL_BARRIER_PIPE = 13    # NEW — paired-node internal pipe/culvert
```

Codes outside this set continue to round-trip as plain `int` per spec-001's policy (`BoundarySegment.bc_type: BoundaryType | int`).

**Rationale**:
- `example10n` uses IBTYPE 0, 3, 24 — three of these four. Naming them by enum makes call-site code (`if seg.bc_type == BoundaryType.INTERNAL_BARRIER: ...`) self-documenting.
- IBTYPE 4 and 13 are common siblings (4 = "external barrier with normal flow", 13 = "internal pipe/culvert"); even though `example10n` doesn't exercise them, naming them in the enum is cheap and documents the family. ADCIRC v55 paired-edge IBTYPEs are: 3 (single, external weir), 4 (single, external barrier with flow), 13 (paired, pipe/culvert), 24 (paired, internal barrier with supercritical flow), 25 (paired, internal pipe/culvert with supercritical flow).
- Keeping the existing alias `WALL = 1` means spec-001 callers using `BoundaryType.WALL` keep working.

**Alternatives considered**:
- Keep all paired-edge IBTYPE codes as plain `int`: rejected — the named enum makes code more readable and is the documented spec-001 convention for the *common* IBTYPE codes.
- Add only IBTYPE 3 and 24 (the codes `example10n` actually exercises): defensible (YAGNI), but the cost of adding two more is trivial and documents the BC family. Erring toward naming.

---

## Decision 4 — `Domain.from_mesh(mesh)` signature and bathymetry interpolation

**Decision**: Add a classmethod on `Domain`:

```python
@classmethod
def from_mesh(
    cls,
    mesh: Mesh,
    *,
    tide_period: float | None = None,
    bbox_pad: float = 0.0,
) -> Domain:
    """Build a Domain from a triangulated Mesh.

    Outer ring + holes are derived by walking the mesh's boundary edges
    (per spec-001's existing `_derive_boundary_segments` helper, run in
    reverse). Bathymetry, if present on the mesh, is wrapped as a
    `LinearNDInterpolator` callable over the source nodes; outside the
    convex hull the interpolant returns NaN, and `bathymetry.create_elevation_grid`
    handles NaN gaps via the existing `inpaint_nans` path.
    """
```

If `mesh.bathymetry is None`, the returned `Domain.bathymetry` is also `None`. If it's present, the interpolator is built once at `from_mesh` time and stored on the `Domain` as the callable.

**Rationale**:
- `LinearNDInterpolator` is the standard SciPy primitive for scattered-to-grid interpolation; already imported by spec-001 era code.
- NaN-outside-hull is the natural failure mode and is already handled by the bathymetry stage's `inpaint_nans` step (per `admesh/bathymetry.py:67`). No new error path needed.
- Building the interpolator once at `from_mesh` time amortizes cost across every grid-sampling call inside `build_h`.
- `bbox_pad` lets a user expand the SDF bbox for re-meshing larger than the source domain — useful for "extend the domain offshore" workflows. Default `0.0` matches the source mesh exactly.

**Alternatives considered**:
- `griddata(method='linear')` per call: simpler but slower (rebuilds the triangulation every call). Rejected.
- Nearest-neighbour interpolation: faster but produces a step-function bathymetry that the bathymetry stage's gradient computation amplifies into spurious size-field discontinuities. Rejected.
- Cubic-spline interpolation: smoother but generates negative depths in shallow regions where the source mesh's depth is non-monotonic. Risky — physically meaningless. Rejected for default; could be a future kwarg.

---

## Decision 5 — Reference-test posture for the default stack (Constitution Principle III)

**Decision**: The default-stack acceptance test asserts **structural validity** (topology), not numerical equality to a MATLAB-side reference fixture. The underlying `build_h(...)` composer's output is *already* covered by spec-001 era reference tests for each individual stage (curvature, medial-axis, bathymetry, tide, smoother) at `atol=1e-8` / `rtol=1e-6`. Spec-002 does not add new `.npz` fixtures because it composes existing-tested stages — it does not introduce new numerical computation.

The structural-validity gate (positive signed area, boundary-edge preservation, full-domain coverage) is a *different kind* of test — it verifies that the integration produces a topologically valid mesh, not that any specific numeric value matches MATLAB.

**Rationale**:
- Constitution Principle III applies to *ports*, where the MATLAB output is the authoritative reference. Spec 002 isn't porting a stage; it's wiring already-tested ports into a new orchestration. The orchestration has no MATLAB analog (MATLAB ADmesh doesn't have a single `triangulate(domain)` entry point — the user threads the stages manually via the GUI or the legacy `ADmeshRoutine.m`).
- A structural-validity gate is also more robust than a node-count or quality-metric gate: it catches the "produced no triangulation at all" failure, the "triangulation has a hole" failure, and the "elements outside the domain" failure — all of which we observed in the prior session's bad WNAT mesh.
- The user explicitly chose structural validity over numeric quality during `/speckit-clarify` ("i honestly just want a valid mesh that respects all of the boundaries and meshes the entire domain").

**Alternatives considered**:
- Add `.npz` reference fixtures from a MATLAB run of `ADmeshRoutine.m` on each Tier domain: would require regenerating fixtures and the MATLAB seed for distmesh would not match Python's, producing irreconcilable mismatches. Rejected.
- Skip the WNAT regression entirely: rejected — it's the release gate.
- Use min-quality threshold from the input fixture as a relative gate (Option A from `/speckit-clarify`): rejected by the user.

---

## Decision 6 — Tier 1.5 fixture acquisition (Shinnecock vs. Idealized Inlet)

**Decision**: Pull **Shinnecock Bay** from ADCIRC's official examples catalogue during `/speckit-implement`. Source: `https://adcirc.org/home/documentation/example-problems/` → "Shinnecock Bay" listing, OR the canonical mirror at `adcirc/adcirc-cg` GitHub repo's `work/example/shinnecock/` directory. Stored at `tests/fixtures/fort14/adcirc_examples/shinnecock.14` with provenance documented in the new `PROVENANCE.md` manifest.

Target characteristics:
- Real coastline (small NY bay, public-domain ADCIRC example)
- ~3K nodes / ~5K elements (between Tier 0 polygons and Tier 1 example10n)
- IBTYPE 0/-1 boundaries (ocean + mainland) plus probably one or two island holes
- Bathymetric data populated (real depths)

**Rationale**:
- Shinnecock is the canonical ADCIRC small-bay example — used in countless ADCIRC tutorials and papers since the 1990s. Provenance is unambiguous.
- Real coastline + real bathymetry exercises the bathymetry stage of the default-stack (which `example10n` doesn't, since it's a synthetic wetting-and-drying scenario with simple depth).
- Sub-5K-node size keeps the regression test fast (< 30 s wall-clock target).

**Alternatives considered**:
- Idealized Inlet (synthetic, BC-rich, weirs): defensible — adds more BC variety than Shinnecock — but `example10n` already covers the BC-rich case at Tier 1, so adding another synthetic at Tier 1.5 is redundant. Rejected for now; could be added as Tier 1.7 later.
- NOAA's operational Chesapeake mesh (~50K nodes): too large for the < 60s wall-clock budget on Tier 2 WNAT, let alone Tier 1.5. Rejected.
- Lake Erie (sibling MADMESHR fixture, ~5K nodes): real-world coastline and the right size, BUT the local copy in `MADMESHR/01_.14_Files/Lake_Erie_mesh_refined.14` lacks BC sections (it's a mesh-generator output, like most MADMESHR fixtures). Acquisition cost not justified.

---

## Summary of locked decisions

| # | Domain | Decision (one-liner) |
|---|---|---|
| 1 | Default-depth constant | `triangulate(default_depth: float = 1.0)` kwarg; warns when `tide_period` set without bathymetry |
| 2 | Paired-edge data shape | `BoundarySegment.paired_node_ids` + `.barrier_data` optional fields; flat list, no subclass |
| 3 | BoundaryType enum extension | Add `EXTERNAL_BARRIER=3`, `EXTERNAL_BARRIER_FLUX=4`, `INTERNAL_BARRIER_PIPE=13`, `INTERNAL_BARRIER=24` |
| 4 | Domain.from_mesh interpolator | `LinearNDInterpolator` over source nodes; NaN-outside-hull handled by `inpaint_nans` |
| 5 | Reference-test posture | Structural validity (topology) gate; no new `.npz` fixtures; existing per-stage MATLAB references unchanged |
| 6 | Tier 1.5 fixture | Shinnecock Bay (ADCIRC official example) — pulled during `/speckit-implement` |

All Phase-0 unknowns resolved. Proceeding to Phase 1 (data-model.md, contracts/, quickstart.md).
