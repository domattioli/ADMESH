# Spec 023 — GitHub Pages Interactive Demo (#118)

## 1. Summary

Extend the existing MkDocs Material site at `https://domattioli.github.io/ADMESH/` with an
interactive demo page: select or upload a fort.14 domain, configure minimal hyperparameters,
run ADMESH in-browser (Pyodide WASM), watch the truss-solver iterate frame-by-frame, and
download the result as fort.14. Citations block present on every page. "Quick and dirty, keep
it simple but pretty" — two-phase delivery separates the static-animation MVP (no blockers)
from the full Pyodide-compute path (two blocking sub-issues).

**Issue**: #118  
**Profile**: planning — spec only, no code ships this PR  
**Priority**: high / roadmap

---

## 2. Context

### 2.1 Existing infrastructure

| Asset | State |
|-------|-------|
| MkDocs Material site | Live at `domattioli.github.io/ADMESH/` |
| Deploy workflow | `.github/workflows/docs.yml` — `mkdocs gh-deploy` on push to `daily-issue-fixing` / `main` |
| Python package | `admesh2D` on PyPI, version 0.2.1 |
| Runtime deps | `numpy>=1.24`, `scipy>=1.11`, `numba>=0.58`, `shapely>=2.0` |
| Citation file | `CITATION.cff` — paper DOI + Zenodo DOI already recorded |

### 2.2 Citations (from `CITATION.cff`)

Algorithm paper:
> Conroy, C. J., Kubatko, E. J., & West, D. W. (2012). ADMESH: an advanced, automatic
> unstructured mesh generator for shallow water models. *Ocean Dynamics*, 62(10), 1503–1517.
> https://doi.org/10.1007/s10236-012-0574-0

Software archive:
> Mattioli, D. et al. ADMESH (Python port). Zenodo.
> https://doi.org/10.5281/zenodo.20264101

---

## 3. Requirements

### 3.1 Functional

| ID | Requirement |
|----|-------------|
| FR-001 | User selects from ≥3 bundled default fort.14 domains (sourced from test fixtures or MVP benchmark suite) |
| FR-002 | User uploads a custom fort.14 file (≤5 MB, client-side size check before Pyodide loads) |
| FR-003 | Minimal hyperparameter controls: `h0` (float input), size-field preset (dropdown: constant / curvature), `max_iter` (int slider 5–200) |
| FR-004 | "Compute" button triggers ADMESH pipeline; page remains responsive (Pyodide web worker) |
| FR-005 | Per-iteration truss-solver frames (node positions, triangulation, mean quality) stream to animation panel via `postMessage`; pause/resume scrubber |
| FR-006 | Final mesh quality histogram rendered inline (Plotly-lite or Canvas2D) |
| FR-007 | "Download fort.14" button exports computed mesh |
| FR-008 | Citations block on demo page: paper DOI + Zenodo DOI, both hyperlinked |
| FR-009 | Page responsive at ≥375 px viewport |

### 3.2 Non-functional

| ID | Requirement |
|----|-------------|
| NFR-001 | Purely static: deployed to `gh-pages` via `mkdocs gh-deploy`, no server |
| NFR-002 | Pyodide bundle + admesh wheel ≤60 MB gzip; cold-start progress indicator visible |
| NFR-003 | Demo accessible at `https://domattioli.github.io/ADMESH/demo/` |
| NFR-004 | Tested in Chrome 120+, Firefox 120+, Safari 17+ |

---

## 4. Architecture

### 4.1 Hosting

MkDocs Material handles all static pages. The demo page lives at
`docs/demo/index.html` as a raw HTML override (MkDocs supports `!` nav entries for
raw files, or place it under `docs/overrides/`). Add nav entry:

```yaml
nav:
  - ...
  - Demo: demo/index.html
```

CI (`docs.yml`) continues to build + deploy via `mkdocs gh-deploy`; a new step before
`mkdocs build` regenerates pre-baked frame data (Phase 1).

### 4.2 Compute — Pyodide (Phase 2)

Pyodide 0.27 runs Python 3.12 in a WASM sandbox. `numpy`, `scipy`, `shapely` have
pre-compiled Pyodide wheels; `numba` does **not** (JIT compilation unavailable in WASM).

**Primary blocker — numba**: `admesh` calls `@numba.jit`-decorated functions in the
hot path. Pyodide path requires a `ADMESH_NO_NUMBA=1` / `use_numba=False` fallback
that substitutes pure-numpy equivalents. This must be landed as a separate issue before
Phase 2 begins.

Data flow:

```
[JS FileReader]
      │  ArrayBuffer (fort.14 bytes)
      ▼
[Pyodide Web Worker]
  io.BytesIO → admesh.io.read_fort14()
  admesh.triangulate(domain, h0=h0, fh=fh, max_iter=max_iter, record_iters=True)
      │  yields IterFrame(p, t, q_mean) per distmesh2d_admesh iteration
      ▼
[postMessage → main thread]
  Canvas2D triangle renderer + quality chart update
      │
      ▼
[Download button]
  admesh.io.write_fort14(mesh) → bytes → Blob → <a> click
```

### 4.3 Pre-baked animation (Phase 1, no blockers)

CI runs ADMESH on 3 default domains (e.g., unit square, annulus, WNAT excerpt), serializes
per-iteration frames to `docs/demo/data/{domain}.jsonl`:

```json
{"iter": 0, "p": [[x,y],...], "t": [[a,b,c],...], "q_mean": 0.71}
{"iter": 1, "p": [[x,y],...], "t": [[a,b,c],...], "q_mean": 0.74}
...
```

Static page loads `.jsonl` via `fetch`, replays animation client-side. No Python in browser.
Requires the `record_iters=True` kwarg on `distmesh2d_admesh` (blocking sub-issue, see §6).

### 4.4 Visualization stack

- **Triangle mesh**: Canvas2D `fillPath` per triangle, coloured by quality (blue=low, green=high). Zero JS dependencies.
- **Animation scrubber**: `<input type="range">` + `requestAnimationFrame` loop.
- **Quality histogram**: Plotly.js `bar` trace loaded from CDN (≈3 MB, cached). Fallback: Canvas2D mini-bars if CDN fails.
- **Styling**: inherit MkDocs Material CSS palette (CSS custom properties `--md-primary-fg-color` etc.) for visual consistency.

---

## 5. Risks

| # | Risk | Severity | Mitigation |
|---|------|----------|------------|
| R-01 | `numba` unavailable in Pyodide | High | Gate Phase 2 on numba-optional sub-issue (§6.1) |
| R-02 | `record_iters` kwarg not implemented | High | Gate Phase 1 data gen on sub-issue (§6.2); Phase 1 ships after that issue closes |
| R-03 | Pyodide cold-start >15s on slow connections | Med | Show progress bar; offer pre-baked demo as fallback during load; `localStorage` cache |
| R-04 | fort.14 parse speed in WASM | Med | Parse in worker; 5 MB upload cap; warn user before compute |
| R-05 | `shapely` WASM wheels missing or broken | Low | Verify against Pyodide 0.27 package index; shapely 2.x uses pre-compiled GEOS |
| R-06 | `docs.yml` deploys from `daily-issue-fixing` not `daily-maintenance` | Low | Demo data gen step added to `docs.yml`; frame data committed to repo for Phase 1 |
| R-07 | MkDocs strict mode rejects raw HTML page | Low | Use `docs_dir` override or `!` prefix in nav; MkDocs Material supports this |

---

## 6. Blocking Sub-Issues to File

Before implementation, open two issues:

### 6.1 `numba-optional path` (blocks Phase 2)

> **Title**: `[feat] ADMESH_NO_NUMBA=1 env flag — pure-numpy fallback for numba-jit functions`
>
> ADMESH uses `@numba.jit` decorators for performance. Pyodide (WASM) cannot JIT-compile
> Python. Add `ADMESH_NO_NUMBA=1` env var (or `use_numba=False` kwarg on `triangulate()`)
> that wraps numba-decorated functions in a plain Python fallback. Acceptance: full test
> suite passes with `ADMESH_NO_NUMBA=1`; Pyodide sandbox can `import admesh` and run
> `triangulate()` on a unit-square domain.

### 6.2 `record_iters` kwarg (blocks Phase 1 CI data generation)

> **Title**: `[feat] record_iters=True on distmesh2d_admesh — serialize per-iteration frames`
>
> Add `record_iters: bool = False` to `distmesh2d_admesh` (`distmesh.py:638`). When true,
> accumulate `IterFrame(iter=int, p=ndarray, t=ndarray, q_mean=float)` per outer iteration.
> Return as second element of a tuple: `(p, t, frames)`. Acceptance: frame list grows
> monotonically; `q_mean` matches `_element_quality_mean` output.

---

## 7. Implementation Plan

### Phase 1 — static pre-baked demos

1. Land sub-issue 6.2 (`record_iters`).
2. Add CI step to `docs.yml`:
   - `pip install -e ".[dev]"` (already present)
   - Run ADMESH on 3 default domains with `record_iters=True`; write `docs/demo/data/`
3. Build `docs/demo/index.html`:
   - Domain selector dropdown (3 options)
   - Canvas2D renderer + scrubber
   - Citations block (both DOIs)
4. Add `demo/index.html` to MkDocs nav.
5. Deploy; verify at `domattioli.github.io/ADMESH/demo/`.

### Phase 2 — Pyodide interactive compute

Prerequisites: sub-issues 6.1 (numba-optional) + 6.2 (record_iters) both closed.

1. Add Pyodide 0.27 worker script (`docs/demo/worker.js`).
2. Wire upload button → FileReader → worker; display progress.
3. Hyperparameter form (h0, preset, max_iter) → `triangulate()` call in worker.
4. `postMessage` frame stream → existing Canvas2D renderer.
5. Download button — Blob from worker output.
6. Graceful error + Binder/Colab fallback if Pyodide fails to load.

---

## 8. Acceptance Criteria

| # | Criterion | Phase |
|---|-----------|-------|
| AC-001 | Three default-domain animations play at `domattioli.github.io/ADMESH/demo/` in Chrome + Firefox | 1 |
| AC-002 | Citations block present; both DOIs hyperlink correctly | 1 |
| AC-003 | CI regenerates frame data on every deploy trigger | 1 |
| AC-004 | Page layout valid at 375 px and 1440 px viewports | 1 |
| AC-005 | User can upload fort.14, press Compute, view animation, download result in ≤60s for ≤2000-node meshes | 2 |
| AC-006 | Pyodide load failure shows graceful message + Binder/Colab link | 2 |
| AC-007 | `ADMESH_NO_NUMBA=1` passes full test suite | 2 (prereq) |

---

*Spec 023 — created 2026-05-31*
