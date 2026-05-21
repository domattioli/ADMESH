# CLAUDE.md

<!-- maintained-by: maintain-claude-md skill -->

Operational reference for Claude Code sessions on ADMESH.

**Read these three at every session start (in order):**
`CONSTITUTION.md` → `PROJECT_PLAN.md` → `CLAUDE.md`.

If CLAUDE.md contradicts constitution, constitution wins.

---

## Project overview

Python port of `01_ADMESH_Library` from [`domattioli/QuADMesh-MATLAB`](https://github.com/domattioli/QuADMesh-MATLAB) at commit `19b2eb9f078a648daec3fd40d5d4c6e072f467ac`. See `CONSTITUTION.md` Article I for north star; Article II for hard rules (faithful port, no C extensions in first cut, 0-based indexing).

Local MATLAB reference clone: `/workspace/QuADMesh-MATLAB` (branch `main`). Source tree of interest: `01_ADMESH_Library/`.

---

## DomI Sync Contract

This repo = downstream consumer of [`domattioli/DomI`](https://github.com/domattioli/DomI), upstream source of truth for shared skills, MANIFEST, policy.

**On every session start**, `scripts/instructions_on_start.sh` invokes `sync-from-domi` skill's `check_pin.sh` to detect drift against `domattioli/DomI@main`. Check compares pinned commit in `.domi-pin` against upstream HEAD + verifies MANIFEST.md hash at that pin.

**Hard stop on drift.** If local pin behind upstream (exit code 1) or manifest hash mismatches at pinned SHA (exit code 3, "forked"), startup hook prints HARD STOP banner + exits non-zero. Session refuses all write work until operator (or Claude) invokes `sync-from-domi` skill via `> sync from DomI`, which pulls changed artifacts, runs `update_pin.sh`, commits refreshed `.domi-pin`.

**Skipped checks.** When `gh` unavailable (exit code 4), check skipped with warning + session continues — infra failures must not block work. Unpinned state (exit code 2) allowed for first-time setup.

**Plumbing:**
- `.domi-pin` (committed) — ledger of upstream SHA + MANIFEST.md sha256.
- `scripts/instructions_on_start.sh` — startup hook with drift gate.
- `sync-from-domi`, `request-from-domi`, `introspect` plugins — installed from DomI marketplace (`claude plugin marketplace add domattioli/DomI`).

**MUST NOT** edit DomI-owned skills directly in this repo. Submit changes upstream via `request-from-domi`; downstream = pull-only.

---

## Stream Timeout Prevention

1. Each numbered task ONE AT A TIME. Complete fully, confirm, next.
2. Never write file >~150 lines in single tool call. Multi-pass append/edit if longer.
3. Fresh session if conversation long (20+ tool calls). Error worsens with session size.
4. Keep grep/search outputs short. Flags `--include`, `-l` (list files only) limit output size.
5. On timeout, retry shorter form. Don't repeat entire task from scratch.

## Commands

```bash
# Install for development
pip install -e ".[dev]"

# Run all tests
pytest tests/ -q

# Run single stage's tests
pytest tests/test_distance.py -v

# Benchmark Numba mesh_size solver vs. C baseline
python scripts/bench_mesh_size.py

# Export fresh reference fixtures from MATLAB (requires MATLAB)
matlab -batch "run('scripts/export_matlab_fixtures.m')"
```

---

## Domain Loading & API (v0.2+)

**v0.2 breaking change**: `domain_from_polygon()` + `domain_from_sdf()` removed from public API. All domains now come from files or ADMESH-Domains registry. Domain definitions become version-controlled artifacts, not ad-hoc Python objects.

**File-based domain loading:**
```python
from admesh import load_domain_from_toml, load_domain_from_json, load_domain_from_fort14

# Load domain then triangulate
domain = load_domain_from_toml("domain.toml")
mesh = admesh.triangulate(domain, h0=0.1)

# Or pass path/mesh_id directly to triangulate()
mesh = admesh.triangulate("domain.toml", h0=0.1)
mesh = admesh.triangulate("domain.json", h0=0.1)
mesh = admesh.triangulate("existing_mesh.14", h0=0.1)  # Extract boundary
```

**Registry integration (requires `admesh-domains` package):**
```python
from admesh import load_domain_from_registry, list_available_domains

domains = list_available_domains()
mesh = admesh.triangulate("noaa-hsofs-v20", h0=0.1)  # Auto-detects registry
```

**Supported domain file formats:**
- `TOML` — ADMESH-Domains native format (recommended; version-controllable)
- `JSON` — Universal portable format
- `.14` / `.grd` — Fort.14 ADCIRC mesh files (extracts boundary as domain)

**Migration from v0.1:**
```python
# v0.1 (removed) — no longer works
domain = admesh.domain_from_polygon([outer_ring, hole_ring])
domain = admesh.domain_from_sdf(my_sdf, bbox=(-1, -1, 1, 1))

# v0.2 — save polygon to JSON once, load every time
import json
domain_dict = {"bbox": [-1, -1, 1, 1], "rings": [outer_ring.tolist()]}
with open("my_domain.json", "w") as f:
    json.dump(domain_dict, f)
mesh = admesh.triangulate("my_domain.json", h0=0.1)

# v0.2 — custom SDF: use Domain dataclass directly (still exported)
from admesh import Domain
domain = Domain(sdf=my_sdf_callable, bbox=(-1, -1, 1, 1))
mesh = admesh.triangulate(domain, h0=0.1)
```

See `docs/DOMAIN_IO.md` for complete examples + format specifications.

---

## Architecture

Package has **two layers**:

1. **Faithful-port stage modules** (Constitution Principle I — locked, must stay numerically identical to MATLAB). One module per MATLAB stage, bottom-up dependency order.
2. **Additive Pythonic API layer** (spec-001 through spec-005). Public user-facing surface — `triangulate()`, `Mesh`, `Domain`, fort.14 I/O, loaders, registry integration, viz, quad-prep. Composes stage modules; never modifies them.

```
admesh/
  __init__.py          # public API re-exports (Domain, Mesh, triangulate, …)

  # Faithful-port stage modules (locked) ------------------------------
  routine.py           # 01 — top-level driver (ADmeshRoutine, ADmeshSubMeshRoutine)
  background_grid.py   # 02 — CreateBackgroundGrid
  distance.py          # 03 — SignedDistanceFunction, PTS2PointList
  curvature.py         # 04 — CurvatureFunction
  medial_axis.py       # 05 — MedialAxisFunction, TriMedialAxisFunction, medial_distance_FMM
  bathymetry.py        # 06 — BathymetryFunction
  dominate_tide.py     # 07 — DominateTideFunction
  boundary.py          # 08 — EnforceBoundaryConditions, create_polygon_structure
  mesh_size.py         # 09 — MeshSizeFunction + Numba-JIT iterative solver
  distmesh.py          # 10 — distmesh2d + fixmesh (triangulation only; tri2quad out of scope)
  quality.py           # 11 — MeshQuality
  in_polygon.py        # 12 — InPolygon
  inpaint.py           # 13 — inpaint_nans

  # Additive Pythonic API layer (spec-001+, strictly composes above)
  api.py               # spec-001 — Domain/Mesh/BoundarySegment dataclasses + triangulate()
  boundary_types.py    # spec-001 — BoundaryType enum (ADCIRC IBTYPE codes incl. 3/4/13/24)
  fort14.py            # spec-001 — read_fort14 / write_fort14 round-trip I/O
  size_field.py        # spec-002 — SizeFieldFn protocol + compose_size_field stack
  loaders.py           # spec-002 — load_domain_from_{toml,json,fort14}
  domains.py           # MVP domain helpers (square, L-shape, U-shape, hole, doughnut)
  viz.py               # optional matplotlib mesh.plot() (extras=[viz])
  quad_prep.py         # spec-004 — smooth_for_quadrangulation (right-isoceles smoother)
  registry.py          # spec-005 — load_domain_from_registry, list_available_domains

tests/
  test_<stage>.py              # faithful-port stage tests (one per stage)
  test_api_*.py                # spec-001 public-API surface
  test_fort14_*.py             # fort.14 round-trip + reference corpus
  test_size_field_composition.py # size-field stack
  test_quad_prep*.py           # spec-004
  test_registry.py             # spec-005
  test_matlab_port.py          # cross-stage MATLAB parity smoke
  test_backward_compat_full_suite.py # v0.1 → v0.2 migration guard
  fixtures/<stage>/            # .npz inputs+outputs captured from MATLAB
  fixtures/fort14/             # ADCIRC reference meshes (incl. wnat_test.14)

scripts/
  export_matlab_fixtures.m     # MATLAB-side fixture emitter
  mat_to_npz.py                # one-off .mat → .npz converter
  bench_mesh_size.py           # Numba vs. C solver benchmark
  render_*.py                  # demo / inspection plots → output/
  wnat_demo.py                 # WNAT structural-validity gate driver
  pre_tag_check.sh             # release-gate pre-flight

specs/
  001-pythonize-and-fort14-integration/  # SHIPPED — Pythonic API + fort.14 I/O
  002-size-field-defaults/               # IN-FLIGHT — default size-field stack (0.1.0 blocker)
  004-quad-prep-smoother/                # IN-FLIGHT — pre-quad triangle smoother
  005-adcirc-mesh-registry/              # IN-FLIGHT — federated mesh registry

docs/
  PORTING_NOTES.md     # running log of MATLAB → Python substitutions
  DOMAIN_IO.md         # domain file format spec (TOML / JSON / fort.14)
  sessions/            # per-session plan + state handoff files
  persistence_journal.md  # log of session interruptions / redirects

output/                # generated PNGs / artifacts (gitignored except gate plots)
```

**Locked vs additive**: any change to 13 faithful-port stage modules requires Constitution-Principle-I justification. New behaviour belongs in additive layer. Stage modules can be *called* from additive layer, never reverse.

---

## MATLAB → Python conventions

**Naming**
- `CreateBackgroundGrid.m` → `create_background_grid()` in `admesh/background_grid.py`.
- Private helpers keep MATLAB name in snake_case, leading underscore if module-private.

**Indexing**
- MATLAB 1-based → Python 0-based. Subtract 1 wherever MATLAB source indexes into arrays.
- MATLAB `end` → Python `-1` or `len(x) - 1`.
- MATLAB `x(i:j)` inclusive → Python `x[i-1:j]` (half-open, remember upper bound doesn't shift).

**Common substitutions**
| MATLAB | Python |
|---|---|
| `inpolygon(xq, yq, xv, yv)` | `admesh.in_polygon.in_polygon(xq, yq, xv, yv)` (our port) |
| `delaunay(x, y)` | `scipy.spatial.Delaunay(np.c_[x, y]).simplices` |
| `griddata` | `scipy.interpolate.griddata` |
| `bwdist` | `scipy.ndimage.distance_transform_edt` |
| `struct` | `dataclasses.dataclass` or dict — pick per-module |
| cell array of varying-length vectors | `list[np.ndarray]` |

Document each non-obvious substitution in `docs/PORTING_NOTES.md` with one-line note on any behavior difference (closed-vs-open boundary, tie-breaking, ordering).

**Docstring template**
```python
def create_background_grid(domain, params):
    """Build structured background grid over domain.

    Port of ``01_ADMESH_Library/02_Create_Background_Grid/CreateBackgroundGrid.m``
    from QuADMesh-MATLAB @ 19b2eb9.

    Parameters
    ----------
    domain : ...
    params : ...

    Returns
    -------
    grid : ...
    """
```

---

## Numba conventions

`admesh/mesh_size.py` hosts iterative PDE solver ported from `MeshSizeIterativeSolver.c`. Keep two implementations in-module:

1. `_solve_iter_py(...)` — pure NumPy, readable, reference.
2. `_solve_iter_nb(...)` — `@njit(cache=True)`, optimized.

Test in `tests/test_mesh_size.py` asserts they agree to `atol=1e-10` on fixed input. Public `solve_iter(...)` dispatches to Numba path by default, with `use_numba=False` kwarg for debugging.

---

## Testing

- One test file per stage: `tests/test_<stage>.py`.
- Fixtures: `.npz` under `tests/fixtures/<stage>/<case>.npz` with named arrays for inputs + expected outputs.
- Load pattern:
  ```python
  data = np.load("tests/fixtures/distance/square.npz")
  out = admesh.distance.signed_distance(data["x"], data["y"], data["poly"])
  np.testing.assert_allclose(out, data["expected"], atol=1e-8)
  ```
- Keep fixtures small (<1 MB per file ideally) so repo stays lightweight.

---

## Session cadence (lightweight)

Each working session:
1. **Orient** — read `CONSTITUTION.md`, `PROJECT_PLAN.md`, this file.
2. **Pick stage** from current phase in `PROJECT_PLAN.md`.
3. **Port** MATLAB source, committing per file/function.
4. **Test** against fixtures; iterate until green.
5. **Commit + push.** Update `PROJECT_PLAN.md` "Where we are today" if phase milestone landed.

No mandatory session reports, no 4-agent planning, no dispatch queue — this = port, not research project. Keep simple.

---

## Branching (operational)

See **Constitution Article VI rules 5–8** for binding rules. Quick operational summary:

- **Default to `main`.** Don't create branches for one-off edits.
- **Speckit = only branch-creator.** New feature branches come from `/speckit-specify` (which fires `before_specify` git hook). Don't run `git checkout -b` directly.
- **Speckit naming only.** Branches follow `NNN-<short-name>` (sequential) per `.specify/init-options.json`. Don't create or accept `claude/<feature>-<hash>` branches; if session-system pre-creates one, ignore or consolidate under speckit branch.
- **Scan first.** Before invoking `/speckit-specify`, run `git branch -a` + look for branch already covering same feature (by short-name, keywords, or related issue #). Reuse rather than create parallel one.
- **Consolidate redundancies.** If duplicate branches for same feature found, ask user once, then delete redundant ones (local + remote) + keep only speckit-named branch.

---

## Related repos on disk + on GitHub

| Path / URL | What it is |
|---|---|
| `/workspace/QuADMesh-MATLAB` | MATLAB source (read-only reference) |
| `/workspace/MADMESHR` | RL-based **mesh generator** for tri/quad/mixed 2D meshes (advancing-front, Soft Actor-Critic). MVP/PoC, not on PyPI. Long-term positioning vs ADMESH undecided: may deprecate ADMESH or remain sibling. Faithful-port boundary still applies — MADMESHR concepts must not bleed into 13 locked stage modules in `admesh/*.py`. |
| [`domattioli/CHILmesh`](https://github.com/domattioli/CHILmesh) | Same-author Python **mesh data structure + smoother** for tri/quad/mixed (PyPI: `chilmesh`). Composes downstream of ADMESH — wrap ADMESH output for FEM smoothing, quality analysis, or `fort.14` I/O. Boundary formalized in [`docs/adr/ADR-001-chilmesh-boundary.md`](docs/adr/ADR-001-chilmesh-boundary.md) (spec 015). Not a faithful-port concern; references in docs only. |
| `/workspace/ADMESH` | This repo |
| [`domattioli/ADMESH-Domains`](https://github.com/domattioli/ADMESH-Domains) | Federated registry of ADCIRC-compatible meshes — split out of this repo on 2026-04-26 |
| [`domattioli/DomI`](https://github.com/domattioli/DomI) | Upstream skill provider. Foundational skills (`github-release`, `pypi-publish`, `api-key-rotation`, `send-email`, `act-autonomously`, `speckit-*`) sourced from here via `sync-from-domi`. |

<!-- SPECKIT START -->
**Shipped:** `001-pythonize-and-fort14-integration` — Pythonic public API (`Domain`, `Mesh`, `triangulate()`) + ADCIRC fort.14 round-trip I/O. Now public admesh contract.

**In-flight specs** (read each spec's `spec.md` + `plan.md` before touching its modules):

- `002-size-field-defaults` — wire MATLAB-faithful size-field stack (curvature → medial-axis → bathymetry → tide, `min`-stacked) as Phase-1 default in `triangulate()`; extends fort.14 with IBTYPE 3 / 4 / 13 / 24 paired-edge BC records. **0.1.0 release blocker** — gated on WNAT structural-validity gate ([issue #10](https://github.com/domattioli/ADMESH/issues/10)).
- `004-quad-prep-smoother` — `smooth_for_quadrangulation()` nudges ADMESH triangulations toward right-isoceles so downstream tri-to-quad fusion (CHILmesh `tri2quad`, OceanMesh2D, ADCIRC v55+) produces clean quads instead of rhombi.
- `005-adcirc-mesh-registry` — federated mesh registry for ADCIRC meshes (TOML manifests, HuggingFace mirror for redistributable licenses, slug + SHA-256 IDs). Split-out `ADMESH-Domains` repo = upstream catalog; this spec wires registry lookup into `triangulate(mesh_id)`.

**Constitution Principle I** still binds: 13 faithful-port stage modules MUST stay numerically identical to MATLAB. New behaviour goes in additive-layer modules (`api.py`, `fort14.py`, `boundary_types.py`, `loaders.py`, `size_field.py`, `viz.py`, `quad_prep.py`, `registry.py`, `domains.py`) — strictly additive, never replacing locked modules.
<!-- SPECKIT END -->
