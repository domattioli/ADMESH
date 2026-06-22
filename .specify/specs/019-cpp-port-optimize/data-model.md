# Phase 1 Data Model: Full C++ Rewrite of ADMESH

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-05-25

Entities are the native C++ types that are the source of truth; the Python
dataclasses become thin views over them via pybind11. Field names mirror the
existing frozen Python dataclasses so the binding is a 1:1 facade (FR-002).

## Domain

Native input description meshed by `triangulate`.

| Field | C++ type | Notes |
|---|---|---|
| `vertices` | `Eigen::MatrixX2d` (N×2) | boundary polygon vertices, row-major at I/O boundary |
| `segments` | `Eigen::MatrixX2i` | edge connectivity (boundary loops) |
| `boundaries` | `std::vector<BoundarySegment>` | typed boundary loops |
| `bbox` | `std::array<double,4>` | xmin,xmax,ymin,ymax |
| `sdf` | `std::function<...>` or callback handle | optional signed-distance fn; may bridge to a Python callable (R6) |
| `bathymetry` | `std::optional<Eigen::VectorXd>` | per-vertex depth, optional |

**Source**: file (fort.14 / JSON / TOML) or in-memory construction. US1 requires
file-based construction with **no Python** (edge case + FR-001).

## Mesh

Output of the pipeline; mirrors the frozen Python `Mesh` dataclass.

| Field | C++ type | Python view |
|---|---|---|
| `nodes` | `Eigen::MatrixX2d` (N×2) | `nodes: np.ndarray` |
| `elements` | `Eigen::MatrixX3i` (T×3) | `elements: np.ndarray` |
| `boundaries` | `std::vector<BoundarySegment>` | `boundaries: tuple[BoundarySegment,...]` |
| `bathymetry` | `std::optional<Eigen::VectorXd>` | `bathymetry: np.ndarray \| None` |
| `quality` | `Eigen::VectorXd` (T) | `quality: np.ndarray` |

**Invariant**: zero-copy where possible — pybind11 exposes Eigen buffers to
NumPy without copying (raw-buffer access from PR #103). Mesh is immutable once
returned (matches frozen dataclass).

## BoundarySegment

| Field | C++ type | Notes |
|---|---|---|
| `node_indices` | `Eigen::VectorXi` | 0-based (Art II.3); converted at fort.14 I/O |
| `bc_type` | `int` | ADCIRC IBTYPE code |
| `btype` | `BoundaryType` enum | mapped names; unmapped codes preserve as raw int |

**BoundaryType** (IntEnum mirror): `OPEN=0`, `MAINLAND=1`, `ISLAND=11`,
`MAINLAND_FLUX=20`; paired-edge/weir `3/4/13/24` preserved (FR-008).

## CppStage

The unit of the port. Not a runtime object — an organizing contract.

| Attribute | Value |
|---|---|
| `name` | one of the 13 stage names |
| `parity_mode` | `bit_parity` \| `relaxed` (R8 table) |
| `tolerance` | `atol=1e-8` (bit) or documented per-stage value (relaxed) |
| `fixture` | `tests/fixtures/<stage>/*.npz` (authoritative oracle) |
| `fallback` | the matching `admesh/_stages/<stage>.py` Numba impl (permanent, FR-004) |

**State transition** (per stage during execution):
`unported (Python only)` → `ported, parity-pending` → `ported, parity-green`.
A stage is "done" only at parity-green (US3). Mid-port, both C++ and Python
outputs are checked against the same fixture (US3 scenario 2).

## Backend (selector state)

| Field | Values | Source |
|---|---|---|
| `mode` | `cpp` \| `python` \| `auto` | kwarg > env `ADMESH_BACKEND` > auto (R5) |
| `cpp_available` | bool | true iff `_distmesh_cpp`/native module imported |

**Rule**: `mode=cpp` with `cpp_available=false` → raise (no silent fallback);
`mode=auto` → cpp if available else python.

## Parity Fixture

Captured MATLAB input/expected `.npz`, one per stage/case. Load-only, immutable
oracle (Constitution Art V.2). Regenerated only on MATLAB source-commit pin
change. Both the C++ stage and the Numba fallback assert against the same file.

## Build Artifact

| Artifact | Produced by | Consumer |
|---|---|---|
| `libadmesh` (static/shared) + headers | standalone CMake | native C++ app (US1) |
| platform wheel (`.whl`) | scikit-build-core + cibuildwheel | PyPI / `pip install` (US2/US4) |
| sdist (`.tar.gz`) | scikit-build-core | source install; soft-degrades to Numba (R4) |
