# Spec 011 — Atomic tasks

| # | Task | Files | Depends on | Acceptance |
|---|---|---|---|---|
| T011-1 | Author render script skeleton + rcParams pin | `scripts/render_annulus_animation.py` (new) | — | File loads, runs `--help` |
| T011-2 | Implement `IterationSweepCapture` w/ frame dedupe | `scripts/render_annulus_animation.py` | T011-1 | `.frames` non-empty, monotone in `n_pts` |
| T011-3 | Implement `render_frame(ax, p, t, k, ...)` | `scripts/render_annulus_animation.py` | T011-1 | Single-frame manual call renders w/o error |
| T011-4 | Wire `PillowWriter` GIF encoder + post-optimization | `scripts/render_annulus_animation.py` | T011-2, T011-3 | `papers/annulus_meshing.gif` created |
| T011-5 | Wire `FFMpegWriter` MP4 encoder with graceful skip | `scripts/render_annulus_animation.py` | T011-2, T011-3 | MP4 written when ffmpeg present; warning otherwise |
| T011-6 | Add README "Meshing in action" subsection | `README.md` | T011-4 | GIF embed lands after Quickstart code block |
| T011-7 | Verify GIF size ≤ 60 KB; tune CAPS if needed | `scripts/render_annulus_animation.py`, `papers/annulus_meshing.gif` | T011-4 | `ls -lh` ≤ 60 KB |
| T011-8 | Verify README renders on GitHub (post-push) | — | T011-6 | Visual confirmation in PR preview |
| T011-9 | Add a docs-test (optional) that asserts artifact present + non-empty | `tests/test_docs_assets.py` (new, tiny) | T011-4 | `pytest tests/test_docs_assets.py` exit 0 |

## Cross-repo integration points

- **None.** Pure ADMESH-internal. No MADMESHR/CHILMESH/admesh-domains
  coupling. The script consumes the public `admesh.triangulate` API
  and the bundled `domains.ANNULUS`.

## Task-to-acceptance-criteria mapping

| Acceptance criterion (issue #70) | Tasks |
|---|---|
| 10–20 s video illustrating annulus meshing | T011-1..T011-4 |
| Embed into README | T011-6 |
| Reproducible artifact | T011-1, T011-7 |

## Phase boundaries

- **Tasks T011-1..T011-9** are all implementation-phase work. This
  spec ships **planning artifacts** in the current run (per CORE
  MANDATE). The implementation tasks live as a follow-up "implement
  spec 011" comment on issue #70 and execute in a subsequent session
  on the same `daily-issue-fixing` branch.
- T011-9 is optional — the script being checked in is itself the
  guard against artifact drift; a unit test that asserts the GIF
  exists is belt-and-braces.
