# `fort.14` cheat sheet

Quick reference for ADCIRC's `fort.14` mesh format. The authoritative
parsing contract for ADMESH lives at
[`specs/002-size-field-defaults/contracts/fort14-paired-edge.md`](https://github.com/domattioli/ADMESH/blob/main/specs/002-size-field-defaults/contracts/fort14-paired-edge.md).
The official ADCIRC docs are at
<https://adcirc.org/home/documentation/users-manual-v53/input-file-descriptions/adcirc-grid-and-boundary-information-file-fort-14/>.

For the conceptual primer (what these BC categories *mean*), see
[Concepts](Concepts.md) §5.

## Layout

```
AGRID                              ! mesh title
NE  NN                             ! n_elements  n_nodes
JN  X(JN) Y(JN) DP(JN)             ! NN node records: id  x  y  depth
JE  NHY  NM(1) NM(2) NM(3)         ! NE element records: id  3  n0 n1 n2 (1-based)
NOPE                               ! number of open-ocean boundary segments
NETA                               ! total number of open-ocean boundary nodes
... open-ocean records ...
NBOU                               ! number of land/normal-flow boundary segments
NVEL                               ! total number of land boundary nodes
... land records (vary by IBTYPE) ...
```

ADMESH's reader is in
[`admesh/fort14.py`](https://github.com/domattioli/ADMESH/blob/main/admesh/fort14.py).
Indices in the file are **1-based**; ADMESH stores them **0-based**
internally (subtracts 1 on read, adds 1 on write — see
[Concepts](Concepts.md) §7).

## IBTYPE codes (land boundary section)

| IBTYPE | Meaning | Per-node fields | ADMESH support |
|---|---|---|---|
| 0 | mainland (no normal flow) | `node_id` | ✅ |
| 1 | island (no normal flow, closed loop) | `node_id` | ✅ |
| 2 | external barrier with prescribed flux | `node_id` | ✅ (read-through) |
| **3** | **outer barrier (weir, paired-edge)** | `node_id  BARLANHT  BARLANCFSP` | ✅ spec-002 |
| **4** | **internal barrier (weir, paired)** | `node1 node2  BARINHT  BARINCFSB  BARINCFSP` | ✅ spec-002 |
| 10 | mainland (with rad-stress) | `node_id` | ✅ (read-through) |
| 11 | island (with rad-stress) | `node_id` | ✅ (read-through) |
| 12 | external barrier (with rad-stress) | `node_id` | ✅ (read-through) |
| **13** | **outer barrier with rad-stress (paired)** | as IBTYPE 3 | ✅ spec-002 |
| **20** | culvert (paired) | as IBTYPE 4 | ⚠️ partial |
| **24** | **internal barrier + culvert (paired)** | `node1 node2  BARINHT  BARINCFSB  BARINCFSP  PIPEHT  PIPECOEF  PIPEDIAM` | ✅ spec-002 |

The **bolded** entries are paired-edge records — each line ties two
nodes together as the two sides of a hydraulic structure (weir,
levee, culvert). spec-002 added explicit support for these in the
reader / writer round-trip; see issue
[#10](https://github.com/domattioli/ADMESH/issues/10) for the
release-gate context.

## What a paired-edge record looks like

For an internal barrier (IBTYPE 4 or 24), the BC file groups two
parallel rows of boundary nodes — one row per side of the structure
— and each line of the record lists **both** node IDs:

```
flow direction →                                         flow direction →
   north of barrier  ←─────────────────────────────────  ●        ←──┐
                                                         ▲           │ N
                                                         │           │ O
                                              ┌──────────┘           │ D
                                              │                      │ E
   ▼ vertical                                 │                       │
       barrier  ████  ████  ████  ████  ████  ████  ████  ████        │
       height                                   │                     │
                                              ┌─┘                     │
                                              │                       │
                                                         ▼            │
   south of barrier  ←─────────────────────────────────  ●        ←──┘

   IBTYPE 4 record (one paired edge per line):
     node1   node2   BARINHT   BARINCFSB   BARINCFSP
       12      18      4.5       1.05         0.45
       13      19      4.5       1.05         0.45
       14      20      4.5       1.05         0.45
                                                ⤷  same hydraulic
                                                   structure, three
                                                   paired edges
```

A reader that splits per-node (assuming one node ID per line) silently
drops half the pairing and corrupts the BC structure. ADMESH parses
paired-edge records column-aware via `Mesh.boundary_segments[*].barrier_data`.

## Round-tripping in ADMESH

```python
import admesh

mesh = admesh.read_fort14("input.14")
mesh.to_fort14("output.14")

# Idempotent: round-tripping a Mesh through fort.14 is exact.
assert mesh.equals(admesh.read_fort14("output.14"))
```

## Reference fixtures

| Fixture | Tier | Location | Use |
|---|---|---|---|
| `tests/fixtures/fort14/synthetic/*` | 0 | this repo | unit tests, every PR |
| `wetting_and_drying_test.14` | 1 | [ADMESH-Domains](https://github.com/domattioli/ADMESH-Domains) registry | small ADCIRC sample |
| `wnat_test.14` | 2 | [ADMESH-Domains](https://github.com/domattioli/ADMESH-Domains) registry | Western North Atlantic (0.1.0 release gate) |

Tier-1 and Tier-2 fixtures have moved to the
[ADMESH-Domains](https://github.com/domattioli/ADMESH-Domains)
sibling registry — pull them via the `admesh-domains` package rather
than vendoring locally.

## Common gotchas

- **1-based vs 0-based**: file is 1-based; in-memory ADMESH `Mesh` is
  0-based. Don't mix them.
- **NHY is always 3** in v52 grid format (triangles only). Quad
  meshes use a different file format and are not in scope for v1.
- **Paired-edge records list TWO node ids per line** (IBTYPE 4, 13,
  24). A reader that assumes one-id-per-line silently drops half the
  pairing.
- **BARLANHT depths are negative-down** to match ADCIRC's depth
  convention (positive = below datum).
- **Inline `=` comments** are sometimes present on segment header
  lines. ADMESH's parser tolerates them (added in spec-002 to handle
  `wetting_and_drying_test.14`).
