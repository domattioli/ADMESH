# Issue #5 Task Breakdown: Gmsh .msh I/O Integration (Feature 003)

**Issue**: #5  
**Status**: Planning phase  
**Spec**: docs/planning/SPEC_005_GMSH_IO.md  
**Acceptance**: Feature 003 shipping with v1.1 or post-v1.0 release  

---

## Atomic Task List (in implementation order)

### Task 1: Create `admesh/gmsh.py` — File I/O module
**Objective**: Implement hand-parsed Gmsh v2.2 reader and writer  
**Acceptance**: Module is importable; `read_msh` and `write_msh` functions exist and pass basic tests  
**Depends on**: None  
**Owner**: Implementation phase  
**Effort**: 200 lines (~1.5 hours)  
**File**: `admesh/gmsh.py`

**Checklist**:
- [ ] `GmshParseError` exception class defined
- [ ] `_DEFAULT_PHYSICAL_GROUPS: dict[str, BoundaryType]` mapping table (see spec)
- [ ] `read_msh(path, physical_group_map=None) → Mesh` function
  - [ ] Tokenize input file
  - [ ] Parse `$PhysicalNames` section → dict[int, str]
  - [ ] Parse `$Nodes` section → dict[int, (x, y, z)]
  - [ ] Parse `$Elements` section → list[(type, nodes, phys_group)]
  - [ ] Filter for `type=2` (triangles) on boundary tags
  - [ ] Construct `Mesh` + `BoundarySegment` list
  - [ ] Handle malformed input gracefully (raise `GmshParseError`)
- [ ] `write_msh(mesh: Mesh, path: str | Path) → None` function
  - [ ] Emit `$MeshFormat` (v2.2)
  - [ ] Emit `$PhysicalNames` from `mesh.boundaries` BoundaryTypes
  - [ ] Emit `$Nodes` from `mesh.nodes`
  - [ ] Emit `$Elements` from `mesh.elements`
  - [ ] Assign correct type markers (2 = triangle)
  - [ ] Assign physical group tags correctly
- [ ] Helper functions: `_parse_msh2_nodes`, `_parse_msh2_elements`, `_parse_msh2_physical_names`
- [ ] Inline comments (minimal, WHY-focused)
- [ ] Docstrings (at module & function level; one-line per function)

---

### Task 2: Create test fixtures
**Objective**: Hand-write minimal `.msh` files for testing  
**Acceptance**: Fixtures are valid Gmsh v2.2 files; Gmsh can open them without errors  
**Depends on**: None (can run in parallel with Task 1)  
**Owner**: Implementation phase  
**Effort**: 30 minutes  
**Files**: `tests/fixtures/gmsh/*.msh`

**Checklist**:
- [ ] `square.msh` — minimal unit square (4 nodes, 2 triangles, 1 boundary group)
- [ ] `l_shape.msh` — L-shaped domain with 2 boundary groups
- [ ] `u_shape.msh` — U-shaped domain (or substitute with second fixture)
- [ ] All fixtures use v2.2 format; hand-written for clarity
- [ ] Each fixture includes `$PhysicalNames` with descriptive names (e.g., "open", "mainland")
- [ ] Gmsh 4.1+ can parse each file without warnings (manual validation or CI check)

---

### Task 3: Create integration tests
**Objective**: Test `read_msh` and `write_msh` functions  
**Acceptance**: All tests pass; round-trip Gmsh → admesh → Gmsh preserves fidelity  
**Depends on**: Tasks 1 & 2  
**Owner**: Implementation phase  
**Effort**: 250 lines (~2 hours)  
**File**: `tests/test_gmsh_io.py`

**Checklist**:
- [ ] `test_read_msh_v2_basic` — read `square.msh`, assert `n_nodes == 4, n_elements == 2`
- [ ] `test_read_msh_physical_names` — read fixture, assert boundary types are mapped correctly
- [ ] `test_read_msh_unmapped_physical_groups` — numeric tags → int (no crash, just log warning)
- [ ] `test_write_msh_basic` — create minimal Mesh, write to `.msh`, re-read, assert consistency
- [ ] `test_gmsh_roundtrip_square` — read square.msh → write → read again, assert bitwise identical
- [ ] `test_gmsh_roundtrip_l_shape` — same for L-shaped fixture
- [ ] `test_gmsh_physical_groups_to_boundary_types` — assert all BoundaryTypes have Gmsh mappings
- [ ] `test_gmsh_boundary_labels_survive_roundtrip` — Gmsh → admesh → Gmsh, boundary names preserved
- [ ] `test_gmsh_fort14_roundtrip` — Gmsh → admesh → fort.14 → admesh → Gmsh, labels survive
- [ ] `test_gmsh_io_with_mvp_domains` — read/write all 5 MVP domains (square, L, U, hole, doughnut)
- [ ] `test_gmsh_parse_error_on_malformed` — feed invalid input, expect `GmshParseError`
- [ ] All tests use fixtures from `tests/fixtures/gmsh/`

---

### Task 4: Update `admesh/api.py` — Add convenience method
**Objective**: Add `Mesh.to_msh(path)` method  
**Acceptance**: Method exists; delegates to `write_msh`  
**Depends on**: Task 1  
**Owner**: Implementation phase  
**Effort**: 5 lines  
**File**: `admesh/api.py`

**Checklist**:
- [ ] Add method to `Mesh` dataclass:
  ```python
  def to_msh(self, path: str | Path) -> None:
      """Export mesh to Gmsh ASCII v2.2 format."""
      from admesh.gmsh import write_msh
      write_msh(self, path)
  ```
- [ ] Docstring is one-liner
- [ ] No additional validation (delegate to `write_msh`)

---

### Task 5: Update `admesh/__init__.py` — Re-export
**Objective**: Make Gmsh functions part of public API  
**Acceptance**: `admesh.read_msh`, `admesh.write_msh`, `admesh.GmshParseError` are importable  
**Depends on**: Task 1  
**Owner**: Implementation phase  
**Effort**: 5 lines  
**File**: `admesh/__init__.py`

**Checklist**:
- [ ] Add to `__all__`:
  ```python
  from .gmsh import read_msh, write_msh, GmshParseError
  ```
- [ ] Verify imports appear in `__all__` list
- [ ] No circular imports

---

### Task 6: Create design documentation
**Objective**: Document physical-group mapping, format rationale, limitations  
**Acceptance**: `docs/GMSH_IO_DESIGN.md` is created; design decisions are explained  
**Depends on**: None (can run in parallel)  
**Owner**: Planning phase (completed as part of spec)  
**Effort**: Already completed in SPEC_005_GMSH_IO.md  
**File**: `docs/planning/SPEC_005_GMSH_IO.md`

**Checklist**:
- [ ] Mapping table is clear (physical group name → BoundaryType)
- [ ] Format version choice (v2.2) is justified
- [ ] Known limitations are documented
- [ ] Out-of-scope items are listed (3D, quads, gmsh API)

---

### Task 7: Update documentation
**Objective**: Update existing docs with Gmsh references  
**Acceptance**: `PORTING_NOTES.md`, `CHANGELOG.md`, and API docs reference Gmsh  
**Depends on**: Tasks 1–4  
**Owner**: Implementation phase  
**Effort**: 30 minutes  
**Files**: `docs/PORTING_NOTES.md`, `CHANGELOG.md`, README.md (if exists)

**Checklist**:
- [ ] `PORTING_NOTES.md`: Add section on Gmsh format design decisions
  - [ ] Note: v2.2 (not v4.x) to avoid external dependency
  - [ ] Note: Physical-group → BoundaryType mapping table
  - [ ] Note: Known limitations (2D only, triangles only)
- [ ] `CHANGELOG.md`: Add entry for Feature 003 (when released)
  - [ ] "Add Feature 003: Gmsh .msh I/O integration. Read/write Gmsh ASCII v2.2 format. (Issue #5)"
- [ ] API docstring in `admesh/__init__.py`: mention `read_msh`, `write_msh` alongside `read_fort14`, `write_fort14`
- [ ] Code examples in docstring (optional, but nice-to-have)

---

### Task 8: Regression testing
**Objective**: Ensure fort.14 I/O still works; no breakage  
**Acceptance**: All existing fort.14 tests pass  
**Depends on**: Tasks 1–5  
**Owner**: Implementation phase  
**Effort**: 5 minutes (just run existing tests)  
**Command**: `pytest tests/test_fort14_io.py -v`

**Checklist**:
- [ ] All fort.14 I/O tests pass
- [ ] No new warnings or deprecations
- [ ] Performance unchanged (compare against baseline if profiled)

---

### Task 9: Integration test: round-trip across all domains
**Objective**: Verify Gmsh ↔ fort.14 round-trip on MVP and real fixtures  
**Acceptance**: All domains survive Gmsh → admesh → fort.14 → admesh → Gmsh  
**Depends on**: Tasks 1–7  
**Owner**: Implementation phase  
**Effort**: 20 minutes (just run tests)  
**Command**: `pytest tests/test_gmsh_io.py::test_gmsh_fort14_roundtrip -v`

**Checklist**:
- [ ] Test runs on 5 MVP domains + any available real fixtures
- [ ] Mesh node/element counts are preserved
- [ ] Boundary labels survive both translations
- [ ] No NaN or Inf values in coordinates

---

### Task 10: Cleanup & merge
**Objective**: Finalize code, commit, push to `daily-issue-fixing` branch  
**Acceptance**: All commits are on `daily-issue-fixing`; PR is ready  
**Depends on**: All tasks 1–9  
**Owner**: Implementation phase  
**Effort**: 15 minutes  

**Checklist**:
- [ ] All code formatted (black, isort, if applicable)
- [ ] All tests pass locally: `pytest tests/test_gmsh_io.py tests/test_fort14_io.py -v`
- [ ] Type hints are present (if codebase uses them)
- [ ] Docstrings are one-liners (no multi-line docstrings)
- [ ] Commits are atomic:
  - Commit 1: admesh/gmsh.py + tests + fixtures
  - Commit 2: admesh/api.py + admesh/__init__.py
  - Commit 3: docs/ updates
- [ ] Commit messages reference issue #5: `Resolve #5: Implement Gmsh I/O (Feature 003)`
- [ ] Push to origin/daily-issue-fixing
- [ ] Create PR (draft) if one doesn't exist

---

## Dependency Graph

```
Task 1: gmsh.py  → (depends on nothing)
Task 2: fixtures → (parallel with Task 1)
Task 3: tests    → depends on Tasks 1 & 2
Task 4: api.py   → depends on Task 1
Task 5: __init__ → depends on Task 1
Task 6: docs     → (parallel with Tasks 1–5; already done in spec)
Task 7: update   → depends on Tasks 1–4
Task 8: regress  → depends on Tasks 1–5
Task 9: round-tn → depends on Tasks 1–8
Task 10: merge   → depends on Tasks 1–9
```

**Critical path**: 1 → 3 → 9 → 10 (~6 hours total, mostly implementation)

---

## Estimation

| Phase | Tasks | Est. Time | Buffer |
|---|---|---|---|
| Planning | 1 (spec) | 1 hour | Done |
| Implementation | 2–5 | 2 hours | +30 min |
| Testing | 3, 8, 9 | 1.5 hours | +30 min |
| Docs & Cleanup | 6, 7, 10 | 1 hour | +15 min |
| **Total** | **All** | **~5.5 hours** | **+1.5 hours** |

**Ideal: 6–7 hours for full implementation + testing**

---

## Out of Scope (for v1.0)

- Gmsh Python API integration (if needed, Feature 004)
- v4.x format support (too complex without upstream package)
- 3D or mixed-dimensionality meshes
- Quad elements
- Named physical-group overrides (API hook reserved for future)
