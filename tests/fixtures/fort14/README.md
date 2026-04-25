# fort.14 test fixtures

This directory holds ADCIRC fort.14 mesh files used by the
`tests/test_fort14_*.py` suites. Three subdirectories, three roles.

## Layout

| Directory | Purpose | Min files | Size budget (combined) |
|-----------|---------|----------:|-----------------------:|
| `adcirc_examples/` | Public ADCIRC documentation example meshes (e.g. Shinnecock Inlet). Source of truth for the v55 grammar. | 2 | 500 KB |
| `community/` | Real-world ADCIRC meshes from public sources. Excerpts allowed when full meshes exceed budget. | 3 | 1 MB |
| `malformed/` | Hand-crafted negative-test inputs. Each file violates exactly one grammar rule. | 10 | 100 KB |

Total directory budget: **< 2 MB** combined. Reject contributions that
push past it; trim or excerpt instead.

## Rules for adding fixtures

1. **Plain text only.** No binary, no compressed archives. fort.14 is
   ASCII; the suite parses files as text.
2. **No PII or proprietary geometry.** Only public-domain or
   permissively-licensed meshes. Document provenance below for every
   non-trivial file.
3. **Excerpts must round-trip structurally.** If you trim a community
   mesh to fit the budget, the trimmed file must still parse and
   round-trip via `read_fort14` → `write_fort14`.
4. **`malformed/` files violate exactly one rule each.** The negative
   tests parametrize over them; one-rule-per-file keeps failures
   diagnosable.

## Provenance

Add an entry under the appropriate heading whenever you check in a new
fixture.

### `adcirc_examples/`

- **`wnat_test.14`** (1.2 MB, 9,934 nodes / 18,578 elements) —
  Western North Atlantic test domain. Bbox roughly
  `(-97.85°W, 8.00°N) → (-60.04°W, 45.77°N)`, bathymetry
  0.1 m → 7,572 m (positive-down on disk; positive-up in `Mesh`).
  Single outer-ring boundary, no declared open/land segments.
  Originally derived from Hagen et al.'s WNAT meshes; this is the
  small (~10K-node) variant redistributed widely with ADMESH and
  ADCIRC tutorials. Public domain. Used by
  `tests/test_fort14_reference_corpus.py` and the
  `scripts/wnat_demo.py` end-to-end demo.

  **Known data limitation — Bermuda is absent.** Despite the bbox
  covering Bermuda's location (-64.78°W, 32.30°N), this small
  variant carries no topological boundary in that region: 134 nodes
  lie within 1.5° of Bermuda but none participate in a one-triangle
  edge, and bathymetry there is uniformly 488–4811 m deep. The mesh
  smooths over the Bermuda platform entirely. Verify with::

      python scripts/diagnose_wnat_bermuda.py

  See issue #12 for the investigation. A higher-resolution upstream
  WNAT (HSOFS, EC2015, or the QuADMesh-MATLAB reference fixture)
  is required to round-trip Bermuda as a hole. To produce a slim
  budget-friendly fixture from any such upstream::

      python scripts/extract_boundary_only_fort14.py upstream.14 \
          tests/fixtures/fort14/community/wnat_islands.14

### `community/`

_(none yet — populated by T027)_

### `malformed/`

Ten hand-crafted negative-test fixtures, each violating exactly one
fort.14 grammar rule. Source: hand-authored in this repo by T025; no
external provenance required.

- `element_node_out_of_range.14` — element references vertex id beyond NN
- `invalid_nodes_per_element.14` — element line declares 4 nodes (not 3)
- `missing_open_boundary_block.14` — file ends after the element block
- `negative_node_count.14` — counts line has negative NN
- `non_integer_node_id.14` — node id token is `2.5`
- `non_monotonic_node_ids.14` — second node has id 5 instead of 2
- `non_numeric_coordinate.14` — alphabetic where float expected
- `truncated_element_block.14` — declared NE=2 but only 1 element line
- `wrong_node_count_too_many.14` — declared NN=5 but only 4 nodes follow
- `wrong_segment_node_count.14` — segment declares 4 nodes, only 2 follow
