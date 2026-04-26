# Registry Test Fixtures

Golden-file fixtures for schema validation, query testing, and integration tests.

## Structure

- `simple.toml` — minimal 2-entry manifest for basic validation tests
- `with_lineage.toml` — parent+child+grandchild meshes with provenance history
- `with_deprecation.toml` — includes deprecated/tombstoned mesh entries
- `expected/` — expected query results (JSON fixtures for integration tests)

## Usage

Load fixtures in tests:

```python
import tomllib
data = tomllib.load(open("tests/fixtures/registry/simple.toml", "rb"))
manifest = Manifest(**data)
```

## Adding New Fixtures

1. Create a representative TOML manifest
2. Write it to `tests/fixtures/registry/<name>.toml`
3. If testing query results, create `tests/fixtures/registry/expected/<name>_results.json`
4. Document the fixture's purpose in this README
