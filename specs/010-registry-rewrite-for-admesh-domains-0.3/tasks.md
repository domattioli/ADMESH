# Spec 010 — Atomic tasks

Each task is independently testable. Dependencies ordered top-down.

| # | Task | Files | Depends on | Acceptance |
|---|---|---|---|---|
| T010-1 | Add `[registry]` extra to `pyproject.toml` | `pyproject.toml` | — | `pip install -e .[registry]` resolves cleanly |
| T010-2 | Extract `_resolve_mesh(name, mesh_id)` helper in `admesh/registry.py` | `admesh/registry.py` | T010-1 | Helper returns a `Mesh` ref; existing tests still pass |
| T010-3 | Rewrite `load_domain_from_registry` against 0.3.x | `admesh/registry.py` | T010-2 | Returns `admesh.Domain` on `BaranjaHill` w/ extra installed |
| T010-4 | Rewrite `list_available_domains` against 0.3.x | `admesh/registry.py` | T010-2 | Returns non-empty `dict[str, str]` sorted by key |
| T010-5 | Rewrite `load_domain_with_metadata` against 0.3.x | `admesh/registry.py` | T010-2 | Returns `(Domain, dict)`; meta has `bounding_box` |
| T010-6 | Add `huggingface_hub` import-guard branch | `admesh/registry.py` | T010-3 | Without extra: `ImportError` with install hint, no upstream traceback |
| T010-7 | Strike "Known drift" from contract doc | `docs/ADMESH_DOMAINS_CONTRACT.md` | T010-3..T010-5 | Section removed; "Network fetch" section added |
| T010-8 | Add offline positive-path test for `list_available_domains` | `tests/test_registry.py` | T010-4 | Test passes without network |
| T010-9 | Add slow positive-path test for `load_domain_from_registry` | `tests/test_registry.py` | T010-3 | `pytest -m slow` passes locally |
| T010-10 | Add slow positive-path test for `load_domain_with_metadata` | `tests/test_registry.py` | T010-5 | `pytest -m slow` passes locally |
| T010-11 | Add end-to-end contract test | `tests/test_admesh_domains_contract.py` | T010-3 | `pytest -m slow` passes locally |
| T010-12 | Verify `slow` marker registered | `pyproject.toml` or `pytest.ini` | T010-9..T010-11 | No `PytestUnknownMarkWarning` on slow runs |
| T010-13 | Run full offline suite | — | T010-1..T010-12 | `pytest -q` exit 0 |
| T010-14 | Run slow lane | — | T010-1..T010-12 | `pytest -q -m slow` exit 0 (with extras) |

## Cross-repo integration points

- **`admesh-domains` 0.3.x API surface** — read-only consumer. No
  upstream change required. If T010-3..T010-5 reveal a new gap (e.g.
  `Mesh.get_mesh` signature drift), open a child issue against
  `domattioli/ADMESH-Domains`, do not patch here.
- **`huggingface_hub`** — used only via `Mesh.load()`. Pin
  `>=0.20` to match upstream's tested floor.
- **`MADMESHR` / `CHILMESH`** — not affected by this spec; the
  registry surface is ADMESH-internal.

## Task-to-acceptance-criteria mapping

| Acceptance criterion (issue #64) | Tasks |
|---|---|
| `load_domain_from_registry("BaranjaHill")` returns usable `Domain` | T010-3, T010-9 |
| `list_available_domains()` returns non-empty mapping | T010-4, T010-8 |
| `load_domain_with_metadata("BaranjaHill")` returns `(Domain, dict)` | T010-5, T010-10 |
| Clear `ImportError` without extras | T010-6 |
| New positive-path slow tests | T010-8, T010-9, T010-10, T010-11 |
| "Known drift" section deleted; contract test green | T010-7, T010-11, T010-13 |

## Phase boundaries

- **Tasks T010-1..T010-7** are the **planning artifacts and source-of-
  truth edits**. They are the deliverables of this spec under the
  planning-phase mandate.
- **Tasks T010-8..T010-14** are the **implementation-phase** verification
  steps. Per CORE MANDATE this run stays planning-only; the
  implementation-phase tasks are filed under a follow-up "implement
  spec 010" comment on issue #64 and executed in a subsequent session
  on the same `daily-issue-fixing` branch.
