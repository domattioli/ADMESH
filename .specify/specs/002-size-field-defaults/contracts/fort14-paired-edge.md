# Contract: fort.14 Reader/Writer — Paired-Edge BC Records (IBTYPE 3, 4, 13, 24)

**Spec**: [../spec.md](../spec.md) · **Plan**: [../plan.md](../plan.md)
**Surface**: `admesh.fort14.read_fort14`, `admesh.fort14.write_fort14`
**Audience**: implementers of the spec-002 fort.14 extensions

The spec-001 fort.14 reader treats every land-boundary node line as a single integer ID. ADCIRC v55 land-boundary types 3 / 4 / 13 / 24 / 25 are **paired-edge** or **single-edge-with-payload** records — each line carries 4–5 numeric tokens. This contract specifies how the spec-002 reader/writer extends to handle them while preserving 100% backward-compat with spec-001's spec-supported codes (0, 1, 11, 20).

---

## ADCIRC v55 grammar reference

Per the ADCIRC user manual (v55), the land-boundary block has this structure:

```
NBOU                                      ! number of land boundary segments
NVEL                                      ! total nodes (single-node) or pairs (paired-edge)
for each land segment:
    NVELL  IBTYPE                         ! segment header: count, code
    if IBTYPE in {0, 1, 2, 11, 12, 13?, 21, 22}:   ! single-node land (no barrier payload)
        repeat NVELL times: ID            ! one integer per line
    if IBTYPE in {3, 13, 23}:             ! external barrier — single node + crest data
        repeat NVELL times: ID  HBAR  COEF_SUB  COEF_SUPER
    if IBTYPE in {4, 14, 24, 25}:         ! internal/external paired-edge barrier
        repeat NVELL times: ID  ID_PAIRED  HBAR  COEF_SUB  COEF_SUPER
```

The "paired-edge" identifier is BOTH the IBTYPE code AND a count interpretation: for IBTYPE 24, `NVELL` counts node *pairs*, and each line emits 5 tokens. For IBTYPE 0, `NVELL` counts single nodes, each line emits 1 token (the node ID).

ADCIRC distinguishes them by code; some implementations (and the `wetting_and_drying_test.14` fixture in particular) annotate the segment header with explanatory text — `"= Number of node pairs for weir (land boundary 7)"` — which the reader can use as a sanity check but MUST NOT depend on for grammar.

---

## Reader contract

`admesh.fort14.read_fort14(path)` MUST handle the v55 grammar exactly:

```python
def _read_land_segment(cursor: _Cursor, n_nodes: int) -> BoundarySegment:
    seg_line = cursor.next_line("land-segment 'NVELL IBTYPE' line")
    seg_tokens = seg_line.split()
    nvell = int(seg_tokens[0])
    ibtype = int(seg_tokens[1])

    if ibtype in _SINGLE_NODE_LAND_IBTYPES:
        # IBTYPE 0, 1, 11, 20, 21, 22 — single-node, no payload
        node_ids = _read_single_node_records(cursor, nvell)
        return BoundarySegment(
            node_ids=node_ids,
            bc_type=_coerce_bc(ibtype),
            is_open=False,
        )

    elif ibtype in _SINGLE_NODE_BARRIER_IBTYPES:
        # IBTYPE 3, 13, 23 — single-node + crest + 2 coeffs (3 floats)
        node_ids, barrier = _read_single_node_barrier_records(cursor, nvell, n_cols=3)
        return BoundarySegment(
            node_ids=node_ids,
            bc_type=_coerce_bc(ibtype),
            is_open=False,
            barrier_data=barrier,
        )

    elif ibtype in _PAIRED_NODE_BARRIER_IBTYPES:
        # IBTYPE 4, 14, 24, 25 — paired-node + crest + coeffs (3 floats)
        node_ids, paired, barrier = _read_paired_node_barrier_records(cursor, nvell, n_cols=3)
        return BoundarySegment(
            node_ids=node_ids,
            bc_type=_coerce_bc(ibtype),
            is_open=False,
            paired_node_ids=paired,
            barrier_data=barrier,
        )

    else:
        # Unknown IBTYPE — fall back to single-node parsing for backward compat
        # with spec-001's "preserve unknown codes as int" policy. Log via
        # PORTING_NOTES if encountered in real fixtures.
        node_ids = _read_single_node_records(cursor, nvell)
        return BoundarySegment(
            node_ids=node_ids,
            bc_type=ibtype,  # plain int, not enum
            is_open=False,
        )
```

**Constants** (defined in `admesh/fort14.py` module-level):

```python
_SINGLE_NODE_LAND_IBTYPES = frozenset({0, 1, 2, 11, 12, 21, 22})
_SINGLE_NODE_BARRIER_IBTYPES = frozenset({3, 13, 23})    # 3 columns: hbar, coef_sub, coef_super
_PAIRED_NODE_BARRIER_IBTYPES = frozenset({4, 14, 24, 25})  # 3 columns + paired ID
```

Note: IBTYPE 13 is documented as `INTERNAL_BARRIER_PIPE` in our enum (single-node barrier with pipe coefficients), but ADCIRC v55 allows pipe-internal-barrier in paired-node form too. The fixture-driven implementation: if `wetting_and_drying_test.14` uses IBTYPE 13 in single-node form, it joins `_SINGLE_NODE_BARRIER_IBTYPES`. If it appears in paired-node form in any future fixture, we move it. The frozenset definitions are tunable — what's NOT tunable is the grammar pattern (1, 4, or 5 tokens per record line).

**Token-count discrimination** (defensive fallback): if the IBTYPE is unknown but the first record line has exactly 4 or 5 tokens with the trailing 3 being floats, treat it as a barrier record and parse accordingly. This is a soft heuristic — log via `PORTING_NOTES.md` when triggered.

**Index conversion**: 1-based on disk → 0-based in memory, applied to BOTH `node_ids` AND `paired_node_ids` (per spec-001's existing 1↔0 conversion isolation).

**Validation**:
- All node IDs (single + paired) MUST be in `[1, n_nodes]` on disk; raise `Fort14ParseError` otherwise.
- `barrier_data` floats are parsed via `_parse_float` with the existing error-context machinery from spec 001.

---

## Writer contract

`admesh.fort14.write_fort14(mesh, path)` MUST emit grammatically-correct records for the new BC types:

```python
def _write_land_segment(seg: BoundarySegment, file, n_nodes: int) -> None:
    nvell = len(seg.node_ids)
    ibtype = int(seg.bc_type)
    file.write(f"{nvell} {ibtype} = Number of nodes for land boundary ...\n")

    if seg.barrier_data is None:
        # Single-node, no payload (spec-001 path)
        for nid in seg.node_ids:
            file.write(f"{nid + 1}\n")  # 0-based → 1-based on disk

    elif seg.paired_node_ids is None:
        # Single-node + crest (IBTYPE 3, 13, 23)
        for i, nid in enumerate(seg.node_ids):
            cols = " ".join(f"{x:.3f}" for x in seg.barrier_data[i])
            file.write(f"{nid + 1} {cols}\n")

    else:
        # Paired-node + crest (IBTYPE 4, 14, 24, 25)
        for i, (nid, pid) in enumerate(zip(seg.node_ids, seg.paired_node_ids)):
            cols = " ".join(f"{x:.3f}" for x in seg.barrier_data[i])
            file.write(f"{nid + 1} {pid + 1} {cols}\n")
```

**Float formatting**: `%.3f` for crest elevations (consistent with the `wetting_and_drying_test.14` fixture's formatting) and coefficients. If round-trip fidelity requires more precision (TBD during testing), bump to `%.6f`.

---

## Round-trip fidelity contract

For every fixture in the test ladder:

```python
def test_fort14_round_trip(fixture_path):
    mesh1 = read_fort14(fixture_path)
    write_fort14(mesh1, tmp_path)
    mesh2 = read_fort14(tmp_path)
    assert mesh1.equals(mesh2, atol=1e-3)   # 1mm tolerance for crest elevations
```

`Mesh.equals` is extended (per [data-model.md](../data-model.md)) to compare `paired_node_ids` (exact int) and `barrier_data` (`atol`/`rtol`-aware float).

`atol=1e-3` reflects the `%.3f` writer formatting; if precision tightens to `%.6f`, `atol` tightens to `1e-6`.

---

## Error contract — `Fort14ParseError` extensions

The existing `Fort14ParseError(line_no, expected, actual)` from spec 001 carries enough information to debug malformed paired-edge records. New error situations:

| Failure | `expected` text | Triggered when |
|---|---|---|
| Wrong token count for IBTYPE 24 segment record | `"node-pair record (5 tokens: nid pid hbar c_sub c_super)"` | record line has fewer than 5 tokens |
| Non-numeric crest elevation | `"float crest_elev"` | `barrier_data` token fails float parse |
| Paired node ID out of range | `f"paired node id in [1, {n_nodes}]"` | `id_paired` outside valid range |
| Unknown IBTYPE with paired-edge-shaped data | (warning, not error) | falls back to single-node parsing; logs to `docs/PORTING_NOTES.md` |

---

## Fixture coverage

The two new test modules MUST cover:

| Test | Fixture | Asserts |
|---|---|---|
| `test_fort14_paired_round_trip[example10n]` | `wetting_and_drying_test.14` | full round-trip; 9 land segments preserved with correct IBTYPE codes; all `barrier_data` floats match within `atol=1e-3` |
| `test_fort14_ibtype_3_external_weir` | unit test | synthetic single-segment mesh with IBTYPE 3 records; round-trip exact |
| `test_fort14_ibtype_24_internal_barrier` | unit test | synthetic single-segment mesh with IBTYPE 24 records; round-trip exact, paired IDs preserved |
| `test_fort14_unknown_ibtype_falls_back` | unit test | IBTYPE 99 with single-node records → `bc_type` is `int(99)`, parses OK |
| `test_fort14_malformed_paired_record` | malformed fixture | IBTYPE 24 record with 3 tokens → raises `Fort14ParseError` with line number + expected |

All five MUST pass before the spec-002 implementation phase is "done" per the constitution's stage-completion definition.
