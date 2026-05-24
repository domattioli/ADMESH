# ADMESH Performance Optimization Milestone

## Goal

Optimize the ADMESH 2D unstructured-mesh generation pipeline for speed and
memory, using the **best-fit language and data structures per hotspot**,
benchmarked end-to-end on the **Western North Atlantic ~3M-node domain
("wnat-admesh-3m")** as the realistic reference workload.

## Context

ADMESH (`admesh2D`) is a Python/NumPy/Numba faithful port of the MATLAB
`01_ADMESH_Library`. v0.2.1 shipped: Pythonic API, fort.14 round-trip,
13-stage faithful pipeline, valence balancing, custom size-field hooks.

The faithful-port phase is COMPLETE. Per the project Constitution
(`docs/governance/CONSTITUTION.md`), optimization is now sanctioned.

## Hard constraints (Constitution Article II — non-negotiable)

1. **Numerical fidelity preserved.** Every optimization must keep outputs
   bit-for-bit faithful to MATLAB within documented tolerance
   (`atol=1e-8, rtol=1e-6`). The 250+ reference test suite must stay green.
   No optimization may change generated meshes.
2. **Language escalation is gated, not free.** Default backend stays
   NumPy + Numba. A faster language (Cython / C / Rust) is permitted ONLY
   for a hotspot where profiling shows Numba underperforms by >2x on a
   realistic domain, AND each escalation ships with a written justification.
3. **`pip install` without a C toolchain stays possible.** The north star is
   a toolchain-free install. Any compiled extension must be optional /
   gracefully degrade to a pure-Python+Numba path, OR ship as prebuilt
   wheels — never become a mandatory build-from-source dependency.
4. **0-based indexing, row-major NumPy internals** unchanged.

## Scope

- Build a reproducible benchmark harness around the wnat-admesh-3m domain
  (and 1-2 smaller domains for fast iteration) measuring per-stage and
  end-to-end wall-clock + peak memory.
- Profile the 13-stage pipeline; rank hotspots by share of runtime/memory.
- For each top hotspot: choose the best-fit data structure (e.g. spatial
  indexing, sparse vs dense, contiguous layouts) and, where Article II
  rule 2 is satisfied, the best-fit language. Implement, re-benchmark,
  verify fidelity.
- Regression guard: benchmark + fidelity tests wired into CI.

## Out of scope

- Algorithmic changes that alter mesh output.
- 3D / anisotropic / non-triangular meshing.
- Mandatory C-toolchain installs.

## Success criteria

- Documented, reproducible speedup on wnat-admesh-3m (target: meaningful
  end-to-end reduction, with per-stage attribution).
- All reference fidelity tests still pass.
- Any language escalation carries profiling evidence (>2x) + justification.
- Default `pip install admesh2D` still works with no C toolchain.
