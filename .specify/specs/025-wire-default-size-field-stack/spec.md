# Spec 025 — Wire default size-field stack in `triangulate()` — 3-step plan (resolves #65)

**Status:** Planning-phase only. No code shipping in this commit (ADMESH planning profile).
**Issue:** [#65 Wire default size-field stack in triangulate() (3-step plan from #10) — fresh-mesh quality improvement](https://github.com/domattioli/ADMESH/issues/65) — `status: ready`, `type: feat`, `priority: normal`, milestone M3: Cycle break + ADMESH-B.
**Related:** [#10](https://github.com/domattioli/ADMESH/issues/10) (original size-field overshoot report; closes on this issue's merge), spec 009 R4 ([`specs/009-release-readiness-for-0.1.0/spec.md`](../009-release-readiness-for-0.1.0/spec.md)), spec 017 ([`specs/017-default-size-field-stack/spec.md`](../017-default-size-field-stack/spec.md)), [#8](https://github.com/domattioli/ADMESH/issues/8) (GPU acceleration), [#86](https://github.com/domattioli/ADMESH/issues/86) (C++/Rust port), spec 020 ([`specs/020-wnat-benchmark-quality/spec.md`](../020-wnat-benchmark-quality/spec.md)).
**Branch:** `daily-maintenance` (planning); implementation on `daily-issue-fixing` or a dedicated `feat/65-wire-size-field-stack` branch.
**Token budget:** MEDIUM (3 focused edits: `api.py::Domain`, `api.py::Domain.from_mesh`, `api.py::triangulate`; no new modules).

---

## 1. Problem statement

`triangulate()` currently creates a **uniform clamped field** when `h_min`/`h_max` are provided, rather than calling `build_h()` — the default size-field stack (curvature + medial + bathymetry). This causes:

- **Coastline fidelity failure**: Uniform spacing does not respect domain curvature or narrow features; the SDF projection places nodes far from the boundary on sparse/coarse real-world fixtures.
- **Benchmark quality defect**: Spec 020 identified the same root cause in `benchmarks/_bench_worker.py`; the fix there is blocked on this issue.
- **Observable symptom**: `output/release_gate_rebuild.png` shows quality / topology fidelity problems that the structural-validity gate (spec 009) does not catch — the freshly-triangulated WNAT mesh has large near-degenerate triangles in open water.

The operator's 2026-05-13 planning comment on #10 identified the gap as a **feature incompleteness** (uniform-clamp fallback was a placeholder, not a design decision) and provided a concrete 3-step implementation plan. This spec formalizes that plan.

## 2. Why this is post-0.1.0

The 0.1.0 tag shipped against the structural-validity gate (spec 009 R4, FR-031..FR-034). All four acceptance tests in `tests/test_default_size_field.py` pass without `xfail` as of commit `5cdfecf`. The quality improvement in this spec is orthogonal to structural validity; implementing it mid-spec would have carried regression risk on currently-green Tier-1/Tier-2 tests. This scope belongs to 0.2.0 (milestone M3).

## 3. 3-step implementation plan

### Step 1 — Add `bathymetry` field to `Domain`

Add an optional `bathymetry: Callable | None = None` field to the `Domain` dataclass in `admesh/api.py`:

```python
@dataclass(frozen=True, slots=True)
class Domain:
    sdf: Callable
    bbox: tuple
    bathymetry: Callable | None = None   # NEW
    pfix: ndarray | None = None
    pts: ndarray | None = None
    bc_segments: tuple = ()
```

Behavioral contract:
- Defaults to `None` — no change for domains without bathymetry data.
- When `None`, `triangulate()` and `build_h()` skip the bathymetry stage (identical to current behavior).
- When set, the callable must satisfy `bathymetry(points: (K,2)) -> depth: (K,)`.

No other call sites are affected in Step 1 (the field is additive).

### Step 2 — Populate `bathymetry` in `Domain.from_mesh()`

When constructing a `Domain` from an existing ADCIRC mesh that carries bathymetry data, extract a `NearestNDInterpolator` and store it as `domain.bathymetry`:

```python
# admesh/api.py :: Domain.from_mesh()
if mesh.bathymetry is not None:
    from scipy.interpolate import NearestNDInterpolator
    bathy_interp = NearestNDInterpolator(
        mesh.nodes,
        mesh.bathymetry,
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

Interpolator choice rationale (from #10 investigation):
- `LinearNDInterpolator` returns 67.8% NaN outside the convex hull on the `wetting_and_drying_test.14` fixture (WNAT open-water region is outside the hull of the source mesh node set).
- `NearestNDInterpolator` returns 0% NaN, matches the source range exactly, and is robust for this use case.

### Step 3 — Wire `build_h()` in `triangulate()`

Replace the uniform-clamp fallback with a call to `build_h()` when `size_field is None and h_max is not None`:

```python
# admesh/api.py :: triangulate()
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
    # (else: use caller-supplied size_field or uniform h_max clamp as before)
```

These are the **spec-002/017 production parameters** (curvature_scale=20.0, medial_scale=0.1, bathy_scale=0.5, g=0.2). The `bathymetry` kwarg fires only when `domain.bathymetry is not None`; for polygon-only domains it is `None` and `build_h` skips the bathymetry stage (no behavior change for Tier-0 polygon tests).

## 4. Acceptance criteria

- [ ] **AC-001**: `Domain.bathymetry: Callable | None` field added; defaults to `None`; `Domain` remains hashable/frozen.
- [ ] **AC-002**: `Domain.from_mesh()` populates `bathymetry` via `NearestNDInterpolator` when `mesh.bathymetry is not None`; passes `fill_value=mesh.bathymetry.mean()`.
- [ ] **AC-003**: `triangulate()` calls `build_h()` (with spec-017 production parameters) when `size_field is None and h_max is not None`. The uniform-clamp fallback is removed for this case.
- [ ] **AC-004**: All 4 Tier-1 / Tier-2 tests in `tests/test_default_size_field.py` still pass without `xfail` decoration.
- [ ] **AC-005**: All Tier-0 tests still pass (`TestTier0PolygonDomains` — no bathymetry → uniform fallback path, if any, unchanged).
- [ ] **AC-006**: No regression on the broader suite (`pytest -q` exit 0).
- [ ] **AC-007** (visual): `output/release_gate_rebuild.png` shows quality improvement vs. the 0.1.0 baseline — mesh-quality histogram shifts toward higher q and coastline fidelity is visibly improved on the WNAT fixture.
- [ ] **AC-008**: `bash scripts/pre_tag_check.sh` exits 0.
- [ ] **AC-009** (closes #10): Issue #10 is closed by the operator on this issue's merge (not by automation).

## 5. Risk register

| Risk | Mitigation |
|---|---|
| Step 3 reintroduces the overshoot originally documented in #10 (size-field-driven boundary projection failures) | Run Tier-1/Tier-2 tests after each step independently; revert Step 3 if structural validity regresses (AC-004 gate) |
| Tier-0 polygon-domain regression: no-bathymetry path produces a different size field than the old uniform-clamp | Tier-0 exercised by `TestTier0PolygonDomains`; verify after Step 3 before marking AC-005 done |
| Tier-2 60-second wall-clock budget violated by full stack on WNAT (~10K nodes) | `build_h` has been profiled at ≪ 60 s on similar fixtures (spec-017 session); instrument the call with `time.perf_counter` if it slips; spec-020 benchmark can serve as a baseline |
| `Domain` dataclass becomes non-hashable if `bathymetry` is a mutable callable | `frozen=True` + `slots=True` already prevents assignment post-construction; `NearestNDInterpolator` is a Python object — use `field(hash=False, compare=False)` if equality comparison breaks |
| `Domain.from_mesh()` is called with a mesh whose `bathymetry` attribute is missing (older fixture files) | Guard: `if hasattr(mesh, 'bathymetry') and mesh.bathymetry is not None` |

## 6. Dependency ordering

The three steps can be implemented in sequence within a single session (each is a small, independent edit):

1. **Step 1** (Domain field) — no blockers.
2. **Step 2** (`from_mesh`) — requires Step 1's field to exist.
3. **Step 3** (`triangulate` wiring) — requires Step 1's field; independent of Step 2 (Step 2 is only relevant when `Domain.from_mesh()` is called, i.e., ADCIRC `.14` input path).

**External dependency:** If #65 lands before spec-020's full Option 1 is implemented, the benchmark worker (`benchmarks/_bench_worker.py`) must be updated to use `triangulate()` directly (as spec-020 specifies), since `build_h` will now be called inside `triangulate()` rather than being available as a standalone call in the worker.

## 7. Test plan

| Test | Fixture | Assertion |
|---|---|---|
| `test_domain_bathymetry_field_default` | `UNIT_SQUARE` domain (no mesh) | `Domain.bathymetry is None`; all Tier-0 tests pass |
| `test_from_mesh_bathymetry_populated` | `wetting_and_drying_test.14` | `domain.bathymetry` is a `NearestNDInterpolator`; queried on held-out nodes, returns 0% NaN |
| `test_from_mesh_no_bathymetry` | mesh without `.bathymetry` attribute | `domain.bathymetry is None`; no `AttributeError` |
| `test_triangulate_calls_build_h` | `UNIT_SQUARE`, `h_max=0.1` | Monkeypatch `build_h`; assert it is called with `curvature_scale=20.0`, `medial_scale=0.1` |
| `test_triangulate_bathymetry_fires` | `wetting_and_drying_test.14` via `from_mesh` | `build_h` called with `bathymetry=<NearestNDInterpolator>` |
| `test_triangulate_no_bathymetry_skips` | polygon domain | `build_h` called with `bathymetry=None` |
| Tier-0 regression | `pytest tests/test_default_size_field.py -q` | All 4 tests pass without xfail |
| Tier-2 wall-clock | WNAT fixture, timed | `triangulate()` completes in ≤ 60 s |
| Visual review | `output/release_gate_rebuild.png` | Quality histogram and coastline fidelity visibly improved vs. 0.1.0 baseline |

## 8. Files likely touched (implementation session)

- `admesh/api.py` — three targeted edits: `Domain` dataclass (Step 1), `Domain.from_mesh()` (Step 2), `triangulate()` (Step 3).
- `tests/test_default_size_field.py` — existing tests must pass; may need to update expected `min_q` floor if quality improves.
- `tests/test_triangulate_wiring.py` — new test file with the monkeypatched `build_h` assertions from §7.
- `scripts/pre_tag_check.sh` — verify it still exits 0 after the change (AC-008).
- `output/release_gate_rebuild.png` — regenerate (run `scripts/diagnose_issue_10.py`) after implementation for visual verification.
- `docs/PORTING_NOTES.md` — note the `triangulate()` wiring change and the `Domain.bathymetry` addition.

## 9. Out of scope

- Adding a new `min_q` or edge-length-distribution-match gate to `tests/test_default_size_field.py` (separate quality-gate spec).
- GPU / multi-core acceleration of the size-field stack (issue #8).
- Investigation tools rewrite (`scripts/diagnose_issue_10.py` already shipped).
- The C++/Rust port (issue #86) — orthogonal track.
- Octree size-field integration (spec 021 / #115, spec 024 / #114) — orthogonal; `build_h` is the uniform-grid stack; the octree stack is a separate `fh` provider.

## 10. Cross-references

- #65 — this issue; the operator's 3-step plan is the direct source for §3.
- #10 — original size-field overshoot report; closes on this issue's merge (AC-009).
- spec 009 R4 (`specs/009-release-readiness-for-0.1.0/spec.md`) — structural-validity gate that scoped this work as post-0.1.0.
- spec 017 (`specs/017-default-size-field-stack/spec.md`) — `build_h` production parameters that Step 3 uses.
- spec 020 (`specs/020-wnat-benchmark-quality/spec.md`) — benchmark quality fix; its Option 1 depends on this spec landing (see §6 external dependency).
- `scripts/diagnose_issue_10.py` — diagnostic driver for before/after visual validation (AC-007).
- `admesh/_stages/mesh_size.py::build_h` — the function wired in Step 3.
