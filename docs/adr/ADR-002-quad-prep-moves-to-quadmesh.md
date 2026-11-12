# ADR-002: quad preparation moves to QuADMESH

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-11 |
| Supersedes | ADR-001 disposition of `admesh.quad_prep`; ADR-001 issue #41 lines |
| Superseded work | ADMESH issue #236, PR #237 |

## Context

`admesh.quad_prep` (`smooth_for_quadrangulation`) and the unreleased `admesh.quad_layers` prototype both output triangles. Their only purpose is to prepare triangles for tri-to-quad fusion. ADR-001 kept `quad_prep` in ADMESH as a gift to downstream consumers.

The operator ruled on 2026-11-11 that anything that exists only to serve quad fusion lives in QuADMESH.

## Decision

QuADMESH owns quad preparation: `quadmesh.quad_prep` and `quadmesh.quad_layers`. ADMESH owns triangle generation for triangle consumers. `admesh.quality.right_iso_quality` and `admesh.valence` stay in ADMESH.

## Consequences

- Breaking removal of `admesh.quad_prep` and `admesh.quad_layers`. No deprecation shim.
- The removal ships in a minor release by operator decision, and 2.0 is reserved for a later release.
- Migration: `from quadmesh.quad_prep import smooth_for_quadrangulation`.
- QuADMESH does not depend on ADMESH.
- ADMESH issue #236 and PR #237 are superseded.
