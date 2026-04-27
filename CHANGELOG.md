# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-04-27

### Added
- Issue #10 fix: Robust polygon SDF with winding-number testing for multiply-connected domains
- Convergence detection in distmesh to prevent hanging on pathological size fields
- GitHub release skill with automatic credential and metadata detection
- PyPI publish skill with retry logic and verification
- Comprehensive diagnostic infrastructure for mesh generation issues
- Support for real-world ADCIRC coastal mesh fixtures (Tier-1, Tier-2)

### Fixed
- Domain.from_mesh() SDF construction for accurate boundary distance computation
- Distmesh oscillation and timeout issues through stagnant iteration detection
- Size-field stack domain overshoot on multiply-connected domains

### Documentation
- Complete specification for issue #10 fix
- Implementation plan and 28-task decomposition
- Diagnostic harness and profiler modules
- Release automation guides

### Technical Details
- Replaced bbox-based SDF heuristic with proper winding-number algorithm
- Added convergence detection with 20-iteration stagnation threshold
- Automated release workflow with non-interactive skill implementations
