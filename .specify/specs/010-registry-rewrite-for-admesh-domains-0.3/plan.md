# Spec 010 — Implementation plan

## Phase order

The work is one logical change but is sequenced so each commit leaves
the tree green.

### Phase 1 — Optional dependency

1. Edit `pyproject.toml`: add
   ```toml
   [project.optional-dependencies]
   registry = ["huggingface_hub>=0.20"]
   ```
   under the existing `[project.optional-dependencies]` block (after
   `viz`, before any tooling extras).
2. No code change yet; verify `pip install -e .[registry]` resolves
   `huggingface_hub` without conflict.

### Phase 2 — Rewrite `admesh/registry.py`

1. Replace `load_domain_from_registry(mesh_id)` with
   `load_domain_from_registry(name, mesh_id="default@v1")`.
   - Lazy import `admesh_domains`.
   - Lazy import `admesh.fort14.read_fort14` and `admesh.api.Domain`
     inside the function body (avoids the existing module-load circular
     import risk; `admesh/__init__.py` already imports `registry`
     after `fort14` so this is belt-and-braces).
   - Map upstream `KeyError`/`AttributeError` to a clear `ValueError`.
   - Detect missing `huggingface_hub` before calling `Mesh.load()` and
     raise the install-hint `ImportError`.
2. Replace `list_available_domains()` body with the 0.3.x iteration
   pattern. Return `dict[str, str]` sorted by key.
3. Replace `load_domain_with_metadata(...)` with the resolution path
   from FR-010-3. Build the metadata dict from a curated list of
   attributes (skip-on-missing).
4. Keep `_convert_to_admesh_domain` untouched.
5. Update module docstring to reference the new contract.

### Phase 3 — Documentation

1. Edit `docs/ADMESH_DOMAINS_CONTRACT.md`:
   - Delete lines under `## Known drift (as of 2026-05-15)` through
     `behind a 'slow' marker since they hit the network).`
   - Insert a new `## Network fetch` section linking the `[registry]`
     extra to `Mesh.load()` and noting that the `slow` lane validates
     the end-to-end path.
   - Bump the trailing `## Contract validation` block to mention
     `test_end_to_end_load_domain_from_registry`.

### Phase 4 — Tests

1. `tests/test_registry.py`:
   - Add three new tests below the existing six. Use
     `@pytest.mark.slow` + `pytest.importorskip("huggingface_hub")` for
     network ones; the `list_available_domains` test is offline-safe.
2. `tests/test_admesh_domains_contract.py`:
   - Add `test_end_to_end_load_domain_from_registry` at the bottom
     with the same gating.
3. `pytest.ini` / `pyproject.toml` `[tool.pytest.ini_options]`:
   - Verify `slow` marker is already declared. If not, add to the
     `markers = [...]` list (see existing `markers` declaration; the
     spec-009 `slow` marker should already exist).

### Phase 5 — Verification

1. `pip install -e .[registry,dev]`.
2. `pytest tests/test_registry.py tests/test_admesh_domains_contract.py -v`.
3. `pytest tests/test_registry.py tests/test_admesh_domains_contract.py -v -m slow`.
4. `python -c "import admesh; d = admesh.load_domain_from_registry('BaranjaHill'); print(d.bbox)"`.
5. Full suite: `pytest -q` (offline lane only — the new slow tests are
   skipped without `-m slow`).

## File-by-file diff sketch

### `admesh/registry.py`

- Module docstring: bump version reference.
- `load_domain_from_registry`: signature gains `mesh_id="default@v1"`;
  body switches to top-level functions + `Mesh.load()`.
- `list_available_domains`: iterates `admesh_domains.list_domains()`,
  builds the dict via dict-comprehension over `.name` /
  `.full_name`/`.description`.
- `load_domain_with_metadata`: shares resolution helper with FR-010-1
  (extract a private `_resolve_mesh(name, mesh_id)` inside the module).
- `_convert_to_admesh_domain`: unchanged.

### `pyproject.toml`

```diff
 [project.optional-dependencies]
 dev = [...]
 viz = ["matplotlib>=3.7"]
+registry = ["huggingface_hub>=0.20"]
```

### `docs/ADMESH_DOMAINS_CONTRACT.md`

```diff
-## Known drift (as of 2026-05-15)
-
-**`admesh/registry.py` is broken against `admesh-domains` 0.3.x.** ...
-...behind a `slow` marker since they hit the network).
+## Network fetch
+
+`admesh_domains.Mesh.load()` downloads the underlying fort.14 from
+the upstream HuggingFace mirror. ADMESH treats this as opt-in:
+install with `pip install admesh2D[registry]` to pull in
+`huggingface_hub`. Without the extra, `admesh.load_domain_from_registry`
+raises a clear `ImportError` before any network call. The slow CI lane
+exercises the full chain on `BaranjaHill`.
```

### `tests/test_registry.py`

```python
@pytest.mark.slow
def test_load_domain_from_registry_baranja_hill():
    pytest.importorskip("admesh_domains")
    pytest.importorskip("huggingface_hub")
    domain = load_domain_from_registry("BaranjaHill")
    assert isinstance(domain, Domain)
    # BaranjaHill sits in a known coastal bbox; sanity-check the type.
    assert isinstance(domain.bbox, tuple) and len(domain.bbox) == 4

def test_list_available_domains_nonempty():
    pytest.importorskip("admesh_domains")
    domains = list_available_domains()
    assert isinstance(domains, dict)
    assert len(domains) > 0
    assert all(isinstance(v, str) for v in domains.values())

@pytest.mark.slow
def test_load_domain_with_metadata_baranja_hill():
    pytest.importorskip("admesh_domains")
    pytest.importorskip("huggingface_hub")
    domain, meta = load_domain_with_metadata("BaranjaHill")
    assert isinstance(domain, Domain)
    assert isinstance(meta, dict)
    assert "bounding_box" in meta
```

## Risks revisited (operational)

- If `BaranjaHill` is no longer the smallest fixture at run time, the
  slow tests still pass; size is a comment, not a constraint.
- If `Mesh.get_mesh` returns a different sentinel for missing IDs,
  the fallback warning still fires from the broader `AttributeError`
  catch.

## Done definition

Spec 010 is **done** when:
- [ ] All FRs in the spec are implemented.
- [ ] `pytest -q` passes on the offline lane.
- [ ] `pytest -q -m slow` passes locally (with `[registry]` installed).
- [ ] `docs/ADMESH_DOMAINS_CONTRACT.md` no longer carries a drift
      caveat.
- [ ] Issue #64 closed with a "resolved by spec 010" comment + commit
      SHA.
