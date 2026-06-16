# Spec 010 — Registry adapter rewrite for `admesh-domains` 0.3.x

**Status**: Planning
**Tracks**: [#64](https://github.com/domattioli/ADMESH/issues/64)
**Branch**: `daily-maintenance` (no new branch — per CORE MANDATE)
**Severity**: high · **Type**: bug · **Scope**: integration
**Companion**: spec 009 R2 (contract surface), `docs/ADMESH_DOMAINS_CONTRACT.md`

## 1. Problem statement

`admesh/registry.py` was authored against an older `admesh-domains`
registry-object pattern (`load_default_registry().get_domain(...)` returning
an object with `.rings` / `.fixed_points`). The currently pinned version
(`admesh-domains==0.3.2`) replaced that with top-level functions
(`admesh_domains.get_domain(name)`) and a new `Domain` data shape (no
`.rings`; instead a `.meshes: list[Mesh]` where each `Mesh` carries a
downloadable `.path`).

Result: every public registry entry-point in ADMESH currently raises
`AttributeError: module 'admesh_domains' has no attribute
'load_default_registry'` against the installed sibling. The contract
test (`tests/test_admesh_domains_contract.py`, spec 009 R2) catches the
symbol drift but does not exercise `admesh.load_domain_from_registry()`
end-to-end, so this defect slipped through the 0.1.0 ship.

## 2. Goals

1. Restore the three public registry entry-points against the 0.3.x
   surface so `admesh.load_domain_from_registry(...)`, `admesh.list_available_domains()`,
   and `admesh.load_domain_with_metadata(...)` all return usable values.
2. Treat the `huggingface_hub` network dependency as an opt-in install
   extra (`pip install admesh2D[registry]`) so the core package stays
   slim and CI does not need network.
3. Retire the "Known drift" caveat from
   `docs/ADMESH_DOMAINS_CONTRACT.md` once the adapter is wired.
4. Add an end-to-end positive-path test (gated behind `slow` + network)
   so future drift in either direction is caught at CI time.

## 3. Non-goals

- Rewriting `admesh-domains` itself; this spec consumes the existing
  public API.
- Adding local-manifest discovery, mesh search facets, or per-domain
  facet metadata beyond the `Mesh` attributes already exposed.
- Caching the converted `admesh.Domain` between calls. Pass-through is
  acceptable for 0.1.x; a cache lives in a follow-up issue.
- Touching `_convert_to_admesh_domain`. The helper is kept verbatim so
  the existing mock-driven tests in `tests/test_registry.py` continue
  to validate the legacy shape (useful for downstream packages that
  still construct domains from rings).

## 4. Functional requirements

### FR-010-1 — `load_domain_from_registry(name, mesh_id="default@v1")`

Signature change: gains an optional `mesh_id` keyword (default
`"default@v1"`). The first positional is now the *domain* name (e.g.
`"BaranjaHill"`), matching `admesh_domains.get_domain`.

Behavior:

1. Lazy-import `admesh_domains`. Raise `ImportError` with the install
   hint if missing.
2. Resolve `ad_domain = admesh_domains.get_domain(name)`. A
   `KeyError`/`ValueError`/`AttributeError` from upstream is wrapped as
   `ValueError(f"Domain {name!r} not found in admesh-domains registry")`.
3. Resolve `mesh_ref = ad_domain.get_mesh(mesh_id)` when available; on
   `AttributeError`/`KeyError` fall back to `ad_domain.meshes[0]` and
   emit a `UserWarning` naming the fallback id.
4. If `not mesh_ref.exists()`: call `mesh_ref.load()`. A missing
   `huggingface_hub` install must surface as `ImportError` pointing at
   `pip install admesh2D[registry]`, not a cryptic upstream traceback.
5. `src = admesh.read_fort14(mesh_ref.path)` then
   `return admesh.Domain.from_mesh(src)`.

### FR-010-2 — `list_available_domains() -> dict[str, str]`

Replaces the broken `registry.list_domains()` call. Returns a mapping
of `domain.name -> (domain.full_name or domain.description or "")` for
every entry returned by `admesh_domains.list_domains()`. Sorted by key.
Empty registry returns `{}`.

### FR-010-3 — `load_domain_with_metadata(name, mesh_id="default@v1") -> tuple[Domain, dict]`

Same resolution path as FR-010-1. The metadata dict is built from
`mesh_ref` (`license`, `contributor`, `bounding_box`, `filename`,
`id`) plus `ad_domain` (`category`, `region`, `full_name`,
`description`). Missing attributes are skipped (no `None` placeholder
values).

### FR-010-4 — Optional dependency wiring

`pyproject.toml`:

```toml
[project.optional-dependencies]
registry = ["huggingface_hub>=0.20"]
```

`admesh/registry.py` must not import `huggingface_hub` at module load.
The dependency is exercised lazily by `Mesh.load()`. If the extra is
missing and `Mesh.exists()` is `False`, the adapter raises:

```text
ImportError: Fetching '<name>' from admesh-domains requires the
'huggingface_hub' package. Install with:
  pip install admesh2D[registry]
```

### FR-010-5 — Documentation

`docs/ADMESH_DOMAINS_CONTRACT.md`:
- Delete the "Known drift (as of 2026-05-15)" section.
- Add a "Network fetch" paragraph linking the `[registry]` extra to
  `Mesh.load()`.
- Bump the validation note to mention the new positive-path test.

### FR-010-6 — Test surface

`tests/test_registry.py`:
- Keep all six existing tests (legacy + import-error path).
- Add `test_load_domain_from_registry_baranja_hill` decorated with
  `@pytest.mark.slow` and `pytest.importorskip("huggingface_hub")`.
  Asserts `isinstance(domain, admesh.Domain)` and bbox sanity.
- Add `test_list_available_domains_nonempty` (no network) that asserts
  `len(list_available_domains()) > 0` and that all values are `str`.
- Add `test_load_domain_with_metadata_baranja_hill` decorated with
  `slow` + importorskip. Asserts the metadata dict carries
  `bounding_box` and (when present) `license`.

`tests/test_admesh_domains_contract.py`:
- Add `test_end_to_end_load_domain_from_registry` (slow + importorskip)
  that calls `admesh.load_domain_from_registry("BaranjaHill")` and
  asserts a usable `Domain`. Closes the gap that let #64 land.

## 5. Acceptance criteria (from issue #64, verbatim)

- [ ] `admesh.load_domain_from_registry("BaranjaHill")` returns a usable
      `admesh.Domain` (with `[registry]` extra installed).
- [ ] `admesh.list_available_domains()` returns a non-empty mapping.
- [ ] `admesh.load_domain_with_metadata("BaranjaHill")` returns
      `(Domain, dict)` with `license` / `bounding_box` populated where
      upstream provides them.
- [ ] Without the `[registry]` extra, the three functions raise a clear
      `ImportError` pointing to the install command (not a cryptic
      `huggingface_hub` traceback).
- [ ] New positive-path tests in `tests/test_registry.py`, marked
      `slow`, exercise the full chain on `BaranjaHill` (smallest
      fixture at 0.08 MB).
- [ ] `docs/ADMESH_DOMAINS_CONTRACT.md` "Known drift" section deleted;
      contract test still green.

## 6. Architectural decisions

- **Pass-through, not cache.** The first call materializes via network
  through `huggingface_hub`; subsequent calls hit local disk because
  `Mesh.exists()` short-circuits the download. A per-process in-memory
  cache of the `admesh.Domain` object is deferred — the conversion cost
  is dominated by I/O, and a stale cache during dev is more painful
  than the savings.
- **Default `mesh_id="default@v1"`.** Conventional handle in
  `admesh-domains 0.3.x` registry. When absent, fall back to
  `domain.meshes[0]` with a `UserWarning` so silent drift is visible.
- **Keep `_convert_to_admesh_domain`.** The four existing tests
  (`test_convert_to_admesh_domain_*`) validate the legacy "domain has
  `.rings`" shape and exercise `_domain_from_polygon`. Removing the
  helper drops coverage of that path; the marginal maintenance cost
  is one untouched function.
- **Slow tests, not skipped tests.** Network-dependent paths run under
  `pytest -m slow`. Default CI lane stays offline; release-readiness
  lane adds `-m "slow or not slow"`.

## 7. Risks

| Risk | Mitigation |
|---|---|
| `BaranjaHill` fixture moves / 404 on HF mirror | `slow` lane; failure flags upstream, not our code |
| `huggingface_hub` dep bloats `[registry]` install | Pin `>=0.20` only; no transitive surprises |
| `Mesh.get_mesh(mesh_id)` API absent on some `Domain` | Fallback to `domain.meshes[0]` + warning |
| Existing import-error tests start passing/failing when extras change | Each test re-imports `admesh_domains` in-body, so install-state is the gate |
| `read_fort14` slow on large meshes (network + parse) | Pin smallest fixture `BaranjaHill` (0.08 MB) for the slow test |

## 8. Token budget

**Medium.** Three function rewrites + one optional dep + two new tests
+ one doc edit. Not productively decomposable: the three functions
share a resolution path and one PR cycle keeps the contract test green.

## 9. Out of scope (explicit follow-ups)

- Local-manifest support — track in a new issue once `admesh-domains`
  ships `load_manifest(path)` as stable.
- Domain-search / facet UX (`find_domains`, `find_meshes`) — separate
  ergonomics issue.
- Re-export of `admesh_domains.find_meshes` as `admesh.find_meshes` —
  re-evaluate after 0.2.x ships.
- Caching policy — separate issue once we measure hit rate in real
  workflows.
