# Plan 017 — Default Size-Field Stack Wiring

**Spec:** [017-default-size-field-stack/spec.md](./spec.md)
**Phase:** planning only. Implementation occurs in a follow-up
session when the 0.2.0 milestone opens.

---

## 1. Constitution gate

- Principle I (faithful-port locked modules): **untouched**. All
  edits in this plan are confined to `admesh/api.py` (additive
  layer) and tests / docs. `admesh/_stages/mesh_size.py::build_h`
  is consumed unchanged; the call signature in spec §3 step 3
  matches the existing `build_h(domain, base, curvature_scale,
  medial_scale, bathymetry, bathy_scale, hmin, hmax, g)` surface.
- Principle II (no C extensions): N/A — pure Python composition
  edit.
- ADR-001 (CHILmesh boundary): bathymetry interpolation stays on
  the ADMESH side. CHILmesh consumes the resulting `Mesh.bathymetry`
  array, not the `Domain.bathymetry` callable.

## 2. Sequencing

Three steps, each a separate commit. Land in order so the bisect
window is narrow if a Tier-1 / Tier-2 regression appears.

### Step 1 — `Domain.bathymetry` field

**Edits:**

1. `admesh/api.py` — add `bathymetry: Callable | None = None` to
   the `Domain` dataclass (admesh/api.py:232). Position the field
   AFTER `bbox` and BEFORE `pfix`, matching the issue snippet, but
   audit positional callers first (see §3 below).
2. `admesh/api.py:__doc__` — extend the `Domain` docstring
   `Attributes` section with one paragraph on `bathymetry`.
3. `admesh/__init__.py` — no change. `Domain` is already
   re-exported.
4. `tests/test_api_domain.py` (or equivalent existing surface
   test) — assert default `Domain.bathymetry is None`.

**Validation:**

- `pytest tests/test_api_domain.py -q`
- `pytest tests/ -q` — no regression.

**Commit:** `feat(017): add Domain.bathymetry interpolant field (#65)`

### Step 2 — `Domain.from_mesh()` populates bathymetry

**Edits:**

1. `admesh/api.py:260–...` — after the existing
   `LinearNDInterpolator` SDF build, add the
   `NearestNDInterpolator` bathymetry build. Guard with
   `if mesh.bathymetry is not None`.
2. Pass `bathymetry=bathy_interp` to the `cls(...)` return.
3. New test file `tests/test_domain_bathymetry.py`:
   - Case A: `Domain.from_mesh(mesh_with_bathy)` →
     `domain.bathymetry((x, y))` returns finite values inside the
     bbox.
   - Case B: `Domain.from_mesh(mesh_without_bathy)` →
     `domain.bathymetry is None`.
   - Case C: `Domain.from_mesh(wetting_and_drying_test.14_mesh)` —
     0% NaN inside the domain bbox.
   - Case D: round-trip — `Mesh → Domain → triangulate → Mesh` does
     not lose bathymetry shape (NB: the new mesh has its own
     interpolated bathymetry; assert finite-everywhere, not
     value-identity).

**Validation:**

- `pytest tests/test_domain_bathymetry.py -q`
- `pytest tests/ -q`

**Commit:** `feat(017): populate Domain.bathymetry in from_mesh (#65)`

### Step 3 — Wire `build_h` in the default `triangulate()` branch

**Edits:**

1. `admesh/api.py:713–742` — current dispatcher prefers the
   bounded uniform fallback in `compose_size_field` when only
   `h_min` / `h_max` are passed. Add a sub-branch:
   ```python
   if (
       size_field is None
       and not user_contribs
       and h_max is not None
   ):
       from admesh._stages.mesh_size import build_h
       fh = build_h(
           domain,
           base=h_max,
           curvature_scale=20.0,
           medial_scale=0.1,
           bathymetry=domain.bathymetry,
           bathy_scale=0.5,
           hmin=h_max / 10.0,
           hmax=h_max,
           g=0.2,
       )
   ```
2. Leave the `h_min`-only path on the existing uniform fallback.
3. `docs/PORTING_NOTES.md` — append a 0.2.0 entry: "default
   size-field stack (build_h) now wired into `triangulate()` when
   only `h_max` is supplied; previously a uniform clamped field."
4. Re-run `scripts/render_release_gate.py` — capture before/after
   PNGs for the PR description.

**Validation:**

- `pytest tests/test_default_size_field.py -q` — all 4 acceptance
  tests still pass.
- `pytest tests/ -q` — no regression.
- `python scripts/diagnose_issue_10.py` — produces report.
- `python scripts/render_release_gate.py` — generates PNG.
- `bash scripts/pre_tag_check.sh`.

**Commit:** `feat(017): wire build_h default in triangulate() (#65)`

## 3. Pre-implementation audit checklist

Before opening the impl PR, the implementer must:

- [ ] `grep -rn "Domain(" admesh/ tests/ specs/` — list every
  `Domain` constructor call. Convert any positional form to
  keyword form so the new field can be inserted anywhere in the
  dataclass order without breaking callers.
- [ ] Confirm `build_h` signature matches spec snippet at the
  commit ADMESH lands the impl. If `mesh_size.py::build_h` has
  shifted, update the call snippet in step 3.
- [ ] Confirm `mesh.bathymetry` shape contract: `(N_nodes,)`
  float64. Read admesh/api.py:165 for the equality test, which is
  the canonical contract.
- [ ] Confirm `wetting_and_drying_test.14` fixture is still
  present under `tests/fixtures/fort14/`.
- [ ] Read the most recent #10 thread for any new constraints
  added since the 2026-05-13 planning comment.

## 4. Rollback

Each step is a separate commit. If Tier-1 / Tier-2 acceptance
tests regress on Step 3, `git revert` Step 3's commit. Steps 1
and 2 are inert without Step 3 — they extend the surface but do
not change `triangulate()` behavior, so they can ship even if
Step 3 is rolled back.

## 5. Cross-repo notes

- **CHILmesh:** No impact. `Domain.bathymetry` is internal to
  ADMESH. `Mesh.bathymetry` (the consumer-facing array) is
  unchanged.
- **MADMESHR:** No impact. MADMESHR consumes meshes, not domains.
- **ADMESH-Domains:** No impact. Domain TOML / JSON files do not
  encode a bathymetry interpolant — they encode boundary geometry.
  The bathymetry path activates only on the
  `Domain.from_mesh(mesh_with_bathy)` codepath, which already
  routes through `Mesh` → `Domain`, not file → `Domain`.
- **QuADMesh:** No direct impact. If the post-port QuADMesh API
  ever wraps `triangulate()` and re-supplies a bathymetry callable,
  it would consume the new field; document during QuADMesh port
  rather than here.

## 6. Open questions (resolve before impl)

1. Does `build_h` enforce any `domain.bbox` ⊆ bathymetry
   interpolant support contract? If yes, document; if no, confirm
   safe extrapolation behavior of `NearestNDInterpolator` outside
   the convex hull (it returns nearest-node value, not
   `fill_value`, which differs from `LinearNDInterpolator`).
2. Should the `build_h` knobs (`curvature_scale=20.0`,
   `medial_scale=0.1`, `bathy_scale=0.5`, `g=0.2`) be parameters
   on `triangulate()` or stay hard-coded defaults? Spec stance:
   hard-code in this spec; expose as kwargs in a follow-up spec
   gated on user feedback after 0.2.0 ships.
3. Where does the visual-quality gate live — manual PR-time
   review of `output/release_gate_rebuild.png`, or scripted
   threshold on a mesh-quality metric? Spec stance: PR-time visual
   review; scripted gate is a separate quality-gate spec.
