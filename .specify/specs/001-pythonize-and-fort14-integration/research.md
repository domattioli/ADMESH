# Phase 0 Research: Pythonic API Layer + fort.14 I/O

**Feature**: 001-pythonize-and-fort14-integration
**Date**: 2026-04-24

This document resolves all NEEDS CLARIFICATION items from the Technical Context and records design decisions for the implementation phase.

---

## Decision: Module organization for the Pythonic layer

**Decision**: Add five new modules under `admesh/`: `api.py`, `fort14.py`, `boundary_types.py`, `size_field.py`, `viz.py`. The 13 existing stage modules are untouched. Public API is re-exported from `admesh/__init__.py`.

**Rationale**:
- Keeps the faithful-port modules visually and namespace-isolated from the new layer. A reader can tell at a glance which module is "MATLAB-mirror" and which is "Pythonic surface."
- Five modules is small enough to navigate without subpackages; nesting (`admesh/pythonic/api.py`) was rejected as premature.
- `boundary_types.py` is split out from `api.py` because the enum is shared by `fort14.py` and `viz.py` and would otherwise create a circular import.

**Alternatives considered**:
- *Subpackage `admesh/pythonic/`*: rejected — adds an import-path level for no organizational gain at five modules.
- *Single `admesh/public.py` containing everything*: rejected — fort.14 grammar code is large enough (target ~400 LOC) to deserve its own file; co-locating it with dataclasses degrades readability.
- *Inline new types into existing stage modules*: rejected — directly violates the "faithful surface unchanged" guarantee; reviewers can no longer diff against MATLAB.

---

## Decision: `Mesh` and `Domain` are frozen dataclasses

**Decision**: `Mesh` and `Domain` are `@dataclass(frozen=True, slots=True)` with NumPy arrays as fields. `BoundarySegment` is a frozen dataclass holding a 1-D `np.ndarray[int64]` of node IDs and a `BoundaryType` code.

**Rationale**:
- Frozen + slots gives Python's normal equality and hashing for free, prevents accidental mutation, and reduces per-instance memory.
- NumPy arrays as direct fields (rather than tuple-wrapped) keep the arithmetic surface usable: `mesh.nodes[:, 0]` works, `mesh.elements.shape` works, etc.
- `frozen=True` does not freeze the underlying NumPy buffer — array contents can still be modified in place by hostile code, but that's a deliberate Python convention (no language-level immutability) and is documented.

**Alternatives considered**:
- *Plain class with `__init__`*: rejected — loses free `__eq__`/`__repr__`, more boilerplate.
- *NamedTuple*: rejected — encourages tuple-unpacking which we explicitly want to discourage (FR-002 forbids tuple returns at public boundaries).
- *Pydantic model*: rejected — adds a heavyweight dependency for what is essentially structural data.

---

## Decision: ADCIRC fort.14 grammar reference

**Decision**: Target the ADCIRC v55.xx fort.14 grammar as documented in the [ADCIRC user manual](https://adcirc.org/home/documentation/users-manual-v55/). Specifically:

```
Line 1:        AGRID (free-text title, ≤80 chars)
Line 2:        NE  NN                        (n_elements, n_nodes)
Lines 3..NN+2: JN  X  Y  DP                  (node_id, lon/x, lat/y, depth_below_datum)
Lines:         JE  NHY  NM1  NM2  NM3        (element_id, n_vertices=3, vertex_ids; one per element)
Line:          NOPE                          (n_open_boundary_segments)
Line:          NETA                          (total open boundary nodes — cumulative)
For each open segment k = 1..NOPE:
  Line:        NVDLL[k]  IBTYPE[k]           (n_nodes_in_segment, BC code; IBTYPE often 0)
  Lines:       NBDV[k][1..NVDLL[k]]          (node IDs, one per line)
Line:          NBOU                          (n_land_boundary_segments)
Line:          NVEL                          (total land boundary nodes — cumulative)
For each land segment k = 1..NBOU:
  Line:        NVELL[k]  IBTYPE[k]           (n_nodes, BC code; 0/1/2/10/11/12/13/20/21/22/...)
  Lines:       NBVV[k][1..NVELL[k]]          (node IDs, one per line; some IBTYPEs add extra cols)
```

**Rationale**:
- v55 is the current ADCIRC release; chilmesh and most active deployments target it.
- Fixed-format text means the writer can be a deterministic string generator and the reader a line-oriented parser — no third-party grammar library needed.
- Extra-column IBTYPEs (barriers, weirs) are explicitly handled as numeric round-trip per FR-012; the v1 enum (FR-022) names only the no-extra-column codes.

**Alternatives considered**:
- *v53 / earlier grammars*: rejected — adds backward-compat surface that no current user requests. Best-effort handling for older variants is allowed by the spec's Assumptions but not engineered for.
- *External library (e.g. `pyadcirc`)*: rejected — adds a dependency for what is straightforward fixed-format text I/O. Reviewing whether such a library exists, is maintained, and has compatible licensing is not worth the time saved.

---

## Decision: Index conversion strictly at I/O boundary

**Decision**: All internal arrays (`mesh.elements`, `BoundarySegment.node_ids`) use 0-based indexing. The fort.14 reader subtracts 1 from every ID at parse time; the writer adds 1 at emit time. **No internal helper accepts 1-based indices.** No internal helper emits them.

**Rationale**:
- Constitution Principle IV mandates 0-based indexing internally.
- Centralizing the conversion at the I/O boundary means every downstream test, plotting helper, and computation can assume 0-based without re-checking.
- Matches the existing convention of the faithful-port surface.

**Alternatives considered**:
- *Index-conversion utility function exposed in the public API*: rejected — invites users to call it incorrectly. The conversion is internal to `fort14.py`.

---

## Decision: Bathymetry sign convention

**Decision**: Internal `Mesh` carries bathymetry as **elevation** (positive-up) when present. The fort.14 writer applies `depth = -elevation` at emit time. The reader applies `elevation = -depth` at parse time. When `mesh.bathymetry is None`, the writer emits zeros.

**Rationale**:
- The MATLAB faithful port produces elevation-style fields; preserving that in the internal `Mesh` keeps the internal arithmetic consistent with the faithful surface.
- ADCIRC's convention is well-documented as positive-down depth; the sign flip is mechanical and should not surprise.
- Round-trip preserves the physical field exactly because the flip is its own inverse.

**Alternatives considered**:
- *Internal positive-down*: rejected — would require sign-flipping every faithful-port output during the Pythonic-layer wrap, multiplying the surface where bugs can hide.

---

## Decision: matplotlib is an optional dependency, lazy-imported

**Decision**: matplotlib is declared in `pyproject.toml` under `[project.optional-dependencies]` as `viz = ["matplotlib>=3.7"]`. The `Mesh.plot()` method imports matplotlib **inside the method body**, not at module load. `import admesh` succeeds in environments without matplotlib.

**Rationale**:
- Headless servers (CI, batch processing) shouldn't be forced to install matplotlib.
- Lazy import means even when matplotlib is missing, the user can read/write fort.14, run `triangulate`, and use every other API without error.
- An `ImportError` raised lazily inside `plot()` (per FR-021) gives the user a precise, actionable message naming the `viz` extra.

**Alternatives considered**:
- *Hard dependency*: rejected — violates the "no install-graph entanglement" principle inherited from the chilmesh-Option-A reasoning.
- *Soft TYPE_CHECKING import only*: rejected — would still need a runtime-import branch, and the TYPE_CHECKING guard adds noise without benefit when the type is only used internally.

---

## Decision: Two-phase size-field composition implementation

**Decision**: A single composer function in `size_field.py`:

```
compose(builtins: list[Callable], user_contribs: list[Callable], combine: Callable = np.minimum.reduce) -> SizeField
```

Phase 1 evaluates `builtins` and applies `np.minimum.reduce`. Phase 2 applies `combine` to the Phase-1 result and the evaluated `user_contribs`. The default `combine` is `np.minimum.reduce`, matching MATLAB's `min`-stack at every layer; users can pass any callable that takes a list of `(N,)` arrays and returns an `(N,)` array.

**Rationale**:
- Mirrors the spec's clarified two-phase semantics literally — built-ins always `min`-stack, user contributions go through the user-chosen combiner.
- Decouples the *built-in* min-stack (Constitution-Principle-I-protected) from the *user* combiner (where flexibility is wanted).
- A single composer function is small enough to test exhaustively against the faithful-port `mesh_size.py` for the no-user-contribution case.

**Alternatives considered**:
- *Single-pass composer with combiner pluggable for both phases*: rejected — risks user-side bugs corrupting the built-in stack; violates spec's clarification answer (Option C, two-phase).
- *Class-based pipeline with `add_stage(callable)` builder*: rejected as premature OO. Functions compose; a class adds state with no behavioral need.

---

## Decision: fort.14 reader error reporting

**Decision**: The reader raises `Fort14ParseError` (subclass of `ValueError`) on first error encountered. The exception message includes:
- The 1-based **line number** in the file (matching what a text editor would show).
- A short description of **what was expected** (e.g., "expected `n_elements n_nodes` on line 2, got 1 token").
- The **actual line content** (truncated to 120 chars) for context.

**Rationale**:
- "Raise on first error" matches Python's standard parsing idiom (e.g., `json.loads`); collecting multiple errors is a feature for IDEs/linters, not for a mesh I/O library.
- Line numbers + expectation + actual content gives the user the same information they'd get from a human-readable diff.
- Subclassing `ValueError` lets callers `except ValueError` for generic robustness while specifically catching `Fort14ParseError` when they want to react to malformed-mesh cases distinctly.

**Alternatives considered**:
- *Collect all errors, raise a multi-error*: rejected as scope creep for v1; can be added non-breakingly later by extending `Fort14ParseError` with an `errors` list.
- *Custom hierarchy unrelated to ValueError*: rejected — breaks the "catch generic ValueError" idiom users expect from parsing libraries.

---

## Decision: Performance target for v1 — none beyond the existing quality gates

**Decision**: v1 carries no new performance gate. The existing constitutional gates (`min_q ≥ 0.30`, `mean_q ≥ 0.60` on MVP domains; full faithful-port test suite green) remain. fort.14 I/O performance is not benchmarked in v1.

**Rationale**:
- The Outstanding clarification item from `/speckit-clarify` was "perf target for typical meshes" — low impact, deferred.
- No user has reported a perf bottleneck. Optimizing fort.14 I/O before there's a measured pain point is premature.
- The reader/writer design (line-oriented, no double-pass) is fast enough for any reasonable MVP mesh size; if a >1M-node user appears later, profile-guided optimization can land non-breakingly because the public API doesn't expose internal buffering.

**Alternatives considered**:
- *Set a target like "1M nodes in <5s on a 2024 laptop"*: rejected — no measured baseline to anchor it, and "fast enough" for the MVP test domains is implicit.
- *Add a benchmark script*: deferred — adds maintenance burden with no acceptance criterion to validate against. Will be revisited if/when the streaming-I/O extension is specced.

---

## Decision: Curated fort.14 reference corpus

**Decision**: The reference corpus for SC-005 is split into three subdirectories under `tests/fixtures/fort14/`:

1. `adcirc_examples/` — at least 2 official ADCIRC documentation example meshes (e.g., the Shinnecock Inlet test case shipped with ADCIRC).
2. `community/` — at least 3 real-world meshes contributed by external users or sourced from public ADCIRC mesh repositories.
3. `malformed/` — at least 10 hand-crafted malformed inputs covering distinct error categories (missing header, wrong node count, non-monotonic IDs, non-numeric where numeric expected, etc.) — serves SC-007.

Total target size: <2 MB combined (large meshes use a header-only excerpt where appropriate).

**Rationale**:
- Concrete, named sources keep SC-005 measurable.
- Splitting the corpus into three folders makes test parameterization straightforward (one parametrize per folder).
- The malformed corpus is the simplest way to verify "10 categories of malformed input" from SC-007.

**Alternatives considered**:
- *Generate fort.14 fuzz inputs at test time*: rejected — flaky and depends on a fuzzer dependency. Hand-crafted is auditable.
- *Single mega-corpus*: rejected — mixes happy and unhappy paths in one folder, harder to navigate.

---

## Open Items (none)

All NEEDS CLARIFICATION items from Technical Context are resolved. The Outstanding "perf target" item from `/speckit-clarify` is documented above as a deliberate non-goal for v1.
