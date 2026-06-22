# Tasks 017 — Default Size-Field Stack Wiring

**Spec:** [017-default-size-field-stack/spec.md](./spec.md)
**Plan:** [017-default-size-field-stack/plan.md](./plan.md)

Atomic, ordered task list. Each `T-017-N` is intended to land as
one commit. Tests precede implementation per Constitution
Principle VII (test-first).

---

## T-017-0 — Pre-impl audit (planning, no commit)

- [ ] Run `grep -rn "Domain(" admesh/ tests/ specs/` and record
      every positional constructor call site in this file under §
      "audit notes" below.
- [ ] Confirm `build_h` signature at HEAD matches spec §3 step 3.
      If drift, file a sub-issue against this spec.
- [ ] Confirm `tests/fixtures/fort14/wetting_and_drying_test.14`
      present. If missing, file a sub-issue.

## T-017-1 — Test scaffold: `Domain.bathymetry` field default

- [ ] Add (or extend) `tests/test_api_domain.py::test_domain_bathymetry_defaults_to_none`.
- [ ] Run `pytest tests/test_api_domain.py -q`. Expect new test to
      FAIL (`AttributeError: 'Domain' object has no attribute
      'bathymetry'`).

Commit: `test(017): scaffold Domain.bathymetry default test (#65)`

## T-017-2 — Impl: add `Domain.bathymetry` field

- [ ] Edit `admesh/api.py:232` — add
      `bathymetry: Callable[[np.ndarray], np.ndarray] | None = None`.
- [ ] Update `Domain` docstring `Attributes` section.
- [ ] Run `pytest tests/test_api_domain.py -q`. Expect PASS.
- [ ] Run `pytest tests/ -q`. Expect no regression.

Commit: `feat(017): add Domain.bathymetry interpolant field (#65)`

## T-017-3 — Test scaffold: `Domain.from_mesh()` bathymetry population

- [ ] New file `tests/test_domain_bathymetry.py` with cases A–D
      from plan §2 step 2.
- [ ] Run `pytest tests/test_domain_bathymetry.py -q`. Expect all
      cases FAIL until T-017-4 lands.

Commit: `test(017): scaffold Domain.from_mesh bathymetry tests (#65)`

## T-017-4 — Impl: `Domain.from_mesh()` populates bathymetry

- [ ] Edit `admesh/api.py::Domain.from_mesh` to build
      `NearestNDInterpolator` when `mesh.bathymetry is not None`.
- [ ] Pass `bathymetry=bathy_interp` (or `None`) to `cls(...)`.
- [ ] Run `pytest tests/test_domain_bathymetry.py -q`. Expect PASS.
- [ ] Run `pytest tests/ -q`. Expect no regression.

Commit: `feat(017): populate Domain.bathymetry in from_mesh (#65)`

## T-017-5 — Test scaffold: `triangulate()` default-stack branch

- [ ] Add `tests/test_default_size_field.py::test_build_h_wired_when_only_h_max_given`:
  - Construct a small polygon domain with `bathymetry=None`.
  - Triangulate with only `h_max=0.1` (no `size_field`, no
    `user_contribs`, no `h_min`).
  - Assert the returned mesh has variable edge lengths (not
    uniform) — sentinel that `build_h` ran rather than
    `compose_size_field` uniform-fallback.
- [ ] Run the test — expect FAIL until T-017-6 lands.

Commit: `test(017): scaffold build_h-dispatch sentinel test (#65)`

## T-017-6 — Impl: wire `build_h` in `triangulate()` default branch

- [ ] Edit `admesh/api.py:704–742` per plan §2 step 3.
- [ ] Run `pytest tests/test_default_size_field.py -q`. Expect all
      4 acceptance tests + new sentinel PASS.
- [ ] Run `pytest tests/ -q`. Expect no regression.
- [ ] Generate diagnostic evidence:
  - `python scripts/diagnose_issue_10.py > /tmp/diag.txt`
  - `python scripts/render_release_gate.py`
  - Attach `output/release_gate_rebuild.png` to the PR description.
- [ ] Run `bash scripts/pre_tag_check.sh`.

Commit: `feat(017): wire build_h default in triangulate() (#65)`

## T-017-7 — Docs

- [ ] `docs/PORTING_NOTES.md` — append 0.2.0 entry.
- [ ] `CLAUDE.md` — update spec 002 in-flight note to mark
      "default-stack wiring shipped via spec 017".

Commit: `docs(017): note default-stack wiring in PORTING_NOTES (#65)`

## T-017-8 — Close issue

- [ ] Comment on #65 with:
  - Spec / plan / tasks merged commit SHA.
  - PR URL.
  - Visual evidence (release-gate PNG before/after).
  - Diagnostic numbers from `diagnose_issue_10.py`.
- [ ] Close #65 only after PR merges to `main`.
- [ ] Close #10 referencing #65 as the resolving issue.

---

## Audit notes (populate during T-017-0)

```
Positional `Domain(` constructor sites:
  <fill during T-017-0>

`build_h` signature verified at SHA:
  <fill during T-017-0>

`wetting_and_drying_test.14` present:
  <yes/no, path>
```

---

## Estimated effort

- T-017-0: 15 min (audit only)
- T-017-1 + T-017-2: 20 min
- T-017-3 + T-017-4: 45 min
- T-017-5 + T-017-6: 60 min (regression risk)
- T-017-7 + T-017-8: 15 min

Total: ~2.5 h wall-clock, single session if no regressions found.
