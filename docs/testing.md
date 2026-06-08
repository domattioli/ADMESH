# Testing

See **[TESTING.md](https://github.com/domattioli/ADMESH/blob/development/TESTING.md)**
at the repository root for the full testing guide.

## Quick reference

```bash
# Standard CI lane (matches .github/workflows/tests.yml)
pytest -m "not slow" -q

# Full suite (matches .github/workflows/tests-slow.yml)
pytest -q

# Coverage
pytest --cov=admesh --cov-report=term-missing
```

## Markers

| Marker             | Meaning                                                    |
|--------------------|------------------------------------------------------------|
| `slow`             | Tests requiring real coastal fixtures or long wall-clock   |
| `requires_matlab`  | Tests requiring MATLAB-derived `.npz` fixtures             |
| `requires_chilmesh`| Tests requiring `chilmesh` Python package                  |

`slow` is the only formal pytest marker (declared in `pyproject.toml`).
The others are conventional names used by `skipif` / `importorskip` patterns.
