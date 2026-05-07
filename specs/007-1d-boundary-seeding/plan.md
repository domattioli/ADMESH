# Implementation Plan: 1D Boundary Seeding for Domain Path

**Branch**: `daily-issue-fixing` | **Date**: 2026-05-07 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/007-1d-boundary-seeding/spec.md`

## Summary

Short boundary segments in polygonal domains (e.g. the 0.1-wide notch floor in
`NOTCHED_RECTANGLE`) receive too few boundary nodes from the interior lattice
alone. This feature adds a `boundary_polygon` optional field to `Domain` and a
`_seed_boundary_1d()` helper that subdivides each polygon edge at `fh`-evaluated
spacing, prepending those seeds to `pfix` so distmesh2d treats them as fixed.
MATLAB reference: `createInitialPointList.m` @ 19b2eb9 seeds the PTS path this
way; we adapt the same logic for the canonical Domain path.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: NumPy (already in project); no new deps
**Storage**: N/A
**Testing**: pytest
**Target Platform**: Any platform where admesh runs
**Project Type**: Library
**Performance Goals**: `_seed_boundary_1d` < 10 ms for a 100-vertex polygon at h0=0.01
**Constraints**: Pure Python/NumPy only (Constitution Principle II)
**Scale/Scope**: Affects `Domain` + `routine.py`; minimal surface area

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Faithful Port Before Optimization | PASS | Mirrors createInitialPointList.m intent for Domain path |
| II. Pure-Python First | PASS | Only NumPy; no C/Cython/MEX |
| III. Reference-Test Discipline | PASS | Automated test asserts node count on notch walls |
| IV. Stage-by-Stage Bottom-Up | PASS | Adds one helper; does not rewrite existing stages |
| V. Report-and-Advance Cadence | PASS | Planning then implementation |

**GATE: All gates pass. Proceeding.**

## Project Structure

```text
admesh/
├── domains.py           <- add boundary_polygon field to Domain
└── routine.py           <- add _seed_boundary_1d(); update triangulate()

tests/
└── test_routine.py      <- notch-wall node-count assertions
```

## Complexity Tracking

No constitution violations. No special justification required.
