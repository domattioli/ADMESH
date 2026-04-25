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

_(none yet — populated by T026)_

### `community/`

_(none yet — populated by T027)_

### `malformed/`

_(none yet — populated by T025; hand-crafted in this repo, no external
provenance required)_
