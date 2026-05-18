# Spec 010 — Atomic tasks

Each task is independently testable. Dependencies ordered top-down.

| # | Task | Files | Depends on | Acceptance |
|---|---|---|---|---|
| T010-1 | Add `[registry]` extra to `pyproject.toml` | `pyproject.toml` | — | DONE — commit `05fd02d` |
| T010-2 | Extract `_resolve_mesh(name, mesh_id)` helper in `admesh/registry.py` | `admesh/registry.py` | T010-1 | DONE — commit `05fd02d` |
| T010-3 | Rewrite `load_domain_from_registry` against 0.3.x | `admesh/registry.py` | T010-2 | DONE — commit `05fd02d` |
| T010-4 | Rewrite `list_available_domains` against 0.3.x | `admesh/registry.py` | T010-2 | DONE — commit `05fd02d` (sorted by key, str values) |
| T010-5 | Rewrite `load_domain_with_metadata` against 0.3.x | `admesh/registry.py` | T010-2 | DONE — commit `05fd02d` |
| T010-6 | Add `huggingface_hub` import-guard branch | `admesh/registry.py` | T010-3 | DONE — commit `05fd02d` (no upstream traceback verified) |
| T010-7 | Strike "Known drift" from contract doc | `docs/ADMESH_DOMAINS_CONTRACT.md` | T010-3..T010-5 | DONE — commit `05fd02d` |
| T010-8 | Add offline positive-path test for `list_available_domains` | `tests/test_registry.py` | T010-4 | DONE — commit `05fd02d` |
| T010-9 | Add slow positive-path test for `load_domain_from_registry` | `tests/test_registry.py` | T010-3 | DONE — commit `05fd02d` (slow lane needs network) |
| T010-10 | Add slow positive-path test for `load_domain_with_metadata` | `tests/test_registry.py` | T010-5 | DONE — commit `05fd02d` (slow lane needs network) |
| T010-11 | Add end-to-end contract test | `tests/test_admesh_domains_contract.py` | T010-3 | DONE — commit `05fd02d` (slow lane needs network) |
| T010-12 | Verify `slow` marker registered | `pyproject.toml` or `pytest.ini` | T010-9..T010-11 | DONE — already declared (spec 009) |
| T010-13 | Run full offline suite | — | T010-1..T010-12 | DONE — 361 passed, 12 expected skips, 3 slow deselected |
| T010-14 | Run slow lane | — | T010-1..T010-12 | PENDING — needs CI host with HF Hub network access |

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

- **Tasks T010-1..T010-7** — source-of-truth edits (adapter rewrite +
  contract-doc update). Shipped in commit `05fd02d` on
  `daily-issue-fixing` (PR #72).
- **Tasks T010-8..T010-13** — offline test surface and full local
  validation. Shipped in the same commit. Offline `pytest -q -m
  "not slow"` exit 0 (361 passed, 12 expected skips, 3 slow
  deselected).
- **Task T010-14** — slow lane in CI. Pending a host with network
  access to the HF Hub mirror; the new `slow` tests skip cleanly when
  `huggingface_hub` is missing.
