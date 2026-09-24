# ADMESH

Python port of `01_ADMESH_Library` from [`domattioli/QuADMesh-MATLAB`](https://github.com/domattioli/QuADMesh-MATLAB) at commit `19b2eb9f078a648daec3fd40d5d4c6e072f467ac`. **Two layers:** locked faithful-port stage modules (numerically identical to MATLAB) + additive Pythonic API layer. Published on PyPI as `admesh2D` (v0.5.1+).

---

## Hard rules

1. **Faithful-port invariant (Constitution Principle I):** 13 stage modules under `src/admesh/_stages/` must remain numerically identical to MATLAB source. Any change requires Constitution-Principle-I justification. New behavior belongs in additive-layer modules only.

2. **No C extensions in first cut:** Per Article II, v0.5.1+ permits *exploration* of C++ post-port; first-generation port must be pure Python.

3. **0-based indexing:** All Python implementations use 0-based indices. Document MATLAB → Python index substitutions in `docs/PORTING_NOTES.md`.

4. **DomI sync contract:** This repo is a downstream consumer of [`domattioli/DomI`](https://github.com/domattioli/DomI). Changes to DomI-owned skills must go upstream via `request-from-domi`; downstream is pull-only. **Hard stop on `.domi-pin` drift** — `scripts/instructions_on_start.sh` refuses all write work until synced.

5. **No secrets in commits:** Never commit `.env`, `*token*`, `*secret*`, `*.pem`, `*credentials*`.

6. **No force-push to shared branches:** All policy-bound branches (`main`, `development`) are protected.

---

## Repository layout

```
ADMESH/
├── src/admesh/
│   ├── __init__.py                  # public API re-exports
│   ├── _stages/                     # 13 faithful-port stage modules (LOCKED)
│   │   ├── routine.py               # 01 — top-level driver
│   │   ├── background_grid.py       # 02
│   │   ├── distance.py              # 03
│   │   ├── curvature.py             # 04
│   │   ├── medial_axis.py           # 05
│   │   ├── bathymetry.py            # 06
│   │   ├── dominate_tide.py         # 07
│   │   ├── boundary.py              # 08
│   │   ├── mesh_size.py             # 09 + Numba-JIT solver
│   │   ├── distmesh.py              # 10
│   │   ├── quality.py               # 11
│   │   ├── in_polygon.py            # 12
│   │   └── inpaint.py               # 13
│   └── (Additive API layer)
│       ├── api.py                   # spec-001: Domain/Mesh/triangulate
│       ├── boundary_types.py        # spec-001: ADCIRC IBTYPE enum
│       ├── fort14.py                # spec-001: fort.14 I/O
│       ├── loaders.py               # spec-002: load_domain_from_*
│       ├── size_field.py            # spec-002: size-field stack
│       ├── domains.py               # MVP domain helpers
│       ├── viz.py                   # optional matplotlib
│       ├── quad_prep.py             # spec-004: tri→quad smoother
│       └── registry.py              # spec-005: mesh registry
├── tests/
│   ├── test_<stage>.py              # one per stage (fixtures from MATLAB)
│   ├── test_api_*.py                # spec-001 public API
│   ├── test_fort14_*.py             # fort.14 round-trip
│   ├── test_size_field_composition.py
│   ├── test_quad_prep*.py
│   ├── test_registry.py
│   ├── test_matlab_port.py          # cross-stage parity smoke
│   ├── fixtures/<stage>/*.npz       # reference inputs + outputs from MATLAB
│   └── fixtures/fort14/             # ADCIRC reference meshes
├── scripts/
│   ├── export_matlab_fixtures.m     # MATLAB-side fixture emitter
│   ├── bench_mesh_size.py           # Numba vs. C solver benchmark
│   ├── render_*.py                  # demo plots
│   └── wnat_demo.py                 # structural-validity gate
├── docs/
│   ├── governance/
│   │   ├── CONSTITUTION.md          # hard rules & principles
│   │   └── PROJECT_PLAN.md          # roadmap & current state
│   ├── PORTING_NOTES.md             # MATLAB → Python substitutions
│   ├── DOMAIN_IO.md                 # domain file formats
│   ├── sessions/                    # per-session handoff notes
│   └── adr/                         # architecture decision records
├── .specify/specs/                  # feature specs (spec-001 through 005+)
├── pyproject.toml                   # package metadata
└── .domi-pin                        # DomI sync pinning (committed)
```

**Locked vs. additive:** Changes to the 13 stage modules require Constitution-Principle-I justification. New API/behavior belongs in additive-layer modules (`api.py`, `fort14.py`, `loaders.py`, etc.), strictly composing stage modules, never reverse.

---

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

**Domain Loading (v0.2+):**
```python
from admesh import triangulate

# File-based domain loading (TOML, JSON, or fort.14)
mesh = triangulate("domain.toml", h0=0.1)
mesh = triangulate("domain.json", h0=0.1)
mesh = triangulate("existing_mesh.14", h0=0.1)  # Extract boundary

# Registry integration
from admesh import load_domain_from_registry
mesh = triangulate("noaa-hsofs-v20", h0=0.1)  # Auto-detects registry
```

**Migration from v0.1:** `domain_from_polygon()` and `domain_from_sdf()` were removed. Save domains to TOML/JSON and load via file path, or construct a `Domain` dataclass directly. See `docs/DOMAIN_IO.md` for full API and format specs.

---

## Conventions

### MATLAB → Python naming
- `CreateBackgroundGrid.m` → `create_background_grid()` in module `admesh/background_grid.py`
- Private helpers keep MATLAB name in snake_case; prefix with `_` if module-private

### Indexing
- **MATLAB 1-based → Python 0-based.** Subtract 1 wherever MATLAB source indexes arrays.
- **MATLAB `end` → Python `-1` or `len(x) - 1`**
- **MATLAB `x(i:j)` (inclusive) → Python `x[i-1:j]` (half-open)**

### Common substitutions
| MATLAB | Python |
|--------|--------|
| `inpolygon(xq, yq, xv, yv)` | `admesh.in_polygon.in_polygon(xq, yq, xv, yv)` |
| `delaunay(x, y)` | `scipy.spatial.Delaunay(np.c_[x, y]).simplices` |
| `griddata(...)` | `scipy.interpolate.griddata(...)` |
| `bwdist(...)` | `scipy.ndimage.distance_transform_edt(...)` |
| `struct(...)` | `dataclasses.dataclass` or dict (pick per-module) |
| cell array of varying-length vectors | `list[np.ndarray]` |

Document each non-obvious substitution in `docs/PORTING_NOTES.md` with a one-line note on any behavior difference (closed-vs-open boundary, tie-breaking, ordering).

### Docstring template
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

### Numba conventions
`admesh/mesh_size.py` houses the iterative PDE solver ported from `MeshSizeIterativeSolver.c`. Maintain two implementations in-module:

1. `_solve_iter_py(...)` — pure NumPy, readable reference.
2. `_solve_iter_nb(...)` — `@njit(cache=True)`, optimized.

Tests assert they agree to `atol=1e-10` on fixed input. Public `solve_iter(...)` dispatches to the Numba path by default, with `use_numba=False` kwarg for debugging.

---

## Testing

- **One test file per stage:** `tests/test_<stage>.py` (e.g., `test_distance.py` for stage 03).
- **Fixtures:** `.npz` files under `tests/fixtures/<stage>/<case>.npz` with named arrays for inputs + expected outputs (captured from MATLAB).
- **Load pattern:**
  ```python
  data = np.load("tests/fixtures/distance/square.npz")
  out = admesh.distance.signed_distance(data["x"], data["y"], data["poly"])
  np.testing.assert_allclose(out, data["expected"], atol=1e-8, rtol=1e-6)
  ```
- **Default tolerances:** `atol=1e-8, rtol=1e-6` (override in docstring if needed).
- **Fixture size:** Keep `.npz` files small (<1 MB per file) to maintain lightweight repo.

### Binding vs. advisory checks
- **Structural validity (binding):** positive-area triangles, points inside domain, watertight boundary. This is the gate.
- **Quality gate (advisory, not binding):** The default `quality_gate=(0.30, 0.60)` kwarg (min_q ≥ 0.30, mean_q ≥ 0.60) is an MVP port-sanity smoke target, **not a hard requirement** (per Constitution Article V.5, #140). Quality is controlled via `hmin`/`hmax`/`g` size-field knobs; override `quality_gate=(0.0, 0.0)` when design legitimately lowers minimum quality.

---

## Branch & commit policy

See **Constitution Article VI** for binding rules; this is the operational summary.

- **Default to `main`.** Don't create branches for one-off edits.
- **Speckit-driven branching:** New feature branches come from `/speckit-specify` (fires `before_specify` git hook). **Do not run `git checkout -b` directly.** Branch names: `NNN-<short-name>` (sequential) per `.specify/init-options.json`.
- **Scan before creating:** Before invoking `/speckit-specify`, run `git branch -a` to check for existing branches covering the same feature. Reuse rather than create parallel branches.
- **Single-purpose PRs:** Each PR addresses one logical change. Merge to `main` via PR (never direct push). Squash or rebase merge (not plain merge) and delete the branch after.
- **Commit format:** `<type>: <imperative summary>`, where `<type>` ∈ {fix, feat, docs, chore, refactor, test}. No `wip`, `fixup!`, `squash!`, `tmp`, `test commit` prefixes on main-bound PRs.
- **Hard stops:**
  - No force-push to `main` or shared branches.
  - No direct push to `main` — PR review + CI required.
  - No secrets (`.env`, `*token*`, etc.) in commits.

---

## Edit hygiene

The number of tokens used to edit files is best minimized, all else being equal. Therefore, when it will not affect the end result, opt first for surgical edits rather than rewriting entire existing files.

**Stream timeout prevention:**
1. Each numbered task ONE AT A TIME. Complete fully, confirm, next.
2. Never write file >~150 lines in single tool call. Multi-pass append/edit if longer.
3. Fresh session if conversation reaches 20+ tool calls. Error worsens with session size.
4. Keep grep/search outputs short. Use flags like `--include`, `-l` (list files only) to limit output size.
5. On timeout, retry with a shorter form. Don't repeat entire task from scratch.

---

## Related repositories

| Path / URL | What it is |
|---|---|
| `/workspace/QuADMesh-MATLAB` | MATLAB source (read-only reference clone, branch `main`, source tree: `01_ADMESH_Library/`) |
| `/workspace/MADMESHR` | RL-based mesh generator (tri/quad/mixed, advancing-front + SAC). MVP/PoC, not on PyPI. Long-term positioning vs. ADMESH undecided. Faithful-port boundary still applies — MADMESHR concepts must not bleed into locked stage modules. |
| [`domattioli/CHILmesh`](https://github.com/domattioli/CHILmesh) | Python mesh data structure + smoother (tri/quad/mixed, PyPI: `chilmesh`). Composes downstream of ADMESH. Boundary in [`docs/adr/ADR-001-chilmesh-boundary.md`](docs/adr/ADR-001-chilmesh-boundary.md) (spec 015). Not a faithful-port concern; references in docs only. |
| [`domattioli/ADMESH-Domains`](https://github.com/domattioli/ADMESH-Domains) | Federated registry of ADCIRC-compatible meshes. Split out of this repo on 2026-04-26. |
| [`domattioli/DomI`](https://github.com/domattioli/DomI) | Upstream skill provider. Foundational skills (`github-release`, `pypi-publish`, `api-key-rotation`, `send-email`, `act-autonomously`, `speckit-*`) sourced via `sync-from-domi`. |

---

## Reference docs

- **Constitution & project plan:** `docs/governance/CONSTITUTION.md` (hard rules, principles, session cadence) and `docs/governance/PROJECT_PLAN.md` (roadmap, current phase, "where we are today").
- **PORTING_NOTES.md:** Running log of MATLAB → Python substitutions and behavior differences.
- **DOMAIN_IO.md:** Complete domain file format specification (TOML, JSON, fort.14).
- **Session notes:** `docs/sessions/session-NNN.md` per-session handoff (decisions, files touched, next steps).
- **Architecture Decision Records:** `docs/adr/` (e.g., `ADR-001-chilmesh-boundary.md`).

### Specs
**Active feature specs** (read each spec's `spec.md` + `plan.md` before touching its modules):
- **`001-pythonize-and-fort14-integration` (SHIPPED):** Pythonic API (`Domain`, `Mesh`, `triangulate()`) + ADCIRC fort.14 round-trip I/O. Now public contract.
- **`002-size-field-defaults` (IN-FLIGHT):** Wire MATLAB-faithful size-field stack (curvature → medial-axis → bathymetry → tide, min-stacked) as Phase-1 default; extend fort.14 with IBTYPE 3/4/13/24 BC records. Originally 0.1.0 blocker (gated on issue #10, now closed; 0.1.0 shipped).
- **`004-quad-prep-smoother` (IN-FLIGHT):** `smooth_for_quadrangulation()` nudges triangles toward right-isoceles for downstream tri→quad fusion.
- **`005-adcirc-mesh-registry` (IN-FLIGHT):** Federated mesh registry (TOML manifests, HF mirror, slug + SHA-256 IDs). ADMESH-Domains upstream catalog; this spec wires registry lookup into `triangulate()`.

All specs live under `.specify/specs/NNN-feature-name/` with: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `tasks.md`.

### Repo-local labels (issue #87 triage)
These labels have no DomI canonical equivalent and are intentionally repo-local:

| Label | Meaning |
|-------|---------|
| `numerics` | Faithful-port numerical-identity / size-field math concerns |
| `performance` | Runtime / benchmark / optimization work |
| `roadmap` | Strategic / milestone-tracking issues |
| `domi-sync` | DomI upstream sync chores (`chore: sync DomI@<sha>`) |
| `post-0.1.0` / `post-v1` | Deferred past the 0.1.0 / 1.0 milestones |
| `io` | fort.14 / Gmsh / format-bridge I/O |
| `gpu` | GPU / parallel-acceleration investigations |
| `integration` | Cross-stage / cross-repo integration work |
| `pypi` | PyPI packaging / distribution |

(Note: The non-canon `tests` label was deleted in #87 sweep; use the canonical `scope: testing` instead.)
