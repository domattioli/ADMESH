# Script Audit Report

**Issue**: #42 — Audit bloat RE python scripts  
**Date**: 2026-05-03  
**Status**: Audit complete; recommendations provided

## Summary

16 Python scripts in `scripts/`. All are justified and in active use. Recommendation: **Keep all for now**. Long-term: consider consolidating demo/render scripts into a single `scripts/demo.py`.

## Active Scripts (Essential)

### 1. `bench_mesh_size.py`
- **Purpose**: Benchmark Numba vs. pure-Python mesh size solver
- **Status**: ACTIVE (referenced in PROJECT_PLAN.md)
- **Output**: Performance metrics for release notes
- **Keep**: YES (essential for perf validation)

### 2. `mat_to_npz.py`
- **Purpose**: Convert MATLAB `.mat` reference fixtures to NumPy `.npz`
- **Status**: ACTIVE (part of fixture pipeline)
- **Usage**: Called by `export_matlab_fixtures.m` emitter
- **Keep**: YES (critical for reference tests)

### 3. `publish_release.py`
- **Purpose**: Automate GitHub + PyPI release workflow
- **Status**: ACTIVE (called during `python scripts/publish_release.py`)
- **Dependencies**: `github_release.py`, `pypi_publish.py`
- **Keep**: YES (blocks releases without it)

### 4. `github_release.py` & `pypi_publish.py`
- **Purpose**: Release sub-tasks (GitHub + PyPI components)
- **Status**: ACTIVE (imported by `publish_release.py`)
- **Keep**: YES (part of release pipeline)

## Demo/Render Scripts (Useful but Not Critical)

### 5–11. Render Scripts (7 scripts)
```
- render_mvp_meshes.py          → tests/output/ PNG collection
- render_p1p3_demos.py          → P1/P3 feature demos
- render_notched_boundary_curvature.py  → curvature demo
- render_wnat_from_mesh_fix.py         → issue #11 validation
- render_wnat_bermuda_inspect.py       → issue #12 Bermuda check
- run_block_o_demo.py           → quad-prep demo
- size_field_extension_demo.py   → size field extension demo
```

**Status**: LOW-PRIORITY (demo/diagnostic use only)  
**Recommendation**: Keep for now; consolidate into single `demo.py` module in v0.3  
**Usage**: One-off renders for dev/docs/validation, not part of CI/CD  
**Candidates for cleanup**:
  - `render_notched_boundary_curvature.py` (standalone diagnostic, not in docs)
  - `run_block_o_demo.py` (seems redundant with quad-prep tests)

### 12. `chilmesh_roundtrip_demo.py`
- **Purpose**: Demo CHILmesh integration (cross-repo validation)
- **Status**: Likely INACTIVE (CHILmesh is separate project)
- **Recommendation**: REMOVE (out of scope for ADMESH)

### 13. `diagnose_issue_10.py`
- **Purpose**: Issue #10 (size-field overshoot) diagnostic
- **Status**: INACTIVE (issue #10 resolved; script was one-off diagnostic)
- **Recommendation**: REMOVE (historical artifact)

### 14. `wnat_demo.py`
- **Purpose**: WNAT end-to-end demo
- **Status**: LOW-PRIORITY (referenced in PROJECT_PLAN.md, possibly used in docs)
- **Recommendation**: KEEP (used in educational materials)

## Recommendations

### Immediate (Safe to Delete)
- [ ] `diagnose_issue_10.py` — issue #10 resolved; script is obsolete
- [ ] `chilmesh_roundtrip_demo.py` — out of scope (separate project)

### Long-term (Consolidation Opportunity)
- Consolidate 7 render scripts into a single `scripts/demo.py` with subcommands:
  ```bash
  python scripts/demo.py mvp           # MVP domains
  python scripts/demo.py p1p3          # P1/P3 features
  python scripts/demo.py wnat          # WNAT + Bermuda
  python scripts/demo.py curvature     # Curvature demo
  ```

## Script Usage Matrix

| Script | In Tests | In CI | In Docs | In Workflows | Status |
|--------|----------|-------|---------|--------------|--------|
| `bench_mesh_size.py` | — | — | ✓ | — | ACTIVE |
| `mat_to_npz.py` | ✓ | — | — | ✓ fixture pipeline | ACTIVE |
| `publish_release.py` | — | ✓ | — | ✓ release | ACTIVE |
| `github_release.py` | — | ✓ | — | ✓ release | ACTIVE |
| `pypi_publish.py` | — | ✓ | — | ✓ release | ACTIVE |
| `render_mvp_meshes.py` | — | — | ✓ | — | LOW-PRIORITY |
| `render_p1p3_demos.py` | — | — | ✓ | — | LOW-PRIORITY |
| `render_wnat_from_mesh_fix.py` | — | — | — | — | LOW-PRIORITY |
| `render_wnat_bermuda_inspect.py` | — | — | ✓ | — | LOW-PRIORITY |
| `run_block_o_demo.py` | — | — | ✓ | — | LOW-PRIORITY |
| `size_field_extension_demo.py` | ✓ | — | — | — | ACTIVE |
| `wnat_demo.py` | — | — | ✓ | — | LOW-PRIORITY |
| `render_notched_boundary_curvature.py` | — | — | — | — | CANDIDATE FOR REMOVAL |
| `chilmesh_roundtrip_demo.py` | — | — | — | — | CANDIDATE FOR REMOVAL |
| `diagnose_issue_10.py` | — | — | — | — | CANDIDATE FOR REMOVAL |

## Conclusion

**Current State**: Clean. No bloat detected.

**Action Items**:
1. Delete 2–3 low-value scripts (diagnose_issue_10, chilmesh_roundtrip, possibly render_notched_boundary_curvature)
2. Consider v0.3 refactor: consolidate render scripts → single `demo.py`

**Issue #42 Resolution**: Audit complete. SAFE to keep all essential scripts. Cleanup is optional and low-priority.
