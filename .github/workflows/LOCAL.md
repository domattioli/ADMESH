# LOCAL.md — repo-local workflow registry (spec-010 v2.3)

Workflows listed here are intentionally repo-local (not DomI-managed copies). Adding a
new local workflow requires a row here in the same PR — unlisted local
workflows fail the workflow-conformance gate.

| Workflow | Justification |
|---|---|
| `build-wheels.yml` | cibuildwheel compiled-wheel matrix for the C++ backend — repo-specific build pipeline |
| `cleanup-deployments.yml` | GitHub Pages deployment pruning — repo-specific |
| `docs.yml` | mkdocs site deploy to admesh.domattioli.com — repo-specific |
| `publish.yml` | PyPI release, tag-triggered — repo-specific release pipeline |
| `tests-slow.yml` | slow-lane pytest (block_o fixtures) — migration candidate for the tests.yml template later |
