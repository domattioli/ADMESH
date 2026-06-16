# Spec 011 — Annulus meshing animation for README

**Status**: Planning
**Tracks**: [#70](https://github.com/domattioli/ADMESH/issues/70)
**Branch**: `daily-maintenance` (no new branch — per CORE MANDATE)
**Severity**: medium · **Type**: documentation · **Scope**: docs + scripts

## 1. Problem statement

ADMESH's README currently shows only the Quickstart code snippet and a
single static figure (`papers/fig8_admesh_wnat.png`). New users have no
visual evidence of *how* the mesher works — the distmesh force-based
relaxation is the algorithmic core of the package and is much easier to
*see* than to read about.

Issue #70 asks for a 10–20 second video showing the meshing process on
an annulus domain (disk with a circular hole — a clean canonical
geometry that exercises both an outer boundary and an inner hole). The
video should embed in the README to give one-glance functional clarity.

## 2. Goals

1. Capture per-iteration node positions + triangulation from
   `distmesh2d` on the bundled `ANNULUS` domain.
2. Render those frames into a short, looped, web-friendly video
   (animated GIF for compatibility; MP4 as a higher-quality fallback).
3. Embed the animation in the README Quickstart section.
4. Make the render reproducible from a single script
   (`scripts/render_annulus_animation.py`) so the artifact can be
   regenerated as the algorithm evolves.
5. Do **not** add any new runtime dependency to the core package.
   Animation tooling (matplotlib `FuncAnimation`, `pillow` for GIF,
   optionally `ffmpeg` for MP4) is dev/docs-only.

## 3. Non-goals

- Adding a generic animation API to `admesh.viz`. The need today is
  one canonical artifact; a public `viz.animate(...)` surface is
  premature.
- Animations for the other four MVP domains (UNIT_DISK, UNIT_SQUARE,
  POLYGON_L, NACA0012). The annulus is the showcase because it has
  both an outer and an inner boundary; the others can follow under a
  separate spec if useful.
- Real-time / interactive viewers (Plotly, Bokeh). The artifact is a
  static, embeddable file.

## 4. Functional requirements

### FR-011-1 — Per-iteration frame capture

`admesh._stages.distmesh.distmesh2d` already exposes
`return_diagnostics=True` which records per-iteration *summary stats*
(`iter`, `n_pts`, `n_elements`, `max_disp`, `n_outside`) — see
`admesh/_stages/distmesh.py:218-226`. Animation needs the actual node
positions and the triangulation snapshot.

Two options. Spec mandates **Option A** (no upstream change):

- **Option A (chosen)**: The render script wraps `distmesh2d`
  indirectly. It calls into the public `admesh.triangulate(...)` once
  per "frame index" with a successively higher `max_iter` cap (e.g.
  `max_iter ∈ {1, 2, 4, 8, 16, 32, 64, ..., 200}`) using the same RNG
  seed, capturing the full `Mesh` at each cap. The seeded RNG path is
  deterministic — `admesh/_stages/distmesh.py:106-107` confirms
  `np.random.default_rng(seed)` controls the rejection step. The
  algorithm is monotone in `max_iter` so each capture is a valid
  snapshot of where the relaxation stood at iteration `k`. This costs
  ~`log N` runs but is zero-impact on the core code.
- **Option B (rejected for this spec)**: Add `return_frames=True` to
  `distmesh2d` returning a `list[tuple[np.ndarray, np.ndarray]]` of
  `(p, t)` snapshots. Cleaner, but invades the core path. Filed as a
  future spec when a second consumer needs it.

### FR-011-2 — Domain + parameters

The annulus is already defined: `admesh._stages.domains.ANNULUS`
(`fd=_sdf_annulus`, `bbox=(-1, -1, 1, 1)`, inner radius 0.4, outer 1.0)
— see `admesh/_stages/domains.py:60-117`. The render script uses:

```python
domain = admesh.domains.ANNULUS
mesh = admesh.triangulate(domain, h_max=0.12, max_iter=k, seed=0)
```

with `h_max=0.12` (matches `tests/test_api_triangulate.py:23` and
`scripts/render_mvp_meshes.py:35` — proven mesh density) and
`max_iter` swept across the geometric sequence above.

### FR-011-3 — Frame-rendering format

Each frame:

- Matplotlib `Figure` at 6×6 inch, 100 DPI (square canvas — annulus is
  symmetric).
- `ax.triplot(...)` for triangle edges, `lw=0.6`, color `#1f77b4`.
- `ax.plot(...)` for node positions, `'o'`, `ms=2.0`, color `#ff7f0e`.
- Outer boundary circle drawn at radius 1.0; inner hole at 0.4 (so
  the geometry is visible at frame 0 before any mesh forms).
- Per-frame title: `f"iter {k}, n_pts={mesh.nodes.shape[0]}, n_tri={mesh.elements.shape[0]}"`.
- `ax.set_xlim(-1.1, 1.1)`, `ax.set_ylim(-1.1, 1.1)`, `ax.set_aspect("equal")`.
- `ax.set_axis_off()` to keep visual focus on the mesh.

### FR-011-4 — Encoding

Two outputs, both committed:

1. **`papers/annulus_meshing.gif`** — 12 fps, 12–18 frames, looped,
   max 60 KB after optimization. Embeddable on GitHub README without
   any JS/MP4 hassle.
2. **`papers/annulus_meshing.mp4`** — same frames at 12 fps,
   H.264 encoded, ≤ 500 KB. Used by the documentation site when
   higher fidelity is needed.

Encoding via `matplotlib.animation.PillowWriter` for the GIF and
`matplotlib.animation.FFMpegWriter` for the MP4. If `ffmpeg` is not
available the MP4 step is skipped with a warning (GIF is the canonical
artifact).

### FR-011-5 — Script

New file: `scripts/render_annulus_animation.py`. Self-contained,
no new imports outside `admesh`, `numpy`, `matplotlib`. Top-of-file
docstring explains the iteration-sweep capture trick + dependency
expectations (`pip install matplotlib pillow`). Runs in well under one
minute on a developer laptop. Writes both outputs to `papers/`.

### FR-011-6 — README embed

Edit `README.md` to add a new subsection after the Quickstart code
block (current insertion target: between lines 83 and 85, immediately
after the `Mesh` dataclass description, before the "Round-trip"
subsection). Use GitHub's native image embed (the GIF) at 60% width:

```markdown
### Meshing in action

The annulus domain in motion — distmesh2d's force-balance relaxation
finds a high-quality unstructured mesh in ~200 iterations.

<img src="https://raw.githubusercontent.com/domattioli/ADMESH/main/papers/annulus_meshing.gif" alt="ADMESH annulus meshing animation" width="60%">
```

The raw URL points at `main` so the embed survives branch rebases.

## 5. Acceptance criteria

- [ ] `scripts/render_annulus_animation.py` exists, is self-contained,
      and runs to completion in ≤ 90 s on a developer laptop.
- [ ] `papers/annulus_meshing.gif` is committed, ≤ 60 KB, 12–18 frames,
      duration 1.0–1.5 s per loop (target the user's 10–20 s in
      *aggregate viewing time*, not per-loop duration).
- [ ] `papers/annulus_meshing.mp4` is committed (or, if `ffmpeg`
      unavailable in the build environment, the README falls back to
      GIF only — script logs the reason).
- [ ] README Quickstart section embeds the GIF at 60% width with alt
      text.
- [ ] No new entry in `[project.dependencies]`. New dev deps (`pillow`,
      `ffmpeg-python` if needed) go under `[project.optional-dependencies] viz`.
- [ ] `pre_tag_check.sh` (if it lints docs) still exits 0.

## 6. Architectural decisions

- **Iteration-sweep capture instead of distmesh API change.** Keeps
  the core algorithm untouched. Recapture cost is logarithmic and
  irrelevant for a one-shot artifact regeneration. The same trick
  generalizes to any other MVP domain without a code change.
- **GIF as canonical, MP4 as bonus.** GIF embeds frictionlessly on
  GitHub; MP4 is a quality upgrade for docs sites. Two-format outputs
  let the README work everywhere without script branching.
- **Annulus only.** Issue #70 names the annulus explicitly. A "render
  all five MVPs as an animation gallery" temptation is held back: it
  triples script complexity and dilutes the README's first-glance
  message. File as a separate enhancement if anyone wants it.
- **Seed=0, deterministic.** The capture relies on
  `np.random.default_rng(seed)` being stable; pin `seed=0` and assert
  the same seed across all captures. If the RNG path changes upstream,
  the artifact is regenerated rather than patched.

## 7. Risks

| Risk | Mitigation |
|---|---|
| `triangulate(..., max_iter=k)` early returns before reaching `k` (convergence) | Sweep stops at the convergence cap and pads the GIF tail with the converged frame |
| GIF size exceeds 60 KB | Reduce frames to 12; downsample to 5×5 inch; optimize with `pillow.Image.save(optimize=True)` |
| `ffmpeg` unavailable in CI | MP4 step is best-effort; GIF is the canonical embed |
| Matplotlib font/style drift between releases | Pin the script's `mpl.rcParams` defaults at the top |
| GitHub README image cache stale after push | Documented in script comment: use `?v=N` cache-buster on the embed URL when regenerating |

## 8. Token budget

**Small-to-medium.** One new script (~120 lines), one new GIF, one
new MP4, one README edit. Self-contained, no core-code touch. Not
decomposable beyond "ship GIF first, MP4 follow-up" — and that's not
a meaningful split.

## 9. Out of scope (explicit follow-ups)

- Animations for the other four MVP domains — separate issue if
  desired.
- Public `admesh.viz.animate(...)` surface — defer until a second
  consumer materializes.
- Native `distmesh2d` frame-capture (`return_frames=True`) — file as
  spec 012 when needed by a non-rendering consumer (e.g. a future
  debug tool).
- Interactive web embeds (Plotly / observable). Out of scope here.
