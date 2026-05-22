# Spec 017 — Wire Default Size-Field Stack in `triangulate()` (resolves #65)

**Status:** Planning-phase only. No code shipping in this commit.
**Issue:** [#65 Wire default size-field stack in triangulate() (3-step plan from #10) — fresh-mesh quality improvement](https://github.com/domattioli/ADMESH/issues/65)
**Related:** [#10](https://github.com/domattioli/ADMESH/issues/10) (original report, retained for the quality concern; closes on #65 merge)
**Branch:** `daily-issue-fixing`
**Target:** post-0.1.0 (0.2.0 scope)
**Token budget:** MEDIUM (1 dataclass field, 2 callsite edits, 4 acceptance tests already-green, 1 new bathymetry-path test, 1 visual gate, ~6 unit tests)

---

## 1. Problem statement

Issue #10 was the size-field overshoot report on real-world coastal
fixtures. The structural-validity gate (positive area, every node +
centroid inside the domain SDF, mesh area ≥ 95% of source polygon
area) was satisfied in spec 002 commit `b6c42ec` and locked by the
formal acceptance suite in `tests/test_default_size_field.py`
(commit `d4ed8dc`). All four acceptance tests pass without `xfail`
as of 2026-05-17 on the `009-release-readiness-for-0.1.0` branch
(spec 009 R4 commit `5cdfecf`).

Visual inspection of fresh meshes (#10 second comment) shows the
mesh-quality / topology fidelity problems the structural-validity
gate does not catch. The maintainer's planning comment on #10 dated
2026-05-13 identifies the root cause as feature incompleteness, not
a bug:

> 1. **Current State:** `triangulate()` creates only a uniform
>    clamped field when `h_min`/`h_max` are provided.
> 2. **Expected State:** Should call `build_h()` — the default
>    size-field stack with curvature + medial + bathymetry.
> 3. **Result:** Uniform mesh does not respect domain boundaries on
>    sparse / coarse real-world fixtures.

The 3-step plan in that comment is concrete; this spec captures it
as a planning artifact so the implementation can land post-0.1.0
without re-clarifying the design at code time.

## 2. Why post-0.1.0

The 0.1.0 tag ships against the structural-validity gate per spec
009 R4 (FR-031..FR-034). The quality improvement is orthogonal to
structural validity; implementing the 3-step plan mid-spec would
carry regression risk on the currently-green Tier-1 / Tier-2 tests.
Splitting the work as 0.2.0 scope keeps the 0.1.0 surface focused
on the API + I/O + governance contracts established in spec 009.

## 3. Scope

In-scope (planning phase, this spec):

### Step 1 — Add `bathymetry` field to `Domain`

```python
@dataclass(frozen=True, slots=True)
class Domain:
    sdf: Callable
    bbox: tuple
    bathymetry: Callable | None = None   # NEW (post-Step 1)
    pfix: ndarray | None = None
    pts: ndarray | None = None
    bc_segments: tuple = ()
```

Verified surface (admesh/api.py:232–258 at sha `fb73d03`):

- `Domain` is `@dataclass(frozen=True, slots=True)`.
- Existing fields: `sdf`, `bbox`, `pfix`, `pts`, `bc_segments`.
- Adding `bathymetry: Callable | None = None` before `pfix` keeps
  positional-construct sites stable only if every caller uses
  keyword args. Field ordering during impl must verify
  `Domain.from_mesh()` and any test fixture that positionally
  constructs `Domain`.

### Step 2 — Extract bathymetry in `Domain.from_mesh()`

```python
if mesh.bathymetry is not None:
    from scipy.interpolate import NearestNDInterpolator
    bathy_interp = NearestNDInterpolator(
        mesh.nodes, mesh.bathymetry,
        fill_value=mesh.bathymetry.mean(),
    )
else:
    bathy_interp = None

return cls(
    sdf=sdf,
    bbox=bbox,
    bathymetry=bathy_interp,
    bc_segments=bc_segments,
)
```

`NearestNDInterpolator` is the documented choice over
`LinearNDInterpolator`: investigation on `wetting_and_drying_test.14`
showed `LinearNDInterpolator` returns 67.8% NaN outside the convex
hull while `NearestNDInterpolator` returns 0% NaN, matches source
range exactly, and is robust on the WNAT fixture.

`Domain.from_mesh()` currently uses `LinearNDInterpolator` in the
SDF construction (admesh/api.py:278). The replacement is local to
the bathymetry interpolant — the SDF path is unaffected.

### Step 3 — Wire the default stack in `triangulate()`

```python
def triangulate(...):
    if size_field is None and h_max is not None:
        from admesh._stages.mesh_size import build_h
        fh = build_h(
            domain,
            base=h_max,
            curvature_scale=20.0,
            medial_scale=0.1,
            bathymetry=domain.bathymetry,
            bathy_scale=0.5,
            hmin=h_max / 10,
            hmax=h_max,
            g=0.2,
        )
```

The current dispatcher at `admesh/api.py:704–742` is more nuanced
than the issue snippet — `compose_size_field` already wires a
bounded uniform fallback when `h_min` / `h_max` are passed without
user contribs. Step 3 must:

1. Detect the existing
   `size_field is None and (h_min is not None or h_max is not None)`
   branch at admesh/api.py:742.
2. Replace the uniform-fallback construction with a `build_h(...)`
   call when `h_max is not None` (the gate the issue prescribes).
3. Keep the `h_min`-only path on the existing uniform fallback
   (the `build_h` recipe needs `hmin = h_max / 10` and a `hmax`
   ceiling — both require `h_max` to be set).
4. Pass `bathymetry=domain.bathymetry` only when the field is set.
   The `build_h` signature already accepts `bathymetry=None`.

## 4. Out of scope

- New `min_q` / edge-length-distribution-match gates on
  `tests/test_default_size_field.py` — separate quality-gate spec.
- GPU / multi-core acceleration of the size-field stack (#8).
- Investigation tools rewrite (already shipped in
  `scripts/diagnose_issue_10.py`).
- Changes to any of the 13 faithful-port stage modules; this is an
  additive-layer change to `admesh/api.py` only, per Constitution
  Principle I.
- Re-tuning the `curvature_scale=20.0`, `medial_scale=0.1`,
  `bathy_scale=0.5`, `g=0.2` knobs — these are the documented
  defaults from the #10 planning comment; tuning is a follow-up
  spec gated on real-world quality data.

## 5. Risk register

| Risk | Mitigation |
|---|---|
| Step 3 reintroduces the overshoot #10 originally documented (size-field-driven boundary projection failures) | Run Tier-1 / Tier-2 acceptance tests after each step; revert if structural validity regresses. |
| Tier-0 polygon-domain regression (no bathymetry → uniform fallback different from current uniform-clamp) | Tier-0 already exercised by `TestTier0PolygonDomains`; verify after Step 3. The `build_h` fallback with `bathymetry=None` should converge to a clamped curvature+medial field — likely no Tier-0 regression but must be measured. |
| Tier-2 60-second wall-clock budget violated by full stack on WNAT (~10K nodes) | `build_h` has been profiled at ≪ 60 s on similar fixtures; instrument the call if it slips. |
| `Domain` field order change breaks positional-construct test fixtures | Audit all `Domain(...)` constructor sites under `tests/` and `admesh/` before merging Step 1; convert to kwargs if any positional form found. |
| `Mesh.bathymetry` shape mismatch with `mesh.nodes` triggers `NearestNDInterpolator` build failure on read | Step 2 must guard with `if mesh.bathymetry is not None and mesh.bathymetry.shape == (mesh.nodes.shape[0],)`. Existing equality check at admesh/api.py:165–171 confirms 1D-per-node is the contract. |
| Frozen-dataclass + `Callable` non-trivial equality | `Domain` is frozen but does not implement custom `__eq__`. Two `Domain` instances built from the same mesh would not compare equal on `bathymetry` (callable identity). Document that `Domain` equality is not part of the contract; tests should compare meshes, not domains. |

## 6. Success criteria

- [ ] `Domain.bathymetry: Callable | None` field exists; defaults to `None`.
- [ ] `Domain.from_mesh()` populates `bathymetry` via
  `NearestNDInterpolator` when `mesh.bathymetry is not None`.
- [ ] `triangulate()` calls `build_h()` on the
  `size_field is None and h_max is not None` branch.
- [ ] All 4 Tier-1 / Tier-2 tests in
  `tests/test_default_size_field.py` still pass — no `xfail`.
- [ ] All Tier-0 tests still pass.
- [ ] No regression on the broader suite (`pytest -q` exit 0).
- [ ] New `tests/test_domain_bathymetry.py` covers the
  `Domain.from_mesh()` bathymetry-populate path on the
  `wetting_and_drying_test.14` fixture and a no-bathymetry fixture.
- [ ] Visual review of `output/release_gate_rebuild.png` shows
  quality improvement vs the 0.1.0 baseline (mesh-quality
  histogram + coastline fidelity). Render via
  `python scripts/render_release_gate.py` post-Step 3.
- [ ] `bash scripts/pre_tag_check.sh` exits 0.
- [ ] `docs/PORTING_NOTES.md` gets a 0.2.0 entry summarizing the
  default-stack wiring.

## 7. Cross-references

- Issue #10 — original report, closes on #65 merge.
- Issue #65 — this spec's parent.
- Spec 002 (`size-field-defaults`) — the in-flight spec that built
  `build_h`. Now consumed.
- Spec 009 R4 — structural-validity acceptance for 0.1.0 ship.
- Spec 015 / ADR-001 — CHILmesh boundary; bathymetry interpolation
  lives on the ADMESH side of the boundary per ADR-001.
- `admesh/_stages/mesh_size.py::build_h` — the function wired in
  Step 3.
- `scripts/diagnose_issue_10.py` — diagnostic driver; rerun
  before / after Step 3 commits as evidence on the PR.

## 8. Token-budget rationale

- Step 1: SMALL — 1 dataclass field + 1-line repr / equality
  audit.
- Step 2: SMALL — ~10 LoC swap of interpolant + None-guard.
- Step 3: SMALL — 1 dispatcher branch edit + ~10 LoC of `build_h`
  call.
- Tests: MEDIUM — 1 new test file (~5 cases) + audit the 4
  existing acceptance tests.
- Docs: SMALL — one PORTING_NOTES.md entry.

Total: MEDIUM. Single PR feasible. If WNAT performance regression
shows up the spec splits into 017-default-size-field-stack (Steps
1 + 2) and 018-build-h-dispatch (Step 3) to isolate the
acceptance-test risk.
