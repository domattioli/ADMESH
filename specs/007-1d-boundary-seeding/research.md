# Research: 1D Boundary Seeding

**Feature**: 007-1d-boundary-seeding
**Date**: 2026-05-07

## Decision 1: Seeding Algorithm

**Decision**: Uniform subdivision at `fh`-evaluated midpoint spacing.

**Rationale**: The PTS path in `distmesh2d_admesh` uses the ring vertices
directly. For the Domain path, subdividing each polygon edge into
`floor(edge_length / local_h)` equal intervals and placing seeds at interior
intervals achieves the same coverage guarantee.

**Alternatives considered**:
- Full 1D truss-force solver: better for strongly graded fh but much more complex; deferred.
- Short-edge threshold hack: rejected (magic-number, degrades adjacent long edges).

## Decision 2: Where `_seed_boundary_1d` lives

**Decision**: In `admesh/routine.py` as a module-private helper.

**Rationale**: Consumed only by `triangulate()`. distmesh.py is a faithful-port zone.

## Decision 3: `boundary_polygon` field placement

**Decision**: Optional `NDArray | None` field on `Domain` dataclass (default `None`).

**Rationale**: Follows the same pattern as `fixed_points`. `None` preserves backward compat.

## Decision 4: Seed spacing formula

**Decision**: `n_segs = int(edge_len / local_h)`. Seeds at `t = k/n_segs` for k=1..n_segs-1.

## Decision 5: `fh` signature

**Decision**: Call `fh(midpoint.reshape(1,2))[0]`. Fall back to `h0` if NaN or <=0.

## MATLAB Reference

`createInitialPointList.m` @ 19b2eb9: PTS path seeds boundary nodes from pre-sampled
ring vertices. This feature brings the same guarantee to the Domain path.

## Unknowns Resolved

No unresolved questions.
